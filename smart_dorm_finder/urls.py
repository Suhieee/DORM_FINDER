from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from accounts.views import RoleBasedRedirectView

urlpatterns = [
    path('admin/', admin.site.urls),
    path('accounts/', include('accounts.urls')),
    path('dormitory/', include('dormitory.urls')),
    path('', RoleBasedRedirectView.as_view(), name='home_redirect'),
     
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
