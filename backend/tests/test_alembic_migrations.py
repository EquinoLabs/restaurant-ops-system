import os
import importlib.util
import pytest

def load_migration_module(filename: str):
    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    file_path = os.path.join(base_dir, "alembic", "versions", filename)
    spec = importlib.util.spec_from_file_location("migration_module", file_path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def test_alembic_migration_0008_structure():
    m0008 = load_migration_module("0008_order_idempotency_keys.py")
    assert m0008.revision == '0008_order_idempotency_keys'
    assert m0008.down_revision == '0007_audit_log_business_id_nullable'
    assert callable(m0008.upgrade)
    assert callable(m0008.downgrade)

def test_alembic_migration_0009_structure():
    m0009 = load_migration_module("0009_order_number_unique_constraint.py")
    assert m0009.revision == '0009_order_number_unique_constraint'
    assert m0009.down_revision == '0008_order_idempotency_keys'
    assert callable(m0009.upgrade)
    assert callable(m0009.downgrade)

def test_alembic_migration_0010_structure():
    m0010 = load_migration_module("0010_subscription_entitlements_schema.py")
    assert m0010.revision == '0010_subscription_entitlements_schema'
    assert m0010.down_revision == '0009_order_number_unique_constraint'
    assert callable(m0010.upgrade)
    assert callable(m0010.downgrade)

def test_migration_0010_precheck_aborts(monkeypatch):
    import uuid
    import sqlalchemy as sa
    from sqlalchemy import create_engine

    m0010 = load_migration_module("0010_subscription_entitlements_schema.py")
    
    # Create temp SQLite DB with businesses table
    engine = create_engine("sqlite:///:memory:")
    with engine.begin() as conn:
        conn.execute(sa.text(
            "CREATE TABLE businesses ("
            "id CHAR(36) PRIMARY KEY, "
            "name VARCHAR(200) NOT NULL, "
            "status VARCHAR(20) NOT NULL, "
            "subscription_status VARCHAR(20) NOT NULL, "
            "plan_name VARCHAR(50), "
            "max_outlets INTEGER, "
            "trial_ends_at DATETIME"
            ")"
        ))
        unmapped_id = str(uuid.uuid4())
        conn.execute(sa.text(
            "INSERT INTO businesses (id, name, status, subscription_status, plan_name) "
            "VALUES (:id, 'Test Biz', 'active', 'trial', 'unsupported_custom_plan')"
        ), {'id': unmapped_id})

    # Mock op.get_bind() to return our engine connection
    with engine.connect() as conn:
        monkeypatch.setattr(m0010.op, "get_bind", lambda: conn)
        with pytest.raises(RuntimeError) as exc_info:
            m0010.upgrade()

        err_msg = str(exc_info.value)
        assert "Migration 0010 aborted" in err_msg
        assert "unmapped plan_name values" in err_msg
        assert unmapped_id in err_msg
        assert "unsupported_custom_plan" in err_msg


def test_alembic_migration_0011_structure():
    m0011 = load_migration_module("0011_add_platform_role_column.py")
    assert m0011.revision == '0011_add_platform_role_column'
    assert m0011.down_revision == '0010_subscription_entitlements_schema'
    assert callable(m0011.upgrade)
    assert callable(m0011.downgrade)


def test_migration_0011_upgrade_and_downgrade_execution():
    """
    Validates migration 0011 upgrade and downgrade execution against an isolated SQLite test database.

    Verifies:
    1. users.platform_role column is added as nullable String(20).
    2. Index ix_users_platform_role is created (non-unique).
    3. Pre-existing user rows and fields survive intact with platform_role IS NULL (no premature backfill).
    4. Migration 0011 adds zero check constraints or unique indexes (unconstrained expansion).
    5. downgrade() drops platform_role and ix_users_platform_role, preserving pre-existing data.

    PostgreSQL Validation Limitation:
    SQLite does not enforce or validate PostgreSQL-specific transactional advisory locks
    or partial unique index expressions. True PostgreSQL concurrency and constraint
    serialization requires the dedicated PostgreSQL integration test suite.
    """
    import sqlalchemy as sa
    from sqlalchemy import create_engine, text, inspect
    from alembic.migration import MigrationContext
    from alembic.operations import Operations

    m0011 = load_migration_module("0011_add_platform_role_column.py")

    engine = create_engine("sqlite:///:memory:")
    conn = engine.connect()

    try:
        # 1. Setup isolated users table matching revision 0010 schema
        conn.execute(text("""
            CREATE TABLE users (
                id VARCHAR(36) PRIMARY KEY,
                email VARCHAR(254) NOT NULL UNIQUE,
                password_hash VARCHAR(255) NOT NULL,
                display_name VARCHAR(150) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'active',
                is_platform_admin BOOLEAN NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL,
                updated_at DATETIME NOT NULL
            )
        """))

        # 2. Seed representative pre-existing users (legacy admin and staff)
        conn.execute(text("""
            INSERT INTO users (id, email, password_hash, display_name, status, is_platform_admin, created_at, updated_at)
            VALUES
                ('u-admin', 'legacy_admin@test.com', 'hash_admin', 'Legacy Admin', 'active', 1, '2026-10-10 10:00:00', '2026-10-10 10:00:00'),
                ('u-staff', 'staff@test.com', 'hash_staff', 'Staff Member', 'active', 0, '2026-10-10 10:00:00', '2026-10-10 10:00:00')
        """))
        conn.commit()

        # 3. Configure Alembic operations context and execute upgrade()
        ctx = MigrationContext.configure(conn)
        with Operations.context(ctx):
            m0011.upgrade()

        insp = inspect(conn)

        # 4. Verify platform_role column properties
        columns = {c['name']: c for c in insp.get_columns('users')}
        assert "platform_role" in columns
        assert columns['platform_role']['nullable'] is True

        # 5. Verify index ix_users_platform_role exists and is non-unique
        indexes = {i['name']: i for i in insp.get_indexes('users')}
        assert "ix_users_platform_role" in indexes
        assert not indexes['ix_users_platform_role']['unique']
        assert indexes['ix_users_platform_role']['column_names'] == ['platform_role']

        # 6. Verify NO check constraints were added in this migration (expansion only)
        check_constraints = insp.get_check_constraints('users')
        assert len(check_constraints) == 0

        # 7. Verify pre-existing data survived intact and NO data backfill was performed
        admin_row = conn.execute(text(
            "SELECT email, is_platform_admin, platform_role FROM users WHERE id = 'u-admin'"
        )).fetchone()
        assert admin_row[0] == "legacy_admin@test.com"
        assert admin_row[1] == 1  # is_platform_admin preserved
        assert admin_row[2] is None  # platform_role NOT backfilled yet

        staff_row = conn.execute(text(
            "SELECT email, is_platform_admin, platform_role FROM users WHERE id = 'u-staff'"
        )).fetchone()
        assert staff_row[0] == "staff@test.com"
        assert staff_row[1] == 0
        assert staff_row[2] is None

        # 8. Execute downgrade()
        with Operations.context(ctx):
            m0011.downgrade()

        insp_post_down = inspect(conn)

        # 9. Verify column and index are dropped
        post_columns = [c['name'] for c in insp_post_down.get_columns('users')]
        assert "platform_role" not in post_columns

        post_indexes = [i['name'] for i in insp_post_down.get_indexes('users')]
        assert "ix_users_platform_role" not in post_indexes

        # 10. Verify pre-existing user data still intact after downgrade
        admin_post_down = conn.execute(text(
            "SELECT email, is_platform_admin FROM users WHERE id = 'u-admin'"
        )).fetchone()
        assert admin_post_down[0] == "legacy_admin@test.com"
        assert admin_post_down[1] == 1

    finally:
        conn.close()
        engine.dispose()
