from django.shortcuts import render
from django.template import RequestContext

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