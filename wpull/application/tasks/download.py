import asyncio
import gettext
import logging
import functools

import tornado.netutil

from wpull.backport.logging import BraceMessage as __
from wpull.cookie import BetterMozillaCookieJar
from wpull.namevalue import NameValueRecord
from wpull.pipeline.pipeline import ItemTask
from wpull.pipeline.session import ItemSession
from wpull.pipeline.app import AppSession
import wpull.resmon
import wpull.string

from wpull.protocol.http.stream import Stream as HTTPStream
import wpull.util
import wpull.processor.coprocessor.youtubedl
import wpull.application.hook

_logger = logging.getLogger(__name__)
_ = gettext.gettext


class ParserSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        self._build_html_parser(session)
        self._build_demux_document_scraper(session)

    @classmethod
    def _build_html_parser(cls, session: AppSession):
        if session.args.html_parser == 'html5lib':
            from wpull.document.htmlparse.html5lib_ import HTMLParser
        else:
            from wpull.document.htmlparse.lxml_ import HTMLParser

        session.factory.class_map['HTMLParser'] = HTMLParser
        session.factory.new('HTMLParser')

    @classmethod
    def _build_demux_document_scraper(cls, session: AppSession):
        '''Create demux document scraper.'''
        session.factory.new(
            'DemuxDocumentScraper', cls._build_document_scrapers(session))

    @classmethod
    def _build_document_scrapers(cls, session: AppSession):
        '''Create the document scrapers.

        Returns:
            A list of document scrapers
        '''
        html_parser = session.factory['HTMLParser']
        element_walker = session.factory.new('ElementWalker')

        scrapers = [
            session.factory.new(
                'HTMLScraper',
                html_parser,
                element_walker,
                followed_tags=session.args.follow_tags,
                ignored_tags=session.args.ignore_tags,
                only_relative=session.args.relative,
                robots=session.args.robots,
                encoding_override=session.args.remote_encoding,
            ),
        ]

        if 'css' in session.args.link_extractors:
            css_scraper = session.factory.new(
                'CSSScraper',
                encoding_override=session.args.remote_encoding,
            )
            scrapers.append(css_scraper)
            element_walker.css_scraper = css_scraper

        if 'javascript' in session.args.link_extractors:
            javascript_scraper = session.factory.new(
                'JavaScriptScraper',
                encoding_override=session.args.remote_encoding,
            )
            scrapers.append(javascript_scraper)
            element_walker.javascript_scraper = javascript_scraper

        if session.args.sitemaps:
            scrapers.append(session.factory.new(
                'SitemapScraper', html_parser,
                encoding_override=session.args.remote_encoding,
            ))

        return scrapers


class ClientSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        self._build_web_client(session)
        self._build_ftp_client(session)

    @classmethod
    def _build_request_factory(cls, session: AppSession):
        '''Create the request factory.

        A request factory is any callable object that returns a
        :class:`.http.Request`. The callable must accept the same
        arguments to Request.

        Returns:
            A callable object
        '''
        def request_factory(*args, **kwargs):
            request = session.factory.class_map['Request'](*args, **kwargs)

            user_agent = session.args.user_agent or session.default_user_agent

            request.fields['User-Agent'] = user_agent

            if session.args.referer:
                request.fields['Referer'] = session.args.referer

            for header_string in session.args.header:
                request.fields.parse(header_string)

            if session.args.http_compression:
                request.fields['Accept-Encoding'] = 'gzip, deflate'

            if session.args.no_cache:
                request.fields['Cache-Control'] = 'no-cache, must-revalidate'
                request.fields['Pragma'] = 'no-cache'

            return request

        return request_factory

    @classmethod
    def _build_http_client(cls, session: AppSession):
        '''Create the HTTP client.

        Returns:
            Client: An instance of :class:`.http.Client`.
        '''
        # TODO:
        # recorder = self._build_recorder()

        stream_factory = functools.partial(
            HTTPStream,
            ignore_length=session.args.ignore_length,
            keep_alive=session.args.http_keep_alive)

        return session.factory.new(
            'HTTPClient',
            connection_pool=session.factory['ConnectionPool'],
            stream_factory=stream_factory
         )

    @classmethod
    def _build_web_client(cls, session: AppSession):
        '''Build Web Client.'''
        cookie_jar = cls._build_cookie_jar(session)
        http_client = cls._build_http_client(session)

        redirect_factory = functools.partial(
            session.factory.class_map['RedirectTracker'],
            max_redirects=session.args.max_redirect
        )

        return session.factory.new(
            'WebClient',
            http_client,
            redirect_tracker_factory=redirect_factory,
            cookie_jar=cookie_jar,
            request_factory=cls._build_request_factory(session),
        )

    @classmethod
    def _build_cookie_jar(cls, session: AppSession):
        '''Build the cookie jar'''

        if not session.args.cookies:
            return

        if session.args.load_cookies or session.args.save_cookies:
            session.factory.set('CookieJar', BetterMozillaCookieJar)

            cookie_jar = session.factory.new('CookieJar')

            if session.args.load_cookies:
                cookie_jar.load(session.args.load_cookies, ignore_discard=True)
        else:
            cookie_jar = session.factory.new('CookieJar')

        policy = session.factory.new('CookiePolicy', cookie_jar=cookie_jar)

        cookie_jar.set_policy(policy)

        _logger.debug(__('Loaded cookies: {0}', list(cookie_jar)))

        cookie_jar_wrapper = session.factory.new(
            'CookieJarWrapper',
            cookie_jar,
            save_filename=session.args.save_cookies,
            keep_session_cookies=session.args.keep_session_cookies,
        )

        return cookie_jar_wrapper

    @classmethod
    def _build_ftp_client(cls, session: AppSession):
        '''Build FTP client.'''
        return session.factory.new(
            'FTPClient',
            connection_pool=session.factory['ConnectionPool'],
            # TODO: recorder
            # recorder=session.factory['DemuxRecorder'],
        )


class ProxyServerSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        '''Build MITM proxy server.'''
        args = session.args
        if not (args.youtube_dl or args.proxy_server):
            return

        proxy_server = session.factory.new(
            'HTTPProxyServer',
            session.factory['HTTPClient'],
        )

        cookie_jar = session.factory.get('CookieJarWrapper')
        proxy_coprocessor = session.factory.new(
            'ProxyCoprocessor',
            session
        )

        proxy_socket = tornado.netutil.bind_sockets(
            session.args.proxy_server_port,
            address=session.args.proxy_server_address
        )[0]
        proxy_port = proxy_socket.getsockname()[1]

        proxy_async_server = yield from asyncio.start_server(proxy_server, sock=proxy_socket)

        session.async_servers.append(proxy_async_server)
        session.proxy_server_port = proxy_port


class ProcessorSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        self._build_processor(session)

    @classmethod
    def _build_processor(cls, session: AppSession):
        '''Create the Processor

        Returns:
            Processor: An instance of :class:`.processor.BaseProcessor`.
        '''
        web_processor = cls._build_web_processor(session)
        ftp_processor = cls._build_ftp_processor(session)
        delegate_processor = session.factory.new('Processor')

        delegate_processor.register('http', web_processor)
        delegate_processor.register('https', web_processor)
        delegate_processor.register('ftp', ftp_processor)

    @classmethod
    def _build_web_processor(cls, session: AppSession):
        '''Build WebProcessor.'''
        args = session.args
        url_filter = session.factory['DemuxURLFilter']
        document_scraper = session.factory['DemuxDocumentScraper']
        file_writer = session.factory['FileWriter']
        post_data = cls._get_post_data(session.args)
        web_client = session.factory['WebClient']

        robots_txt_checker = cls._build_robots_txt_checker(session)

        http_username = args.user or args.http_user
        http_password = args.password or args.http_password
        ftp_username = args.user or args.ftp_user
        ftp_password = args.password or args.ftp_password

        fetch_rule = session.factory.new(
            'FetchRule',
            url_filter=url_filter, robots_txt_checker=robots_txt_checker,
            http_login=(http_username, http_password),
            ftp_login=(ftp_username, ftp_password),
            duration_timeout=args.session_timeout,
        )

        waiter = session.factory.new(
            'Waiter',
            wait=args.wait,
            random_wait=args.random_wait,
            max_wait=args.waitretry)

        result_rule = session.factory.new(
            'ResultRule',
            ssl_verification=args.check_certificate,
            retry_connrefused=args.retry_connrefused,
            retry_dns_error=args.retry_dns_error,
            waiter=waiter,
            statistics=session.factory['Statistics'],
        )

        processing_rule = session.factory.new(
            'ProcessingRule',
            fetch_rule,
            document_scraper=document_scraper,
            sitemaps=session.args.sitemaps,
            url_rewriter=session.factory.get('URLRewriter'),
        )

        web_processor_fetch_params = session.factory.new(
            'WebProcessorFetchParams',
            post_data=post_data,
            strong_redirects=args.strong_redirects,
            content_on_error=args.content_on_error,
        )

        processor = session.factory.new(
            'WebProcessor',
            web_client,
            web_processor_fetch_params,
        )

        return processor

    @classmethod
    def _build_ftp_processor(cls, session: AppSession):
        '''Build FTPProcessor.'''
        ftp_client = session.factory['FTPClient']

        fetch_params = session.factory.new(
            'FTPProcessorFetchParams',
            remove_listing=session.args.remove_listing,
            retr_symlinks=session.args.retr_symlinks,
            preserve_permissions=session.args.preserve_permissions,
            glob=session.args.glob,
        )

        return session.factory.new(
            'FTPProcessor',
            ftp_client,
            fetch_params,
        )

    @classmethod
    def _get_post_data(cls, args):
        '''Return the post data.'''
        if args.post_data:
            return args.post_data
        elif args.post_file:
            return args.post_file.read()

    @classmethod
    def _build_robots_txt_checker(cls, session: AppSession):
        '''Build robots.txt checker.'''
        if session.args.robots:
            robots_txt_pool = session.factory.new('RobotsTxtPool')
            robots_txt_checker = session.factory.new(
                'RobotsTxtChecker',
                web_client=session.factory['WebClient'],
                robots_txt_pool=robots_txt_pool
            )

            return robots_txt_checker

    @classmethod
    def _build_recorder(cls, session: AppSession):
        '''Create the Recorder.

        Returns:
            DemuxRecorder: An instance of :class:`.recorder.DemuxRecorder`.
        '''

        return session.factory.new('DemuxRecorder', recorders)


class CoprocessorSetupTask(ItemTask[ItemSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        args = session.args
        if args.youtube_dl or args.proxy_server:
            proxy_port = session.proxy_server_port
            assert proxy_port

        if args.youtube_dl:
            youtube_dl_coprocessor = self._build_youtube_dl_coprocessor(session, proxy_port)
        else:
            youtube_dl_coprocessor = None

    @classmethod
    def _build_youtube_dl_coprocessor(cls, session: AppSession, proxy_port: int):
        '''Build youtube-dl coprocessor.'''

        # Test early for executable
        wpull.processor.coprocessor.youtubedl.get_version(session.args.youtube_dl_exe)

        coprocessor = session.factory.new(
            'YoutubeDlCoprocessor',
            session.args.youtube_dl_exe,
            (session.args.proxy_server_address, proxy_port),
            root_path=session.args.directory_prefix,
            user_agent=session.args.user_agent or session.default_user_agent,
            warc_recorder=session.factory.get('WARCRecorder'),
            inet_family=session.args.inet_family,
            # Proxy will always present a invalid MITM cert
            #check_certificate=session.args.check_certificate
            check_certificate=False
        )

        return coprocessor


class ProcessTask(ItemTask[ItemSession]):
    @asyncio.coroutine
    def process(self, session: ItemSession):
        yield from session.app_session.factory['Processor'].process(session)

        assert session.is_processed

        session.finish()


class BackgroundAsyncTask(ItemTask[ItemSession]):
    @asyncio.coroutine
    def process(self, session: ItemSession):
        for task in session.app_session.background_async_tasks:
            if task.done():
                yield from task


class CheckQuotaTask(ItemTask[ItemSession]):
    @asyncio.coroutine
    def process(self, session: ItemSession):
        statistics = session.app_session.factory['Statistics']

        if statistics.is_quota_exceeded:
            session.app_session.factory['Application'].stop()
