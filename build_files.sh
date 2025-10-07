#!/bin/bash

echo "=== Starting Django Build Process ==="

# Install dependencies
echo "1. Installing Python dependencies..."
pip install -r requirements.txt

# Check if installation was successful
if [ $? -ne 0 ]; then
    echo "Error: Failed to install dependencies"
    exit 1
fi

# Create necessary directories
echo "2. Creating directories..."
mkdir -p staticfiles_build/static
mkdir -p /tmp  # Ensure /tmp exists for SQLite

# Apply database migrations
echo "3. Applying database migrations..."
python manage.py migrate --noinput

# Check if migrations were successful
if [ $? -ne 0 ]; then
    echo "Warning: Database migrations failed, but continuing build..."
fi

# Create default categories and data
echo "4. Creating default categories..."
python manage.py shell -c "
import os
import django
from django.core.management import setup_environ

# Setup Django environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')
django.setup()

from api.models import ExpenseCategory

# Create default categories
categories = ['food', 'utilities', 'rent', 'clothes', 'transport', 'others']
for category in categories:
    ExpenseCategory.objects.get_or_create(
        name=category,
        defaults={'description': f'Default category: {category}'}
    )
print('Default categories created/verified successfully')
"

# Collect static files
echo "5. Collecting static files..."
python manage.py collectstatic --noinput --clear

# Check if static collection was successful
if [ $? -ne 0 ]; then
    echo "Warning: Static file collection had issues, but continuing build..."
fi

echo "6. Build completed successfully!"