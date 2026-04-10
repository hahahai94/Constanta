from django.core.management.base import BaseCommand
from chat.models import Message
from django.db.models import Count


class Command(BaseCommand):
    help = 'Поиск дубликатов файлов по хешу'

    def handle(self, *args, **kwargs):
        duplicates = Message.objects.filter(
            attachment_hash__isnull=False
        ).exclude(
            attachment_hash=''
        ).values('attachment_hash').annotate(
            count=Count('id')
        ).filter(count__gt=1)

        if duplicates:
            self.stdout.write(self.style.WARNING(f'Найдено {len(duplicates)} хешей с дубликатами:'))
            for dup in duplicates:
                self.stdout.write(f"  Хеш: {dup['attachment_hash'][:16]}... ( {dup['count']} раз )")
        else:
            self.stdout.write(self.style.SUCCESS('Дубликатов не найдено!'))