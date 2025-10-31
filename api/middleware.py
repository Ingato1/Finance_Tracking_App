from django.core.cache import cache
from django.http import HttpResponseForbidden

class RateLimitMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path in ['/login/', '/register/'] and request.method == 'POST':
            ip = request.META.get('REMOTE_ADDR')
            key = f'rate_limit_{ip}'
            attempts = cache.get(key, 0)
            
            if attempts >= 5:  # Max 5 attempts
                return HttpResponseForbidden('Too many attempts. Please try again later.')
            
            cache.set(key, attempts + 1, 300)  # 5 minutes timeout
        
        return self.get_response(request)