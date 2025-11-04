from django.core.cache import cache
from django.http import HttpResponseForbidden

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # Match both the auth app's login path and custom patterns
        login_paths = ['/login/', '/accounts/login/']
        register_paths = ['/register/', '/accounts/register/']

        if request.method == 'POST' and (request.path in login_paths or request.path in register_paths):
            ip = request.META.get('REMOTE_ADDR', 'unknown')
            key = f'rate_limit_{ip}'
            attempts = cache.get(key, 0)

            if attempts >= 5:  # Max 5 attempts
                return HttpResponseForbidden('Too many attempts. Please try again later.')

            # Use a safe default TTL (5 minutes)
            cache.set(key, attempts + 1, 300)

        return self.get_response(request)