import gzip
import os
import unittest

from wpull.application.builder import Builder
from wpull.application.options import AppArgumentParser
from wpull.errors import ExitStatus
from wpull.testing.integration.base import HTTPGoodAppTestCase
import wpull.testing.async
from wpull.testing.integration.http_app_test import MockDNSResolver


def setup_mock_web_client(builder, request_log):
    class MockWebClient(builder.factory.class_map['WebClient']):
        def session(self, request):
            request_log.append(request)
            return super().session(request)
    builder.factory.class_map['WebClient'] = MockWebClient


class TestPrioritiserHTTPGoodApp(HTTPGoodAppTestCase):
    @wpull.testing.async.async_test()
    def test_app_args_priority_regex(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/static/style.css'),
            self.get_url('/static/mojibake.html'),
            self.get_url('/static/DEUUEAUGH.html'),
            self.get_url('/static/simple_javascript.html'),
            '--priority-regex', r'/DEUUEAUGH\.html', '3',
            '--priority-regex', r'/mojibake\.html', '2',
            '--priority-regex', r'/simple_javascript\.html', '1',
        ])
        builder = Builder(args, unit_test=True)

        request_log = []
        setup_mock_web_client(builder, request_log)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 4)
        self.assertEqual(
            [r.resource_path for r in request_log],
            [
                '/static/DEUUEAUGH.html',
                '/static/mojibake.html',
                '/static/simple_javascript.html',
                '/static/style.css'
            ]
        )

    @wpull.testing.async.async_test()
    def test_app_args_priority_domain(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/static/style.css').replace('localhost', 'alpha.example.invalid'),
            self.get_url('/static/mojibake.html').replace('localhost', 'beta.example.invalid'),
            self.get_url('/static/DEUUEAUGH.html').replace('localhost', 'gamma.example.invalid'),
            self.get_url('/static/simple_javascript.html').replace('localhost', 'delta.example.invalid'),
            '--priority-domain', 'gamma.example.invalid', '3',
            '--priority-domain', 'beta.example.invalid', '2',
            '--priority-domain', 'delta.example.invalid', '1',
        ])
        builder = Builder(args, unit_test=True)
        builder.factory.class_map['Resolver'] = MockDNSResolver

        request_log = []
        setup_mock_web_client(builder, request_log)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 4)
        self.assertEqual(
            [r.resource_path for r in request_log],
            [
                '/static/DEUUEAUGH.html',
                '/static/mojibake.html',
                '/static/simple_javascript.html',
                '/static/style.css'
            ]
        )

    @wpull.testing.async.async_test()
    def test_app_priority_recursive(self):
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/blog/'),
            '--no-robots',
            '--recursive', '--level', 'inf',
            '--page-requisites',
            '--priority-regex', r'/blog/\?page=6', ' -1',
            '--priority-regex', r'/blog/\?page=', '2',
        ])
        builder = Builder(args, unit_test=True)

        request_log = []
        setup_mock_web_client(builder, request_log)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 5)

        self.assertEqual(
            [r.resource_path for r in request_log],
            [
                '/blog/',
                '/blog/?page=2',
                '/blog/?page=3',
                '/blog/?page=4',
                '/blog/?page=5',
                '/stylesheet1.css',
                '/blog/?page=6'
            ]
        )

    @wpull.testing.async.async_test()
    def test_app_priority_plugin_get_urls(self):
        filename = os.path.join(os.path.dirname(__file__), 'sample_user_scripts', 'prioritisation.plugin.py')
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/blog/'),
            '--no-robots',
            '--recursive', '--level', 'inf',
            '--page-requisites',
            '--priority-regex', r'/blog/\?page=6', ' -1',
            '--priority-regex', r'/blog/\?.*&tab=', '3',
            '--priority-regex', r'/blog/\?tab=', '1',
            '--priority-regex', r'/blog/\?page=', '2',
            '--plugin-script', filename,
        ])
        builder = Builder(args, unit_test=True)

        request_log = []
        setup_mock_web_client(builder, request_log)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 11)

        self.assertEqual(
            [r.resource_path for r in request_log],
            [
                '/blog/', # prio 0
                '/blog/?page=2', # prio 2
                '/blog/?page=3', # prio 2
                '/blog/?page=3&tab=1', '/blog/?page=3&tab=2', '/blog/?page=3&tab=3', # prio 3
                '/blog/?page=4', '/blog/?page=5', # prio 2
                '/blog/?tab=1', '/blog/?tab=2', '/blog/?tab=3', # prio 1
                '/stylesheet1.css', # prio 0
                '/blog/?page=6', # prio -1
            ]
        )

    @wpull.testing.async.async_test()
    def test_app_priority_plugin_get_urls_with_priorities(self):
        # Same as test_app_priority_plugin_get_urls, but with the priorities for the URLs
        # added by the plugin set within the plugin rather than with --priority-* options
        filename = os.path.join(os.path.dirname(__file__), 'sample_user_scripts', 'prioritisation.plugin.py')
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/blog/?get_urls_with_prio=1'), # Flag for the plugin to set priorities
            '--no-robots',
            '--recursive', '--level', 'inf',
            '--page-requisites',
            '--priority-regex', r'/blog/\?page=6', ' -1',
            '--priority-regex', r'/blog/\?page=', '2',
            '--plugin-script', filename,
        ])
        builder = Builder(args, unit_test=True)

        request_log = []
        setup_mock_web_client(builder, request_log)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 11)

        self.assertEqual(
            [r.resource_path for r in request_log],
            [
                '/blog/?get_urls_with_prio=1',
                '/blog/?page=2',
                '/blog/?page=3',
                '/blog/?page=3&tab=1', '/blog/?page=3&tab=2', '/blog/?page=3&tab=3',
                '/blog/?page=4', '/blog/?page=5',
                '/blog/?tab=1', '/blog/?tab=2', '/blog/?tab=3',
                '/stylesheet1.css',
                '/blog/?page=6',
            ]
        )

    @wpull.testing.async.async_test()
    def test_app_priority_plugin_get_priority(self):
        # Same as test_app_priority_plugin_get_urls_with_priorities, but with the priorities
        # for the URLs added by the plugin in get_priority rather than in get_urls
        filename = os.path.join(os.path.dirname(__file__), 'sample_user_scripts', 'prioritisation.plugin.py')
        arg_parser = AppArgumentParser()
        args = arg_parser.parse_args([
            self.get_url('/blog/?enable_get_priority=1'), # Flag for the plugin to activate get_priority hook
            '--no-robots',
            '--recursive', '--level', 'inf',
            '--page-requisites',
            '--priority-regex', r'/blog/\?page=6', ' -1',
            '--priority-regex', r'/blog/\?page=', '2',
            '--plugin-script', filename,
        ])
        builder = Builder(args, unit_test=True)

        request_log = []
        setup_mock_web_client(builder, request_log)

        app = builder.build()
        exit_code = yield from app.run()

        self.assertEqual(0, exit_code)
        self.assertEqual(builder.factory['Statistics'].files, 11)

        self.assertEqual(
            [r.resource_path for r in request_log],
            [
                '/blog/?enable_get_priority=1',
                '/blog/?page=2',
                '/blog/?page=3',
                '/blog/?page=3&tab=1', '/blog/?page=3&tab=2', '/blog/?page=3&tab=3',
                '/blog/?page=4', '/blog/?page=5',
                '/blog/?tab=1', '/blog/?tab=2', '/blog/?tab=3',
                '/stylesheet1.css',
                '/blog/?page=6',
            ]
        )
