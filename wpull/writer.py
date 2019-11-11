# encoding=utf-8
'''Document writers.'''
# Wpull. Copyright 2013-2015: Christopher Foo and others. License: GPL v3.
import abc
import email.utils
import gettext
import http.client
import itertools
import logging
import os
import re
import shutil
import time

from typing import cast, BinaryIO, Optional

from wpull.backport.logging import StyleAdapter
from wpull.body import Body
from wpull.document.css import CSSReader
from wpull.document.html import HTMLReader
from wpull.path import anti_clobber_dir_path, parse_content_disposition, \
    PathNamer
import wpull.util
from wpull.protocol.abstract.request import BaseRequest, BaseResponse, \
    SerializableMixin
from wpull.protocol.http.request import Response as HTTPResponse
from wpull.protocol.ftp.request import Response as FTPResponse

_ = gettext.gettext
_logger = StyleAdapter(logging.getLogger(__name__))


class BaseWriter(object, metaclass=abc.ABCMeta):
    '''Base class for document writers.'''
    @abc.abstractmethod
    def session(self) -> 'BaseWriterSession':
        '''Return a session for a document.'''


class BaseWriterSession(object, metaclass=abc.ABCMeta):
    '''Base class for a single document to be written.'''
    @abc.abstractmethod
    def process_request(self, request: BaseRequest) -> BaseRequest:
        '''Rewrite the request if needed.

        This function is called by a Processor after it has created the
        Request, but before submitting it to a Client.

        Returns:
            The original Request or a modified Request
        '''

    @abc.abstractmethod
    def process_response(self, response: BaseResponse):
        '''Do any processing using the given response if needed.

        This function is called by a Processor before any response or error
        handling is done.
        '''

    @abc.abstractmethod
    def save_document(self, response: BaseResponse) -> str:
        '''Process and save the document.

        This function is called by a Processor once the Processor deemed
        the document should be saved (i.e., a "200 OK" response).

        Returns:
            The filename of the document.
        '''

    @abc.abstractmethod
    def discard_document(self, response: BaseResponse):
        '''Don't save the document.

        This function is called by a Processor once the Processor deemed
        the document should be deleted (i.e., a "404 Not Found" response).
        '''

    @abc.abstractmethod
    def extra_resource_path(self, suffix: str) -> Optional[str]:
        '''Return a filename suitable for saving extra resources.
        '''


