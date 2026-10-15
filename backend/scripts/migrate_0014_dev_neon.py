"""
One-shot guarded migration of revision 0014_add_missing_tenant_indexes to the
ROMS DEVELOPMENT Neon database (the application DATABASE_URL target).

This is NOT the disposable-test runner and does not modify postgres_guard.py.
It is purpose-built for this single revision and this single target.

Usage (from backend/):
    python scripts/migrate_0014_dev_neon.py                 # read-only preflight only
    python scripts/migrate_0014_dev_neon.py --confirm-0014  # preflight + apply ONCE + verify

Safety properties:
- Credentials are never printed (redaction via tests.postgres_guard.redact_dsn).
- The configured URL must be a Neon host; the localhost POSTGRES_* fallback
  configuration is refused.
- Connects via the DIRECT Neon endpoint (configured '-pooler' hostname with
  the documented '-pooler' label removed) and PROVES the direct path:
    * the TCP/TLS connection must succeed,
    * server-side neon.endpoint_id must equal the direct endpoint token,
    * 'SHOW pool_mode' must FAIL (pgbouncer exposes pool_mode; PostgreSQL does not),
      so a pooler path can never carry the DDL.
- Project/branch/endpoint identity is read AUTHORITATIVELY from the server
  (neon.project_id / neon.branch_id / neon.endpoint_id settings), not inferred
  from the hostname, and reported (these are identifiers, not secrets).
- Preconditions, any failure stops BEFORE any DDL:
    * alembic_version is exactly 0013_outlet_subscriptions (0014 => already
      applied: verification-only, no write; anything else => hard stop),
    * tables outlet_subscriptions and business_memberships exist,
    * 0013 index set present, including partial unique
      uq_outlet_subscription_current with its is_current predicate,
    * the two 0014 indexes are absent.
- Applies EXACTLY '0014_add_missing_tenant_indexes' (never 'head', never a
  user-supplied revision) through Alembic's programmatic API with the verified
  connection injected via cfg.attributes['connection'] - the same mechanism
  alembic/env.py already prefers for injected connections. env.py is not
  modified. Bare alembic CLI is never used.
- PostgreSQL DDL is transactional: 0014's two CREATE INDEX statements and the
  alembic_version update run inside one transaction (env.py begin_transaction
  around run_migrations). A connection drop rolls back to a clean 0013 state;
  an interruption after commit but before the client observes success is
  reported as AMBIGUOUS and requires read-only inspection - never an
  automatic retry.
- Never downgrades, never resets, never drops anything.
- After a successful apply: revision check, index shape checks (btree,
  non-unique, non-partial, indisvalid), uq_outlet_subscription_current
  definition unchanged, and a full pg_indexes catalog diff proving exactly
  the two expected additions and zero removals/changes.
- Isolated constraint test (confirm mode): synthetic plan/business/outlet and
  two current subscriptions in a transaction that is always rolled back;
  duplicate must raise IntegrityError; no committed test data is possible.
"""
import argparse
import os
import sys
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse, urlunparse

import sqlalchemy as sa

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from tests.postgres_guard import redact_dsn  # reuse redaction only; guard unmodified

TARGET_REVISION = "0014_add_missing_tenant_indexes"
EXPECTED_PRIOR_REVISION = "0013_outlet_subscriptions"
EXPECTED_NEW_INDEXES = (
    ("ix_outlet_subscriptions_outlet_id", "outlet_subscriptions", "outlet_id"),
    ("ix_business_memberships_business_id", "business_memberships", "business_id"),
)
REQUIRED_0013_INDEXES = (
    "uq_outlet_subscription_current",
    "ix_outlet_subscriptions_business_id",
    "ix_outlet_subscriptions_status",
    "ix_business_memberships_user_id",
    "uq_business_user_membership",
)
REQUIRED_TABLES = ("outlet_subscriptions", "business_memberships")


class PreflightFailure(RuntimeError):
    """A safety precondition failed; no DDL may proceed."""


