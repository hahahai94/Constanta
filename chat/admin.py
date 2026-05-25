import csv
import os
from django.contrib import admin, messages
from django.contrib.auth.models import User
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from django.contrib.sessions.models import Session
from django.http import HttpResponse
from django.utils.html import format_html
from django.utils.timezone import now
from django.db.models import Count, Q
from django.contrib.admin import AdminSite

from .models import Group, Message, GroupMember


# ==============================================================================
# 🛠 ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ==============================================================================
def export_to_csv(modeladmin, request, queryset, filename, fields, headers):
    """Универсальный экспорт в CSV"""
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for obj in queryset:
        row = [getattr(obj, field, '') for field in fields]
        writer.writerow(row)
    return response


def cleanup_user_media(user):
    """Удаляет аватарку пользователя и связанные файлы"""
    try:
        if user.avatar:
            if os.path.isfile(user.avatar.path):
                os.remove(user.avatar.path)
    except Exception:
        pass


# ==============================================================================
# 👤 АДМИНКА ПОЛЬЗОВАТЕЛЕЙ (ULTIMATE)
# ==============================================================================
class UserGroupsInline(admin.TabularInline):
    model = Group
    fk_name = 'owner'
    extra = 0
    readonly_fields = ('created_at',)
    can_delete = False


class UserMessagesInline(admin.TabularInline):
    model = Message
    fk_name = 'sender'
    extra = 0
    readonly_fields = ('created_at', 'content')
    can_delete = True


@admin.register(User)
class UltimateUserAdmin(BaseUserAdmin):
    list_display = ('username', 'email', 'is_active', 'is_staff', 'message_count', 'last_login', 'avatar_preview')
    list_filter = ('is_active', 'is_staff', 'is_superuser', 'groups', 'last_login')
    search_fields = ('username', 'email', 'first_name', 'last_name')
    ordering = ('-last_login',)
    readonly_fields = ('date_joined', 'last_login', 'password')
    inlines = [UserGroupsInline, UserMessagesInline]

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
        return "❌"

    avatar_preview.short_description = "Фото"

    def message_count(self, obj):
        return Message.objects.filter(sender=obj).count()

    message_count.short_description = "Сообщений"

    # 🚀 ДЕЙСТВИЯ
    @admin.action(description="🗑️ Удалить с полной очисткой")
    def hard_delete_users(self, request, queryset):
        for user in queryset:
            cleanup_user_media(user)
            # Удаляем сессии пользователя
            Session.objects.filter(session_data__contains=user.username).delete()
        count, _ = queryset.delete()
        self.message_user(request, f"✅ Удалено {count} пользователей + очищены медиа и сессии.", messages.SUCCESS)

    @admin.action(description="📤 Экспорт в CSV")
    def export_users_csv(self, request, queryset):
        return export_to_csv(self, request, queryset, 'users',
                             ['id', 'username', 'email', 'is_active', 'date_joined', 'last_login'],
                             ['ID', 'Логин', 'Email', 'Активен', 'Дата регистрации', 'Последний вход'])

    @admin.action(description="🔐 Сбросить пароль на 12345")
    def reset_passwords(self, request, queryset):
        for user in queryset:
            user.set_password('12345')
            user.save()
        self.message_user(request, f"🔑 Пароль сброшен у {queryset.count()} пользователей (новый: 12345)",
                          messages.WARNING)

    @admin.action(description="👥 Добавить в группу по умолчанию")
    def assign_default_group(self, request, queryset):
        default_group, _ = Group.objects.get_or_create(name="Общий чат")
        for user in queryset:
            GroupMember.objects.get_or_create(group=default_group, user=user)
        self.message_user(request, f"✅ {queryset.count()} пользователей добавлены в 'Общий чат'", messages.SUCCESS)

    actions = ['hard_delete_users', 'export_users_csv', 'reset_passwords', 'assign_default_group']


# ==============================================================================
# 📢 АДМИНКА ГРУПП (PRO)
# ==============================================================================
class GroupMembersInline(admin.TabularInline):
    model = GroupMember
    extra = 0
    readonly_fields = ('joined_at',)


class GroupMessagesInline(admin.TabularInline):
    model = Message
    fk_name = 'group'
    extra = 0
    readonly_fields = ('sender', 'created_at', 'content')
    can_delete = True


