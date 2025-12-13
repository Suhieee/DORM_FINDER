from django.contrib import admin
from django.urls import path, include
from django.views.static import serve
from django.conf import settings
from django.conf.urls.static import static
from django.views.generic import RedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dormitory/', include('dormitory.urls')),
    path('', RedirectView.as_view(url='/dormitory/', permanent=False), name='home'),
    path("profile/", include("user_profile.urls", namespace="user_profile")),
    
    # Manual serving - ALWAYS works with DEBUG=False
    path('media/<path:path>', serve, {'document_root': settings.MEDIA_ROOT}),
    path('static/<path:path>', serve, {'document_root': settings.STATIC_ROOT}),
]

handler404 = 'smart_dorm_finder.views.handler404'
handler429 = 'smart_dorm_finder.views.handler429'  # Rate limit exceeded