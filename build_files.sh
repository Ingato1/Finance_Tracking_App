#!/bin/bash

echo "=== Starting Django Build Process ==="

# Install dependencies
echo "1. Installing Python dependencies..."
pip install -r requirements.txt

# Create necessary directories
echo "2. Creating directories..."
mkdir -p staticfiles_build/static
mkdir -p /tmp  # Ensure /tmp exists for SQLite

# Apply database migrations (only if using SQLite)
echo "3. Applying database migrations..."
python manage.py migrate --noinput

# Create default categories and data
echo "4. Creating default categories..."
python manage.py shell -c "
from api.models import ExpenseCategory

categories = ['food', 'utilities', 'rent', 'clothes', 'transport', 'others']
for category in categories:
    ExpenseCategory.objects.get_or_create(name=category)
print('Default categories created successfully')
"

# Collect static files
echo "5. Collecting static files..."
python manage.py collectstatic --noinput

echo "6. Build completed successfully!"
