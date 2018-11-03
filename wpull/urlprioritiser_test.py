# encoding=utf-8

import unittest

from wpull.application.plugin import PluginFunctions
from wpull.pipeline.item import URLRecord
from wpull.url import URLInfo
from wpull.urlprioritiser import URLPrioritiser
from wpull.urlfilter import RegexFilter


PRIORITIES = [
    (RegexFilter(accepted=r'//example\.com/'), 3),
    (RegexFilter(accepted=r'^ftp://'), -1),
    (RegexFilter(accepted=r'^https?://example\.net/critical/'), 2),
    (RegexFilter(accepted=r'//example\.net/'), 1),
]


def build_hooked_prioritiser(hook_function):
    class HookedURLPrioritiser(URLPrioritiser):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.hook_dispatcher.connect(PluginFunctions.get_priority, hook_function)
    return HookedURLPrioritiser(PRIORITIES)


class TestURLPrioritiser(unittest.TestCase):
    def test_get_priority(self):
        prioritiser = URLPrioritiser(PRIORITIES)

        url_record = URLRecord()
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.com/foo.html'), url_record), 3)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('ftp://example.com/bar'), url_record), 3)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.net/critical/missile_codes'), url_record), 2)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.net/baz'), url_record), 1)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.org/'), url_record), 0)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('ftp://example.net/baz'), url_record), -1)

    def test_hook_simple(self):
        hook_calls = []

        def hook(url_info: URLInfo, url_record: URLRecord):
            hook_calls.append((url_info, url_record))
            return None

        prioritiser = build_hooked_prioritiser(hook)

        original_url_info = URLInfo.parse('https://example.com/foo.html')
        original_url_record = URLRecord() # TODO: pass a proper URLRecord instead
        self.assertEqual(prioritiser.get_priority(original_url_info, original_url_record), 3)
        self.assertEqual(len(hook_calls), 1)
        # Verify that the hook is called with a copy of the URLInfo and URLRecord instances
        self.assertEqual(hook_calls[0][0], original_url_info)
        self.assertIsNot(hook_calls[0][0], original_url_info)
        #self.assertEqual(hook_calls[0][1], original_url_record) # TODO: URLRecord does not provide __eq__
        self.assertIsNot(hook_calls[0][1], original_url_record)
        self.assertIs(hook_calls[0][1].priority, None)

    def test_hook_overrides(self):
        def hook(url_info: URLInfo, url_record: URLRecord):
            if url_info.url == 'https://example.com/bar':
                return -10
            return None

        prioritiser = build_hooked_prioritiser(hook)

        url_record = URLRecord()
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.com/foo.html'), url_record), 3)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.com/bar'), url_record), -10)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.com/baz'), url_record), 3)
