from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    # TODO: в реальности по-хорошему admin/ надо допускать или по IP или заменить на что-то более сложное, а то боты задолбят
    path('admin/', admin.site.urls),
    path('', include('chat.urls')),
]

# TODO: У тебя есть nginx, он и должен отдавать всю статику, это он будет делать в разы быстрее
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
