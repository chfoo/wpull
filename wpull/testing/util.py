import contextlib
import logging
import os
from tempfile import TemporaryDirectory
import tornado.testing

_logger = logging.getLogger(__name__)


class TempDirMixin:
    def set_up_temp_dir(self):
        assert not getattr(self, 'original_dir', None), self.original_dir
        self.original_dir = os.getcwd()
        self.temp_dir = TemporaryDirectory()
        os.chdir(self.temp_dir.name)

        _logger.debug('Switch to %s', self.temp_dir.name)

    def tear_down_temp_dir(self):
        os.chdir(self.original_dir)
        self.temp_dir.cleanup()
        self.original_dir = None

    @contextlib.contextmanager
    def cd_tempdir(self):
        original_dir = os.getcwd()

        with TemporaryDirectory() as temp_dir:
            try:
                os.chdir(temp_dir)
                yield temp_dir
            finally:
                os.chdir(original_dir)


class GetUrlFixMixin:
    # A mixin to undo the change in tornado@84bb2e28 which replaces localhost with 127.0.0.1.
    # https://github.com/tornadoweb/tornado/commit/84bb2e285e15415bb86cbdf2326b19f0debb80fd

    def get_url(self, *args, **kwargs):
        r = super().get_url(*args, **kwargs)
        if '//127.0.0.1:' in r:
            r = r.replace('127.0.0.1', 'localhost', 1)
        return r


class AsyncHTTPTestCase(GetUrlFixMixin, tornado.testing.AsyncHTTPTestCase):
    pass


class AsyncHTTPSTestCase(GetUrlFixMixin, tornado.testing.AsyncHTTPSTestCase):
    pass
