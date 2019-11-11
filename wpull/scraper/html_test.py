import os.path
import shutil
import sys
import unittest

import wpull.util
from wpull.body import Body
from wpull.document.htmlparse.html5lib_ import HTMLParser as HTML5LibHTMLParser
from wpull.pipeline.item import LinkType
from wpull.protocol.http.request import Request, Response
from wpull.scraper.css import CSSScraper
from wpull.scraper.html import HTMLScraper, ElementWalker
from wpull.scraper.javascript import JavaScriptScraper
from wpull.util import IS_PYPY

if not IS_PYPY:
    from wpull.document.htmlparse.lxml_ import HTMLParser as LxmlHTMLParser
else:
    LxmlHTMLParser = type(NotImplemented)

ROOT_PATH = os.path.join(os.path.dirname(__file__), '..')


class Mixin(object):
    def get_html_parser(self):
        raise NotImplementedError()  # pragma: no cover

    def test_html_scraper_links(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, 'OK')
        response.body = Body()
        response.fields['Refresh'] = '3; url=header_refresh.html'

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'many_urls.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual('utf-8', scrape_result.encoding)

        self.assertEqual({
            'http://example.com/style_import_url.css',
            'http://example.com/style_import_quote_url.css',
            'http://example.com/style_single_quote_import.css',
            'http://example.com/style_double_quote_import.css',
            'http://example.com/link_href.css',
            'http://example.com/script.js',
            'http://example.com/body_background.png',
            'http://example.com/images/table_background.png',
            'http://example.com/images/td_background.png',
            'http://example.com/images/th_background.png',
            'http://example.com/style_url1.png',
            'http://example.com/style_url2.png',
            'http://example.com/applet/',  # returned by lxml
            'http://example.com/applet/applet_code.class',
            'http://example.com/applet/applet_src.class',
            'http://example.com/bgsound.mid',
            'http://example.com/audio_src.wav',
            'http://example.com/audio_poster.jpeg',
            'http://example.net/source_src.wav',
            'http://example.com/video_src.webm',
            'http://example.com/video_poster.jpeg',
            'http://example.net/track_src.vtt',
            'http://example.net/source_src.webm',
            'http://example.com/embed_src.mov',
            'http://example.com/fig_src.png',
            'http://example.com/frame_src.html',
            'http://example.com/iframe_src.html',
            'http://example.com/img_href.png',
            'http://example.com/img_lowsrc.png',
            'http://example.com/img_src.png',
            'http://example.com/img_data.png',
            'http://example.com/img_srcset_1.jpeg',
            'http://example.com/img_srcset_2.jpeg',
            'http://example.com/img_srcset_3.jpeg',
            'http://example.com/input_src.png',
            'http://example.com/layer_src.png',
            'http://example.com/object/',  # returned by lxml
            'http://example.com/object/object_data.swf',
            'http://example.com/object/object_archive.dat',
            'mailto:internet',
            'object_not_url_codebase',
            'http://example.com/param_ref_value.php',
            'http://example.com/overlay_src.html',
            'http://example.com/script_variable.png',
        },
            inline_urls
        )
        self.assertEqual({
            'http://example.com/og_image.png',
            'http://example.com/og_url.html',
            'http://example.com/og_audio.mp3',
            'http://example.com/og_video.webm',
            'http://example.com/twitter_image.png',
            'http://example.com/twitter_image0.png',
            'http://example.com/twitter_image1.png',
            'http://example.com/twitter_image2.png',
            'http://example.com/twitter_image3.png',
            'http://example.com/twitter_player.html',
            'http://example.com/twitter_stream.mp4',
            'http://example.net/soup.html',
            'http://example.com/a_href.html',
            'http://example.com/area_href.html',
            'http://example.com/frame_src.html',
            'http://example.com/embed_href.html',
            'http://example.com/embed_src.mov',
            'http://example.com/form_action.html',
            'http://example.com/iframe_src.html',
            'http://example.com/layer_src.png',
            'http://example.com/overlay_src.html',
            'ftp://ftp.protocol.invalid/',
            'mailto:user@example.com',
            'http://a-double-slash.example',
            'http://example.com/header_refresh.html',
            'https://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:8080/ipv6',
            'http://example.com/document_write.html',
            'http://example.com/http_document_write.html',
            'http://example.com/http_document_write2.html',
            'http://example.com/http document write.html',
            'http://example.com/script_variable.html',
            'http://example.com/http_script_variable.html',
            'https://example.com/https_script_variable.html',
            'ftp://example.com/ftp_script_variable.html',
            'http://example.com/end_dir_script_variable/',
            'http://example.com/start_dir_script_variable',
            'http://example.com/../relative_dir_script_variable'
            if sys.version_info < (3, 5) else
            'http://example.com/relative_dir_script_variable',
            'http://example.com/script_json.html',
            'http://example.com/http_script_json.html?a=b',
            'http://example.com/a_javascript_link.html',
            'http://example.com/a_onclick_link.html',
        },
            linked_urls
        )

        for url in inline_urls | linked_urls:
            self.assertIsInstance(url, str)

    def test_html_scraper_reject_type(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'many_urls.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response,
                                       link_type=LinkType.css)
        self.assertFalse(scrape_result)

    def test_html_soup(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['Refresh'] = 'yes'

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples', 'soup.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual(
            {'http://example.com/ABOUTM~1.JPG'},
            inline_urls
        )
        self.assertEqual(
            {
                'http://example.com/BLOG',
                'http://example.com/web ring/Join.htm',
            },
            linked_urls
        )

    def test_html_mojibake(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['content-type'] = 'text/html; charset=Shift_JIS'

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'mojibake.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual('shift_jis', scrape_result.encoding)

        self.assertEqual(
            set(),
            inline_urls
        )
        self.assertEqual(
            {'http://example.com/文字化け'},
            linked_urls
        )

    def test_html_krokozyabry(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['content-type'] = 'text/html; charset=KOI8-R'

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'krokozyabry.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual('koi8-r', scrape_result.encoding)

        self.assertEqual(
            set(),
            inline_urls
        )
        self.assertEqual(
            {'http://example.com/Кракозябры'},
            linked_urls
        )

    def test_html_scraper_links_base_href(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'basehref.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual('utf-8', scrape_result.encoding)

        self.assertEqual({
            'http://cdn.example.com/stylesheet1.css',
            'http://www.example.com/stylesheet2.css',
            'http://example.com/a/stylesheet3.css',
            'http://example.com/a/dir/image1.png',
            'http://example.com/dir/image2.png',
            'http://example.net/image3.png',
            'http://example.com/dir/image4.png',
        },
            inline_urls
        )
        self.assertEqual({
            'http://example.com/a/'
        },
            linked_urls
        )

    def test_xhtml(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples', 'xhtml.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual(
            {
                'http://example.com/image.png',
                'http://example.com/script.js',
            },
            inline_urls
        )
        self.assertEqual(
            {
                'http://example.com/link'
            },
            linked_urls
        )

    def test_xhtml_invalid(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'xhtml_invalid.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual(
            {
                'http://example.com/image.png',
                'http://example.com/script.js',
            },
            inline_urls
        )
        self.assertEqual(
            {
                'http://example.com/link'
            },
            linked_urls
        )

    def test_html_wrong_charset(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples', 'kcna.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertEqual('utf-16-le', scrape_result.encoding)

        self.assertEqual(
            {
                'http://example.com/utm/__utm.js',
                'http://example.com/Knewskage.gif',
                'http://example.com/Lline.gif',
                'http://example.com/Sline.gif',
                'http://example.com/korean01.gif',
                'http://example.com/korean02.gif',
                'http://example.com/english01.gif',
                'http://example.com/english02.gif',
                'http://example.com/Tongsinkage.gif',
                'http://example.com/Knewskage.gif',
            },
            inline_urls
        )
        self.assertEqual(
            {
                'http://example.com/index-k.htm',
                'http://example.com/index-e.htm',
            },
            linked_urls
        )

    def test_html_not_quite_charset(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'videogame_top.htm')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links

        self.assertIn(
            'http://example.com/copyright_2001_2006_rtype.gif',
            inline_urls
        )
        self.assertIn(
            'http://www.geocities.jp/gamehouse_grindcrusher/',
            linked_urls
        )

    def test_html_garbage(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['content-type'] = 'text/html'

        with wpull.util.reset_file_offset(response.body):
            response.body.write(
                b'\x01\x00\x01\x00l~Z\xff\x0f`y\x80\x00p<\x7f'
                b'\xffndo\xff\xff-\x83{d\xec</\xfe\x80\x00\xb4Bo'
                b'\x7f\xff\xff\xffV\xc1\xff\x7f\xff7'
            )

        scrape_info = scraper.scrape(request, response)

        self.assertTrue(scrape_info)

    def test_html_encoding_lxml_name_mismatch(self):
        '''It should accept encoding names with underscore.'''
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['content-type'] = 'text/html; charset=EUC_KR'

        with wpull.util.reset_file_offset(response.body):
            response.body.write(
                '힖'.encode('euc_kr')
            )

        scrape_info = scraper.scrape(request, response)

        self.assertTrue(scrape_info)
        self.assertEqual('euc_kr', scrape_info['encoding'])

    def test_html_serious_bad_encoding(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker,
                              encoding_override='utf8')
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['content-type'] = 'text/html; charset=utf8'

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples',
                                          'xkcd_1_evil.html')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_info = scraper.scrape(request, response)

        self.assertTrue(scrape_info)

    def test_rss_as_html(self):
        element_walker = ElementWalker(
            css_scraper=CSSScraper(), javascript_scraper=JavaScriptScraper())
        scraper = HTMLScraper(self.get_html_parser(), element_walker)
        request = Request('http://example.com/')
        response = Response(200, '')
        response.body = Body()
        response.fields['content-type'] = 'application/rss+xml'

        with wpull.util.reset_file_offset(response.body):
            html_file_path = os.path.join(ROOT_PATH,
                                          'testing', 'samples', 'rss.xml')
            with open(html_file_path, 'rb') as in_file:
                shutil.copyfileobj(in_file, response.body)

        scrape_result = scraper.scrape(request, response)

        self.assertTrue(scrape_result)
        inline_urls = scrape_result.inline_links
        linked_urls = scrape_result.linked_links
        self.assertFalse(
            inline_urls
        )
        self.assertEqual(
            {
                'http://www.someexamplerssdomain.com/main.html',
                'http://www.wikipedia.org/'
            },
            linked_urls
        )


@unittest.skipIf(IS_PYPY, 'Not supported under PyPy')
class TestLxmlHTMLScraper(Mixin, unittest.TestCase):
    def get_html_parser(self):
        return LxmlHTMLParser()


class TestHTML5LibHTMLScraper(Mixin, unittest.TestCase):
    def get_html_parser(self):
        return HTML5LibHTMLParser()
