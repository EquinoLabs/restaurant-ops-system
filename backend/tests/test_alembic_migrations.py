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



