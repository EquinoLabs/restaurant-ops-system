# ROMS — Database Infrastructure Decision: Neon PostgreSQL Integration Specification

**Version:** 1.0  
**Date:** 9 October 2026  
**Status:** Technology decision — selected  
**Project:** Restaurant Operations Management System (ROMS)  

---

## 1. Executive Summary & Technology Decision

ROMS uses **Neon PostgreSQL** as its managed relational database platform. Neon provides persistent database infrastructure for all operational and financial data. The backend connects to Neon via a standard PostgreSQL connection string using SQLAlchemy 2.x and the `psycopg 3` driver.

The database layer remains strictly compatible with standard PostgreSQL so the application can be migrated to another PostgreSQL provider in the future without changing any domain models or schema declarations.

- **Official dashboard:** [console.neon.tech](https://console.neon.tech/)
- **Official documentation:** [neon.tech/docs](https://neon.tech/docs/)

---

## 2. Architecture & Data Flow

```text
React + Vite + TypeScript (Frontend)
            |
            | HTTPS / REST API
            v
     FastAPI Backend (Modular Monolith)
            |
            | SQLAlchemy 2.x + psycopg 3
            v
      Neon PostgreSQL Database
            ├── Businesses
            ├── Outlets
            ├── Staff & Permissions (R2+)
            ├── Menu Categories & Items (R1)
            ├── Tables & Dining Sessions (R3+)
            ├── Orders & Order Items (R3+)
            ├── Payments & Payment Events (R6+)
            ├── Kitchen Tickets (R4+)
            ├── Bills & Bill Associations (R7+)
            └── Audit Logs (R2+)
```

> [!IMPORTANT]
> **Data Scoping & Security Rules**
> - The frontend **never** connects directly to Neon.
> - All database operations pass through the FastAPI backend where validation, authorization, business rules, and transaction boundaries are enforced.
> - Neon is the authoritative source of truth. Browser state must not be treated as authoritative data.

---

## 3. Technology Stack & Driver Configuration

| Concern | Selected Technology |
| --- | --- |
| **Database Provider** | Neon |
| **Database Engine** | PostgreSQL 16+ |
| **Backend** | Python + FastAPI |
| **ORM** | SQLAlchemy 2.x (Synchronous session per request) |
| **Migrations** | Alembic |
| **PostgreSQL Driver** | `psycopg 3` (`psycopg[binary]>=3.1.0`) |
| **Configuration** | Environment variables (`DATABASE_URL` preferred, `POSTGRES_*` fallback) |

---

## 4. Connection String Management & URL Normalization

The backend reads database credentials from environment variables with explicit precedence:

1. **`DATABASE_URL`** (Preferred for Neon and remote environments):
   - Example format: `postgresql+psycopg://USER:PASSWORD@HOST/DATABASE?sslmode=require`
   - URL Normalization Rule:
     - `postgresql://...` $\rightarrow$ `postgresql+psycopg://...`
     - `postgres://...` $\rightarrow$ `postgresql+psycopg://...`
     - `postgresql+psycopg://...` (unchanged)
     - All query parameters (e.g. `sslmode=require`) are preserved intact.

2. **`POSTGRES_*` individual variables** (Fallback for local PostgreSQL / Docker):
   - Combines `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_SERVER`, `POSTGRES_PORT`, `POSTGRES_DB` into `postgresql+psycopg://...`.

---

## 5. Connection Pooling & Compute Resiliency

Neon compute instances auto-suspend after inactivity. The SQLAlchemy engine is configured for resilient connection handling:

- `pool_pre_ping=True`: Pings the connection before executing statements to detect suspended or stale connections and automatically reconnect.
- `pool_size=5`, `max_overflow=10`: Sized for typical single-process web workers.
- `pool_timeout=30`: Maximum seconds to wait for a connection from the pool.
- `pool_recycle=1800`: Recycles connections older than 30 minutes.

---

## 6. Migration Rules with Alembic

- All production schema changes are managed strictly via versioned Alembic migrations.
- `Base.metadata.create_all()` is used only in isolated unit tests (`sqlite:///:memory:` with `StaticPool`).
- Migrations must be reviewed and executed against `DATABASE_URL` in a controlled deployment step.

---

## 7. Security & Compliance Requirements

- **Credential Privacy**: Never commit `DATABASE_URL` or secrets to Git repository or frontend code.
- **Log Masking**: Connection URLs and passwords must never be printed or logged in raw form.
- **TLS/SSL**: Production connections to Neon must specify `sslmode=require`.