def _redact(url: str) -> str:
    return redact_dsn(url)


def _load_direct_target() -> Tuple[str, str, str, str]:
    """
    Load the application DATABASE_URL from the repository-root .env (authoritative
    development configuration; never the CWD-relative fallback), derive the direct
    Neon endpoint URL, and return (direct_url, direct_host, endpoint_token, database).
    No credentials are printed here or anywhere else.
    """
    from app.core.config import Settings

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    repo_root = os.path.dirname(backend_dir)
    root_env = os.path.join(repo_root, ".env")
    if not os.path.exists(root_env):
        raise PreflightFailure(f"Repository-root .env not found at {root_env}; refusing to guess a target.")

    settings = Settings(_env_file=root_env)
    raw = (settings.DATABASE_URL or "").strip()
    if not raw:
        raise PreflightFailure(
            "DATABASE_URL is not set in the repository-root .env; the localhost POSTGRES_* "
            "fallback configuration is refused for this operation."
        )

    parsed = urlparse(settings.SQLALCHEMY_DATABASE_URI)  # normalized scheme
    host = (parsed.hostname or "").lower()
    if "neon.tech" not in host:
        raise PreflightFailure(
            f"Configured DATABASE_URL host '{host}' is not a Neon host; this one-shot script "
            "only targets the development Neon database. Refusing."
        )

    labels = host.split(".")
    endpoint_label = labels[0]
    if not endpoint_label.startswith("ep-"):
        raise PreflightFailure(f"Host label '{endpoint_label}' does not look like a Neon endpoint id. Refusing.")

    if endpoint_label.endswith("-pooler"):
        direct_label = endpoint_label[: -len("-pooler")]
    else:
        direct_label = endpoint_label
    if not direct_label.startswith("ep-") or direct_label == endpoint_label and "-pooler" in endpoint_label:
        raise PreflightFailure("Could not derive a direct endpoint label from the configured host. Refusing.")

    direct_host = ".".join([direct_label] + labels[1:])
    netloc = parsed.netloc
    if parsed.password:
        userpass_host = netloc.rsplit("@", 1)[0]
        direct_netloc = f"{userpass_host}@{direct_host}"
    else:
        direct_netloc = direct_host
    if parsed.port:
        direct_netloc = direct_netloc.replace(direct_host, f"{direct_host}:{parsed.port}")
    direct_url = urlunparse(
        (parsed.scheme, direct_netloc, parsed.path, parsed.params, parsed.query, parsed.fragment)
    )
    database = (parsed.path or "").lstrip("/")
    if not database:
        raise PreflightFailure("Configured DATABASE_URL has no database name. Refusing.")
    return direct_url, direct_host, direct_label, database


def _connect(direct_url: str) -> sa.Engine:
    return sa.create_engine(
        direct_url,
        poolclass=sa.pool.NullPool,
        connect_args={"connect_timeout": 20},
    )