@admin.register(Group)
class UltimateGroupAdmin(admin.ModelAdmin):
    list_display = ('name', 'owner', 'member_count', 'message_count', 'created_at', 'avatar_preview')
    list_filter = ('created_at', 'owner')
    search_fields = ('name', 'owner__username', 'description')
    ordering = ('-created_at',)
    inlines = [GroupMembersInline, GroupMessagesInline]

    def avatar_preview(self, obj):
        if obj.avatar:
            return format_html(
                '<img src="{}" style="width: 35px; height: 35px; border-radius: 50%; object-fit: cover;"/>',
                obj.avatar.url)
        return "📁"

    avatar_preview.short_description = "Фото"

    def member_count(self, obj):
        return GroupMember.objects.filter(group=obj).count()

    member_count.short_description = "Участников"

    def message_count(self, obj):
        return Message.objects.filter(group=obj).count()

    message_count.short_description = "Сообщений"

    @admin.action(description="🗑️ Удалить группу и файлы")
    def hard_delete_groups(self, request, queryset):
        for group in queryset:
            if group.avatar and os.path.isfile(group.avatar.path):
                os.remove(group.avatar.path)
        count, _ = queryset.delete()
        self.message_user(request, f"🗑️ Удалено {count} групп + очищены аватарки", messages.SUCCESS)

    @admin.action(description="📤 Экспорт участников в CSV")
    def export_group_members(self, request, queryset):
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = 'attachment; filename="group_members.csv"'
        writer = csv.writer(response)
        writer.writerow(['Группа', 'Пользователь', 'Роль', 'Дата вступления'])
        for group in queryset:
            for member in GroupMember.objects.filter(group=group):
                writer.writerow([group.name, member.user.username, member.role, member.joined_at])
        return response

    actions = ['hard_delete_groups', 'export_group_members']


# ==============================================================================
# 💬 АДМИНКА СООБЩЕНИЙ (MAX)
# ==============================================================================
@admin.register(Message)
class UltimateMessageAdmin(admin.ModelAdmin):
    list_display = ('id', 'sender', 'content_preview', 'attachment_type', 'created_at', 'target')
    list_filter = ('attachment_type', 'created_at', 'sender', 'receiver', 'group')
    search_fields = ('content', 'sender__username', 'attachment_original_name')
    readonly_fields = ('created_at', 'attachment_hash', 'mentions')
    ordering = ('-created_at',)
    list_per_page = 50

    def content_preview(self, obj):
        return (obj.content[:60] + "...") if obj.content else "[Файл/Пусто]"

    content_preview.short_description = "Текст"

    def target(self, obj):
        if obj.group: return f"👥 {obj.group.name}"
        if obj.receiver: return f"👤 {obj.receiver.username}"
        return "❓"

    target.short_description = "Куда"

    @admin.action(description="🗑️ Удалить сообщения и файлы")
    def hard_delete_messages(self, request, queryset):
        deleted_count = 0
        for msg in queryset:
            if msg.attachment and os.path.isfile(msg.attachment.path):
                os.remove(msg.attachment.path)
            deleted_count += 1
        queryset.delete()
        self.message_user(request, f"🗑️ Удалено {deleted_count} сообщений + вложения", messages.SUCCESS)

    @admin.action(description="📤 Экспорт в CSV")
    def export_messages_csv(self, request, queryset):
        return export_to_csv(self, request, queryset, 'messages',
                             ['id', 'sender__username', 'content', 'attachment_type', 'created_at'],
                             ['ID', 'Отправитель', 'Текст', 'Тип файла', 'Дата'])

    actions = ['hard_delete_messages', 'export_messages_csv']


# ==============================================================================
# 👥 АДМИНКА УЧАСТНИКОВ ГРУПП
# ==============================================================================
@admin.register(GroupMember)
class UltimateGroupMemberAdmin(admin.ModelAdmin):
    list_display = ('group', 'user', 'role', 'joined_at')
    list_filter = ('role', 'group', 'joined_at')
    search_fields = ('user__username', 'group__name')

    @admin.action(description="⭐ Сделать админами")
    def promote_to_admin(self, request, queryset):
        queryset.update(role='admin')
        self.message_user(request, f"✅ {queryset.count()} пользователей стали админами", messages.SUCCESS)

    @admin.action(description="⬇️ Понизить до участников")
    def demote_to_member(self, request, queryset):
        queryset.update(role='member')
        self.message_user(request, f"⬇️ {queryset.count()} пользователей понижены", messages.INFO)

    @admin.action(description="🚫 Исключить из групп")
    def kick_from_groups(self, request, queryset):
        count, _ = queryset.delete()
        self.message_user(request, f"🚫 Исключено {count} участников", messages.WARNING)

    actions = ['promote_to_admin', 'demote_to_member', 'kick_from_groups']


# ==============================================================================
# 📊 КАСТОМНАЯ АДМИН-ПАНЕЛЬ СО СТАТИСТИКОЙ
# ==============================================================================
class ConstantaAdminSite(AdminSite):
    site_header = "Constanta Admin"
    site_title = "Constanta Panel"
    index_title = "Панель управления мессенджером"

    def index(self, request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update({
            'total_users': User.objects.count(),
            'active_users': User.objects.filter(is_active=True).count(),
            'total_groups': Group.objects.count(),
            'total_messages': Message.objects.count(),
            'online_estimate': User.objects.filter(
                last_login__gte=now().replace(hour=0, minute=0, second=0, microsecond=0)).count(),
        })
        return super().index(request, extra_context)


# Заменяем стандартную админку на кастомную
admin_site = ConstantaAdminSite(name='admin')
admin.site = admin_site

# Перерегистрируем модели под новый сайт
admin_site.register(User, UltimateUserAdmin)
admin_site.register(Group, UltimateGroupAdmin)
admin_site.register(Message, UltimateMessageAdmin)
admin_site.register(GroupMember, UltimateGroupMemberAdmin)