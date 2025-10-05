#!/bin/bash

# Install Python dependencies
echo "Installing Python dependencies..."
pip install -r requirements.txt

# Apply database migrations
echo "Applying database migrations..."
python manage.py migrate --noinput

# Collect static files
echo "Collecting static files..."
python manage.py collectstatic --noinput

# Create the staticfiles_build directory
echo "Creating static files directory..."
mkdir -p staticfiles_build

# Copy static files to build directory
echo "Copying static files..."
cp -r staticfiles/* staticfiles_build/ 2>/dev/null || true
cp -r static/* staticfiles_build/ 2>/dev/null || true

echo "Build completed successfully!"
