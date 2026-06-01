from django.contrib import admin
from django.contrib.auth import get_user_model
from django.utils.html import format_html
from django.http import HttpResponse
from django.contrib import messages
from chat.models import Group, Message, GroupMember
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
        return ""

    avatar_preview.short_description = "Фото"

    def member_count(self, obj):
        return GroupMember.objects.filter(group=obj).count()

    member_count.short_description = "Участников"

    def message_count(self, obj):
        return Message.objects.filter(group=obj).count()

    message_count.short_description = "Сообщений"

    @admin.action(description="Удалить группу и файлы")
    def hard_delete_groups(self, request, queryset):
        for group in queryset:
            if group.avatar and os.path.isfile(group.avatar.path):
                os.remove(group.avatar.path)
        count, _ = queryset.delete()
        self.message_user(request, f"Удалено {count} групп + очищены аватарки", messages.SUCCESS)

    @admin.action(description="Экспорт участников в CSV")
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
        if obj.group: return f"Группа: {obj.group.name}"
        if obj.receiver: return f"Пользователь: {obj.receiver.username}"
        return ""

    target.short_description = "Куда"

    @admin.action(description="Удалить сообщения и файлы")
    def hard_delete_messages(self, request, queryset):
        deleted_count = 0
        for msg in queryset:
            if msg.attachment and os.path.isfile(msg.attachment.path):
                os.remove(msg.attachment.path)
            deleted_count += 1
        queryset.delete()
        self.message_user(request, f"Удалено {deleted_count} сообщений + вложения", messages.SUCCESS)

    @admin.action(description="Экспорт в CSV")
    def export_messages_csv(self, request, queryset):
        return export_to_csv(self, request, queryset, 'messages',
                             ['id', 'sender__username', 'content', 'attachment_type', 'created_at'],
                             ['ID', 'Отправитель', 'Текст', 'Тип файла', 'Дата'])

    actions = ['hard_delete_messages', 'export_messages_csv']


@admin.register(GroupMember)
class UltimateGroupMemberAdmin(admin.ModelAdmin):
    list_display = ('group', 'user', 'role', 'joined_at')
    list_filter = ('role', 'group', 'joined_at')
    search_fields = ('user__username', 'group__name')

    @admin.action(description="Сделать админами")
    def promote_to_admin(self, request, queryset):
        queryset.update(role='admin')
        self.message_user(request, f"{queryset.count()} пользователей стали админами", messages.SUCCESS)

    @admin.action(description="Понизить до участников")
    def demote_to_member(self, request, queryset):
        queryset.update(role='member')
        self.message_user(request, f"{queryset.count()} пользователей понижены", messages.INFO)

    @admin.action(description="Исключить из групп")
    def kick_from_groups(self, request, queryset):
        count, _ = queryset.delete()
        self.message_user(request, f"Исключено {count} участников", messages.WARNING)

    actions = ['promote_to_admin', 'demote_to_member', 'kick_from_groups']