class BaseFileWriterSession(BaseWriterSession):
    '''Base class for File Writer Sessions.'''
    def __init__(self, path_namer: PathNamer,
                 file_continuing: bool,
                 headers_included: bool,
                 local_timestamping: bool,
                 adjust_extension: bool,
                 content_disposition: bool,
                 trust_server_names: bool):
        self._path_namer = path_namer
        self._file_continuing = file_continuing
        self._headers_included = headers_included
        self._local_timestamping = local_timestamping
        self._adjust_extension = adjust_extension
        self._content_disposition = content_disposition
        self._trust_server_names = trust_server_names
        self._filename = None
        self._file_continue_requested = False

    @classmethod
    def open_file(cls, filename: str, response: BaseResponse, mode='wb+'):
        '''Open a file object on to the Response Body.

        Args:
            filename: The path where the file is to be saved
            response: Response
            mode: The file mode

        This function will create the directories if not exist.
        '''
        _logger.debug('Saving file to {0}, mode={1}.',
                      filename, mode)

        dir_path = os.path.dirname(filename)
        if dir_path and not os.path.exists(dir_path):
            os.makedirs(dir_path)

        response.body = Body(open(filename, mode))

    @classmethod
    def set_timestamp(cls, filename: str, response: HTTPResponse):
        '''Set the Last-Modified timestamp onto the given file.

        Args:
            filename: The path of the file
            response: Response
        '''
        last_modified = response.fields.get('Last-Modified')

        if not last_modified:
            return

        try:
            last_modified = email.utils.parsedate(last_modified)
        except ValueError:
            _logger.exception('Failed to parse last-modified date.')
            return

        if last_modified is None:
            # email.utils.parsedate returns None if parsing fails
            _logger.error('Failed to parse last-modified date: {!r} -> None.'.format(response.fields.get('Last-Modified')))
            return

        last_modified = time.mktime(last_modified)

        os.utime(filename, (time.time(), last_modified))

    @classmethod
    def save_headers(cls, filename: str, response: HTTPResponse):
        '''Prepend the HTTP response header to the file.

        Args:
            filename: The path of the file
            response: Response
        '''
        new_filename = filename + '-new'

        with open('wb') as new_file:
            new_file.write(response.header())

            with wpull.util.reset_file_offset(response.body):
                response.body.seek(0)
                shutil.copyfileobj(response.body, new_file)

        os.remove(filename)
        os.rename(new_filename, filename)

    def process_request(self, request: BaseRequest):
        if not self._filename:
            self._filename = self._compute_filename(request)

            if self._file_continuing and self._filename:
                self._process_file_continue_request(request)

        return request

    def _compute_filename(self, request: BaseRequest):
        '''Get the appropriate filename from the request.'''
        path = self._path_namer.get_filename(request.url_info)

        if os.path.isdir(path):
            path += '.f'
        else:
            dir_name, name = os.path.split(path)
            path = os.path.join(anti_clobber_dir_path(dir_name), name)

        return path

    def _process_file_continue_request(self, request: BaseRequest):
        '''Modify the request to resume downloading file.'''
        if os.path.exists(self._filename):
            size = os.path.getsize(self._filename)
            request.set_continue(size)
            self._file_continue_requested = True

            _logger.debug('Continue file from {0}.', size)
        else:
            _logger.debug('No file to continue.')

    def process_response(self, response: BaseResponse):
        if not self._filename:
            return

        if response.request.url_info.scheme == 'ftp':
            response = cast(FTPResponse, response)
            if self._file_continue_requested:
                self._process_file_continue_ftp_response(response)
            else:
                self.open_file(self._filename, response)
        else:
            response = cast(HTTPResponse, response)
            code = response.status_code

            if self._file_continue_requested:
                self._process_file_continue_response(response)
            elif 200 <= code <= 299 or 400 <= code:
                if self._trust_server_names:
                    self._rename_with_last_response(response)

                if self._content_disposition:
                    self._rename_with_content_disposition(response)

                if self._adjust_extension:
                    self._append_filename_extension(response)

                self.open_file(self._filename, response)

    def _process_file_continue_response(self, response: HTTPResponse):
        '''Process a partial content response.'''
        code = response.status_code

        if code == http.client.PARTIAL_CONTENT:
            self.open_file(self._filename, response, mode='ab+')
        else:
            self._raise_cannot_continue_error()

    def _process_file_continue_ftp_response(self, response: FTPResponse):
        '''Process a restarted content response.'''
        if response.request.restart_value and response.restart_value:
            self.open_file(self._filename, response, mode='ab+')
        else:
            self._raise_cannot_continue_error()

    def _raise_cannot_continue_error(self):
        '''Raise an error when server cannot continue a file.'''
        # XXX: I cannot find where wget refuses to resume a file
        # when the server does not support range requests. Wget has
        # enums that appear to define this case, it is checked throughout
        # the code, but the HTTP function doesn't even use them.
        # FIXME: unit test is needed for this case
        raise IOError(
            _('Server not able to continue file download: {filename}.')
            .format(filename=self._filename))

    def _append_filename_extension(self, response: BaseResponse):
        '''Append an HTML/CSS file suffix as needed.'''
        if not self._filename:
            return

        if response.request.url_info.scheme not in ('http', 'https'):
            return

        if not re.search(r'\.[hH][tT][mM][lL]?$', self._filename) and \
                HTMLReader.is_response(response):
            self._filename += '.html'
        elif not re.search(r'\.[cC][sS][sS]$', self._filename) and \
                CSSReader.is_response(response):
            self._filename += '.css'

    def _rename_with_content_disposition(self, response: HTTPResponse):
        '''Rename using the Content-Disposition header.'''
        if not self._filename:
            return

        if response.request.url_info.scheme not in ('http', 'https'):
            return

        header_value = response.fields.get('Content-Disposition')

        if not header_value:
            return

        filename = parse_content_disposition(header_value)

        if filename:
            dir_path = os.path.dirname(self._filename)
            new_filename = self._path_namer.safe_filename(filename)
            self._filename = os.path.join(dir_path, new_filename)

    def _rename_with_last_response(self, response):
        if not self._filename:
            return

        if response.request.url_info.scheme not in ('http', 'https'):
            return

        self._filename = self._compute_filename(response.request)

    def save_document(self, response: BaseResponse):
        if self._filename and os.path.exists(self._filename):
            if self._headers_included:
                self.save_headers(self._filename, response)

            if self._local_timestamping and \
                    response.request.url_info.scheme in ('http', 'https'):
                self.set_timestamp(self._filename, cast(HTTPResponse, response))

            return self._filename

    def discard_document(self, response: BaseResponse):
        if self._filename and os.path.exists(self._filename):
            os.remove(self._filename)

    def extra_resource_path(self, suffix: str) -> str:
        if self._filename:
            return self._filename + suffix


