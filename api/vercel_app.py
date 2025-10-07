import os
import sys

# Add the project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# Import and configure Django
import django
from django.core.wsgi import get_wsgi_application

django.setup()

# Create WSGI application
application = get_wsgi_application()

# Vercel requires this
app = application
