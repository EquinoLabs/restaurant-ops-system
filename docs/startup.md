# ROMS — Quick Startup Guide (`startup.md`)

A simple, straightforward guide to start and run the **Restaurant Operations Management System (ROMS)**.

---

## ☁️ Database Note

> **No local database required!**  
> ROMS is connected to **Neon PostgreSQL** in the cloud via `DATABASE_URL` in `.env`. You do **not** need to run Docker or install PostgreSQL locally.

---

## 🚀 Step-by-Step Startup Instructions

### 1. Test Database Connection (Optional Health Check)
Run this command from the project root to verify your cloud connection to Neon:
```powershell
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe -m app.db.check_connection
```

---

### 2. Start the Backend API (FastAPI)
Run this command from the project root:
```powershell
uvicorn app.main:app --app-dir backend --reload --port 8000
```
*(Notice the `--app-dir backend` flag tells Uvicorn where the `app` package lives!)*

- **Backend API URL:** `http://localhost:8000/api/v1`
- **Interactive API Docs (Swagger):** `http://localhost:8000/docs`
- **Health Check Endpoint:** `http://localhost:8000/api/v1/health`

---

### 3. Start the Frontend Applications (React + Vite)
The frontend is structured into three independent applications managed via npm workspaces. All applications should be started directly from the **project root directory** (`restaurant-ops-system`):

---

#### A. Platform Admin Portal (`apps/platform-admin`)
Platform control plane for SaaS governance, tenant directory, plan management, and platform audit logs.
- **Start Command:**
  ```powershell
  npm run dev:platform-admin
  ```
- **Port:** `http://localhost:5176`
- **Key URLs:**
  - Login: `http://localhost:5176/login`
  - Dashboard: `http://localhost:5176/dashboard`
  - Business Directory: `http://localhost:5176/businesses`
  - Subscriptions: `http://localhost:5176/subscriptions`

---

#### B. Business Manager Console (`apps/business-manager`)
Operational interface for restaurant owners, managers, and service staff.
- **Start Command:**
  ```powershell
  npm run dev:business-manager
  ```
- **Port:** `http://localhost:5174`
- **Key URLs:**
  - Staff Login: `http://localhost:5174/login`
  - Menu Admin: `http://localhost:5174/menu`
  - POS Orders: `http://localhost:5174/orders`
  - Kitchen Display System (KDS): `http://localhost:5174/kds`
  - Subscription Summary: `http://localhost:5174/subscription`

---

#### C. Customer Web App (`apps/customer-web`)
Guest-facing digital QR menu, table self-ordering cart, and guest checkout.
- **Start Command:**
  ```powershell
  npm run dev:customer-web
  ```
- **Port:** `http://localhost:5173`
- **Key URLs:**
  - Public Menu (sample outlet): `http://localhost:5173/m/riverside-camp`
  - QR Table Order (sample): `http://localhost:5173/m/riverside-camp?table=T-01`

---

## 🧪 Running Automated Tests and Builds

### Run Backend Tests (pytest)
```powershell
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe -m pytest backend/tests
```

### Run Frontend Tests (vitest)
From the repository root:
```powershell
npm run test                   # Runs all 11 suites across all apps
npm run test:platform-admin    # Tests apps/platform-admin only
npm run test:business-manager  # Tests apps/business-manager only
npm run test:customer-web      # Tests apps/customer-web only
```

### Run Frontend Typecheck
```powershell
npm run typecheck
```

### Build Frontend Production Bundles
```powershell
npm run build                  # Builds all 3 apps independently
npm run build:platform-admin   # Builds apps/platform-admin to dist/
npm run build:business-manager # Builds apps/business-manager to dist/
npm run build:customer-web     # Builds apps/customer-web to dist/
```
