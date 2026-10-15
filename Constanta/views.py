from django.conf import settings
from django.http import HttpResponse
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET
from django.contrib.sitemaps import Sitemap
from django.urls import reverse
from django.shortcuts import render


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
