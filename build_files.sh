#!/bin/bash
set -e  # Exit immediately if a command exits with a non-zero status

# Function to log with timestamps
log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1"
}

# Function to handle errors
error_exit() {
    log "ERROR: $1"
    exit 1
}

log "=== Starting Django Build Process ==="

# Ensure DJANGO_SETTINGS_MODULE is set
if [ -z "$DJANGO_SETTINGS_MODULE" ]; then
    export DJANGO_SETTINGS_MODULE="app.settings"
    log "Set DJANGO_SETTINGS_MODULE to app.settings"
fi

# Install dependencies with error capture
log "1. Installing Python dependencies..."
if ! pip install -r requirements.txt > pip_install.log 2>&1; then
    cat pip_install.log
    error_exit "Failed to install dependencies. See error above."
fi
rm pip_install.log

# Create necessary directories
log "2. Creating directories..."
mkdir -p staticfiles || error_exit "Failed to create staticfiles directory"
mkdir -p /tmp || log "Warning: Could not create /tmp directory, it may already exist"

# Clean existing static files to prevent stale assets
if [ -d "staticfiles" ]; then
    log "Cleaning existing static files..."
    rm -rf staticfiles/* || error_exit "Failed to clean staticfiles directory"
fi

# Collect static files
log "3. Collecting static files..."
if ! python manage.py collectstatic --noinput --clear > static_collect.log 2>&1; then
    cat static_collect.log
    error_exit "Static file collection failed. See error above."
fi
rm static_collect.log

# Verify static files exist
if [ ! -d "staticfiles" ] || [ -z "$(ls -A staticfiles 2>/dev/null)" ]; then
    error_exit "Static files directory is empty after collection"
fi

# Optional: Apply migrations if DATABASE_URL is set
# Note: This runs migrations during build, which is only safe for remote DBs
if [ ! -z "$DATABASE_URL" ]; then
    log "4. Applying database migrations (DATABASE_URL is set)..."
    if ! python manage.py migrate --noinput > migrations.log 2>&1; then
        cat migrations.log
        error_exit "Database migrations failed. See error above."
    fi
    rm migrations.log
else
    log "Skipping migrations: No DATABASE_URL set (will run at startup instead)"
fi

# Check static files were collected
log "5. Verifying build artifacts..."
if [ ! -f "staticfiles/css/mobile-responsive.css" ]; then
    error_exit "Critical static file missing after collection"
fi

log "=== Build completed successfully! ==="
exit 0