def _verify_server_identity(conn: sa.Connection, endpoint_token: str, database: str) -> Dict[str, Any]:
    """Authoritative server-side identity + direct-path proof. Read-only."""
    info: Dict[str, Any] = {}

    server_db = conn.execute(sa.text("SELECT current_database()")).scalar()
    info["database"] = server_db
    if server_db != database:
        raise PreflightFailure(
            f"Connected database '{server_db}' does not match configured database '{database}'. Refusing."
        )

    endpoint_id = conn.execute(sa.text("SELECT current_setting('neon.endpoint_id', true)")).scalar()
    project_id = conn.execute(sa.text("SELECT current_setting('neon.project_id', true)")).scalar()
    branch_id = conn.execute(sa.text("SELECT current_setting('neon.branch_id', true)")).scalar()
    if not endpoint_id or not project_id or not branch_id:
        raise PreflightFailure(
            "Server did not report neon.endpoint_id/neon.project_id/neon.branch_id; "
            "this is not an identifiable Neon compute. Refusing."
        )
    info["endpoint_id"] = str(endpoint_id).strip()
    info["project_id"] = str(project_id).strip()
    info["branch_id"] = str(branch_id).strip()

    if info["endpoint_id"] != endpoint_token:
        raise PreflightFailure(
            f"Server-side neon.endpoint_id '{info['endpoint_id']}' does not match the direct "
            f"endpoint token '{endpoint_token}' derived from configuration. Refusing."
        )

    # Pooler proof: pgbouncer answers SHOW pool_mode; PostgreSQL rejects it.
    try:
        mode = conn.execute(sa.text("SHOW pool_mode")).scalar()
    except Exception as exc:  # noqa: BLE001 - any error is the expected PostgreSQL behavior
        # The deliberate failure aborts the autobegun transaction; roll back
        # so subsequent read-only preflight queries can proceed.
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
        msg = str(exc).lower()
        if "pool_mode" in msg or "unrecognized" in msg or "error" in msg:
            info["pooler_detected"] = False
        else:  # pragma: no cover - defensive
            raise PreflightFailure(f"Unexpected failure probing pool_mode: {type(exc).__name__}. Refusing.") from None
    else:
        raise PreflightFailure(
            f"SHOW pool_mode succeeded (mode={mode!r}): the connection is routed through a pooler. "
            "DDL requires the direct endpoint. Refusing."
        )
    return info


def _read_revision(conn: sa.Connection) -> Optional[str]:
    exists = conn.execute(
        sa.text(
            "SELECT to_regclass('public.alembic_version') IS NOT NULL"
        )
    ).scalar()
    if not exists:
        return None
    return conn.execute(sa.text("SELECT version_num FROM alembic_version")).scalar()


def _index_rows(conn: sa.Connection) -> List[Tuple[str, str, str]]:
    rows = conn.execute(
        sa.text(
            "SELECT tablename, indexname, indexdef FROM pg_indexes "
            "WHERE schemaname = 'public' ORDER BY tablename, indexname"
        )
    ).all()
    return [(r[0], r[1], r[2]) for r in rows]


def _verify_schema_preconditions(conn: sa.Connection, prior_revision: Optional[str]) -> Dict[str, Any]:
    """All checks are read-only. Raises PreflightFailure on any mismatch."""
    result: Dict[str, Any] = {"revision": prior_revision}

    if prior_revision == TARGET_REVISION:
        result["already_at_target"] = True
        return result
    if prior_revision != EXPECTED_PRIOR_REVISION:
        raise PreflightFailure(
            f"alembic_version is {prior_revision!r}; expected exactly "
            f"'{EXPECTED_PRIOR_REVISION}' before applying 0014. Refusing to write."
        )

    tables = {
        r[0]
        for r in conn.execute(
            sa.text(
                "SELECT table_name FROM information_schema.tables "
                "WHERE table_schema = 'public' AND table_type = 'BASE TABLE'"
            )
        ).all()
    }
    missing_tables = [t for t in REQUIRED_TABLES if t not in tables]
    if missing_tables:
        raise PreflightFailure(f"Required tables missing: {missing_tables}. Refusing.")

    catalog = _index_rows(conn)
    by_name: Dict[str, str] = {name: defn for _t, name, defn in catalog}

    missing_0013 = [n for n in REQUIRED_0013_INDEXES if n not in by_name]
    if missing_0013:
        raise PreflightFailure(f"Expected 0013-era indexes missing: {missing_0013}. Refusing.")

    uq_def = by_name["uq_outlet_subscription_current"]
    if "is_current" not in uq_def:
        raise PreflightFailure(
            f"uq_outlet_subscription_current lacks its is_current predicate: {uq_def!r}. Refusing."
        )
    result["uq_outlet_subscription_current_def"] = uq_def

    premature = [n for n, _t, _c in EXPECTED_NEW_INDEXES if n in by_name]
    if premature:
        raise PreflightFailure(
            f"One or more 0014 indexes already exist: {premature}. "
            "Partial application detected; refusing to write."
        )

    result["catalog_before"] = catalog
    result["already_at_target"] = False
    return result


