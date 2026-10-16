"""Тестовый раннер с изолированным ``MEDIA_ROOT``.

Раньше тесты, загружающие файлы, писали в реальный ``media/`` проекта: в
каталоге накопилось почти 800 файлов, а `generate_file_hash` подмешивает
время, поэтому имена каждый раз новые (problems.md, П-14). Здесь медиакаталог
на время прогона переносится во временную папку и удаляется после.
"""

import shutil
import tempfile

from django.test.runner import DiscoverRunner
from django.test.utils import override_settings


class IsolatedMediaRunner(DiscoverRunner):
    def setup_test_environment(self, **kwargs):
        super().setup_test_environment(**kwargs)
        self._media_root = tempfile.mkdtemp(prefix='constanta-test-media-')
        self._media_override = override_settings(MEDIA_ROOT=self._media_root)
        self._media_override.enable()

    def teardown_test_environment(self, **kwargs):
        try:
            self._media_override.disable()
            shutil.rmtree(self._media_root, ignore_errors=True)
        finally:
            super().teardown_test_environment(**kwargs)
