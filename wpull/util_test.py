# encoding=utf-8
import os
import sys
import tempfile
import unittest
from dns.resolver import NoNameservers

from wpull.util import (datetime_str, python_version, filter_pem,
                        parse_iso8601_str, is_ascii, close_on_error,
                        GzipPickleStream)


DEFAULT_TIMEOUT = 30


class TestUtil(unittest.TestCase):
    def test_datetime_str(self):
        self.assertEqual(20, len(datetime_str()))

    def test_parse_iso8601_str(self):
        self.assertEqual(10, parse_iso8601_str('1970-01-01T00:00:10Z'))

    def test_python_version(self):
        version_string = python_version()
        nums = tuple([int(n) for n in version_string.split('.')])
        self.assertEqual(3, len(nums))
        self.assertEqual(nums, sys.version_info[0:3])

    def test_filter_pem(self):
        unclean = (b'Kitten\n'
                   b'-----BEGIN CERTIFICATE-----\n'
                   b'ABCDEFG\n'
                   b'-----END CERTIFICATE-----\n'
                   b'Puppy\n'
                   b'-----BEGIN CERTIFICATE-----\n'
                   b'QWERTY\n'
                   b'-----END CERTIFICATE-----\n'
                   b'Kit\n')
        clean = {
            (
                b'-----BEGIN CERTIFICATE-----\n'
                b'ABCDEFG\n'
                b'-----END CERTIFICATE-----\n'
            ),
            (
                b'-----BEGIN CERTIFICATE-----\n'
                b'QWERTY\n'
                b'-----END CERTIFICATE-----\n'
            )
        }

        self.assertEqual(clean, filter_pem(unclean))

    def test_is_acsii(self):
        self.assertTrue(is_ascii('abc'))
        self.assertFalse(is_ascii('😤'))

    def test_close_on_error(self):
        class MyObject(object):
            def __init__(self):
                self.closed = False

            def close(self):
                self.closed = True

            def oops(self):
                with close_on_error(self.close):
                    raise ValueError()

        my_object = MyObject()
        self.assertRaises(ValueError, my_object.oops)
        self.assertTrue(my_object.closed)

    def test_pickle_stream_filename(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, 'blah.pickle')
            stream = GzipPickleStream(filename, mode='wb')

            for num in range(10):
                stream.dump(num)

            stream = GzipPickleStream(filename, mode='rb')

            for num, obj in enumerate(stream.iter_load()):
                self.assertEqual(num, obj)

    def test_pickle_stream_file_obj(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            filename = os.path.join(temp_dir, 'blah.pickle')
            file = open(filename, mode='wb+')

            stream = GzipPickleStream(file=file, mode='wb')

            for num in range(10):
                stream.dump(num)

            stream = GzipPickleStream(file=file, mode='rb')

            for num, obj in enumerate(stream.iter_load()):
                self.assertEqual(num, obj)