def _build_alembic_config(conn: sa.Connection):
    from alembic.config import Config

    backend_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    ini_path = os.path.join(backend_dir, "alembic.ini")
    if not os.path.exists(ini_path):
        ini_path = os.path.join(backend_dir, "backend", "alembic.ini")
    if not os.path.exists(ini_path):
        raise PreflightFailure("alembic.ini not found; refusing.")
    cfg = Config(ini_path)
    candidates = [
        os.path.join(backend_dir, "alembic"),
        os.path.join(backend_dir, "backend", "alembic"),
    ]
    for c in candidates:
        if os.path.isdir(c) and os.path.isdir(os.path.join(c, "versions")):
            cfg.set_main_option("script_location", os.path.abspath(c))
            break
    else:
        raise PreflightFailure("Alembic script directory not found; refusing.")
    cfg.attributes["connection"] = conn
    return cfg


def _apply_0014(conn: sa.Connection) -> None:
    from alembic import command

    cfg = _build_alembic_config(conn)
    command.upgrade(cfg, TARGET_REVISION)


def _verify_post_migration(conn: sa.Connection, catalog_before: List[Tuple[str, str, str]], uq_def_before: str) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    revision = _read_revision(conn)
    out["revision"] = revision
    if revision != TARGET_REVISION:
        raise PreflightFailure(
            f"Post-migration revision is {revision!r}, expected '{TARGET_REVISION}'. "
            "Do not retry; inspect the database."
        )

    rows = conn.execute(
        sa.text(
            "SELECT i.relname, t.relname, ix.indisunique, ix.indisvalid, "
            "(ix.indpred IS NOT NULL) AS is_partial, am.amname, "
            "pg_get_indexdef(ix.indexrelid) AS indexdef "
            "FROM pg_index ix "
            "JOIN pg_class i ON i.oid = ix.indexrelid "
            "JOIN pg_class t ON t.oid = ix.indrelid "
            "JOIN pg_am am ON am.oid = i.relam "
            "WHERE i.relname IN ('ix_outlet_subscriptions_outlet_id','ix_business_memberships_business_id')"
        )
    ).all()
    out["new_index_rows"] = [
        {"index": r[0], "table": r[1], "unique": r[2], "valid": r[3], "partial": r[4], "am": r[5]}
        for r in rows
    ]
    if len(rows) != 2:
        raise PreflightFailure(f"Expected exactly 2 new index catalog rows, found {len(rows)}. Inspect manually.")
    expected = {n: (t, c) for n, t, c in EXPECTED_NEW_INDEXES}
    for relname, tabname, is_unique, is_valid, is_partial, amname, _defn in rows:
        if relname not in expected:
            raise PreflightFailure(f"Unexpected index {relname} in result set. Inspect manually.")
        exp_table, exp_col = expected[relname]
        if tabname != exp_table:
            raise PreflightFailure(f"{relname} is on table '{tabname}', expected '{exp_table}'.")
        if is_unique:
            raise PreflightFailure(f"{relname} must not be unique.")
        if not is_valid:
            raise PreflightFailure(f"{relname} is not valid (indisvalid=false).")
        if is_partial:
            raise PreflightFailure(f"{relname} must not be partial.")
        if amname != "btree":
            raise PreflightFailure(f"{relname} access method is '{amname}', expected btree.")
        col_defn = conn.execute(
            sa.text(
                "SELECT a.attname FROM pg_index ix "
                "JOIN pg_class i ON i.oid = ix.indexrelid "
                "JOIN unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE "
                "JOIN pg_attribute a ON a.attrelid = ix.indrelid AND a.attnum = k.attnum "
                "WHERE i.relname = :name"
            ),
            {"name": relname},
        ).scalars().all()
        if list(col_defn) != [exp_col]:
            raise PreflightFailure(f"{relname} covers columns {col_defn}, expected ['{exp_col}'].")

    uq_def_after = conn.execute(
        sa.text(
            "SELECT indexdef FROM pg_indexes WHERE schemaname='public' AND indexname='uq_outlet_subscription_current'"
        )
    ).scalar()
    out["uq_outlet_subscription_current_unchanged"] = (uq_def_after == uq_def_before)
    if uq_def_after != uq_def_before:
        raise PreflightFailure("uq_outlet_subscription_current definition changed. Inspect manually.")

    catalog_after = _index_rows(conn)
    before_set, after_set = set(catalog_before), set(catalog_after)
    added = sorted(after_set - before_set)
    removed = sorted(before_set - after_set)
    out["catalog_added"] = [f"{t}.{n}" for t, n, _d in added]
    out["catalog_removed"] = [f"{t}.{n}" for t, n, _d in removed]
    expected_added_names = {n for n, _t, _c in EXPECTED_NEW_INDEXES}
    if removed:
        raise PreflightFailure(f"Indexes disappeared during migration: {out['catalog_removed']}. Inspect manually.")
    if {n for _t, n, _d in added} != expected_added_names or len(added) != 2:
        raise PreflightFailure(
            f"Catalog diff is not exactly the two expected additions: added={out['catalog_added']}. Inspect manually."
        )
    return out


