"""Экспорт в CSV для админки.

Решает две проблемы исходного хелпера (problems.md, П-35):

* ``getattr(obj, 'sender__username')`` не разыменовывает связи и всегда
  возвращал пустую строку — здесь путь разбирается по частям;
* значения, начинающиеся с ``=``, ``+``, ``-`` или ``@``, Excel истолковывает
  как формулу, поэтому они экранируются апострофом.
"""

import csv

from django.http import HttpResponse

# Символы, с которых Excel начинает разбирать формулу.
FORMULA_PREFIXES = ('=', '+', '-', '@', '\t', '\r')


def csv_safe(value):
    """Защищает от формул в Excel."""
    text = '' if value is None else str(value)
    if text.startswith(FORMULA_PREFIXES):
        return "'" + text
    return text


def resolve(obj, path):
    """Читает значение по пути вида ``sender__username``."""
    value = obj
    for part in path.split('__'):
        value = getattr(value, part, None)
        if value is None:
            return ''
    return value


def export_to_csv(modeladmin, request, queryset, filename, fields, headers):
    response = HttpResponse(content_type='text/csv')
    response['Content-Disposition'] = f'attachment; filename="{filename}.csv"'
    writer = csv.writer(response)
    writer.writerow(headers)
    for obj in queryset:
        writer.writerow([csv_safe(resolve(obj, field)) for field in fields])
    return response
