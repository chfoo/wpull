import logging
from http import cookiejar

import asyncio
import tornado.web
import tornado.ioloop

from wpull.testing.async import AsyncTestCase
from wpull.testing.badapp import BadAppTestCase
from wpull.testing.ftp import FTPTestCase
from wpull.testing.goodapp import GoodAppTestCase
from wpull.testing.util import TempDirMixin, AsyncHTTPSTestCase


class AppTestCase(AsyncTestCase, TempDirMixin):
    def setUp(self):
        self._original_cookiejar_debug = cookiejar.debug
        cookiejar.debug = True
        super().setUp()
        self.original_loggers = list(logging.getLogger().handlers)
        self.set_up_temp_dir()

    def tearDown(self):
        super().tearDown()
        cookiejar.debug = self._original_cookiejar_debug

        for handler in list(logging.getLogger().handlers):
            if handler not in self.original_loggers:
                logging.getLogger().removeHandler(handler)

        self.tear_down_temp_dir()


class HTTPGoodAppTestCase(GoodAppTestCase, TempDirMixin):
    def setUp(self):
        self._original_cookiejar_debug = cookiejar.debug
        cookiejar.debug = True
        super().setUp()
        self.original_loggers = list(logging.getLogger().handlers)
        self.set_up_temp_dir()

    def tearDown(self):
        GoodAppTestCase.tearDown(self)
        cookiejar.debug = self._original_cookiejar_debug

        for handler in list(logging.getLogger().handlers):
            if handler not in self.original_loggers:
                logging.getLogger().removeHandler(handler)

        self.tear_down_temp_dir()


class SimpleHandler(tornado.web.RequestHandler):
    def get(self):
        self.write(b'OK')


class HTTPSSimpleAppTestCase(AsyncTestCase, AsyncHTTPSTestCase, TempDirMixin):
    def get_new_ioloop(self):
        tornado.ioloop.IOLoop.configure(
            'wpull.testing.async.TornadoAsyncIOLoop',
            event_loop=self.event_loop)
        ioloop = tornado.ioloop.IOLoop()
        return ioloop

    def setUp(self):
        AsyncTestCase.setUp(self)
        AsyncHTTPSTestCase.setUp(self)
        self.set_up_temp_dir()

    def tearDown(self):
        AsyncHTTPSTestCase.tearDown(self)
        AsyncTestCase.tearDown(self)
        self.tear_down_temp_dir()

    def get_app(self):
        return tornado.web.Application([
            (r'/', SimpleHandler)
        ])


class HTTPBadAppTestCase(BadAppTestCase, TempDirMixin):
    def setUp(self):
        BadAppTestCase.setUp(self)
        self.set_up_temp_dir()

    def tearDown(self):
        BadAppTestCase.tearDown(self)
        self.tear_down_temp_dir()


class FTPAppTestCase(FTPTestCase, TempDirMixin):
    def setUp(self):
        super().setUp()
        self.original_loggers = list(logging.getLogger().handlers)
        self.set_up_temp_dir()

    def tearDown(self):
        FTPTestCase.tearDown(self)

        for handler in list(logging.getLogger().handlers):
            if handler not in self.original_loggers:
                logging.getLogger().removeHandler(handler)

        self.tear_down_temp_dir()


@asyncio.coroutine
def tornado_future_adapter(future):
    event = asyncio.Event()

    future.add_done_callback(lambda dummy: event.set())

    yield from event.wait()

    return future.result()
