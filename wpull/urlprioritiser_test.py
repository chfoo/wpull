# encoding=utf-8

import unittest

from wpull.pipeline.item import URLRecord
from wpull.url import URLInfo
from wpull.urlprioritiser import URLPrioritiser
from wpull.urlfilter import RegexFilter


class TestURLPrioritiser(unittest.TestCase):
    def test_get_priority(self):
        priorities = [
            (RegexFilter(accepted = r'//example\.com/'), 3),
            (RegexFilter(accepted = r'^ftp://'), -1),
            (RegexFilter(accepted = r'^https?://example\.net/critical/'), 2),
            (RegexFilter(accepted = r'//example\.net/'), 1),
        ]
        prioritiser = URLPrioritiser(priorities)

        url_record = URLRecord()
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.com/foo.html'), url_record), 3)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('ftp://example.com/bar'), url_record), 3)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.net/critical/missile_codes'), url_record), 2)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.net/baz'), url_record), 1)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('https://example.org/'), url_record), 0)
        self.assertEqual(prioritiser.get_priority(URLInfo.parse('ftp://example.net/baz'), url_record), -1)
