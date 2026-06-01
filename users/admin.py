from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.utils.timezone import now
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.contrib import messages
from users.models import BannedIP
import csv, os

User = get_user_model()


def export_to_csv(modeladmin, request, queryset, filename, fields, headers):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for obj in queryset:
        row = [getattr(obj, field, '') for field in fields]
        writer.writerow(row)
    return response


@admin.register(User)
class UltimateUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'last_login', 'avatar_preview')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'last_login')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-last_login',)
    readonly_fields = ('date_joined', 'last_login', 'password')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'email', 'avatar')}),
        ('Статус', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Даты', {'fields': ('last_login', 'date_joined')}),
    )

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width: 35px; height: 35px; border-radius: 50%; object-fit: cover;"/>',
                obj.avatar.url)
        return "-"

    avatar_preview.short_description = "Фото"


@admin.register(BannedIP)
class BannedIPAdmin(admin.ModelAdmin):
    list_display = ('ip_address', 'reason', 'banned_at', 'banned_by')
    search_fields = ('ip_address', 'reason')
    list_filter = ('banned_at', 'banned_by')
    readonly_fields = ('banned_at', 'banned_by')

    def save_model(self, request, obj, form, change):
        if not obj.pk:
            obj.banned_by = request.user
        super().save_model(request, obj, form, change)
