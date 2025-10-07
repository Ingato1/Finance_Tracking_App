import os
import sys

# Add the project root to Python path
current_dir = os.path.dirname(os.path.abspath(__file__))
project_root = os.path.dirname(current_dir)
sys.path.insert(0, project_root)

# Set Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

try:
    # Configure Django
    import django
    from django.core.wsgi import get_wsgi_application
    
    # Initialize Django
    django.setup()
    
    # Create WSGI application
    application = get_wsgi_application()
    
    # Vercel requires this
    app = application

except Exception as e:
    # Debug any initialization errors
    def app(environ, start_response):
        start_response('500 Server Error', [('Content-Type', 'text/plain')])
        return [f'Django initialization failed: {str(e)}'.encode()]