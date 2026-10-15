from django.contrib import admin, messages
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.utils import timezone
from django.utils.html import format_html
from django.http import HttpResponse
from users.audit import log_admin_action
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
    # `banned_at` больше не readonly: иначе бан нельзя было выставить даже из
    # админки, и подсистема бана оставалась нерабочей (problems.md, П-4).
    readonly_fields = ('date_joined', 'last_login', 'last_seen', 'password')

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

    @admin.action(description="🚫 Забанить выбранных пользователей")
    def ban_users(self, request, queryset):
        banned = 0
        skipped_self = False
        for user in queryset:
            if user.pk == request.user.pk:
                # иначе администратор заблокировал бы себе доступ
                skipped_self = True
                continue
            if user.banned_at is not None:
                continue
            user.banned_at = timezone.now()
            user.banned_by = request.user
            user.save(update_fields=['banned_at', 'banned_by'])
            log_admin_action(
                request.user, 'ban_user', f'Забанен пользователь {user.username}',
                target_user=user, request=request,
            )
            banned += 1
        message = f'Забанено пользователей: {banned}'
        if skipped_self:
            message += ' (собственный аккаунт пропущен)'
        self.message_user(request, message, messages.SUCCESS)

    @admin.action(description="✅ Разбанить выбранных пользователей")
    def unban_users(self, request, queryset):
        unbanned = 0
        for user in queryset.filter(banned_at__isnull=False):
            user.banned_at = None
            user.banned_by = None
            user.save(update_fields=['banned_at', 'banned_by'])
            log_admin_action(
                request.user, 'unban_user', f'Разбанен пользователь {user.username}',
                target_user=user, request=request,
            )
            unbanned += 1
        self.message_user(request, f'Разбанено пользователей: {unbanned}', messages.SUCCESS)

    @admin.action(description="📄 Экспорт пользователей в CSV")
    def export_users_csv(self, request, queryset):
        return export_to_csv(
            self, request, queryset, 'users',
            ['username', 'nick', 'email', 'is_active', 'last_seen'],
            ['Логин', 'Никнейм', 'Email', 'Активен', 'Последний вход'],
        )

    actions = ['ban_users', 'unban_users', 'export_users_csv']

    def save_model(self, request, obj, form, change):
        """Проставляет автора бана и пишет действие в аудит (problems.md, П-5)."""
        previous_banned_at = None
        if change and obj.pk:
            previous_banned_at = User.objects.filter(
                pk=obj.pk).values_list('banned_at', flat=True).first()

        if obj.banned_at and not obj.banned_by:
            obj.banned_by = request.user

        super().save_model(request, obj, form, change)

        if previous_banned_at is None and obj.banned_at is not None:
            action = 'ban_user'
        elif previous_banned_at is not None and obj.banned_at is None:
            action = 'unban_user'
        else:
            action = 'edit_profile'
        log_admin_action(
            request.user, action,
            f'{obj.username}: {", ".join(form.changed_data) or "создан"}',
            target_user=obj, request=request,
        )

    def delete_model(self, request, obj):
        log_admin_action(
            request.user, 'delete_user', f'Удалён пользователь {obj.username}',
            target_user=None, request=request,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for username in list(queryset.values_list('username', flat=True)):
            log_admin_action(
                request.user, 'delete_user', f'Удалён пользователь {username}',
                request=request,
            )
        super().delete_queryset(request, queryset)


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
        if not change:
            log_admin_action(
                request.user, 'ban_ip', f'Забанен IP {obj.ip_address}',
                request=request,
            )

    def delete_model(self, request, obj):
        log_admin_action(
            request.user, 'unban_ip', f'Разбанен IP {obj.ip_address}',
            request=request,
        )
        super().delete_model(request, obj)

    def delete_queryset(self, request, queryset):
        for ip in list(queryset.values_list('ip_address', flat=True)):
            log_admin_action(
                request.user, 'unban_ip', f'Разбанен IP {ip}', request=request,
            )
        super().delete_queryset(request, queryset)


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
