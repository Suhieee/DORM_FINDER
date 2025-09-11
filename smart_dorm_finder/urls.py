from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView
from django.contrib.staticfiles.urls import staticfiles_urlpatterns

# Import the handler404 view
from .views import handler404

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dormitory/', include('dormitory.urls')),
    # Redirect root to dormitory home page
    path('', RedirectView.as_view(url='/dormitory/', permanent=False), name='home'),
    path("profile/", include("user_profile.urls", namespace="user_profile")),
]

# Add static and media file handling
if settings.DEBUG:
    urlpatterns += staticfiles_urlpatterns()  # This handles static files
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)  # This handles media files

# Register the custom 404 handler
handler404 = 'smart_dorm_finder.views.handler404'
