from django.shortcuts import render
from django.template import RequestContext

def handler404(request, exception):
    """Custom 404 error handler that shows available paths based on user type."""
    context = {}
    response = render(request, '404.html', context)
    response.status_code = 404
    return response 