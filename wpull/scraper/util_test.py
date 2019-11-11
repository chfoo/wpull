import unittest

from wpull.pipeline.item import LinkType
from wpull.scraper.util import clean_link_soup, parse_refresh, is_likely_link, \
    is_unlikely_link, identify_link_type, urljoin_safe


class TestUtil(unittest.TestCase):
    def test_clean_link_soup(self):
        self.assertEqual(
            'http://example.com',
            clean_link_soup('http://example.com  ')
        )
        self.assertEqual(
            'http://example.com/',
            clean_link_soup('\n\r\thttp://example.com\n\r\r\r\n\t/')
        )
        self.assertEqual(
            'http://example.com/ something',
            clean_link_soup('http://example.com\n\t / something  \n\r\t')
        )
        self.assertEqual(
            'http://example.com/dog cat/',
            clean_link_soup('http://example.com/\n dog \tcat\r/\n')
        )
        self.assertEqual(
            'ßðf ¤Jáßðff ßðfœ³²œ¤ œë ßfœ',
            clean_link_soup('ß\tðf ¤Jáßðf\n f ßðfœ³²œ¤ œë ßfœ ')
        )

    def test_parse_refresh(self):
        self.assertEqual(
            'http://example.com', parse_refresh('10;url="http://example.com"')
        )
        self.assertEqual(
            'http://example.com', parse_refresh('10;url= http://example.com ')
        )
        self.assertEqual(
            'example.com', parse_refresh("url =' example.com '")
        )
        self.assertFalse(
            parse_refresh('url=')
        )
        self.assertFalse(
            parse_refresh('url =     ')
        )

    def test_is_likely_link(self):
        self.assertTrue(is_likely_link('image.png'))
        self.assertTrue(is_likely_link('video.mp4'))
        self.assertTrue(is_likely_link('/directory'))
        self.assertTrue(is_likely_link('directory/'))
        self.assertTrue(is_likely_link('/directory/'))
        self.assertTrue(is_likely_link('../directory/'))
        self.assertTrue(is_likely_link('http://example.com/'))
        self.assertTrue(is_likely_link('https://example.com/'))
        self.assertTrue(is_likely_link('ftp://example.com'))
        self.assertTrue(is_likely_link('directory/index.html'))
        self.assertFalse(is_likely_link('directory/another_directory'))
        self.assertTrue(is_likely_link('application/windows.exe'))
        self.assertTrue(is_likely_link('//example.com/admin'))
        self.assertFalse(is_likely_link('12.0'))
        self.assertFalse(is_likely_link('7'))
        self.assertFalse(is_likely_link('horse'))
        self.assertFalse(is_likely_link(''))
        self.assertFalse(is_likely_link('setTimeout(myTimer, 1000)'))
        self.assertFalse(is_likely_link('comment.delete'))
        self.assertFalse(is_likely_link('example.com'))
        self.assertFalse(is_likely_link('example.net'))
        self.assertFalse(is_likely_link('example.org'))
        self.assertFalse(is_likely_link('example.edu'))

    def test_is_unlikely_link(self):
        self.assertTrue(is_unlikely_link('example.com+'))
        self.assertTrue(is_unlikely_link('www.'))
        self.assertTrue(is_unlikely_link(':example.com'))
        self.assertTrue(is_unlikely_link(',example.com'))
        self.assertTrue(is_unlikely_link('http:'))
        self.assertTrue(is_unlikely_link('.example.com'))
        self.assertTrue(is_unlikely_link('doc[0]'))
        self.assertTrue(is_unlikely_link('/'))
        self.assertTrue(is_unlikely_link('//'))
        self.assertTrue(is_unlikely_link('application/json'))
        self.assertTrue(is_unlikely_link('application/javascript'))
        self.assertTrue(is_unlikely_link('text/javascript'))
        self.assertTrue(is_unlikely_link('text/plain'))
        self.assertTrue(is_unlikely_link('/\\/'))
        self.assertTrue(is_unlikely_link('a.help'))
        self.assertTrue(is_unlikely_link('div.menu'))
        self.assertTrue(is_unlikely_link('apikey={YOUR_API_KEY_HERE}'))
        self.assertFalse(is_unlikely_link('http://'))
        self.assertFalse(is_unlikely_link('example'))
        self.assertFalse(is_unlikely_link('example.com'))
        self.assertFalse(is_unlikely_link('//example.com/assets/image.css'))
        self.assertFalse(is_unlikely_link('./image.css'))
        self.assertFalse(is_unlikely_link('../image.css'))
        self.assertFalse(is_unlikely_link('index.html'))
        self.assertFalse(is_unlikely_link('body.html'))

    def test_identifiy_link_type(self):
        self.assertEqual(LinkType.javascript, identify_link_type('hello.js'))
        self.assertEqual(LinkType.css, identify_link_type('hello.css'))
        self.assertEqual(LinkType.html, identify_link_type('hello.html'))
        self.assertEqual(LinkType.media, identify_link_type('hello.mp3'))
        self.assertEqual(LinkType.media, identify_link_type('hello.png'))
        self.assertEqual(LinkType.media, identify_link_type('hello.flv'))
        self.assertFalse(identify_link_type('hello.exe'))

    def test_urljoin_safe(self):
        self.assertEqual(
            'https://example.com/foo/bar',
            urljoin_safe('https://example.com/foo/baz', '\r\n\tba\t\nr')
        )
