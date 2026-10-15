from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils.html import format_html
from django.http import HttpResponse
from users.models import BannedIP, AdminLog, Notification
import csv

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
    # Поля, менять которые разрешено только суперпользователю. В Django 6
    # штатный UserAdmin больше не отключает их для обычного персонала,
    # поэтому без явной защиты сотрудник с правом change_user мог бы одним
    # POST выдать себе суперпользователя (problems.md, П-1).
    PRIVILEGED_FIELDS = ('is_superuser', 'groups', 'user_permissions')

    list_display = ('username', 'nick', 'email', 'is_active', 'is_banned', 'is_staff', 'is_superuser', 'last_seen', 'avatar_preview')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'last_login')
    search_fields = ('username', 'nick', 'email', 'first_name', 'last_name')
    ordering = ('-last_login',)
    readonly_fields = ('date_joined', 'last_login', 'last_seen', 'password', 'banned_at')

    fieldsets = (
        (None, {'fields': ('username', 'password')}),
        ('Профиль', {'fields': ('nick', 'avatar', 'bio')}),
        ('Личные данные', {'fields': ('first_name', 'last_name', 'email')}),
        ('Статус', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}),
        ('Бан', {'fields': ('ban_reason', 'banned_at', 'banned_by')}),
        ('Активность', {'fields': ('last_login', 'last_seen', 'date_joined')}),
    )

    def get_form(self, request, obj=None, **kwargs):
        """Отключает привилегированные поля для не-суперпользователей.

        Без этого любой сотрудник с правом change_user мог бы выставить себе
        is_superuser через POST. Отключённые поля игнорируются при сохранении.
        """
        form = super().get_form(request, obj, **kwargs)
        if request.user.is_superuser:
            return form

        disabled = set(self.PRIVILEGED_FIELDS)
        if obj is not None and obj == request.user:
            # себе нельзя менять и собственный статус
            disabled |= {'is_active', 'is_staff', 'username'}

        for name in disabled:
            if name in form.base_fields:
                form.base_fields[name].disabled = True
        return form

    def get_fieldsets(self, request, obj=None):
        """Скрывает привилегированные поля от не-суперпользователей."""
        fieldsets = super().get_fieldsets(request, obj)
        if request.user.is_superuser:
            return fieldsets

        cleaned = []
        for name, options in fieldsets:
            options = dict(options)
            fields = [f for f in options.get('fields', ())
                      if f not in self.PRIVILEGED_FIELDS]
            if fields:
                options['fields'] = fields
                cleaned.append((name, options))
        return cleaned

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width: 35px; height: 35px; border-radius: 50%; object-fit: cover;"/>',
                obj.avatar.url)
        return "-"

    avatar_preview.short_description = "Фото"

    def is_banned(self, obj):
        return obj.banned_at is not None

    is_banned.boolean = True
    is_banned.short_description = "Забанен"


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


@admin.register(AdminLog)
class AdminLogAdmin(admin.ModelAdmin):
    list_display = ('admin', 'action', 'target_user', 'timestamp', 'ip_address')
    list_filter = ('action', 'timestamp', 'admin')
    search_fields = ('admin__username', 'target_user__username', 'description')
    readonly_fields = ('admin', 'action', 'target_user', 'description', 'timestamp', 'ip_address')
    ordering = ('-timestamp',)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(Notification)
class NotificationAdmin(admin.ModelAdmin):
    list_display = ('user', 'notification_type', 'title', 'is_read', 'created_at')
    list_filter = ('notification_type', 'is_read', 'created_at')
    search_fields = ('user__username', 'title', 'message')
    ordering = ('-created_at',)
