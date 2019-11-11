# encoding=utf8
'''Web processing.'''
import gettext
import io
import logging

import namedlist
import asyncio

from typing import cast, Tuple

from wpull.backport.logging import StyleAdapter
from wpull.body import Body
from wpull.errors import ProtocolError
from wpull.application.hook import HookableMixin, Actions
from wpull.pipeline.item import URLRecord
from wpull.pipeline.session import ItemSession
from wpull.processor.coprocessor.youtubedl import YoutubeDlCoprocessor
from wpull.protocol.http.request import Request, Response
from wpull.protocol.http.web import LoopType, WebClient
from wpull.processor.base import BaseProcessor, BaseProcessorSession, \
    REMOTE_ERRORS
from wpull.processor.rule import FetchRule, ResultRule, ProcessingRule
from wpull.url import URLInfo
from wpull.writer import BaseFileWriter
import wpull.string
import wpull.util


_logger = StyleAdapter(logging.getLogger(__name__))
_ = gettext.gettext

WebProcessorFetchParams = namedlist.namedtuple(
    'WebProcessorFetchParamsType',
    [
        ('post_data', None),
        ('strong_redirects', True),
        ('content_on_error', False),
    ]
)
'''WebProcessorFetchParams

Args:
    post_data (str): If provided, all requests will be POSTed with the
        given `post_data`. `post_data` must be in percent-encoded
        query format ("application/x-www-form-urlencoded").
    strong_redirects (bool): If True, redirects are allowed to span hosts.
'''


class HookPreResponseBreak(ProtocolError):
    '''Hook pre-response break.'''


class WebProcessor(BaseProcessor, HookableMixin):
    '''HTTP processor.

    Args:
        web_client: The web client.
        fetch_params: Fetch parameters

    .. seealso:: :class:`WebProcessorSession`
    '''
    DOCUMENT_STATUS_CODES = (200, 204, 206, 304,)
    '''Default status codes considered successfully fetching a document.'''

    NO_DOCUMENT_STATUS_CODES = (401, 403, 404, 405, 410,)
    '''Default status codes considered a permanent error.'''

    def __init__(self, web_client: WebClient, fetch_params: WebProcessorFetchParams):
        super().__init__()

        self._web_client = web_client
        self._fetch_params = fetch_params
        self._session_class = WebProcessorSession

    @property
    def web_client(self) -> WebClient:
        '''The web client.'''
        return self._web_client

    @property
    def fetch_params(self) -> WebProcessorFetchParams:
        '''The fetch parameters.'''
        return self._fetch_params

    @asyncio.coroutine
    def process(self, item_session: ItemSession):
        session = self._session_class(self, item_session)
        try:
            return (yield from session.process())
        finally:
            session.close()

    def close(self):
        '''Close the web client.'''
        self._web_client.close()


