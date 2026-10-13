# ==============================================================================
# ROMS Platform Governance -- Stage C PostgreSQL Integration Test Runner
# ==============================================================================
# Hardened execution harness for isolated, disposable PostgreSQL integration testing.
# Strictly fail-closed: validates directory structure, preflight DAG state,
# container labels, exit codes, and provides guaranteed try/finally cleanup.
#
# NOTE: This script is prepared for Stage C execution only.
# It MUST NOT be executed without separate, explicit user authorization.
# ==============================================================================

[CmdletBinding()]
param(
    [Parameter(Mandatory = $false)]
    [string]$BackendPath = ""
)

$ErrorActionPreference = "Stop"

# ------------------------------------------------------------------------------
# 1. Working Directory Resolution & Structure Verification
# ------------------------------------------------------------------------------
Write-Host "=========================================================="
Write-Host "ROMS OP-02 Stage C -- Harness Preflight and Path Validation"
Write-Host "=========================================================="

if ($BackendPath) {
    $resolvedBackend = (Resolve-Path $BackendPath -ErrorAction Stop).Path
} else {
    $scriptDir = $PSScriptRoot
    if (-not $scriptDir) {
        $scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
    }
    if (-not $scriptDir) {
        $scriptDir = (Get-Location).Path
    }
    $resolvedBackend = (Split-Path -Parent $scriptDir)
}

Write-Host "[PREFLIGHT] Target Backend Directory: $resolvedBackend"

# Verify mandatory files exist before any external operation
$requiredFiles = @(
    (Join-Path $resolvedBackend "alembic.ini"),
    (Join-Path $resolvedBackend "scripts\init_postgres_test_db.py"),
    (Join-Path $resolvedBackend "scripts\migrate_postgres_test_db.py"),
    (Join-Path $resolvedBackend "tests\test_postgres_concurrency.py"),
    (Join-Path $resolvedBackend "tests\postgres_guard.py")
)

foreach ($req in $requiredFiles) {
    if (-not (Test-Path $req -PathType Leaf)) {
        throw "Preflight Refusal: Required file '$req' does not exist. Aborting before provisioning."
    }
}
Write-Host "[PREFLIGHT] Repository structure verified."

# Set working directory to backend
Push-Location $resolvedBackend

# ------------------------------------------------------------------------------
# 2. Offline Alembic Migration-Head Preflight (Before Provisioning)
# ------------------------------------------------------------------------------
Write-Host "[PREFLIGHT] Validating Alembic migration graph and linear head..."
python -c "import sys; sys.path.insert(0, '.'); from tests.postgres_guard import verify_migration_dag_head; verify_migration_dag_head()"
if ($LASTEXITCODE -ne 0) {
    Pop-Location
    throw "Preflight Refusal: Alembic DAG head verification failed. Multiple heads or unapproved migration drift detected."
}
Write-Host "[PREFLIGHT] Migration DAG positively verified at head '0012_platform_role_constraints'."

# ------------------------------------------------------------------------------
# 3. Environment State Preservation
# ------------------------------------------------------------------------------
$origTestDsn = [System.Environment]::GetEnvironmentVariable("ROMS_POSTGRES_TEST_DATABASE_URL", "Process")
$origRunId   = [System.Environment]::GetEnvironmentVariable("ROMS_POSTGRES_TEST_RUN_ID", "Process")

# Generate correlation run ID and disposable credentials
$RUN_ID = "roms-" + [System.Guid]::NewGuid().ToString("N").Substring(0, 12)
$CONTAINER_NAME = "roms-test-pg-$RUN_ID"
$containerId = $null

