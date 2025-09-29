import os
import sys
from http.server import BaseHTTPRequestHandler
from django.core.wsgi import get_wsgi_application

# Add the current directory to the path
sys.path.insert(0, os.path.dirname(__file__))

# Set the Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'app.settings')

# Get the WSGI application
application = get_wsgi_application()

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.handle_request()

    def do_POST(self):
        self.handle_request()

    def do_PUT(self):
        self.handle_request()

    def do_DELETE(self):
        self.handle_request()

    def do_PATCH(self):
        self.handle_request()

    def handle_request(self):
        # Convert the request to WSGI environ
        environ = self.get_environ()

        # Create a start_response function
        def start_response(status, headers):
            self.send_response(int(status.split()[0]))
            for header, value in headers:
                self.send_header(header, value)
            self.end_headers()

        # Call the WSGI application
        result = application(environ, start_response)

        # Send the response body
        for data in result:
            self.wfile.write(data)

    def get_environ(self):
        # Build the WSGI environ dictionary
        environ = {
            'REQUEST_METHOD': self.command,
            'SCRIPT_NAME': '',
            'PATH_INFO': self.path,
            'QUERY_STRING': '',
            'CONTENT_TYPE': self.headers.get('Content-Type', ''),
            'CONTENT_LENGTH': self.headers.get('Content-Length', '0'),
            'SERVER_NAME': self.headers.get('Host', 'localhost').split(':')[0],
            'SERVER_PORT': '80',
            'wsgi.version': (1, 0),
            'wsgi.url_scheme': 'https',
            'wsgi.input': self.rfile,
            'wsgi.errors': sys.stderr,
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': False,
        }

        # Add HTTP headers
        for header, value in self.headers.items():
            key = 'HTTP_' + header.upper().replace('-', '_')
            environ[key] = value

        return environ