class WebProcessorSession(BaseProcessorSession):
    '''Fetches an HTTP document.

    This Processor Session will handle document redirects within the same
    Session. HTTP errors such as 404 are considered permanent errors.
    HTTP errors like 500 are considered transient errors and are handled in
    subsequence sessions by marking the item as "error".

    If a successful document has been downloaded, it will be scraped for
    URLs to be added to the URL table. This Processor Session is very simple;
    it cannot handle JavaScript or Flash plugins.
    '''
    def __init__(self, processor: WebProcessor, item_session: ItemSession):
        super().__init__()
        self._processor = processor
        self._item_session = item_session

        file_writer = cast(BaseFileWriter, item_session.app_session.factory['FileWriter'])
        self._file_writer_session = file_writer.session()
        self._web_client_session = None

        self._document_codes = WebProcessor.DOCUMENT_STATUS_CODES
        self._no_document_codes = WebProcessor.NO_DOCUMENT_STATUS_CODES

        self._temp_files = set()

        self._fetch_rule = cast(FetchRule, item_session.app_session.factory['FetchRule'])
        self._result_rule = cast(ResultRule, item_session.app_session.factory['ResultRule'])
        self._processing_rule = cast(ProcessingRule, item_session.app_session.factory['ProcessingRule'])
        self._strong_redirects = self._processor.fetch_params.strong_redirects

    def _new_initial_request(self, with_body: bool=True):
        '''Return a new Request to be passed to the Web Client.'''
        url_record = self._item_session.url_record
        url_info = url_record.url_info

        request = self._item_session.app_session.factory['WebClient'].request_factory(url_info.url)

        self._populate_common_request(request)

        if with_body:
            if url_record.post_data or self._processor.fetch_params.post_data:
                self._add_post_data(request)

            if self._file_writer_session:
                request = self._file_writer_session.process_request(request)

        return request

    def _populate_common_request(self, request):
        '''Populate the Request with common fields.'''
        url_record = self._item_session.url_record

        # Note that referrer may have already been set by the --referer option
        if url_record.parent_url and not request.fields.get('Referer'):
            self._add_referrer(request, url_record)

        if self._fetch_rule.http_login:
            request.username, request.password = self._fetch_rule.http_login

    @classmethod
    def _add_referrer(cls, request: Request, url_record: URLRecord):
        '''Add referrer URL to request.'''
        # Prohibit leak of referrer from HTTPS to HTTP
        # rfc7231 section 5.5.2.
        if url_record.parent_url.startswith('https://') and \
                url_record.url_info.scheme == 'http':
            return

        request.fields['Referer'] = url_record.parent_url

    @asyncio.coroutine
    def process(self):
        ok = yield from self._process_robots()

        if not ok:
            return

        self._processing_rule.add_extra_urls(self._item_session)

        self._web_client_session = self._processor.web_client.session(
            self._new_initial_request()
        )

        with self._web_client_session:
            yield from self._process_loop()

        if not self._item_session.is_processed:
            _logger.debug('Was not processed. Skipping.')
            self._item_session.skip()

    @asyncio.coroutine
    def _process_robots(self):
        '''Process robots.txt.

        Coroutine.
        '''
        try:
            self._item_session.request = request = self._new_initial_request(with_body=False)
            verdict, reason = (yield from self._should_fetch_reason_with_robots(
                request))
        except REMOTE_ERRORS as error:
            _logger.error(
                _('Fetching robots.txt for ‘{url}’ '
                  'encountered an error: {error}'),
                url=self._next_url_info.url, error=error
            )
            self._result_rule.handle_error(self._item_session, error)

            wait_time = self._result_rule.get_wait_time(
                self._item_session, error=error
            )

            if wait_time:
                _logger.debug('Sleeping {0}.', wait_time)
                yield from asyncio.sleep(wait_time)

            return False
        else:
            _logger.debug('Robots filter verdict {} reason {}', verdict, reason)

            if not verdict:
                self._item_session.skip()
                return False

        return True

    @asyncio.coroutine
    def _process_loop(self):
        '''Fetch URL including redirects.

        Coroutine.
        '''
        while not self._web_client_session.done():
            self._item_session.request = self._web_client_session.next_request()

            verdict, reason = self._should_fetch_reason()

            _logger.debug('Filter verdict {} reason {}', verdict, reason)

            if not verdict:
                self._item_session.skip()
                break

            exit_early, wait_time = yield from self._fetch_one(cast(Request, self._item_session.request))

            if wait_time:
                _logger.debug('Sleeping {}', wait_time)
                yield from asyncio.sleep(wait_time)

            if exit_early:
                break

    @asyncio.coroutine
    def _fetch_one(self, request: Request) -> Tuple[bool, float]:
        '''Process one of the loop iteration.

        Coroutine.

        Returns:
            If True, stop processing any future requests.
        '''
        _logger.info(_('Fetching ‘{url}’.'), url=request.url)

        response = None

        try:
            response = yield from self._web_client_session.start()
            self._item_session.response = response

            action = self._result_rule.handle_pre_response(self._item_session)

            if action in (Actions.RETRY, Actions.FINISH):
                raise HookPreResponseBreak()

            self._file_writer_session.process_response(response)

            if not response.body:
                response.body = Body(
                    directory=self._item_session.app_session.root_path,
                    hint='resp_cb'
                )

            yield from \
                self._web_client_session.download(
                    file=response.body,
                    duration_timeout=self._fetch_rule.duration_timeout
                )
        except HookPreResponseBreak:
            _logger.debug('Hook pre-response break.')
            return True, None
        except REMOTE_ERRORS as error:
            self._log_error(request, error)

            self._result_rule.handle_error(self._item_session, error)
            wait_time = self._result_rule.get_wait_time(
                self._item_session, error=error
            )

            if request.body:
                request.body.close()

            if response:
                response.body.close()

            return True, wait_time
        else:
            self._log_response(request, response)
            action = self._handle_response(request, response)
            wait_time = self._result_rule.get_wait_time(self._item_session)

            yield from self._run_coprocessors(request, response)

            response.body.close()

            if request.body:
                request.body.close()

            return action != Actions.NORMAL, wait_time

    def close(self):
        '''Close any temp files.'''
        for file in self._temp_files:
            file.close()

    @property
    def _next_url_info(self) -> URLInfo:
        '''Return the next URLInfo to be processed.

        This returns either the original URLInfo or the next URLinfo
        containing the redirect link.
        '''
        if not self._web_client_session:
            return self._item_session.url_record.url_info

        return self._web_client_session.next_request().url_info

    def _should_fetch_reason(self) -> Tuple[bool, str]:
        '''Return info about whether the URL should be fetched.

        Returns:
            tuple: A two item tuple:

            1. bool: If True, the URL should be fetched.
            2. str: A short reason string explaining the verdict.
        '''
        is_redirect = False

        if self._strong_redirects:
            try:
                is_redirect = self._web_client_session.redirect_tracker\
                    .is_redirect()
            except AttributeError:
                pass

        return self._fetch_rule.check_subsequent_web_request(
            self._item_session, is_redirect=is_redirect)

    @asyncio.coroutine
    def _should_fetch_reason_with_robots(self, request: Request) -> Tuple[bool, str]:
        '''Return info whether the URL should be fetched including checking
        robots.txt.

        Coroutine.
        '''
        result = yield from \
            self._fetch_rule.check_initial_web_request(self._item_session, request)
        return result

    def _add_post_data(self, request: Request):
        '''Add data to the payload.'''
        if self._item_session.url_record.post_data:
            data = wpull.string.to_bytes(self._item_session.url_record.post_data)
        else:
            data = wpull.string.to_bytes(
                self._processor.fetch_params.post_data
            )

        request.method = 'POST'
        request.fields['Content-Type'] = 'application/x-www-form-urlencoded'
        request.fields['Content-Length'] = str(len(data))

        _logger.debug('Posting with data {0}.', data)

        if not request.body:
            request.body = Body(io.BytesIO())

        with wpull.util.reset_file_offset(request.body):
            request.body.write(data)

    def _log_response(self, request: Request, response: Response):
        '''Log response.'''
        _logger.info(
            _('Fetched ‘{url}’: {status_code} {reason}. '
                'Length: {content_length} [{content_type}].'),
            url=request.url,
            status_code=response.status_code,
            reason=wpull.string.printable_str(response.reason),
            content_length=wpull.string.printable_str(
                response.fields.get('Content-Length', _('unspecified'))),
            content_type=wpull.string.printable_str(
                response.fields.get('Content-Type', _('unspecified'))),
        )

    def _handle_response(self, request: Request, response: Response) -> Actions:
        '''Process the response.

        Returns:
            A value from :class:`.hook.Actions`.
        '''
        self._item_session.update_record_value(status_code=response.status_code)

        if self._web_client_session.redirect_tracker.is_redirect() or \
                self._web_client_session.loop_type() == LoopType.authentication:
            self._file_writer_session.discard_document(response)

            return self._result_rule.handle_intermediate_response(
                self._item_session
            )
        elif (response.status_code in self._document_codes
              or self._processor.fetch_params.content_on_error):
            filename = self._file_writer_session.save_document(response)

            self._processing_rule.scrape_document(self._item_session)

            return self._result_rule.handle_document(
                self._item_session, filename
            )
        elif response.status_code in self._no_document_codes:
            self._file_writer_session.discard_document(response)

            return self._result_rule.handle_no_document(
                self._item_session
            )
        else:
            self._file_writer_session.discard_document(response)

            return self._result_rule.handle_document_error(
                self._item_session
            )

    def _close_instance_body(self, instance):
        '''Close any files on instance.

        This function will attempt to call ``body.close`` on
        the instance.
        '''
        if hasattr(instance, 'body'):
            instance.body.close()

    def _run_coprocessors(self, request: Request, response: Response):
        youtube_dl_coprocessor = self._item_session.app_session.factory.get('YoutubeDlCoprocessor')

        if youtube_dl_coprocessor:
            youtube_dl_coprocessor = cast(YoutubeDlCoprocessor, youtube_dl_coprocessor)

            yield from youtube_dl_coprocessor.process(
                self._item_session, request, response, self._file_writer_session
            )
