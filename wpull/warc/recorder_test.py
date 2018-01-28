import logging
import os.path
import subprocess
import sys
import re
import unittest

from wpull.body import Body
from wpull.database.sqltable import URLTable
from wpull.protocol.http.request import Request as HTTPRequest, Response as HTTPResponse
from wpull.testing.util import TempDirMixin
from wpull.warc.recorder import WARCRecorder, WARCRecorderParams
from wpull.warc.format import WARCRecord
import wpull.util
from wpull.protocol.ftp.request import Request as FTPRequest, Response as FTPResponse, Reply as FTPReply


_logger = logging.getLogger(__name__)


class TestWARC(unittest.TestCase, TempDirMixin):
    def setUp(self):
        self.set_up_temp_dir()

    def tearDown(self):
        self.tear_down_temp_dir()

    def validate_warc(self, filename, ignore_minor_error=False):
        proc = subprocess.Popen(
            [sys.executable, '-m', 'warcat', 'verify', filename],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE
        )

        stdout_data, stderr_data = proc.communicate()

        output = stderr_data + stdout_data
        output = output.decode('utf8', 'replace')

        if not proc.returncode:
            return

        if not ignore_minor_error:
            raise Exception('Validation failed {}'.format(output))
        else:
            if re.search(r'(VerifyProblem:.+ True\))|(.+Error:)', output):
                raise Exception('Validation failed\n{}'.format(output))

    def test_warc_recorder(self):
        file_prefix = 'asdf'
        warc_filename = 'asdf.warc'
        cdx_filename = 'asdf.cdx'

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                extra_fields=[('Extra-field', 'my_extra_field')],
                cdx=True,
            ),
        )

        request = HTTPRequest('http://example.com/')
        request.prepare_for_send()
        request.address = ('0.0.0.0', 80)
        request.prepare_for_send()
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'KITTEH DOGE')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        _logger.info('FINISHED')

        warc_recorder.close()

        with open(warc_filename, 'rb') as in_file:
            warc_file_content = in_file.read()

        with open(cdx_filename, 'rb') as in_file:
            cdx_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo\r\n', warc_file_content)
        self.assertIn(b'Content-Type: application/warc-fields',
                      warc_file_content)
        self.assertIn(b'WARC-Date: ', warc_file_content)
        self.assertIn(b'WARC-Record-ID: <urn:uuid:', warc_file_content)
        self.assertIn(b'WARC-Block-Digest: sha1:', warc_file_content)
        self.assertIn(b'WARC-Payload-Digest: sha1:', warc_file_content)
        self.assertIn(b'WARC-Type: request\r\n', warc_file_content)
        self.assertIn(b'WARC-Target-URI: http://', warc_file_content)
        self.assertIn(b'Content-Type: application/http;msgtype=request',
                      warc_file_content)
        self.assertIn(b'WARC-Type: response', warc_file_content)
        self.assertIn(b'WARC-Concurrent-To: <urn:uuid:', warc_file_content)
        self.assertIn(b'Content-Type: application/http;msgtype=response',
                      warc_file_content)
        self.assertIn(
            'Wpull/{0}'.format(wpull.version.__version__).encode('utf-8'),
            warc_file_content
        )
        self.assertIn(
            'Python/{0}'.format(
                wpull.util.python_version()).encode('utf-8'),
            warc_file_content
        )
        self.assertIn(b'Extra-Field: my_extra_field', warc_file_content)
        self.assertIn(b'GET / HTTP', warc_file_content)
        self.assertIn(b'KITTEH DOGE', warc_file_content)
        self.assertIn(b'FINISHED', warc_file_content)
        self.assertIn(b'WARC-Target-URI: urn:X-wpull:log', warc_file_content)
        self.assertIn(b'Content-Length:', warc_file_content)
        self.assertNotIn(b'Content-Length: 0', warc_file_content)

        cdx_lines = cdx_file_content.split(b'\n')
        cdx_labels = cdx_lines[0].strip().split(b' ')
        cdx_fields = cdx_lines[1].split(b' ')

        print(cdx_lines)

        self.assertEqual(3, len(cdx_lines))
        self.assertEqual(10, len(cdx_labels))
        self.assertEqual(9, len(cdx_fields))
        self.assertTrue(cdx_lines[0].startswith(b' CDX'))

        self.assertEqual(b'http://example.com/', cdx_fields[0])
        self.assertEqual(b'-', cdx_fields[2])
        self.assertEqual(b'200', cdx_fields[3])
        self.assertNotEqual(b'-', cdx_fields[4])
        self.assertNotEqual(b'0', cdx_fields[5])
        self.assertNotEqual(b'0', cdx_fields[6])
        self.assertEqual(
            os.path.basename(warc_filename), cdx_fields[7].decode('ascii'))

        length = int(cdx_fields[5])
        offset = int(cdx_fields[6])

        with open(warc_filename, 'rb') as in_file:
            in_file.seek(offset)
            data = in_file.read(length)

            assert len(data) == length

        self.assertEqual(b'WARC/1.0', data[:8])

        self.assertIn(b'KITTEH DOGE', data)

        self.validate_warc(warc_filename)

    def test_warc_recorder_ftp(self):
        file_prefix = 'asdf'
        warc_filename = 'asdf.warc'

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(compress=False)
        )

        request = FTPRequest('ftp://example.com/example.txt')
        request.address = ('0.0.0.0', 80)
        response = FTPResponse()
        response.reply = FTPReply(200, 'OK')
        response.body = Body()
        response.data_address = ('0.0.0.0', 12345)

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'KITTEH DOGE')

        session = warc_recorder.new_ftp_recorder_session()
        session.begin_control(request)
        session.control_send_data(b'GIMMEH example.txt')
        session.control_receive_data(b'200 OK, no need to yell.')
        session.begin_transfer(response)
        session.transfer_receive_data(b'KITTEH DOGE')
        session.end_transfer(response)
        session.end_control(response)
        session.close()

        warc_recorder.close()

        with open(warc_filename, 'rb') as in_file:
            warc_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo\r\n', warc_file_content)
        self.assertIn(b'Content-Type: application/warc-fields',
                      warc_file_content)
        self.assertIn(b'WARC-Date: ', warc_file_content)
        self.assertIn(b'WARC-Record-ID: <urn:uuid:', warc_file_content)
        self.assertIn(b'WARC-Block-Digest: sha1:', warc_file_content)
        self.assertNotIn(b'WARC-Payload-Digest: sha1:', warc_file_content)
        self.assertIn(b'WARC-Type: resource\r\n', warc_file_content)
        self.assertIn(b'WARC-Target-URI: ftp://', warc_file_content)
        self.assertIn(b'Content-Type: application/octet-stream',
                      warc_file_content)
        self.assertIn(b'WARC-Type: metadata', warc_file_content)
        self.assertIn(b'WARC-Concurrent-To: <urn:uuid:', warc_file_content)
        self.assertIn(b'Content-Type: text/x-ftp-control-conversation',
                      warc_file_content)
        self.assertIn(
            'Wpull/{0}'.format(wpull.version.__version__).encode('utf-8'),
            warc_file_content
        )
        self.assertIn(
            'Python/{0}'.format(
                wpull.util.python_version()).encode('utf-8'),
            warc_file_content
        )
        self.assertIn(b'KITTEH DOGE', warc_file_content)
        self.assertIn(b'* Opening control connection to', warc_file_content)
        self.assertIn(b'* Kept control connection to', warc_file_content)
        self.assertIn(b'* Opened data connection to ', warc_file_content)
        self.assertIn(b'* Closed data connection to ', warc_file_content)
        self.assertIn(b'> GIMMEH example.txt', warc_file_content)
        self.assertIn(b'< 200 OK, no need to yell.', warc_file_content)

        # Ignore Concurrent Record ID not seen yet
        self.validate_warc(warc_filename, ignore_minor_error=True)

        with open(warc_filename, 'r+b') as in_file:
            # Intentionally modify the contents
            in_file.seek(355)
            in_file.write(b'f')

        with self.assertRaises(Exception):
            # Sanity check that it actually raises error on bad digest
            self.validate_warc(warc_filename, ignore_minor_error=True)

    def test_warc_recorder_max_size(self):
        file_prefix = 'asdf'
        cdx_filename = 'asdf.cdx'

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                extra_fields=[('Extra-field', 'my_extra_field')],
                cdx=True, max_size=1,
            )
        )

        request = HTTPRequest('http://example.com/1')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'KITTEH DOGE')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        request = HTTPRequest('http://example.com/2')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'DOGE KITTEH')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        _logger.info('FINISHED')

        warc_recorder.close()

        with open('asdf-00000.warc', 'rb') as in_file:
            warc_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo', warc_file_content)
        self.assertIn(b'KITTEH DOGE', warc_file_content)

        with open('asdf-00001.warc', 'rb') as in_file:
            warc_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo', warc_file_content)
        self.assertIn(b'DOGE KITTEH', warc_file_content)

        with open(cdx_filename, 'rb') as in_file:
            cdx_file_content = in_file.read()

        cdx_lines = cdx_file_content.split(b'\n')
        cdx_labels = cdx_lines[0].strip().split(b' ')

        print(cdx_lines)

        self.assertEqual(4, len(cdx_lines))
        self.assertEqual(10, len(cdx_labels))

        self.assertIn(b'http://example.com/1', cdx_file_content)
        self.assertIn(b'http://example.com/2', cdx_file_content)

        with open('asdf-meta.warc', 'rb') as in_file:
            meta_file_content = in_file.read()

        self.assertIn(b'FINISHED', meta_file_content)

        self.validate_warc('asdf-00000.warc')
        self.validate_warc('asdf-00001.warc')
        self.validate_warc('asdf-meta.warc')

    def test_warc_recorder_max_size_split_meta(self):
        file_prefix = 'asdf'
        cdx_filename = 'asdf.cdx'

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                extra_fields=[('Extra-field', 'my_extra_field')],
                cdx=True, max_size=1,
                split_meta = True,
            )
        )

        # This produces three data and meta WARCs (00000 to 00002). The reason being that a new WARC is started after the second request.
        # That last WARC does not contain any data, but the third meta WARC contains the "FINISHED" log message.

        _logger.info('Fetching http://example.com/1')
        request = HTTPRequest('http://example.com/1')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'KITTEH DOGE')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        _logger.info('Fetched http://example.com/1') # Note, the normal "Fetched" log message is also emitted before the session is closed. Otherwise, it'd end up in the next meta WARC.
        session.close()

        _logger.info('Fetching http://example.com/2')
        request = HTTPRequest('http://example.com/2')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'DOGE KITTEH')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        _logger.info('Fetched http://example.com/2')
        session.close()

        _logger.info('FINISHED')

        warc_recorder.close()

        self.assertTrue(os.path.exists('asdf-00000.warc'))
        self.assertTrue(os.path.exists('asdf-00001.warc'))
        self.assertTrue(os.path.exists('asdf-00002.warc'))
        self.assertTrue(os.path.exists('asdf-00000-meta.warc'))
        self.assertTrue(os.path.exists('asdf-00001-meta.warc'))
        self.assertTrue(os.path.exists('asdf-00002-meta.warc'))
        self.assertTrue(os.path.exists(cdx_filename))

        with open('asdf-00000.warc', 'rb') as in_file:
            warc_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo', warc_file_content)
        self.assertIn(b'KITTEH DOGE', warc_file_content)

        with open('asdf-00001.warc', 'rb') as in_file:
            warc_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo', warc_file_content)
        self.assertIn(b'DOGE KITTEH', warc_file_content)

        with open('asdf-00002.warc', 'rb') as in_file:
            warc_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: warcinfo', warc_file_content)
        self.assertNotIn(b'WARC-Type: re', warc_file_content) # No request or response

        with open(cdx_filename, 'rb') as in_file:
            cdx_file_content = in_file.read()

        cdx_lines = cdx_file_content.split(b'\n')
        cdx_labels = cdx_lines[0].strip().split(b' ')

        print(cdx_lines)

        self.assertEqual(4, len(cdx_lines))
        self.assertEqual(10, len(cdx_labels))

        self.assertIn(b'http://example.com/1', cdx_file_content)
        self.assertIn(b'http://example.com/2', cdx_file_content)

        with open('asdf-00000-meta.warc', 'rb') as in_file:
            meta_file_content = in_file.read()

        self.assertIn(b'Fetching http://example.com/1', meta_file_content)
        self.assertIn(b'Fetched http://example.com/1', meta_file_content)
        self.assertNotIn(b'http://example.com/2', meta_file_content)
        self.assertNotIn(b'FINISHED', meta_file_content)

        with open('asdf-00001-meta.warc', 'rb') as in_file:
            meta_file_content = in_file.read()

        self.assertNotIn(b'http://example.com/1', meta_file_content)
        self.assertIn(b'Fetching http://example.com/2', meta_file_content)
        self.assertIn(b'Fetched http://example.com/2', meta_file_content)
        self.assertNotIn(b'FINISHED', meta_file_content)

        with open('asdf-00002-meta.warc', 'rb') as in_file:
            meta_file_content = in_file.read()

        self.assertIn(b'FINISHED', meta_file_content)

        self.validate_warc('asdf-00000.warc')
        self.validate_warc('asdf-00001.warc')
        self.validate_warc('asdf-00002.warc')
        self.validate_warc('asdf-00000-meta.warc')
        self.validate_warc('asdf-00001-meta.warc')
        self.validate_warc('asdf-00002-meta.warc')

    def test_warc_recorder_rollback(self):
        warc_filename = 'asdf.warc'
        warc_prefix = 'asdf'

        with open(warc_filename, 'wb') as warc_file:
            warc_file.write(b'a' * 10)

        warc_recorder = WARCRecorder(
            warc_prefix,
            params=WARCRecorderParams(
                compress=False,
            )
        )

        request = HTTPRequest('http://example.com/')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'KITTEH DOGE')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())

        class BadRecord(WARCRecord):
            def __init__(self, original_record):
                super().__init__()
                self.block_file = original_record.block_file
                self.fields = original_record.fields

            def __iter__(self):
                for dummy in range(1000):
                    yield b"where's my elephant?"
                raise OSError('Oops')

        session._request_record = BadRecord(session._request_record)
        original_offset = os.path.getsize(warc_filename)

        with self.assertRaises((OSError, IOError)):
            session.end_request(request)

        new_offset = os.path.getsize(warc_filename)
        self.assertEqual(new_offset, original_offset)
        self.assertFalse(os.path.exists(warc_filename + '-wpullinc'))

        _logger.debug('original offset {0}'.format(original_offset))

    def test_warc_recorder_journal(self):
        warc_filename = 'asdf.warc'
        warc_prefix = 'asdf'

        warc_recorder = WARCRecorder(
            warc_prefix,
            params=WARCRecorderParams(
                compress=False,
            )
        )

        request = HTTPRequest('http://example.com/')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'KITTEH DOGE')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        test_instance = self

        class MockRecord(WARCRecord):
            def __init__(self, original_record):
                super().__init__()
                self.block_file = original_record.block_file
                self.fields = original_record.fields

            def __iter__(self):
                print(list(os.walk('.')))
                test_instance.assertTrue(
                    os.path.exists(warc_filename + '-wpullinc')
                )

                for dummy in range(1000):
                    yield b"where's my elephant?"

        session._request_record = MockRecord(session._request_record)

        session.end_request(request)

        self.assertFalse(os.path.exists(warc_filename + '-wpullinc'))

    def test_warc_recorder_journal_raise_error(self):
        warc_filename = 'asdf.warc'
        warc_prefix = 'asdf'

        with open(warc_filename + '-wpullinc', 'w'):
            pass

        with self.assertRaises(OSError):
            WARCRecorder(
                warc_prefix,
                params=WARCRecorderParams(
                    compress=False,
                )
            )

    def test_cdx_dedup(self):
        url_table = URLTable()
        warc_recorder = WARCRecorder(
            'asdf',
            params=WARCRecorderParams(
                compress=False, cdx=True, url_table=url_table
            )
        )

        url_table.add_visits([
            (
                'http://example.com/fennec',
                '<urn:uuid:8a534d31-bd06-4056-8a0f-bdc5fd611036>',
                'B62D734VFEKIDLFAB7TTSCSZF64BKAYJ'
            )
        ])

        request = HTTPRequest('http://example.com/fennec')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()
        revisit_response_header_size = len(response.to_bytes())

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'kitbit')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        request = HTTPRequest('http://example.com/horse')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OKaaaaaaaaaaaaaaaaaaaaaaaaaa')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'kitbit')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        _logger.info('FINISHED')

        warc_recorder.close()

        with open('asdf.warc', 'rb') as in_file:
            warc_file_content = in_file.read()

        with open('asdf.cdx', 'rb') as in_file:
            cdx_file_content = in_file.read()

        self.assertTrue(warc_file_content.startswith(b'WARC/1.0'))
        self.assertIn(b'WARC-Type: revisit\r\n', warc_file_content)
        self.assertIn(
            b'WARC-Refers-To: '
            b'<urn:uuid:8a534d31-bd06-4056-8a0f-bdc5fd611036>\r\n',
            warc_file_content
        )
        self.assertIn(b'WARC-Truncated: length\r\n', warc_file_content)
        self.assertIn(
            b'WARC-Profile: http://netpreserve.org/warc/1.0/revisit/'
            b'identical-payload-digest\r\n',
            warc_file_content
        )
        self.assertIn(
            b'Content-Length: ' +
            str(revisit_response_header_size).encode('ascii') + b'\r\n',
            warc_file_content
        )
        self.assertIn(
            b'WARC-Target-URI: http://example.com/fennec\r\n',
            warc_file_content
        )
        self.assertIn(
            b'WARC-Target-URI: http://example.com/horse\r\n', warc_file_content
        )
        self.assertEqual(
            1,
            warc_file_content.count(b'kitbit')
        )

        self.assertIn(b'http://example.com/horse ', cdx_file_content)

    def test_warc_move(self):
        file_prefix = 'asdf'
        warc_filename = 'asdf.warc'
        cdx_filename = 'asdf.cdx'

        os.mkdir('./blah/')

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                cdx=True,
                move_to='./blah/'
            ),
        )

        warc_recorder.close()

        self.assertTrue(os.path.exists('./blah/' + warc_filename))
        self.assertTrue(os.path.exists('./blah/' + cdx_filename))

    def test_warc_move_max_size(self):
        file_prefix = 'asdf'
        cdx_filename = 'asdf.cdx'

        os.mkdir('./blah/')

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                cdx=True,
                move_to='./blah/',
                max_size=1,
            ),
        )

        request = HTTPRequest('http://example.com/1')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'BLAH')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        warc_recorder.close()

        self.assertTrue(os.path.exists('./blah/asdf-00000.warc'))
        self.assertTrue(os.path.exists('./blah/asdf-00001.warc'))
        self.assertTrue(os.path.exists('./blah/asdf-meta.warc'))
        self.assertTrue(os.path.exists('./blah/' + cdx_filename))

    def test_warc_move_max_size_split_meta(self):
        file_prefix = 'asdf'
        cdx_filename = 'asdf.cdx'

        os.mkdir('./blah/')

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                cdx=True,
                move_to='./blah/',
                max_size=1,
                split_meta = True,
            ),
        )

        request = HTTPRequest('http://example.com/1')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'BLAH')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        warc_recorder.close()

        self.assertTrue(os.path.exists('./blah/asdf-00000.warc'))
        self.assertTrue(os.path.exists('./blah/asdf-00001.warc'))
        self.assertTrue(os.path.exists('./blah/asdf-00000-meta.warc'))
        self.assertTrue(os.path.exists('./blah/asdf-00001-meta.warc'))
        self.assertTrue(os.path.exists('./blah/' + cdx_filename))

    def test_warc_max_size_and_append(self):
        file_prefix = 'asdf'

        with open('asdf-00000.warc', 'w'):
            pass

        with open('asdf-00001.warc', 'w'):
            pass

        warc_recorder = WARCRecorder(
            file_prefix,
            params=WARCRecorderParams(
                compress=False,
                max_size=1,
                appending=True
            ),
        )

        request = HTTPRequest('http://example.com/1')
        request.address = ('0.0.0.0', 80)
        response = HTTPResponse(200, 'OK')
        response.body = Body()

        with wpull.util.reset_file_offset(response.body):
            response.body.write(b'BLAH')

        session = warc_recorder.new_http_recorder_session()
        session.begin_request(request)
        session.request_data(request.to_bytes())
        session.end_request(request)
        session.begin_response(response)
        session.response_data(response.to_bytes())
        session.response_data(response.body.content())
        session.end_response(response)
        session.close()

        warc_recorder.close()

        self.assertTrue(os.path.exists('asdf-00000.warc'))
        self.assertTrue(os.path.exists('asdf-00001.warc'))
        self.assertTrue(os.path.exists('asdf-00002.warc'))
        self.assertTrue(os.path.exists('asdf-00003.warc'))
        self.assertTrue(os.path.exists('asdf-meta.warc'))

        self.assertEqual(0, os.path.getsize('asdf-00000.warc'))
        self.assertEqual(0, os.path.getsize('asdf-00001.warc'))
        self.assertNotEqual(0, os.path.getsize('asdf-00002.warc'))
        self.assertNotEqual(0, os.path.getsize('asdf-00003.warc'))
        self.assertNotEqual(0, os.path.getsize('asdf-meta.warc'))
