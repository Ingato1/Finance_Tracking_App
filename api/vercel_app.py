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

# --- Auto-migrate on Vercel when using the /tmp SQLite fallback ---
try:
	from django.conf import settings
	from django.core.management import call_command
	import logging

	logger = logging.getLogger(__name__)

	is_vercel = os.environ.get('VERCEL')
	# If running on Vercel and DATABASES is the temporary /tmp sqlite, run migrations
	default_db = settings.DATABASES.get('default', {})
	db_engine = default_db.get('ENGINE', '')
	db_name = default_db.get('NAME', '')

	if is_vercel and 'sqlite3' in db_engine and db_name and db_name.startswith('/tmp'):
		try:
			logger.info('Vercel detected and using /tmp sqlite. Running migrations...')
			# Run migrations non-interactively
			call_command('migrate', '--noinput')
			logger.info('Migrations complete.')
		except Exception as e:
			# Log but do not crash the WSGI process; the app will still start and errors can be investigated
			logger.exception('Auto-migrate on startup failed: %s', e)
except Exception:
	# If anything goes wrong while attempting to auto-migrate, don't prevent the app from starting
	pass
