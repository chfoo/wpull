# encoding=utf-8
'''Proxy Tools'''
import concurrent.futures
import contextlib
import datetime
import logging
import time
import tornado.tcpserver
import toro

import wpull.extended
from wpull.http.request import Request
from wpull.recorder import BaseRecorder, BaseRecorderSession


_logger = logging.getLogger(__name__)


class HTTPProxyServer(tornado.tcpserver.TCPServer):
    '''HTTP proxy server for use with man-in-the-middle recording.

    Args:
        http_client: An instance of :class:`.http.Client`.
    '''
    def __init__(self, http_client, **kwargs):
        super().__init__(**kwargs)
        self._http_client = http_client

    def handle_stream(self, stream, address):
        _logger.debug('Handling stream from {0}.'.format(address))
        # Re-wrap the socket
        if isinstance(stream, tornado.iostream.SSLIOStream):
            wpull_io_stream_class = wpull.extended.SSLIOStream
        else:
            wpull_io_stream_class = wpull.extended.IOStream

        wpull_stream = wpull_io_stream_class(stream.socket, read_timeout=900)

        handler = HTTPProxyHandler(self._http_client, wpull_stream)
        tornado.ioloop.IOLoop.current().add_future(
            handler.handle(), lambda dummy: dummy
        )


class HTTPProxyHandler(object):
    '''Handler class for HTTP Proxy Server.
    
    Args:
        http_client: An instance of :class:`.http.Client`.
        stream: An instance of class:`.extended.IOStream`.
    '''
    def __init__(self, http_client, stream):
        self._http_client = http_client
        self._io_stream = stream

    @tornado.gen.coroutine
    def handle(self):
        '''Process the request.'''
        while not self._io_stream.closed():
            try:
                yield self._handle_request()
            except Exception:
                _logger.exception('Proxy error.')
                self._io_stream.close()

    @tornado.gen.coroutine
    def _handle_request(self):
        '''Process the request.'''
        request = yield self._read_request_header()

        if 'Content-Length' in request.fields:
            yield self._read_request_body(request)

        response_data_queue = toro.Queue()
        recorder = ProxyRecorder(response_data_queue)

        _logger.debug('Fetching.')

        response_future = self._http_client.fetch(
            request, recorder=recorder,
        )

        touch_time = time.time()

        while True:
            try:
                data = yield response_data_queue.get(
                    deadline=datetime.timedelta(seconds=0.1)
                )
            except toro.Timeout:
                try:
                    if response_future.exception(timeout=0):
                        break
                except concurrent.futures.TimeoutError:
                    pass

                if time.time() - touch_time > 900:
                    break
                else:
                    continue

            if not data:
                break

            yield self._io_stream.write(data)

            touch_time = time.time()

        yield response_future

        # TODO: determine whether the upstream connection was closed
        self._io_stream.close()

    @tornado.gen.coroutine
    def _read_request_header(self):
        '''Read the request header.

        Returns:
            Request: A request.
        '''
        request_header_data = yield self._io_stream.read_until_regex(
            br'\r?\n\r?\n')
        status_line, header = request_header_data.split(b'\n', 1)
        method, url, version = Request.parse_status_line(status_line)
        request = Request.new(url, method, url_encoding='latin-1')
        request.version = version

        _logger.debug('Read request {0} {1}.'.format(
            method, url)
        )

        old_host_value = request.fields.pop('Host')

        request.fields.parse(header, strict=False)

        if 'Host' not in request.fields:
            request.fields['Host'] = old_host_value

        raise tornado.gen.Return(request)

    @tornado.gen.coroutine
    def _read_request_body(self, request):
        '''Read the request body.'''
        # TODO: It's unlikely that any client implements sending
        # chunked-transfer encoding, but we probably want to support it anyway
        _logger.debug('Reading request body.')

        body_length = int(request.fields['Content-Length'])
        data_queue = self._io_stream.read_bytes_queue(body_length)

        while True:
            data = yield data_queue.get()

            if not data:
                break

            request.body.content_file.write(data)

        request.body.content_file.seek(0)


class ProxyRecorder(BaseRecorder):
    '''Proxy Recorder.

    This recorder simply relays the response from upstream server to the
    client.
    '''
    def __init__(self, data_queue):
        self._data_queue = data_queue

    @contextlib.contextmanager
    def session(self):
        yield ProxyRecorderSession(self._data_queue)


class ProxyRecorderSession(BaseRecorderSession):
    '''Proxy Recorder Session.'''
    def __init__(self, data_queue):
        self._data_queue = data_queue

    def response_data(self, data):
        '''Callback for the bytes that was received.'''
        self._data_queue.put(data)

    def response(self, response):
        self._data_queue.put(None)


if __name__ == '__main__':
    from wpull.http import Client

    logging.basicConfig(level=logging.DEBUG)

    http_client = Client()
    proxy = HTTPProxyServer(http_client)

    proxy.listen(8888)
    tornado.ioloop.IOLoop.current().start()