def _constraint_test(direct_url: str) -> Dict[str, Any]:
    """
    Isolated duplicate-current-subscription test. Every statement runs inside one
    transaction that is unconditionally rolled back; committed test data is
    impossible. Existing rows are never read for deletion or modification.
    """
    import uuid
    from datetime import timedelta

    from app.db.base import utc_now
    from app.modules.businesses.models import Business
    from app.modules.outlets.models import Outlet
    from app.modules.subscriptions.models import OutletSubscription, Plan

    outcome: Dict[str, Any] = {"ran": True, "duplicate_rejected": False, "historical_allowed": False}
    engine = _connect(direct_url)
    try:
        Session = sa.orm.sessionmaker(bind=engine)
        db = Session()
        try:
            suffix = uuid.uuid4().hex[:12]
            plan = Plan(id=uuid.uuid4(), code=f"neon0014_{suffix}", name="0014 Constraint Test Plan", sort_order=990)
            biz = Business(id=uuid.uuid4(), name=f"0014 Constraint Test Biz {suffix}", status="active")
            db.add_all([plan, biz])
            db.flush()
            outlet = Outlet(
                id=uuid.uuid4(),
                business_id=biz.id,
                name=f"0014 Constraint Outlet {suffix}",
                public_slug=f"neon0014-{suffix}",
                timezone="UTC",
                currency="INR",
                address="0014 constraint test",
                status="active",
            )
            db.add(outlet)
            db.flush()
            now = utc_now()
            db.add(
                OutletSubscription(
                    id=uuid.uuid4(),
                    outlet_id=outlet.id,
                    business_id=biz.id,
                    plan_id=plan.id,
                    status="trial",
                    is_current=True,
                    trial_ends_at=now + timedelta(days=30),
                )
            )
            db.flush()
            db.add(
                OutletSubscription(
                    id=uuid.uuid4(),
                    outlet_id=outlet.id,
                    business_id=biz.id,
                    plan_id=plan.id,
                    status="active",
                    is_current=True,
                    current_period_start=now,
                    current_period_end=now + timedelta(days=30),
                )
            )
            try:
                db.flush()
            except sa.exc.IntegrityError as exc:
                outcome["duplicate_rejected"] = True
                outcome["error_mentions_index"] = "uq_outlet_subscription_current" in str(exc.orig)
            else:
                outcome["duplicate_rejected"] = False

            db.rollback()

            # Second transaction: historical (is_current=false) row alongside a current row.
            plan2 = Plan(id=uuid.uuid4(), code=f"neon0014h_{suffix}", name="0014 Constraint Test Plan H", sort_order=991)
            biz2 = Business(id=uuid.uuid4(), name=f"0014 Constraint BizH {suffix}", status="active")
            db.add_all([plan2, biz2])
            db.flush()
            outlet2 = Outlet(
                id=uuid.uuid4(),
                business_id=biz2.id,
                name=f"0014 Constraint OutletH {suffix}",
                public_slug=f"neon0014h-{suffix}",
                timezone="UTC",
                currency="INR",
                address="0014 constraint test historical",
                status="active",
            )
            db.add(outlet2)
            db.flush()
            now = utc_now()
            db.add(
                OutletSubscription(
                    id=uuid.uuid4(),
                    outlet_id=outlet2.id,
                    business_id=biz2.id,
                    plan_id=plan2.id,
                    status="trial",
                    is_current=True,
                    trial_ends_at=now + timedelta(days=30),
                )
            )
            db.add(
                OutletSubscription(
                    id=uuid.uuid4(),
                    outlet_id=outlet2.id,
                    business_id=biz2.id,
                    plan_id=plan2.id,
                    status="expired",
                    is_current=False,
                    current_period_start=now - timedelta(days=60),
                    current_period_end=now - timedelta(days=30),
                )
            )
            try:
                db.flush()
                outcome["historical_allowed"] = True
            except sa.exc.IntegrityError:
                outcome["historical_allowed"] = False
        finally:
            db.rollback()
            db.close()
    finally:
        engine.dispose()
    return outcome


