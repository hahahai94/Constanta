"""Совместимость: примитив rate limiting переехал в ``users.ratelimit``.

Здесь остался только реэкспорт, чтобы существующие импорты
(``from chat.utils import rate_limit``) продолжали работать.
"""

from users.ratelimit import html_429, json_429, rate_limit  # noqa: F401

__all__ = ['rate_limit', 'json_429', 'html_429']
