# encoding=utf-8

import timeit
import unittest

from wpull.url import URLInfo, schemes_similar, is_subdir, split_query, \
    percent_decode, percent_decode_plus, percent_encode, percent_encode_plus, \
    uppercase_percent_encoding, urljoin, flatten_path, parse_url_or_log


class TestURL(unittest.TestCase):
    @unittest.skip('experiment only')
    def test_lib_vs_wpull(self):
        result_1 = timeit.timeit('''
        from urllib.parse import urlsplit
        for i in range(1000):
            urlsplit('http://donkey{i}.com/waffles{i}'.format(i=i))
        ''', number=100)
        result_2 = timeit.timeit('''
        from wpull.url import URLInfo
        parse = URLInfo.parse
        for i in range(1000):
            parse('http://donkey{i}.com/waffles{i}'.format(i=i))
        ''', number=100)

        print(result_1, result_2)

    def test_url_info_naked(self):
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('Example.Com').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('//example.com').url
        )
        self.assertEqual(
            'http://example.com/Blah',
            URLInfo.parse('//example.com/Blah').url
        )

        url_info = URLInfo.parse('example.com:8080')
        self.assertEqual('http://example.com:8080/', url_info.url)
        self.assertEqual('example.com:8080', url_info.hostname_with_port)
        self.assertEqual(8080, url_info.port)

        url_info = URLInfo.parse('localhost:8080/A/b/C:')
        self.assertEqual('http://localhost:8080/A/b/C:', url_info.url)
        self.assertEqual('localhost:8080', url_info.hostname_with_port)
        self.assertEqual(8080, url_info.port)

        self.assertEqual(
            'http://example.com/Asdf',
            URLInfo.parse('example.com/Asdf#Blah').url
        )
        self.assertEqual(
            'http://example.com/asdf/Ghjk',
            URLInfo.parse('example.com/asdf/Ghjk#blah').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('example.com/').url
        )
        self.assertEqual(
            'https://example.com/',
            URLInfo.parse('https://example.com').url
        )

    def test_url_info_parts(self):
        url_info = URLInfo.parse(
            'HTTP://userName:pass%3Aword@[A::1]:81/ásdF\u200C/ghjK?a=b=c&D#/?')
        self.assertEqual(
            'http://userName:pass:word@[a::1]:81/'
            '%C3%A1sdF%E2%80%8C/ghjK?a=b=c&D',
            url_info.url
        )
        self.assertEqual('http', url_info.scheme)
        self.assertEqual('userName:pass%3Aword@[A::1]:81',
                         url_info.authority)
        self.assertEqual('/ásdF\u200C/ghjK?a=b=c&D#/?', url_info.resource)
        self.assertEqual('userName', url_info.username)
        self.assertEqual('pass:word', url_info.password)
        self.assertEqual('[A::1]:81', url_info.host)
        self.assertEqual('[a::1]:81', url_info.hostname_with_port)
        self.assertEqual('a::1', url_info.hostname)
        self.assertEqual(81, url_info.port)
        self.assertEqual('/%C3%A1sdF%E2%80%8C/ghjK', url_info.path)
        self.assertEqual('a=b=c&D', url_info.query)
        self.assertEqual('/?', url_info.fragment)
        self.assertEqual('utf-8', url_info.encoding)
        self.assertEqual(
            'HTTP://userName:pass%3Aword@[A::1]:81/ásdF\u200C/ghjK?a=b=c&D#/?',
            url_info.raw)
        self.assertEqual(('/%C3%A1sdF%E2%80%8C', 'ghjK'), url_info.split_path())

        url_info = URLInfo.parse(
            'Ftp://N00B:hunter2@LocalHost.Example/mydocs/'
        )
        self.assertEqual('ftp', url_info.scheme)
        self.assertEqual('N00B:hunter2@LocalHost.Example',
                         url_info.authority)
        self.assertEqual('/mydocs/', url_info.resource)
        self.assertEqual('N00B', url_info.username)
        self.assertEqual('hunter2', url_info.password)
        self.assertEqual('LocalHost.Example', url_info.host)
        self.assertEqual('localhost.example', url_info.hostname_with_port)
        self.assertEqual('localhost.example', url_info.hostname)
        self.assertEqual(21, url_info.port)
        self.assertEqual('/mydocs/', url_info.path)
        self.assertFalse(url_info.query)
        self.assertFalse(url_info.fragment)
        self.assertEqual('utf-8', url_info.encoding)
        self.assertEqual(
            'Ftp://N00B:hunter2@LocalHost.Example/mydocs/',
            url_info.raw)
        self.assertEqual(('/mydocs', ''), url_info.split_path())

    def test_url_info_default_port(self):
        self.assertEqual(
            80,
            URLInfo.parse('http://example.com').port
        )
        self.assertEqual(
            443,
            URLInfo.parse('https://example.com').port
        )
        self.assertEqual(
            'example.com',
            URLInfo.parse('http://example.com').hostname_with_port
        )
        self.assertEqual(
            'example.com',
            URLInfo.parse('https://example.com').hostname_with_port
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com:80').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com:').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com:/').url
        )

    def test_url_info_percent_encode(self):
        self.assertEqual(
            'http://example.com/%C3%B0',
            URLInfo.parse('http://example.com/ð').url
        )
        self.assertEqual(
            'http://example.com/blah%20blah/',
            URLInfo.parse('example.com/blah blah/').url
        )
        self.assertEqual(
            'http://example.com/blah%20blah/',
            URLInfo.parse('example.com/blah%20blah/').url
        )
        self.assertEqual(
            'http://www.xn--hda.com/asdf',
            URLInfo.parse('www.ð.com/asdf').url
        )
        self.assertEqual(
            'www.xn--hda.com',
            URLInfo.parse('www.ð.com/asdf').hostname
        )
        self.assertEqual(
            'www.xn--hda.com',
            URLInfo.parse('www.xn--hda.com/asdf').hostname
        )
        self.assertEqual(
            'http://example.com/?blah=%C3%B0',
            URLInfo.parse('example.com?blah=ð').url
        )
        self.assertEqual(
            'http://example.com/?blah=%C3%B0',
            URLInfo.parse('example.com?blah=%c3%b0').url
        )

        url_info = URLInfo.parse('example.com/文字化け/?blah=文字化け',
                                 encoding='shift_jis')
        self.assertEqual(
            'http://example.com/%95%B6%8E%9A%89%BB%82%AF/'
            '?blah=%95%B6%8E%9A%89%BB%82%AF',
            url_info.url
        )
        self.assertEqual(
            '/%95%B6%8E%9A%89%BB%82%AF/',
            url_info.path
        )
        self.assertEqual(
            'blah=%95%B6%8E%9A%89%BB%82%AF',
            url_info.query
        )
        self.assertEqual(
            'shift_jis',
            url_info.encoding
        )

        self.assertEqual(
            'http://example.com/%95%B6%8E%9A%89%BB%82%AF/'
            '?blah=%95%B6%8E%9A%89%BB%82%AF',
            URLInfo.parse('example.com/%95%B6%8E%9A%89%BB%82%AF/'
                          '?blah=%95%B6%8E%9A%89%BB%82%AF',
                          encoding='shift_jis').url
        )
        self.assertEqual(
            'http://example.com/%95%B6%8E%9A%89%BB%82%AF/'
            '?blah=%95%B6%8E%9A%89%BB%82%AF',
            URLInfo.parse('example.com/%95%B6%8E%9A%89%BB%82%AF/'
                          '?blah=%95%B6%8E%9A%89%BB%82%AF').url
        )

        self.assertEqual(
            'http://example.com/'
            '?blah=http%3A%2F%2Fexample.com%2F%3Ffail%3Dtrue',
            URLInfo.parse(
                'http://example.com/'
                '?blah=http%3A%2F%2Fexample.com%2F%3Ffail%3Dtrue').url
        )
        self.assertEqual(
            'http://example.com/'
            '?blah=http://example.com/?fail%3Dtrue',
            URLInfo.parse(
                'http://example.com/'
                '?blah=http://example.com/?fail%3Dtrue').url
        )

        self.assertEqual(
            'http://example.com/??blah=blah[0:]=bl%61h?blah%22&d%26_',
            URLInfo.parse(
                'http://example.com/??blah=blah[0:]=bl%61h?blah"&d%26_').url
        )

    def test_url_info_not_http(self):
        url_info = URLInfo.parse('mailto:user@example.com')
        self.assertEqual('mailto:user@example.com', url_info.url)
        self.assertEqual('mailto', url_info.scheme)

    def test_url_info_invalids(self):
        self.assertRaises(ValueError, URLInfo.parse, '')
        self.assertRaises(ValueError, URLInfo.parse, '#')
        self.assertRaises(ValueError, URLInfo.parse, 'http://')
        self.assertRaises(ValueError, URLInfo.parse, 'example....com')
        self.assertRaises(ValueError, URLInfo.parse, 'http://example....com')
        self.assertRaises(ValueError, URLInfo.parse, 'http://example…com')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[34.4kf]::4')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[34.4kf::4')
        self.assertRaises(ValueError, URLInfo.parse, 'http://dmn3]:3a:45')
        self.assertRaises(ValueError, URLInfo.parse, ':38/3')
        self.assertRaises(ValueError, URLInfo.parse, 'http://][a:@1]')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[[aa]]:4:]6')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[a]')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[a]')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[[a]')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[[a]]a]')
        self.assertRaises(ValueError, URLInfo.parse, 'http://[[a:a]]')
        self.assertRaises(ValueError, URLInfo.parse, 'http:///')
        self.assertRaises(ValueError, URLInfo.parse, 'http:///horse')
        self.assertRaises(ValueError, URLInfo.parse, 'http://?what?')
        self.assertRaises(ValueError, URLInfo.parse, 'http://#egg=wpull')
        self.assertRaises(ValueError, URLInfo.parse, 'http://\x00/')
        self.assertRaises(ValueError, URLInfo.parse, 'http:/a')
        self.assertRaises(ValueError, URLInfo.parse, 'http://@@example.com/@')
        self.assertRaises(
            ValueError, URLInfo.parse,
            'http://ｆａｔ３２ｄｅｆｒａｇｍｅｎｔｅｒ.internets：：８０')
        self.assertRaises(
            ValueError, URLInfo.parse,
            'http://ｆａｔ３２ｄｅｆｒａｇｍｅｎｔｅｒ.internets：８０/')
        self.assertRaises(ValueError, URLInfo.parse, 'http:// /spaaaace')
        self.assertRaises(
            ValueError, URLInfo.parse,
            'http://a-long-long-time-ago-the-earth-was-ruled-by-dinosaurs-'
            'they-were-big-so-not-a-lot-of-people-went-around-hassling-them-'
            'actually-no-people-went-around-hassling-them-'
            'because-there-weren-t-any-people-yet-'
            'just-the-first-tiny-mammals-'
            'basically-life-was-good-'
            'lou-it-just-dont-get-no-better-than-this-'
            'yeah-'
            'then-something-happened-'
            'a-giant-meteorite-struck-the-earth-'
            'goodbye-dinosaurs-'
            'but-what-if-the-dinosaurs-werent-all-destroyed-'
            'what-if-the-impact-of-that-meteorite-created-a-parallel-dimension-'
            'where-the-dinosaurs-continue-to-thrive-'
            'and-evolved-into-intelligent-vicious-aggressive-beings-'
            'just-like-us-'
            'and-hey-what-if-they-found-their-way-back.movie'
        )
        self.assertRaises(
            ValueError, URLInfo.parse, 'http://[...]/python.xml%22')
        self.assertRaises(
            ValueError, URLInfo.parse, 'http://[…]/python.xml%22')
        self.assertRaises(
            ValueError, URLInfo.parse, 'http://[.]/python.xml%22')
        self.assertRaises(
            ValueError, URLInfo.parse, 
            'http://wow:99999999999999999999999999999999999999999999999999999'
            '9999999999999999999999999999999999999999999999999999999999999999')
        self.assertRaises(
            ValueError, URLInfo.parse, 
            'http://wow:-9999999999999999999999999999999999999999999999999999'
            '9999999999999999999999999999999999999999999999999999999999999999')

    def test_url_info_path_folding(self):
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com/.').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com/../').url
        )
        self.assertEqual(
            'http://example.com/index.html',
            URLInfo.parse('http://example.com/../index.html').url
        )
        self.assertEqual(
            'http://example.com/b/style.css',
            URLInfo.parse('http://example.com/a/../../b/style.css').url
        )
        self.assertEqual(
            'http://example.com/a/style.css',
            URLInfo.parse('http://example.com/a/b/../style.css').url
        )

    def test_url_info_reserved_char_is_ok(self):
        self.assertEqual(
            'http://example.com/@49IMG.DLL/$SESSION$/image.png;large',
            URLInfo.parse(
                'http://example.com/@49IMG.DLL/$SESSION$/image.png;large').url
        )
        self.assertEqual(
            'http://example.com/@49IMG.DLL/$SESSION$/imag%C3%A9.png;large',
            URLInfo.parse(
                'http://example.com/@49IMG.DLL/$SESSION$/imagé.png;large').url
        )
        self.assertEqual(
            'http://example.com/$c/%system.exe/',
            URLInfo.parse('http://example.com/$c/%system.exe/').url
        )

    def test_url_info_misleading_parts(self):
        self.assertEqual(
            'http://example.com/?a',
            URLInfo.parse('http://example.com?a').url
        )
        self.assertEqual(
            'http://example.com/?a?',
            URLInfo.parse('http://example.com?a?').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com#a').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com#a?').url
        )
        self.assertEqual(
            'http://example.com/?a',
            URLInfo.parse('http://example.com?a#').url
        )
        self.assertEqual(
            'http://example.com/:10',
            URLInfo.parse('http://example.com/:10').url
        )
        self.assertEqual(
            'http://example.com/?@/',
            URLInfo.parse('http://:@example.com?@/').url
        )
        self.assertEqual(
            'http://example.com/http://example.com',
            URLInfo.parse('http://:@example.com/http://example.com').url
        )
        self.assertEqual(
            'http://example.com/?@/',
            URLInfo.parse('http://:@example.com:?@/').url
        )

    def test_url_info_query(self):
        self.assertEqual(
            'http://example.com/?a=',
            URLInfo.parse('http://example.com?a=').url
        )
        self.assertEqual(
            'http://example.com/?a=1',
            URLInfo.parse('http://example.com?a=1').url
        )
        self.assertEqual(
            'http://example.com/?a=1&b',
            URLInfo.parse('http://example.com?a=1&b').url
        )
        self.assertEqual(
            'http://example.com/?a=1&b=',
            URLInfo.parse('http://example.com?a=1&b=').url
        )

    def test_url_info_ipv6(self):
        self.assertEqual(
            'https://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:8080/ipv6',
            URLInfo.parse(
                'https://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:8080/ipv6'
            ).url
        )
        self.assertEqual(
            '[2001:db8:85a3:8d3:1319:8a2e:370:7348]:8080',
            URLInfo.parse(
                'http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:8080/ipv6'
            ).hostname_with_port
        )
        self.assertEqual(
            'http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]/ipv6',
            URLInfo.parse(
                'http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]/ipv6'
            ).url
        )
        self.assertEqual(
            '[2001:db8:85a3:8d3:1319:8a2e:370:7348]',
            URLInfo.parse(
                'http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]/ipv6'
            ).hostname_with_port
        )

    def test_url_info_trailing_dot(self):
        self.assertEqual(
            'http://example.com./',
            URLInfo.parse('http://example.com./').url
        )

        self.assertEqual(
            'http://example.com.:81/',
            URLInfo.parse('http://example.com.:81/').url
        )

    def test_url_info_username_password(self):
        self.assertEqual(
            'http://UserName@example.com/',
            URLInfo.parse('http://UserName@example.com/').url
        )
        self.assertEqual(
            'http://UserName:PassWord@example.com/',
            URLInfo.parse('http://UserName:PassWord@example.com/').url
        )
        self.assertEqual(
            'http://:PassWord@example.com/',
            URLInfo.parse('http://:PassWord@example.com/').url
        )
        self.assertEqual(
            'http://UserName:Pass:Word@example.com/',
            URLInfo.parse('http://UserName:Pass:Word@example.com/').url
        )
        self.assertEqual(
            'http://User%40Name:Pass:Word@example.com/',
            URLInfo.parse('http://User%40Name:Pass%3AWord@example.com/').url
        )
        self.assertEqual(
            'http://User%20Name%3A@example.com/',
            URLInfo.parse('http://User Name%3A:@example.com/').url
        )

    def test_url_info_round_trip(self):
        urls = [
            'http://example.com/blah%20blah/',
            'example.com:81?blah=%c3%B0',
            'http://example.com/a/../../b/style.css',
            'http://example.com/'
            '?blah=http%3A%2F%2Fexample.com%2F%3Ffail%3Dtrue',
            'http://example.com/??blah=blah[0:]=bl%61h?blah"&d%26_',
            'http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]/ipv6',
        ]

        for url in urls:
            URLInfo.parse(URLInfo.parse(url).url)

    def test_ip_address_normalization(self):
        self.assertEqual(
            'http://192.0.2.235/',
            URLInfo.parse('http://0xC0.0x00.0x02.0xEB').url
        )
        self.assertEqual(
            'http://192.0.2.235/',
            URLInfo.parse('http://0300.0000.0002.0353').url
        )
        self.assertEqual(
            'http://192.0.2.235/',
            URLInfo.parse('http://0xC00002EB/').url
        )
        self.assertEqual(
            'http://192.0.2.235/',
            URLInfo.parse('http://3221226219/').url
        )
        self.assertEqual(
            'http://192.0.2.235/',
            URLInfo.parse('http://030000001353/').url
        )
        self.assertEqual(
            'http://[2001:db8:85a3:8d3:1319:8a2e:370:7348]:8080/ipv6',
            URLInfo.parse(
                'http://[2001:Db8:85a3:8d3:1319:8a2e:370:7348]:8080/ipv6'
            ).url
        )
        self.assertEqual(
            'http://[::1]/',
            URLInfo.parse('http://[0:0:0:0:0:0:0:1]').url
        )
        self.assertEqual(
            'http://[::ffff:c000:280]/',
            URLInfo.parse('http://[::ffff:192.0.2.128]/').url
        )

    def test_url_info_to_dict(self):
        url_info = URLInfo.parse('https://example.com/file.jpg')
        url_info_dict = url_info.to_dict()
        self.assertEqual('/file.jpg', url_info_dict['path'])
        self.assertEqual('example.com', url_info_dict['hostname'])
        self.assertEqual('https', url_info_dict['scheme'])
        self.assertEqual(443, url_info_dict['port'])
        self.assertEqual('utf-8', url_info_dict['encoding'])

    def test_url_info_backslashes_in_path(self):
        self.assertEqual(
            'http://example.com/a/b/',
            URLInfo.parse('http://example.com/a\\b/').url
        )
        self.assertEqual(
            'http://example.com/a/b/',
            URLInfo.parse('http://example.com/a\\b\\').url
        )
        self.assertEqual(
            'http://example.com/a/b/',
            URLInfo.parse('http://example.com\\a/b/').url
        )
        self.assertEqual(
            'http://example.com/a///b/',
            URLInfo.parse('http://example.com/a\\/\\b/').url
        )
        self.assertEqual(
            'http://example.com/',
            URLInfo.parse('http://example.com:\\').url
        )

    def test_schemes_simialar(self):
        self.assertTrue(schemes_similar('http', 'http'))
        self.assertTrue(schemes_similar('https', 'http'))
        self.assertTrue(schemes_similar('http', 'https'))
        self.assertTrue(schemes_similar('https', 'https'))
        self.assertFalse(schemes_similar('ftp', 'http'))
        self.assertTrue(schemes_similar('email', 'email'))

    def test_is_subdir(self):
        self.assertTrue(is_subdir('/profile/blog', '/profile/blog/123'))
        self.assertTrue(is_subdir('/profile/blog/', '/profile/blog/123'))
        self.assertFalse(is_subdir('/profile/blog', '/profile/photo'))

        self.assertTrue(is_subdir('/profile/blog', '/profile/blog/123',
                                  trailing_slash=True))
        self.assertTrue(is_subdir('/profile/blog/', '/profile/blog/123',
                                  trailing_slash=True))
        self.assertFalse(is_subdir('/profile/blog/', '/profile/photo',
                                   trailing_slash=True))
        self.assertTrue(is_subdir('/profile/blog', '/profile/photo',
                                  trailing_slash=True))

        self.assertTrue(is_subdir('/profile/blog-*-', '/profile/blog-1-/',
                                  wildcards=True))
        self.assertFalse(is_subdir('/profile/blog-*-', '/profile/blog/',
                                   wildcards=True))
        self.assertFalse(is_subdir('/profile/blog-*-', '/profile/',
                                   wildcards=True))

    def test_split_query(self):
        self.assertEqual([],
                         split_query('&'))
        self.assertEqual([('a', 'ð')],
                         split_query('a=ð'))
        self.assertEqual([('a', 'ð')],
                         split_query('a=ð&b'))
        self.assertEqual([('a', 'ð')],
                         split_query('a=ð&b='))
        self.assertEqual([('a', 'ð'), ('b', '')],
                         split_query('a=ð&b=', keep_blank_values=True))
        self.assertEqual([('a', 'ð'), ('b', '%2F')],
                         split_query('a=ð&b=%2F'))

    def test_url_percent_encode(self):
        self.assertEqual('a ', percent_decode('a%20'))
        self.assertEqual('að', percent_decode('a%C3%B0'))
        self.assertEqual('a ', percent_decode_plus('a+'))
        self.assertEqual('að', percent_decode_plus('a%C3%B0'))
        self.assertEqual('a%20', percent_encode('a '))
        self.assertEqual('a%C3%B0', percent_encode('að'))
        self.assertEqual('a+', percent_encode_plus('a '))
        self.assertEqual('a%C3%B0', percent_encode_plus('að'))

    def test_uppercase_percent_encoding(self):
        self.assertEqual(
            'ð',
            uppercase_percent_encoding('ð')
        )
        self.assertEqual(
            'qwerty%%asdf',
            uppercase_percent_encoding('qwerty%%asdf')
        )
        self.assertEqual(
            'cAt%2F%EE%AB',
            uppercase_percent_encoding('cAt%2f%ee%ab')
        )

    def test_url_join(self):
        self.assertEqual(
            'http://example.net',
            urljoin('http://example.com', '//example.net')
        )
        self.assertEqual(
            'https://example.net',
            urljoin('https://example.com', '//example.net')
        )
        self.assertEqual(
            'http://example.net',
            urljoin('http://example.com/', '//example.net')
        )
        self.assertEqual(
            'https://example.net',
            urljoin('https://example.com/', '//example.net')
        )
        self.assertEqual(
            'http://example.net/',
            urljoin('http://example.com/', '//example.net/')
        )
        self.assertEqual(
            'https://example.net/',
            urljoin('https://example.com/', '//example.net/')
        )
        self.assertEqual(
            'https://example.com/asdf',
            urljoin('https://example.com/cookies', '/asdf')
        )
        self.assertEqual(
            'http://example.com/asdf',
            urljoin('http://example.com/cookies', 'asdf')
        )
        self.assertEqual(
            'http://example.com/cookies/asdf',
            urljoin('http://example.com/cookies/', 'asdf')
        )
        self.assertEqual(
            'https://example.net/asdf',
            urljoin('https://example.net/', '/asdf')
        )
        self.assertEqual(
            'http://example.net/asdf',
            urljoin('https://example.com', 'http://example.net/asdf')
        )
        self.assertEqual(
            'http://example.com/',
            urljoin('http://example.com', '//example.com/')
        )
        self.assertEqual(
            'http://example.com/',
            urljoin('http://example.com/', '//')
        )
        self.assertEqual(
            'http://example.com/',
            urljoin('http://example.com/', '///')
        )
        self.assertEqual(
            'http://example.com/a/style.css',
            urljoin('http://example.com/a/', './style.css')
        )
        self.assertEqual(
            'http://example.com/style.css',
            urljoin('http://example.com/a/', './../style.css')
        )
        self.assertEqual(
            'sausage',
            urljoin('mailto:hotdogbun', 'sausage')
        )
        self.assertEqual(
            'mailto://sausage',
            urljoin('mailto:hotdogbun', '//sausage')
        )
        self.assertEqual(
            'hotdogbun://sausage',
            urljoin('hotdogbun', '//sausage')
        )

    def test_flatten_path(self):
        self.assertEqual('/', flatten_path(''))
        self.assertEqual('//', flatten_path('//'))
        self.assertEqual('///', flatten_path('///'))
        self.assertEqual('/http://', flatten_path('/http://'))
        self.assertEqual('/', flatten_path('//', flatten_slashes=True))
        self.assertEqual('/', flatten_path('///', flatten_slashes=True))
        self.assertEqual('/http:/', flatten_path('/http://',
                                                 flatten_slashes=True))
        self.assertEqual('/a', flatten_path('a'))
        self.assertEqual('/a/', flatten_path('a/'))
        self.assertEqual('/', flatten_path('.'))
        self.assertEqual('/', flatten_path('./'))
        self.assertEqual('/', flatten_path('/.'))
        self.assertEqual('/', flatten_path('/..'))
        self.assertEqual('/', flatten_path('../'))
        self.assertEqual('/', flatten_path('./.'))
        self.assertEqual('/', flatten_path('/'))
        self.assertEqual('/', flatten_path('/../../../'))
        self.assertEqual('/', flatten_path('/.././'))
        self.assertEqual('/a', flatten_path('/../a/../a'))
        self.assertEqual('/a/', flatten_path('/../a/../a/'))
        self.assertEqual('//a/a/', flatten_path('//a//../a/'))
        self.assertEqual('/a//a///a', flatten_path('/a//a///a'))
        self.assertEqual('/a/',
                         flatten_path('//a//../a/', flatten_slashes=True))
        self.assertEqual('/a/a/a',
                         flatten_path('/a//a///a', flatten_slashes=True))
        self.assertEqual('/index.html', flatten_path('/./index.html'))
        self.assertEqual('/index.html', flatten_path('/../index.html'))
        self.assertEqual('/a/index.html', flatten_path('/a/./index.html'))
        self.assertEqual('/index.html', flatten_path('/a/../index.html'))
        self.assertEqual('/doc/index.html', flatten_path('/../doc/index.html'))
        self.assertEqual(
            '/dog/doc/index.html',
            flatten_path('/dog/cat/../doc/index.html')
        )
        self.assertEqual(
            '/dog/doc/index.html',
            flatten_path('/dog/../dog/./cat/../doc/././../doc/index.html')
        )
        self.assertEqual(
            '/dog//doc//doc/index.html/',
            flatten_path('/dog/../dog//./cat/../doc/.///./../doc/index.html/')
        )
        self.assertEqual(
            '/dog/doc/index.html/',
            flatten_path('/dog/../dog//./cat/../doc/.///./../doc/index.html/',
                         flatten_slashes=True)
        )

    def test_parse_url_or_log(self):
        self.assertTrue(parse_url_or_log('http://example.com'))
        self.assertFalse(parse_url_or_log('http://'))