class BaseFileWriter(BaseWriter):
    '''Base class for saving documents to disk.

    Args:
        path_namer: The path namer.
        file_continuing: If True, the writer will modify requests to fetch
            the remaining portion of the file
        headers_included: If True, the writer will include the HTTP header
            responses on top of the document
        local_timestamping: If True, the writer will set the Last-Modified
            timestamp on downloaded files
        adjust_extension: If True, HTML or CSS file extension will be added
            whenever it is detected as so.
        content_disposition: If True, the filename is extracted from
            the Content-Disposition header.
        trust_server_names: If True and there is redirection, use the last
            given response for the filename.
    '''
    def __init__(self, path_namer: PathNamer,
                 file_continuing: bool=False,
                 headers_included: bool=False,
                 local_timestamping: bool=True,
                 adjust_extension: bool=False,
                 content_disposition: bool=False,
                 trust_server_names: bool=False):
        self._path_namer = path_namer
        self._file_continuing = file_continuing
        self._headers_included = headers_included
        self._local_timestamping = local_timestamping
        self._adjust_extension = adjust_extension
        self._content_disposition = content_disposition
        self._trust_server_names = trust_server_names

    @abc.abstractproperty
    def session_class(self) -> object:
        '''Return the class of File Writer Session.

        This should be overridden by subclasses.
        '''

    def session(self) -> BaseFileWriterSession:
        '''Return the File Writer Session.'''
        return self.session_class(
            self._path_namer,
            self._file_continuing,
            self._headers_included,
            self._local_timestamping,
            self._adjust_extension,
            self._content_disposition,
            self._trust_server_names,
        )


class OverwriteFileWriter(BaseFileWriter):
    '''File writer that overwrites files.'''
    @property
    def session_class(self):
        return OverwriteFileWriterSession


class OverwriteFileWriterSession(BaseFileWriterSession):
    pass


class IgnoreFileWriter(BaseFileWriter):
    '''File writer that ignores files that already exist.'''
    @property
    def session_class(self):
        return IgnoreFileWriterSession


class IgnoreFileWriterSession(BaseFileWriterSession):
    def process_request(self, request):
        if not self._filename or not os.path.exists(self._filename):
            return super().process_request(request)


class AntiClobberFileWriter(BaseFileWriter):
    '''File writer that downloads to a new filename if the original exists.'''
    @property
    def session_class(self):
        return AntiClobberFileWriterSession


class AntiClobberFileWriterSession(BaseFileWriterSession):
    def _compute_filename(self, request: BaseRequest):
        original_filename = self._path_namer.get_filename(request.url_info)
        dir_name, filename = os.path.split(original_filename)
        original_filename = os.path.join(
            anti_clobber_dir_path(dir_name), filename
        )
        candidate_filename = original_filename

        for suffix in itertools.count():
            if suffix:
                candidate_filename = '{0}.{1}'.format(original_filename,
                                                      suffix)

            if not os.path.exists(candidate_filename):
                return candidate_filename


class TimestampingFileWriter(BaseFileWriter):
    '''File writer that only downloads newer files from the server.'''
    @property
    def session_class(self) -> BaseFileWriterSession:
        return TimestampingFileWriterSession


class TimestampingFileWriterSession(BaseFileWriterSession):
    def process_request(self, request: BaseRequest):
        request = super().process_request(request)

        orig_file = '{0}.orig'.format(self._filename)

        if os.path.exists(orig_file):
            modified_time = os.path.getmtime(orig_file)
        elif os.path.exists(self._filename):
            modified_time = os.path.getmtime(self._filename)
        else:
            modified_time = None

        _logger.debug('Checking for last modified={0}.', modified_time)

        if modified_time:
            date_str = email.utils.formatdate(modified_time)

            request.fields['If-Modified-Since'] = date_str

        return request


class NullWriterSession(BaseWriterSession):
    def process_request(self, request):
        return request

    def process_response(self, response):
        return response

    def discard_document(self, response):
        pass

    def save_document(self, response):
        pass

    def extra_resource_path(self, suffix):
        pass


class NullWriter(BaseWriter):
    '''File writer that doesn't write files.'''
    def session(self) -> NullWriterSession:
        return NullWriterSession()


class MuxBody(Body):
    '''Writes data into a second file.'''
    def __init__(self, stream: BinaryIO, **kwargs):
        super().__init__(**kwargs)
        self._stream = stream

    def write(self, data: bytes) -> int:
        self._stream.write(data)
        return super().__getattr__('write')(data)

    def writelines(self, lines):
        for line in lines:
            self._stream.write(line)
        return super().__getattr__('writelines')(lines)

    def flush(self):
        self._stream.flush()
        return super().__getattr__('flush')()

    def close(self):
        self._stream.close()
        return super().__getattr__('close')()


class SingleDocumentWriterSession(BaseWriterSession):
    '''Write all data into stream.'''
    def __init__(self, stream: BinaryIO, headers_included: bool):
        self._stream = stream
        self._headers_included = headers_included

    def process_request(self, request):
        return request

    def process_response(self, response: BaseResponse):
        if self._headers_included and isinstance(response, SerializableMixin):
            self._stream.write(response.to_bytes())

        if not self._stream.readable():
            response.body = MuxBody(self._stream)
        else:
            response.body = Body(self._stream)

        return response

    def discard_document(self, response):
        response.body.flush()

    def save_document(self, response):
        response.body.flush()

    def extra_resource_path(self, suffix):
        pass


class SingleDocumentWriter(BaseWriter):
    '''Writer that writes all the data into a single file.'''
    def __init__(self, stream: BinaryIO, headers_included: bool=False):
        self._stream = stream
        self._headers_included = headers_included

    def session(self) -> SingleDocumentWriterSession:
        return SingleDocumentWriterSession(self._stream, self._headers_included)
