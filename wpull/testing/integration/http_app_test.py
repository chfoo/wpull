import hashlib
import io
import logging
import os
import tempfile
import socket
import sys

import asyncio

from wpull.application.app import Application
from wpull.application.builder import Builder
from wpull.application.options import AppArgumentParser
from wpull.errors import ExitStatus
from wpull.network.dns import Resolver, ResolveResult, AddressInfo
from wpull.testing.integration.base import HTTPGoodAppTestCase, \
    tornado_future_adapter, HTTPBadAppTestCase
import wpull.testing.async
from wpull.url import URLInfo

_logger = logging.getLogger(__name__)


class MockDNSResolver(Resolver):
    def __init__(self, *args, **kwargs):
        Resolver.__init__(self, *args, **kwargs)
        self.hosts_touched = set()

    @asyncio.coroutine
    def resolve(self, host):
        self.hosts_touched.add(host)
        return ResolveResult([
            AddressInfo('127.0.0.1', socket.AF_INET, None, None)
        ])


class TestHTTPGoodApp(HTTPGoodAppTestCase):
    @wpull.testing.async.async_test()
    def test_one_page(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([self.get_url('/')])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()
        self.assertTrue(os.path.exists('index.html'))

        response = yield from tornado_future_adapter(self.http_client.fetch(self.get_url('/')))

        with open('index.html', 'rb') as in_file:
            self.assertEqual(response.body, in_file.read())

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

        cookies = list(builder.factory['CookieJar'])
        _logger.debug('{0}'.format(cookies))
        self.assertEqual(1, len(cookies))
        self.assertEqual('hi', cookies[0].name)
        self.assertEqual('hello', cookies[0].value)

    @wpull.testing.async.async_test()
    def test_big_payload(self):
        hash_obj = hashlib.sha1(b'foxfoxfox')
        payload_list = []

        for dummy in range(10000):
            data = hash_obj.digest()
            hash_obj.update(data)
            payload_list.append(data)

        data = hash_obj.digest()
        payload_list.append(data)
        expected_payload = b''.join(payload_list)

        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([self.get_url('/big_payload')])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()
        self.assertTrue(os.path.exists('big_payload'))

        with open('big_payload', 'rb') as in_file:
            self.assertEqual(expected_payload, in_file.read())

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_many_page_with_some_fail(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/blog_half500/'),
            '--no-parent',
            '--recursive',
            '--page-requisites',
            '-4',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(ExitStatus.server_error, exit_code)
        self.assertGreater(builder.factory['Statistics'].files, 1)
        self.assertGreater(builder.factory['Statistics'].duration, 3)

    @wpull.testing.async.async_test()
    def test_app_args(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            '/',
            '--base', self.get_url('/').encode('utf-8'),
            '--no-parent',
            '--recursive',
            '--page-requisites',
            '--database', b'test?.db',
            '--server-response',
            '--random-wait',
            b'--wait', b'0.1',
            '--protocol-directories',
            '--referer', 'http://test.test',
            '--accept-regex', r'.*',
            '--header', 'Hello: world!',
            '--exclude-domains', 'asdf.invalid',
            '--exclude-hostnames', 'qwerty.invalid,uiop.invalid',
            '--no-clobber',
            '--rotate-dns',
            '-4',
            '--concurrent', '2',
            '--no-check-certificate',
            '--ascii-print',
            '--progress', 'dot',
            '--secure-protocol', 'TLSv1',
            '--convert-links', '--backup-converted',
            '--accept', '*',
            '--restrict-file-names', 'windows,lower',
            '--quota', '10m',
            '--max-filename-length', '100',
            '--user-agent', 'ΑΒΓαβγ',
            '--remote-encoding', 'latin1',
            '--http-compression',
            '--bind-address', '127.0.0.1',
            '--html-parser', 'html5lib',
            '--link-extractors', 'html',
            '--page-requisites-level', '5',
            '--no-strong-crypto',
            '--no-skip-getaddrinfo',
            '--limit-rate', '1m',
            '--session-timeout', '300',
            '--report-speed=bits',
        ])
        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        print(list(os.walk('.')))
        self.assertTrue(os.path.exists(
            'http/localhost+{0}/index.html'.format(self.get_http_port())
        ))
        self.assertTrue(os.path.exists(
            'http/localhost+{0}/index.html.orig'.format(
                self.get_http_port())
        ))

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 2)

    @wpull.testing.async.async_test()
    def test_app_input_file_arg(self):
        arg_parser = AppArgumentParser(real_exit=False)
        with tempfile.NamedTemporaryFile() as in_file:
            in_file.write(self.get_url('/').encode('utf-8'))
            in_file.write(b'\n')
            in_file.write(self.get_url('/blog/?ðfßðfëéå').encode('utf-8'))
            in_file.flush()

            args = arg_parser.parse_args([
                '--input-file', in_file.name
            ])
            builder = Builder(args, unit_test=True)
            app = builder.build()
            exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 2)

    @wpull.testing.async.async_test()
    def test_app_input_html_file_arg(self):
        arg_parser = AppArgumentParser(real_exit=False)
        with tempfile.NamedTemporaryFile() as in_file:
            in_file.write(b'<html><body><a href="')
            in_file.write(self.get_url('/').encode('utf-8'))
            in_file.write(b'">blah<a href="\n')
            in_file.write(self.get_url('/blog/?ðfßðfëéå').encode('utf-8'))
            in_file.write(b'">core</a>')
            in_file.flush()

            args = arg_parser.parse_args([
                '--input-file', in_file.name,
                '--force-html',
            ])
            builder = Builder(args, unit_test=True)
            app = builder.build()
            exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 2)

    @wpull.testing.async.async_test()
    def test_app_input_file_arg_stdin(self):
        arg_parser = AppArgumentParser(real_exit=False)

        real_stdin = sys.stdin
        fake_stdin = io.StringIO(self.get_url('/') + '\n')

        try:
            sys.stdin = fake_stdin
            args = arg_parser.parse_args([
                '--input-file', '-'
            ])
            builder = Builder(args, unit_test=True)
            app = builder.build()
            exit_code = yield from app.run()
        finally:
            sys.stdin = real_stdin

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 1)

    @wpull.testing.async.async_test()
    def test_app_args_post_data(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/post/'),
            '--post-data', 'text=hi',
        ])
        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)

    @wpull.testing.async.async_test()
    def test_iri_handling(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/static/mojibake.html'),
            '-r',
            '--database', 'temp-unittest.db'
        ])
        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        urls = tuple(url_record.url for url_record in
                     builder.factory['URLTable'].get_all())
        self.assertIn(
            self.get_url('/%E6%96%87%E5%AD%97%E5%8C%96%E3%81%91'),
            urls
        )

        self.assertEqual(0, exit_code)

    @wpull.testing.async.async_test()
    def test_save_cookie(self):
        arg_parser = AppArgumentParser()

        with tempfile.NamedTemporaryFile() as in_file:
            in_file.write(b'# Kittens\n')
            in_file.write(b'localhost.local')
            in_file.write(b'\tFALSE\t/\tFALSE\t9999999999\tisloggedin\t1\n')
            in_file.write(b'\tFALSE\t/\tFALSE\t\tadmin\t1\n')
            in_file.flush()

            args = arg_parser.parse_args([
                self.get_url('/some_page/'),
                '--load-cookies', in_file.name,
                '--tries', '1',
                '--save-cookies', 'wpull_test_cookies.txt',
            ])
            builder = Builder(args, unit_test=True)

            app = builder.build()
            exit_code = yield from app.run()

            self.assertEqual(0, exit_code)
            self.assertEqual(1, builder.factory['Statistics'].files)

            with open('wpull_test_cookies.txt', 'rb') as saved_file:
                cookie_data = saved_file.read()

            self.assertIn(b'isloggedin\t1', cookie_data)
            self.assertNotIn(b'admin\t1', cookie_data)

    @wpull.testing.async.async_test()
    def test_session_cookie(self):
        arg_parser = AppArgumentParser()

        with tempfile.NamedTemporaryFile() as in_file:
            in_file.write(b'# Kittens\n')
            in_file.write(b'localhost.local')
            # session cookie, Python style
            in_file.write(b'\tFALSE\t/\tFALSE\t\ttest\tno\n')
            # session cookie, Firefox/Wget/Curl style
            in_file.write(b'\tFALSE\t/\tFALSE\t0\tsessionid\tboxcat\n')
            in_file.flush()

            args = arg_parser.parse_args([
                self.get_url('/cookie'),
                '--load-cookies', in_file.name,
                '--tries', '1',
                '--save-cookies', 'wpull_test_cookies.txt',
                '--keep-session-cookies',
            ])
            builder = Builder(args, unit_test=True)

            app = builder.build()

            callback_called = False

            def callback(pipeline):
                nonlocal callback_called

                if callback_called:
                    return

                callback_called = True
                self.assertEqual(2, len(builder.factory['CookieJar']))

            app.event_dispatcher.add_listener(Application.Event.pipeline_end, callback)

            exit_code = yield from app.run()

            self.assertTrue(callback_called)

            self.assertEqual(0, exit_code)
            self.assertEqual(1, builder.factory['Statistics'].files)

            cookies = list(sorted(builder.factory['CookieJar'],
                                  key=lambda cookie: cookie.name))
            _logger.debug('{0}'.format(cookies))
            self.assertEqual(2, len(cookies))
            self.assertEqual('sessionid', cookies[0].name)
            self.assertEqual('boxcat', cookies[0].value)
            self.assertEqual('test', cookies[1].name)
            self.assertEqual('yes', cookies[1].value)

            with open('wpull_test_cookies.txt', 'rb') as saved_file:
                cookie_data = saved_file.read()

            self.assertIn(b'test\tyes', cookie_data)

    @wpull.testing.async.async_test()
    def test_redirect_diff_host(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/redirect?where=diff-host&port={0}'.format(
                self.get_http_port())),
            '--waitretry', '0'
        ])
        builder = Builder(args, unit_test=True)
        builder.factory.class_map['Resolver'] = MockDNSResolver

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

        resolver = builder.factory['Resolver']
        self.assertIn('somewhereelse.invalid', resolver.hosts_touched)

    @wpull.testing.async.async_test()
    def test_redirect_diff_host_recursive(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/redirect?where=diff-host&port={0}'.format(
                self.get_http_port())),
            '--recursive',
            '--no-robots',
        ])
        builder = Builder(args, unit_test=True)
        builder.factory.class_map['Resolver'] = MockDNSResolver

        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

        resolver = builder.factory['Resolver']
        self.assertIn('somewhereelse.invalid', resolver.hosts_touched)

    @wpull.testing.async.async_test()
    def test_redirect_span_hosts_allow_linked(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url(
                '/span_hosts?port={0}'.format(self.get_http_port())
            ),
            '--span-hosts-allow', 'linked-pages',
            '--no-robots',
            '--recursive',
        ])
        builder = Builder(args, unit_test=True)
        builder.factory.class_map['Resolver'] = MockDNSResolver

        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)
        self.assertEqual(2, builder.factory['Statistics'].files)

        resolver = builder.factory['Resolver']
        self.assertIn('linked.test', resolver.hosts_touched)

    @wpull.testing.async.async_test()
    def test_redirect_span_hosts_page_requisites(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url(
                '/span_hosts?port={0}'.format(self.get_http_port())
            ),
            '--span-hosts-allow', 'page-requisites',
            '--no-robots',
            '--page-requisites',
        ])
        builder = Builder(args, unit_test=True)
        builder.factory.class_map['Resolver'] = MockDNSResolver

        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)
        self.assertEqual(2, builder.factory['Statistics'].files)

        resolver = builder.factory['Resolver']
        self.assertIn('pagereq.test', resolver.hosts_touched)

    @wpull.testing.async.async_test()
    def test_strong_redirect(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/redirect?where=diff-host&port={0}'.format(
                self.get_http_port())),
            '--recursive',
            '--no-strong-redirects',
            '--no-robots',
        ])
        builder = Builder(args, unit_test=True)
        builder.factory.class_map['Resolver'] = MockDNSResolver

        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

        resolver = builder.factory['Resolver']
        self.assertNotIn('somewhereelse.invalid', resolver.hosts_touched)

    @wpull.testing.async.async_test()
    def test_immediate_robots_fail(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/'),
            '--recursive',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()

        def callback(pipeline):
            robots_txt_pool = builder.factory['RobotsTxtPool']
            robots_txt_pool.load_robots_txt(
                URLInfo.parse(self.get_url('/')),
                'User-Agent: *\nDisallow: *\n'
            )

        app.event_dispatcher.add_listener(Application.Event.pipeline_end, callback)

        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_immediate_robots_forbidden(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/forbidden'),
            '--recursive',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_immediate_robots_error(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            'http://127.0.0.1:1',
            self.get_url('/'),
            '--recursive',
            '--tries', '1',
            '--timeout', '10',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(4, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_quota(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/blog_half500/'),
            '--recursive',
            '--quota', '1',
        ])

        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_content_on_error(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/always_error'),
            '--content-on-error',
        ])

        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        print(list(os.walk('.')))
        self.assertTrue(os.path.exists('always_error'))

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_sitemaps(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/'),
            '--no-robots',
            '--sitemaps',
            '--recursive',
        ])

        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        print(list(os.walk('.')))
        self.assertTrue(os.path.exists(
            'localhost:{0}/static/my_file.txt'.format(
                self.get_http_port())
        ))

        self.assertEqual(0, exit_code)
        self.assertGreaterEqual(4, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_sitemaps_and_no_parent(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/dir_or_file/'),
            '--no-robots',
            '--sitemaps',
            '--recursive',
            '--no-parent',
        ])

        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        print(list(os.walk('.')))
        self.assertFalse(os.path.exists(
            'localhost:{0}/static/my_file.txt'.format(
                self.get_http_port())
        ))

        self.assertEqual(0, exit_code)
        self.assertGreaterEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_local_encoding(self):
        arg_parser = AppArgumentParser()

        with tempfile.NamedTemporaryFile() as in_file:
            in_file.write(self.get_url('/?qwerty').encode('utf-32-le'))
            in_file.write('\n'.encode('utf-32-le'))
            in_file.flush()

            opts = [
                self.get_url('/?asdf'),
                '--local-encoding', 'utf-32-le',
                '--input-file', in_file.name
            ]

            opts = [string.encode('utf-32-le') for string in opts]

            args = arg_parser.parse_args(opts)
            builder = Builder(args, unit_test=True)

            app = builder.build()
            exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(2, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_no_iri(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/'),
            '--no-iri',
            '--no-robots'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_output_document(self):
        arg_parser = AppArgumentParser()

        args = arg_parser.parse_args([
            self.get_url('/'),
            '--output-document', 'blah.dat'
        ])

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertTrue(os.path.exists('blah.dat'))
        self.assertTrue(os.path.getsize('blah.dat'))

        self.assertEqual(0, exit_code)

    @wpull.testing.async.async_test()
    def test_misc_urls(self):
        arg_parser = AppArgumentParser()

        args = arg_parser.parse_args([
            'http://[0:0:0:0:0:ffff:a00:0]/',
            '--tries', '1',
            '--timeout', '0.5',
            '-r',
        ])

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(4, exit_code)

    @wpull.testing.async.async_test()
    def test_database_path_question_mark(self):
        arg_parser = AppArgumentParser()

        args = arg_parser.parse_args([
            self.get_url('/'),
            '--database', 'test?.db'
        ])

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertTrue(os.path.exists('test_.db'))

    @wpull.testing.async.async_test()
    def test_database_uri(self):
        arg_parser = AppArgumentParser()

        args = arg_parser.parse_args([
            self.get_url('/'),
            '--database-uri', 'sqlite:///test.db'
        ])

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)

    @wpull.testing.async.async_test()
    def test_basic_auth(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/basic_auth'),
            '--user', 'root',
            '--password', 'smaug',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_basic_auth_fail(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/basic_auth'),
            '--user', 'root',
            '--password', 'toothless',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_page_requisite_level(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/infinite_iframe/'),
            '-r',
            '--page-requisites',
            '--page-requisites-level', '1',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(2, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_link_type(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/always200/'),
            '-r',
            '--page-requisites',
            '--page-requisites-level', '2',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(4, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_escaped_fragment_input_url(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/escape_from_fragments/#!husky-cat'),
            '--escaped-fragment'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

        self.assertTrue(os.path.exists('index.html?_escaped_fragment_=husky-cat'))

    @wpull.testing.async.async_test()
    def test_escaped_fragment_recursive(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/escape_from_fragments/'),
            '-r',
            '--escaped-fragment'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(2, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_strip_session_id(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/forum/'),
            '-r',
            '--strip-session-id',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_referer_option(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/referrer/'),
            '-r',
            '--referer', 'http://left.shark/'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(2, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_referer_option_negative(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/referrer/'),
            '-r',
            '--referer', 'http://superinformation.highway/',
            '--tries', '1',
            '--waitretry', '.1'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_no_cache_arg(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/no-cache'),
            '--tries=1'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(8, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/no-cache'),
            '--tries=1',
            '--no-cache',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_file_continue(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([self.get_url('/static/my_file.txt'),
                                      '--continue', '--debug'])

        filename = os.path.join(self.temp_dir.name, 'my_file.txt')

        with open(filename, 'wb') as out_file:
            out_file.write(b'START')

        app = Builder(args, unit_test=True).build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)

        with open(filename, 'rb') as in_file:
            data = in_file.read()

            self.assertEqual('54388a281352fdb2cfa66009ac0e35dd8916af7c',
                             hashlib.sha1(data).hexdigest())

    @wpull.testing.async.async_test()
    def test_timestamping_hit(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/lastmod'),
            '--timestamping'
        ])

        filename = os.path.join(self.temp_dir.name, 'lastmod')

        with open(filename, 'wb') as out_file:
            out_file.write(b'HI')

        os.utime(filename, (631152000, 631152000))

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)

        with open(filename, 'rb') as in_file:
            self.assertEqual(b'HI', in_file.read())

    @wpull.testing.async.async_test()
    def test_timestamping_miss(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/lastmod'),
            '--timestamping'
        ])

        filename = os.path.join(self.temp_dir.name, 'lastmod')

        with open(filename, 'wb') as out_file:
            out_file.write(b'HI')

        os.utime(filename, (636249600, 636249600))

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)

        with open(filename, 'rb') as in_file:
            self.assertEqual(b'HELLO', in_file.read())

    @wpull.testing.async.async_test()
    def test_timestamping_hit_orig(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/lastmod'),
            '--timestamping'
        ])

        filename = os.path.join(self.temp_dir.name, 'lastmod')
        filename_orig = os.path.join(self.temp_dir.name, 'lastmod')

        with open(filename, 'wb') as out_file:
            out_file.write(b'HI')

        with open(filename_orig, 'wb') as out_file:
            out_file.write(b'HI')

        os.utime(filename_orig, (631152000, 631152000))

        builder = Builder(args, unit_test=True)
        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)

        with open(filename, 'rb') as in_file:
            self.assertEqual(b'HI', in_file.read())

        with open(filename_orig, 'rb') as in_file:
            self.assertEqual(b'HI', in_file.read())


class TestHTTPBadApp(HTTPBadAppTestCase):
    @wpull.testing.async.async_test()
    def test_bad_cookie(self):
        import http.cookiejar
        http.cookiejar.debug = True
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/bad_cookie'),
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

        cookies = list(builder.factory['CookieJar'])
        _logger.debug('{0}'.format(cookies))
        self.assertEqual(4, len(cookies))

    @wpull.testing.async.async_test()
    def test_long_cookie(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/long_cookie'),
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()
        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

        cookies = list(builder.factory['CookieJar'])
        _logger.debug('{0}'.format(cookies))
        self.assertEqual(0, len(cookies))

    @wpull.testing.async.async_test()
    def test_non_http_redirect(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/non_http_redirect'),
            '--recursive',
            '--no-robots'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_bad_redirect(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/bad_redirect'),
            '--recursive',
            '--no-robots',
            '--waitretry', '0.1',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(7, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_ignore_length(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/underrun'),
            '--ignore-length',
            '--no-robots',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    # XXX: slow on pypy
    @wpull.testing.async.async_test(timeout=120)
    def test_bad_utf8(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/utf8_then_binary/doc.html'),
            self.get_url('/utf8_then_binary/doc.xml'),
            self.get_url('/utf8_then_binary/doc.css'),
            self.get_url('/utf8_then_binary/doc.js'),
            '--no-robots',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(4, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_no_content(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/no_content'),
            '--tries=1',
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(1, builder.factory['Statistics'].files)

    @wpull.testing.async.async_test()
    def test_session_timeout(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/sleep_long'),
            '--tries=1',
            '--session-timeout=0.1'
        ])
        builder = Builder(args, unit_test=True)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(4, exit_code)
        self.assertEqual(0, builder.factory['Statistics'].files)