$randomBytes = New-Object byte[] 16
[Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($randomBytes)
$TEST_PASSWORD = [Convert]::ToBase64String($randomBytes) -replace '[^a-zA-Z0-9]',''

Write-Host "=========================================================="
Write-Host "ROMS OP-02 Stage C Starting. Correlation Run ID: $RUN_ID"
Write-Host "Container Name: $CONTAINER_NAME"
Write-Host "=========================================================="

try {
    # --------------------------------------------------------------------------
    # 4. Provision Dedicated Test Container
    # --------------------------------------------------------------------------
    Write-Host "[1/6] Provisioning Docker container on 127.0.0.1:5433..."
    $dockerRunOutput = (docker run -d `
        --name $CONTAINER_NAME `
        --label "roms.test.run_id=$RUN_ID" `
        -p 127.0.0.1:5433:5432 `
        -e POSTGRES_USER=roms_test_user `
        -e POSTGRES_PASSWORD=$TEST_PASSWORD `
        -e POSTGRES_DB=roms_test_db `
        postgres:16-alpine `
        -c roms.run_id=$RUN_ID 2>&1)

    if ($LASTEXITCODE -ne 0 -or -not $dockerRunOutput) {
        throw "Docker provisioning failed with exit code ${LASTEXITCODE}: $dockerRunOutput"
    }

    $rawId = $dockerRunOutput.Trim()
    if ($rawId -notmatch '^[0-9a-fA-F]{12,64}$') {
        throw "Docker provisioning returned an invalid container ID: '$dockerRunOutput'"
    }
    # Only record containerId after positive verification
    $containerId = $rawId
    Write-Host "[SUCCESS] Container provisioned and ID validated: $containerId"

    # --------------------------------------------------------------------------
    # 5. Out-of-Band Docker Metadata Verification
    # --------------------------------------------------------------------------
    Write-Host "[2/6] Verifying container metadata independently via Docker inspect..."
    $inspectedLabel = (docker inspect --format '{{ index .Config.Labels "roms.test.run_id" }}' $containerId 2>&1).Trim()
    if ($LASTEXITCODE -ne 0) {
        throw "Docker inspect failed with exit code ${LASTEXITCODE}: $inspectedLabel"
    }
    if ($inspectedLabel -ne $RUN_ID) {
        throw "Container metadata check failed: expected label '$RUN_ID', got '$inspectedLabel'"
    }
    Write-Host "[SUCCESS] Container metadata correlation verified."

    # --------------------------------------------------------------------------
    # 6. Wait for PostgreSQL Daemon Readiness
    # --------------------------------------------------------------------------
    Write-Host "[3/6] Polling PostgreSQL daemon readiness..."
    $isReady = $false
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Seconds 1
        $status = docker exec $containerId pg_isready -U roms_test_user -d roms_test_db 2>&1
        if ($LASTEXITCODE -eq 0) {
            $isReady = $true
            break
        }
    }
    if (-not $isReady) {
        throw "PostgreSQL daemon failed to become ready within 15 seconds."
    }
    Write-Host "[SUCCESS] PostgreSQL daemon is accepting connections."

    # --------------------------------------------------------------------------
    # 7. Configure Process Environment Variables
    # --------------------------------------------------------------------------
    [System.Environment]::SetEnvironmentVariable("ROMS_POSTGRES_TEST_RUN_ID", $RUN_ID, "Process")
    [System.Environment]::SetEnvironmentVariable("ROMS_POSTGRES_TEST_DATABASE_URL", "postgresql://roms_test_user:$TEST_PASSWORD@127.0.0.1:5433/roms_test_db", "Process")

    # --------------------------------------------------------------------------
    # 8. Bootstrap Disposable Test Database
    # --------------------------------------------------------------------------
    Write-Host "[4/6] Bootstrapping test database marker table..."
    python scripts/init_postgres_test_db.py --confirm-bootstrap --run-id $RUN_ID
    if ($LASTEXITCODE -ne 0) {
        throw "Database bootstrap CLI failed with exit code ${LASTEXITCODE}."
    }
    Write-Host "[SUCCESS] Bootstrap completed."

    # --------------------------------------------------------------------------
    # 9. Apply Isolated Migrations
    # --------------------------------------------------------------------------
    Write-Host "[5/6] Applying isolated migrations via connection injection..."
    python scripts/migrate_postgres_test_db.py --confirm --run-id $RUN_ID
    if ($LASTEXITCODE -ne 0) {
        throw "Isolated migration runner failed with exit code ${LASTEXITCODE}."
    }
    Write-Host "[SUCCESS] Migrations applied and catalog constraints verified."

    # --------------------------------------------------------------------------
    # 10. Execute Concurrency Integration Tests
    # --------------------------------------------------------------------------
    Write-Host "[6/6] Executing PostgreSQL concurrency integration tests..."
    python -m pytest tests/test_postgres_concurrency.py --pg-integration -v
    if ($LASTEXITCODE -ne 0) {
        throw "PostgreSQL concurrency integration test suite failed with exit code ${LASTEXITCODE}."
    }

    Write-Host "=========================================================="
    Write-Host "[COMPLETE] Stage C PostgreSQL Integration Tests PASSED!"
    Write-Host "=========================================================="

} finally {
    # --------------------------------------------------------------------------
    # 11. Guaranteed Safe Cleanup & Environment Restoration
    # --------------------------------------------------------------------------
    Write-Host "[CLEANUP] Restoring process environment variables..."
    [System.Environment]::SetEnvironmentVariable("ROMS_POSTGRES_TEST_DATABASE_URL", $origTestDsn, "Process")
    [System.Environment]::SetEnvironmentVariable("ROMS_POSTGRES_TEST_RUN_ID", $origRunId, "Process")

    if ($containerId) {
        Write-Host "[CLEANUP] Stopping and removing container $containerId..."
        try {
            docker stop $containerId | Out-Null
        } catch {
            Write-Warning "[CLEANUP WARNING] docker stop failed: $_"
        }

        try {
            docker rm -v -f $containerId | Out-Null
            if ($LASTEXITCODE -eq 0) {
                Write-Host "[CLEANUP] Container $containerId successfully removed."
            } else {
                Write-Warning "[CLEANUP WARNING] docker rm exited with code ${LASTEXITCODE}."
            }
        } catch {
            Write-Warning "[CLEANUP WARNING] docker rm threw exception: $_"
        }
    } else {
        Write-Host "[CLEANUP] No container ID was recorded; zero container removal operations performed."
    }

    Pop-Location
}
