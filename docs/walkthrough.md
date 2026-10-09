# ROMS Release 1 (R1) Walkthrough: Foundation, Neon PostgreSQL & QR Generation

Release 1 (R1) of the **Restaurant Operations Management System (ROMS)** is fully implemented with **Neon PostgreSQL** database infrastructure, mobile QR menu UI, and **Permanent QR Code Generation**!

---

## 🎯 Accomplishments & Integration Details

### 1. Permanent QR Code Generation & Download
- **Backend API (`GET /api/v1/public/outlets/{slug}/qr`)**:
  - Dynamically streams a high-resolution, scannable PNG QR code image encoding `http://<domain>/m/<slug>`.
  - Supports optional `?download=true` query flag to set `Content-Disposition: attachment` for instant file downloads.
- **Frontend QR Modal & Download UI**:
  - Added a **"QR Stand"** button on the public menu header.
  - Displays a clean printable QR stand card with scan instructions.
  - Includes a **"Download Printable PNG"** button for staff to save and print QR table stands.

### 2. Database Driver & DSN Normalization (`psycopg 3`)
- **Dependencies**: Replaced `psycopg2-binary` with `psycopg[binary]>=3.1.0` and added `qrcode[pil]>=7.4.2`.
- **Precedence & Scheme Normalization**:
  - `DATABASE_URL` is preferred when set in `.env`.
  - Automatically converts `postgresql://...` and `postgres://...` to `postgresql+psycopg://...` so SQLAlchemy 2.x uses `psycopg 3`.
  - Preserves query parameters like `?sslmode=require` intact.

---

## 🧪 Verification Results

### Automated Backend Tests (`pytest`)
- **Command**: `$env:PYTHONPATH="backend"; .\.venv\Scripts\python.exe -m pytest backend/tests`
- **Result**: `7 passed in 3.13s`
  - `test_normalize_postgres_dsn_schemes`: PASSED
  - `test_database_url_precedence_and_masking`: PASSED
  - `test_health_check`: PASSED
  - `test_get_public_menu_success`: PASSED
  - `test_get_public_menu_not_found`: PASSED
  - `test_generate_qr_code_success`: PASSED (verified PNG binary signature `\x89PNG`)
  - `test_generate_qr_code_download`: PASSED (verified attachment headers)

### Automated Frontend Tests (`vitest`)
- **Command**: `npm test` inside `frontend/`
- **Result**: `2 passed in 0.21s`
