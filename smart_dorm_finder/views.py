from django.shortcuts import render
from django.http import JsonResponse
from django.db import connections
from django.core.cache import cache
from django.utils import timezone

def handler404(request, exception):
    """Custom 404 error handler that shows available paths based on user type."""
    context = {}
    response = render(request, '404.html', context)
    response.status_code = 404
    return response 

def handler429(request, exception=None):
    """Custom 429 error handler for rate limiting."""
    context = {
        'error_message': 'Too many requests. Please slow down and try again in a few moments.'
    }
    response = render(request, '429.html', context)
    response.status_code = 429
    return response


def health_live(request):
    """Liveness probe: process is up and serving requests."""
    payload = {
        'status': 'ok',
        'service': 'dorm-finder',
        'timestamp': timezone.now().isoformat(),
        'request_id': getattr(request, 'request_id', '-'),
    }
    return JsonResponse(payload, status=200)


def health_ready(request):
    """Readiness probe: database and cache checks."""
    checks = {}
    status_code = 200

    try:
        with connections['default'].cursor() as cursor:
            cursor.execute('SELECT 1')
            cursor.fetchone()
        checks['database'] = 'ok'
    except Exception:
        checks['database'] = 'error'
        status_code = 503

    cache_key = f"health:{timezone.now().timestamp()}"
    try:
        cache.set(cache_key, 'ok', timeout=10)
        checks['cache'] = 'ok' if cache.get(cache_key) == 'ok' else 'error'
        if checks['cache'] != 'ok':
            status_code = 503
    except Exception:
        checks['cache'] = 'error'
        status_code = 503

    payload = {
        'status': 'ok' if status_code == 200 else 'degraded',
        'service': 'dorm-finder',
        'checks': checks,
        'timestamp': timezone.now().isoformat(),
        'request_id': getattr(request, 'request_id', '-'),
    }
    return JsonResponse(payload, status=status_code)