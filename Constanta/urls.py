import os
from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from django.contrib.sitemaps.views import sitemap
from Constanta.views import media_file, robots_txt, llms_txt, StaticViewSitemap

sitemaps = {
    'static': StaticViewSitemap,
}

urlpatterns = [
    path('robots.txt', robots_txt, name='robots_txt'),
    path('llms.txt', llms_txt, name='llms_txt'),
    path('sitemap.xml', sitemap, {'sitemaps': sitemaps}, name='sitemap_xml'),
    path(os.environ.get('ADMIN_URL', 'admin/'), admin.site.urls),
    path(f'{settings.MEDIA_URL.strip("/")}/<path:path>', media_file, name='media_file'),
    path('', include('users.urls')),
    path('', include('chat.urls')),
    path('tasks/', include('tasks.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
