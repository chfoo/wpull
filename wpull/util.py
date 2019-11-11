# encoding=utf-8
'''Miscellaneous functions.'''
import calendar
import codecs
import contextlib
import datetime
import gzip
import os.path
import platform
import re
import sys
import time
import zipfile
import pickle
from itertools import zip_longest

IS_PYPY = platform.python_implementation() == 'PyPy'


class ASCIIStreamWriter(codecs.StreamWriter):
    '''A Stream Writer that encodes everything to ASCII.

    By default, the replacement character is a Python backslash sequence.
    '''
    DEFAULT_ERROR = 'backslashreplace'

    def __init__(self, stream, errors=DEFAULT_ERROR):
        codecs.StreamWriter.__init__(self, stream, errors)

    def encode(self, instance, errors=DEFAULT_ERROR):
        return instance.encode('ascii', errors)

    def decode(self, instance, errors=DEFAULT_ERROR):
        return instance.encode('ascii', errors)

    def write(self, instance):
        if hasattr(instance, 'encode'):
            instance = instance.encode('ascii', self.errors)

        if hasattr(instance, 'decode'):
            instance = instance.decode('ascii', self.errors)

        self.stream.write(instance)

    def writelines(self, list_instance):
        for item in list_instance:
            self.write(item)


@contextlib.contextmanager
def reset_file_offset(file):
    '''Reset the file offset back to original position.'''
    offset = file.tell()
    yield
    file.seek(offset)


def peek_file(file, length=4096):
    '''Peek the file by calling ``read`` on it.'''
    with reset_file_offset(file):
        return file.read(length)


def seek_file_end(file):
    '''Seek to the end of the file.'''
    try:
        file.seek(0, 2)
    except ValueError:
        # gzip files don't support seek from end
        while True:
            data = file.read(4096)
            if not data:
                break


def datetime_str():
    '''Return the current time in simple ISO8601 notation.'''
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def parse_iso8601_str(string):
    '''Parse a fixed ISO8601 datetime string.

    .. Note:: This function only parses dates in the format
       ``%Y-%m-%dT%H:%M:%SZ``. You must use a library like ``dateutils``
       to properly parse dates and times.

    Returns:
        float: A UNIX timestamp.
    '''
    datetime_obj = datetime.datetime.strptime(string, "%Y-%m-%dT%H:%M:%SZ")
    return int(calendar.timegm(datetime_obj.utctimetuple()))


def python_version():
    '''Return the Python version as a string.'''
    major, minor, patch = sys.version_info[0:3]
    return '{0}.{1}.{2}'.format(major, minor, patch)


def filter_pem(data):
    '''Processes the bytes for PEM certificates.

    Returns:
        ``set`` containing each certificate
    '''
    assert isinstance(data, bytes), 'Expect bytes. Got {}.'.format(type(data))
    certs = set()
    new_list = []
    in_pem_block = False

    for line in re.split(br'[\r\n]+', data):
        if line == b'-----BEGIN CERTIFICATE-----':
            assert not in_pem_block
            in_pem_block = True
        elif line == b'-----END CERTIFICATE-----':
            assert in_pem_block
            in_pem_block = False

            content = b''.join(new_list)
            content = rewrap_bytes(content)

            certs.add(b'-----BEGIN CERTIFICATE-----\n' +
                      content +
                      b'\n-----END CERTIFICATE-----\n')

            new_list = []
        elif in_pem_block:
            new_list.append(line)

    return certs


def rewrap_bytes(data):
    '''Rewrap characters to 70 character width.

    Intended to rewrap base64 content.
    '''
    return b'\n'.join(
        data[index:index+70] for index in range(0, len(data), 70)
    )


def truncate_file(path):
    '''Truncate the file.'''
    with open(path, 'wb'):
        pass


def get_package_data(filename, mode='rb'):
    '''Return the contents of a real file or a zip file.'''
    if os.path.exists(filename):
        with open(filename, mode=mode) as in_file:
            return in_file.read()
    else:
        parts = os.path.normpath(filename).split(os.sep)

        for part, index in zip(parts, range(len(parts))):
            if part.endswith('.zip'):
                zip_path = os.sep.join(parts[:index + 1])
                member_path = os.sep.join(parts[index + 1:])
                break

        if platform.system() == 'Windows':
            member_path = member_path.replace('\\', '/')

        with zipfile.ZipFile(zip_path) as zip_file:
            return zip_file.read(member_path)


def get_package_filename(filename, package_dir=None):
    '''Return the filename of the data file.'''
    if getattr(sys, 'frozen', False):
        package_dir = os.path.join(
            sys._MEIPASS,
            os.path.basename(os.path.dirname(__file__))
        )
    elif not package_dir:
        package_dir = os.path.dirname(__file__)

    return os.path.join(package_dir, filename)


def is_ascii(text):
    '''Returns whether the given string is ASCII.'''
    try:
        text.encode('ascii', 'strict')
    except UnicodeError:
        return False
    else:
        return True


@contextlib.contextmanager
def close_on_error(close_func):
    '''Context manager to close object on error.'''
    try:
        yield
    except Exception as error:
        if not isinstance(error, StopIteration):
            close_func()
        raise


class PickleStream(object):
    '''Pickle stream helper.'''
    def __init__(self, filename=None, file=None, mode='rb',
                 protocol=pickle.DEFAULT_PROTOCOL):
        if file:
            self._file = file
        else:
            self._file = open(filename, mode)

        self._protocol = protocol

    def dump(self, obj):
        '''Pickle an object.'''
        pickle.dump(obj, self._file, protocol=self._protocol)

    def load(self):
        '''Unpickle an object.'''
        return pickle.load(self._file)

    def iter_load(self):
        '''Unpickle objects.'''
        while True:
            try:
                yield pickle.load(self._file)
            except EOFError:
                break

    def close(self):
        '''Close stream.'''
        self._file.close()


class GzipPickleStream(PickleStream):
    '''gzip compressed pickle stream.'''
    def __init__(self, filename=None, file=None, mode='rb', **kwargs):
        if file:
            self._gzip_file = gzip.GzipFile(fileobj=file, mode=mode)
        else:
            self._gzip_file = gzip.GzipFile(filename, mode=mode)

        super().__init__(file=self._gzip_file, mode=mode, **kwargs)

    def close(self):
        self._gzip_file.close()
        super().close()


def grouper(iterable, n, fillvalue=None):
    "Collect data into fixed-length chunks or blocks"
    # grouper('ABCDEFG', 3, 'x') --> ABC DEF Gxx"
    args = [iter(iterable)] * n
    return zip_longest(*args, fillvalue=fillvalue)
