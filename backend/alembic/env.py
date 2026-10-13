from logging.config import fileConfig
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from app.core.config import settings
from app.db.base import Base
# Import domain models for Alembic autogenerate discovery
from app.modules.businesses.models import Business # noqa
from app.modules.outlets.models import Outlet # noqa
from app.modules.menus.models import MenuCategory, MenuItem # noqa
from app.modules.staff.models import User, OutletMembership # noqa
from app.modules.audit.models import AuditLog # noqa
from app.modules.tables.models import DiningTable # noqa
from app.modules.orders.models import Order, OrderItem # noqa

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def get_url():
    return settings.SQLALCHEMY_DATABASE_URI


def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        configuration = config.get_section(config.config_ini_section) or {}
        configuration["sqlalchemy.url"] = get_url()
        connectable = engine_from_config(
            configuration,
            prefix="sqlalchemy.",
            poolclass=pool.NullPool,
        )

        with connectable.connect() as connection:
            context.configure(
                connection=connection, target_metadata=target_metadata
            )
            with context.begin_transaction():
                context.run_migrations()
    else:
        # Programmatically injected, verified connection (e.g. isolated test runner)
        context.configure(
            connection=connectable, target_metadata=target_metadata
        )
        with context.begin_transaction():
            context.run_migrations()



if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
