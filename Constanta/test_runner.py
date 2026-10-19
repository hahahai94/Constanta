"""Тестовый раннер с изолированным ``MEDIA_ROOT``.

Раньше тесты, загружающие файлы, писали в реальный ``media/`` проекта
(problems.md, П-14). Раннер выбирает каталог, запись в который действительно
проверена, и очищает его после прогона.

``tempfile.mkdtemp()`` нельзя вызывать вслепую: если кандидат недоступен,
Python 3.14 перебирает тысячи имён и фактически зависает. Поэтому сначала
выполняется дешёвая проверка записью файла, и только потом создаётся каталог.
Если снаружи проекта нет ни одного доступного места, используется служебный
каталог ``.test-media`` внутри репозитория: он уже существует и исключён из
git, а реальный ``media/`` остаётся нетронутым.
"""

import os
import shutil
import uuid
from pathlib import Path

from django.conf import settings
from django.test.runner import DiscoverRunner
from django.test.utils import override_settings

FALLBACK_DIR_NAME = '.test-media'
KEEP_FILES = {'.gitkeep'}


def _is_inside(path, project):
    return path == project or project in path.parents


def _can_write(path):
    """Проверяет запись настоящим файлом, не создавая подкаталогов."""
    probe = Path(path) / f'.constanta-probe-{os.getpid()}-{uuid.uuid4().hex}'
    try:
        probe.write_text('ok', encoding='utf-8')
        probe.unlink()
        return True
    except OSError:
        try:
            probe.unlink()
        except OSError:
            pass
        return False


def _external_candidates(project):
    seen = set()
    candidates = [
        os.environ.get('CONSTANTA_TEST_MEDIA_BASE'),
        os.environ.get('LOCALAPPDATA'),
        os.environ.get('TEMP'),
        os.environ.get('TMP'),
        str(Path.home()),
    ]
    if os.name != 'nt':
        candidates.append('/tmp')

    for candidate in candidates:
        if not candidate:
            continue
        path = Path(candidate).resolve()
        if path in seen or _is_inside(path, project):
            continue
        seen.add(path)
        yield path


def _pick_media_root():
    """Возвращает ``(путь, временный_ли_каталог)``."""
    project = Path(settings.BASE_DIR).resolve()

    for base in _external_candidates(project):
        if not _can_write(base):
            continue
        temp_root = base / f'constanta-test-media-{os.getpid()}-{uuid.uuid4().hex}'
        try:
            temp_root.mkdir()
        except OSError:
            continue
        if _can_write(temp_root):
            return str(temp_root), True
        shutil.rmtree(temp_root, ignore_errors=True)

    fallback = project / FALLBACK_DIR_NAME
    try:
        fallback.mkdir(exist_ok=True)
    except OSError as exc:
        raise RuntimeError(
            'Не найдено каталога для временного MEDIA_ROOT. '
            'Задайте CONSTANTA_TEST_MEDIA_BASE на доступный для записи путь.'
        ) from exc

    if not _can_write(fallback):
        raise RuntimeError(
            f'Нет доступа на запись в {fallback}. '
            'Задайте CONSTANTA_TEST_MEDIA_BASE на доступный для записи путь.'
        )
    return str(fallback), False


def _clear_dir(path):
    for child in Path(path).iterdir():
        if child.name in KEEP_FILES:
            continue
        try:
            if child.is_dir() and not child.is_symlink():
                shutil.rmtree(child)
            else:
                child.unlink()
        except OSError:
            pass


class IsolatedMediaRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_root, self._temporary_media = _pick_media_root()

        if not self._temporary_media:
            _clear_dir(self._media_root)

        project = Path(settings.BASE_DIR).resolve()
        created = Path(self._media_root).resolve()
        if created == project or project in created.parents:
            if self._temporary_media:
                shutil.rmtree(self._media_root, ignore_errors=True)
                raise RuntimeError(
                    f'Временный MEDIA_ROOT оказался внутри проекта: {created}')
            if created.name != FALLBACK_DIR_NAME:
                raise RuntimeError(
                    f'MEDIA_ROOT оказался внутри проекта: {created}')

        self._media_override = override_settings(MEDIA_ROOT=self._media_root)
        self._media_override.enable()

    def teardown_test_environment(self, **kwargs):
        try:
            self._media_override.disable()
            if self._temporary_media:
                shutil.rmtree(self._media_root, ignore_errors=True)
            else:
                _clear_dir(self._media_root)
        finally:
            super().teardown_test_environment(**kwargs)