def main() -> int:
    parser = argparse.ArgumentParser(description="One-shot 0014 migration to development Neon.")
    parser.add_argument(
        "--confirm-0014",
        action="store_true",
        default=False,
        help="Required to perform the single upgrade. Without it: read-only preflight only.",
    )
    parser.add_argument(
        "--acknowledge-source-branch",
        action="store_true",
        default=False,
        help=(
            "Required in addition to --confirm-0014 when the target branch equals "
            "postgres_guard.NEON_FORBIDDEN_SOURCE_BRANCH_ID, acknowledging that the "
            "repository normally protects this branch from automated activity."
        ),
    )
    args = parser.parse_args()

    try:
        direct_url, direct_host, endpoint_token, database = _load_direct_target()
    except PreflightFailure as exc:
        print(f"[REFUSAL] {exc}")
        return 2

    print(f"[TARGET] direct_host={direct_host}  database={database}  (credentials redacted: {_redact(direct_url)})")

    engine = _connect(direct_url)
    conn = None
    try:
        try:
            conn = engine.connect()
        except Exception as exc:  # noqa: BLE001
            print(f"[REFUSAL] Could not connect to the direct endpoint: {type(exc).__name__}. Refusing.")
            return 2

        conn.execute(sa.text("SET statement_timeout = '60s'"))

        try:
            identity = _verify_server_identity(conn, endpoint_token, database)
        except PreflightFailure as exc:
            print(f"[REFUSAL] {exc}")
            return 2
        print(
            f"[IDENTITY] endpoint_id={identity['endpoint_id']}  project_id={identity['project_id']}  "
            f"branch_id={identity['branch_id']}  pooler_detected={identity['pooler_detected']}"
        )

        from tests.postgres_guard import NEON_FORBIDDEN_SOURCE_BRANCH_ID

        on_forbidden_source = identity["branch_id"] == NEON_FORBIDDEN_SOURCE_BRANCH_ID
        if on_forbidden_source:
            print(
                f"[WARNING] Target branch {identity['branch_id']} equals postgres_guard."
                "NEON_FORBIDDEN_SOURCE_BRANCH_ID - the repository's test-safety designations "
                "protect this source branch. A write requires --confirm-0014 AND "
                "--acknowledge-source-branch."
            )
            if args.confirm_0014 and not args.acknowledge_source_branch:
                print("[REFUSAL] Source-branch write not acknowledged. Refusing to apply DDL.")
                return 2

        prior = _read_revision(conn)
        try:
            pre = _verify_schema_preconditions(conn, prior)
        except PreflightFailure as exc:
            print(f"[REFUSAL] {exc}")
            return 2

        if pre.get("already_at_target"):
            print(f"[PREFLIGHT] Database is already at revision {TARGET_REVISION}; no write will occur.")
            print("[PREFLIGHT] Verifying current state instead (read-only).")
            uq = conn.execute(
                sa.text(
                    "SELECT indexdef FROM pg_indexes WHERE schemaname='public' "
                    "AND indexname='uq_outlet_subscription_current'"
                )
            ).scalar()
            post = _verify_post_migration(conn, pre.get("catalog_before", _index_rows(conn)), uq or "")
            print(f"[VERIFY] revision={post['revision']}  new_indexes={post['new_index_rows']}")
            print(f"[VERIFY] uq_outlet_subscription_current unchanged={post['uq_outlet_subscription_current_unchanged']}")
            print(f"[VERIFY] catalog added={post['catalog_added']}  removed={post['catalog_removed']}")
            return 0

        print(f"[PREFLIGHT] revision={EXPECTED_PRIOR_REVISION} OK; required tables OK; 0013 indexes OK; 0014 indexes absent OK.")
        print(f"[PREFLIGHT] uq_outlet_subscription_current: {pre['uq_outlet_subscription_current_def']}")
        print(f"[PREFLIGHT] catalog snapshot captured ({len(pre['catalog_before'])} indexes).")

        if not args.confirm_0014:
            print("[PREFLIGHT-ONLY] Re-run with --confirm-0014 to apply the migration exactly once.")
            return 0

        print(f"[APPLY] Upgrading to {TARGET_REVISION} via Alembic programmatic API (injected verified connection).")
        try:
            # End the preflight read transaction so Alembic's env.py
            # begin_transaction() OWNS (and commits) the single migration
            # transaction. CREATE INDEX and the alembic_version update are
            # transactional DDL on PostgreSQL: all-or-nothing.
            conn.commit()
            _apply_0014(conn)
        except Exception as exc:  # noqa: BLE001
            print(f"[FAIL] Upgrade raised {type(exc).__name__}: outcome must be inspected, not retried.")
            safe_rev = None
            try:
                with engine.connect() as c2:
                    safe_rev = _read_revision(c2)
            except Exception:  # noqa: BLE001
                safe_rev = "<unreadable>"
            print(f"[FAIL] Post-failure revision reads as: {safe_rev}")
            return 1

        post = _verify_post_migration(conn, pre["catalog_before"], pre["uq_outlet_subscription_current_def"])
        print(f"[VERIFY] revision={post['revision']}")
        for row in post["new_index_rows"]:
            print(f"[VERIFY] index {row['index']} on {row['table']}: btree={row['am']=='btree'} unique={row['unique']} partial={row['partial']} valid={row['valid']}")
        print(f"[VERIFY] uq_outlet_subscription_current unchanged={post['uq_outlet_subscription_current_unchanged']}")
        print(f"[VERIFY] catalog added={post['catalog_added']}  removed={post['catalog_removed']}")

        try:
            ct = _constraint_test(direct_url)
            print(f"[CONSTRAINT] duplicate_current_rejected={ct['duplicate_rejected']}  historical_row_allowed={ct['historical_allowed']}  (all rows rolled back)")
            if not ct["duplicate_rejected"]:
                print("[CONSTRAINT] WARNING: duplicate was not rejected; treat enforcement as NOT verified.")
        except Exception as exc:  # noqa: BLE001
            print(f"[CONSTRAINT] Test could not be completed safely ({type(exc).__name__}); "
                  "reported as not runtime-verified. Migration result is unaffected.")

        print("[DONE] Migration 0014 applied and verified on the development Neon database.")
        return 0

    finally:
        if conn is not None:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        engine.dispose()


if __name__ == "__main__":
    sys.exit(main())
