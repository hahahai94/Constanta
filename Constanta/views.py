import mimetypes
from pathlib import Path

from django.conf import settings
from django.contrib.auth.decorators import login_required
from django.http import FileResponse, Http404, HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.shortcuts import render

SAFE_MEDIA_PREFIXES = ('avatars/', 'group_avatars/', 'channel_avatars/')
SAFE_IMAGE_TYPES = {
    'image/jpeg', 'image/png', 'image/gif', 'image/webp', 'image/bmp',
}


@login_required
def media_file(request, path):
    """Отдаёт только аватары; вложения доступны через ``download_attachment``."""
    if path.startswith('attachments/') or not path.startswith(SAFE_MEDIA_PREFIXES):
        raise Http404

    base = Path(settings.MEDIA_ROOT).resolve()
    full_path = (base / path).resolve()
    if base not in full_path.parents or not full_path.is_file():
        raise Http404

    content_type, _ = mimetypes.guess_type(full_path.name)
    if content_type not in SAFE_IMAGE_TYPES:
        raise Http404

    response = FileResponse(open(full_path, 'rb'), content_type=content_type)
    response['Content-Disposition'] = f'inline; filename="{full_path.name}"'
    response['X-Content-Type-Options'] = 'nosniff'
    response['Cache-Control'] = 'private, max-age=3600'
    return response


@require_GET
def robots_txt(request):
    # ADMIN_URL здесь намеренно не публикуется: robots.txt — первый файл,
    # который читают сканеры, и раскрывать в нём путь админки нельзя
    # (problems.md, П-22).
    content = render_to_string('robots.txt')
    return HttpResponse(content, content_type='text/plain')


@require_GET
def llms_txt(request):
    content = render_to_string('llms.txt')
    return HttpResponse(content, content_type='text/plain')


class StaticViewSitemap(Sitemap):
    priority = 0.5
    changefreq = 'weekly'

    def items(self):
        return ['auth']

    def location(self, item):
        return reverse(item)
