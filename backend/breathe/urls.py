"""URL configuration for BreatheESG."""
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('api/auth/', include('core.urls')),
    path('api/', include('ingestion.urls')),
    path('api/', include('emissions.urls')),
    path('api/', include('review.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
