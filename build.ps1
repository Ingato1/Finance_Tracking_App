# Function to log with timestamps
function Write-Log {
    param([string]$Message)
    Write-Host "[$([DateTime]::Now.ToString('yyyy-MM-dd HH:mm:ss'))] $Message"
}

# Function to handle errors
function Exit-WithError {
    param([string]$Message)
    Write-Log "ERROR: $Message"
    exit 1
}

Write-Log "=== Starting Django Build Process ==="

# Ensure DJANGO_SETTINGS_MODULE is set
if (-not $env:DJANGO_SETTINGS_MODULE) {
    $env:DJANGO_SETTINGS_MODULE = "app.settings"
    Write-Log "Set DJANGO_SETTINGS_MODULE to app.settings"
}

# Install dependencies with error capture, handling psycopg2 specially
Write-Log "1. Installing Python dependencies..."
# Create a temporary requirements file without psycopg2-binary for local testing
$requirements = Get-Content requirements.txt | Where-Object { $_ -notmatch 'psycopg2-binary' }
$requirements | Set-Content requirements.temp.txt

Write-Log "Installing core dependencies (excluding psycopg2-binary)..."
$pipOutput = python -m pip install -r requirements.temp.txt 2>&1
Remove-Item requirements.temp.txt -Force
if ($LASTEXITCODE -ne 0) {
    $pipOutput
    Exit-WithError "Failed to install core dependencies. See error above."
}

# Try to install psycopg2-binary only if DATABASE_URL is set
if ($env:DATABASE_URL) {
    Write-Log "DATABASE_URL is set, attempting to install psycopg2-binary..."
    $pgOutput = python -m pip install psycopg2-binary==2.9.7 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Log "Warning: Could not install psycopg2-binary, this is expected in local dev"
    }
}

# Create necessary directories
Write-Log "2. Creating directories..."
New-Item -ItemType Directory -Force -Path "staticfiles" | Out-Null
if (-not $?) {
    Exit-WithError "Failed to create staticfiles directory"
}

# Clean existing static files to prevent stale assets
if (Test-Path "staticfiles") {
    Write-Log "Cleaning existing static files..."
    Remove-Item -Path "staticfiles\*" -Recurse -Force
    if (-not $?) {
        Exit-WithError "Failed to clean staticfiles directory"
    }
}

# Collect static files
Write-Log "3. Collecting static files..."
$staticOutput = python manage.py collectstatic --noinput --clear 2>&1
if ($LASTEXITCODE -ne 0) {
    $staticOutput
    Exit-WithError "Static file collection failed. See error above."
}

# Verify static files exist
if (-not (Test-Path "staticfiles") -or -not (Get-ChildItem -Path "staticfiles" -File -Recurse)) {
    Exit-WithError "Static files directory is empty after collection"
}

# Optional: Apply migrations if DATABASE_URL is set
if ($env:DATABASE_URL) {
    Write-Log "4. Applying database migrations (DATABASE_URL is set)..."
    $migrateOutput = python manage.py migrate --noinput 2>&1
    if ($LASTEXITCODE -ne 0) {
        $migrateOutput
        Exit-WithError "Database migrations failed. See error above."
    }
}
else {
    Write-Log "Skipping migrations: No DATABASE_URL set (will run at startup instead)"
}

# Check static files were collected
Write-Log "5. Verifying build artifacts..."
if (-not (Test-Path "staticfiles\css\mobile-responsive.css")) {
    Exit-WithError "Critical static file missing after collection"
}

Write-Log "=== Build completed successfully! ==="
exit 0