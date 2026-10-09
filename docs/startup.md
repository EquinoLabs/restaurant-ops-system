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

### 3. Start the Frontend App (React + Vite)
Open a **new terminal window**, navigate to `frontend`, and run:
```bash
cd frontend
npm run dev
```
- **Frontend App URL:** `http://localhost:5173/m/riverside-camp`

---

## 🧪 Running Automated Tests

### Run Backend Unit Tests (pytest)
```powershell
$env:PYTHONPATH="backend"
.\.venv\Scripts\python.exe -m pytest backend/tests
```

### Run Frontend Unit Tests (vitest)
```bash
cd frontend
npm test
```
