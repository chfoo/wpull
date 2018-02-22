'''URL parsing based on WHATWG URL living standard.'''
import collections
import fnmatch
import functools
import gettext
import ipaddress
import logging
import re
import string
import urllib.parse
import posixpath

from wpull.backport.logging import BraceMessage as __
import wpull.string


_logger = logging.getLogger(__name__)
_ = gettext.gettext


RELATIVE_SCHEME_DEFAULT_PORTS = {
    'ftp': 21,
    'gopher': 70,
    'http': 80,
    'https': 443,
    'ws': 80,
    'wss': 443,
}

SPECIAL_SCHEMES = ['ftp', 'file', 'gopher', 'http', 'https', 'ws', 'wss']
'''Special schemes as defined by the URL Standard'''

C0_CONTROL_SET = frozenset(chr(i) for i in range(0, 0x1f + 1))
'''Characters from 0x00 to 0x1f inclusive'''

DEFAULT_ENCODE_SET = frozenset(b' "#<>?`')
'''Percent encoding set as defined by WHATWG URL living standard.

Does not include U+0000 to U+001F nor U+001F or above.
'''

PASSWORD_ENCODE_SET = DEFAULT_ENCODE_SET | frozenset(b'/@\\')
'''Encoding set for passwords.'''

USERNAME_ENCODE_SET = PASSWORD_ENCODE_SET | frozenset(b':')
'''Encoding set for usernames.'''

QUERY_ENCODE_SET = frozenset(b'"#<>`')
'''Encoding set for query strings.

This set does not include U+0020 (space) so it can be replaced with
U+0043 (plus sign) later.
'''

FRAGMENT_ENCODE_SET = frozenset(b' "<>`')
'''Encoding set for fragment.'''

QUERY_VALUE_ENCODE_SET = QUERY_ENCODE_SET | frozenset(b'&+%')
'''Encoding set for a query value.'''

FORBIDDEN_HOSTNAME_CHARS = frozenset('#%/:?@[\\] ')
'''Forbidden hostname characters.

Does not include non-printing characters. Meant for ASCII.
'''


class URLInfo(object):
    '''Represent parts of a URL.

    Attributes:
        raw (str): Original string.
        scheme (str): Protocol (for example, HTTP, FTP).
        authority (str): Raw userinfo and host.
        path (str): Location of resource. This value always
            begins with a slash (``/``).
        query (str): Additional request parameters.
        fragment (str): Named anchor of a document.
        userinfo (str): Raw username and password.
        username (str): Username.
        password (str): Password.
        host (str): Raw hostname and port.
        hostname (str): Hostname or IP address.
        port (int): IP address port number.
        resource (int): Raw path, query, and fragment. This value always
            begins with a slash (``/``).
        query_map (dict): Mapping of the query. Values are lists.
        url (str): A normalized URL without userinfo and fragment.
        encoding (str): Codec name for IRI support.

    If scheme is not something like HTTP or FTP, the remaining attributes
    are None.

    All attributes are read only.

    For more information about how the URL parts are derived, see
    https://medialize.github.io/URI.js/about-uris.html
    '''

    __slots__ = ('raw', 'scheme', 'authority', 'path', 'query', 'fragment',
                 'userinfo', 'username', 'password',
                 'host', 'hostname', 'port',
                 'resource',
                 '_query_map', '_url', 'encoding',
                 )

    def __init__(self):
        self.raw = None
        self.scheme = None
        self.authority = None
        self.path = None
        self.query = None
        self.fragment = None
        self.userinfo = None
        self.username = None
        self.password = None
        self.host = None
        self.hostname = None
        self.port = None
        self.resource = None
        self._query_map = None
        self._url = None
        self.encoding = None

    @classmethod
    @functools.lru_cache()
    def parse(cls, url, default_scheme='http', encoding='utf-8'):
        '''Parse a URL and return a URLInfo.'''
        if url is None:
            return None

        url = url.strip()
        # TODO: \r\n\t should be removed from anywhere in the URL.
        if frozenset(url) & C0_CONTROL_SET:
            raise ValueError('URL contains control codes: {}'.format(ascii(url)))

        scheme, sep, remaining = url.partition(':')

        if not scheme:
            raise ValueError('URL missing scheme: {}'.format(ascii(url)))

        scheme = scheme.lower()

        if not sep and default_scheme:
            # Likely something like example.com/mystuff
            remaining = url
            scheme = default_scheme
        elif not sep:
            raise ValueError('URI missing colon: {}'.format(ascii(url)))

        if default_scheme and '.' in scheme or scheme == 'localhost':
            # Maybe something like example.com:8080/mystuff or
            # maybe localhost:8080/mystuff
            remaining = '{}:{}'.format(scheme, remaining)
            scheme = default_scheme

        info = URLInfo()
        info.encoding = encoding

        if scheme not in RELATIVE_SCHEME_DEFAULT_PORTS:
            info.raw = url
            info.scheme = scheme
            info.path = remaining

            return info

        if remaining.startswith('//'):
            remaining = remaining[2:]

        path_index = remaining.find('/')
        path_backslash_index = remaining.find('\\')
        query_index = remaining.find('?')
        fragment_index = remaining.find('#')

        try:
            index_tuple = (path_index, path_backslash_index, query_index, fragment_index)
            authority_index = min(num for num in index_tuple if num >= 0)
        except ValueError:
            authority_index = len(remaining)

        authority = remaining[:authority_index]
        resource = remaining[authority_index:]

        try:
            index_tuple = (query_index, fragment_index)
            path_index = min(num for num in index_tuple if num >= 0)
        except ValueError:
            path_index = len(remaining)

        path = remaining[authority_index + 1:path_index] or '/'

        if scheme in SPECIAL_SCHEMES:
            # Backslashes in the path of special URLs are treated like slashes
            # except they cause a validation error, which is ignored.
            path = path.replace('\\', '/')

        if fragment_index >= 0:
            query_index = fragment_index
        else:
            query_index = len(remaining)

        query = remaining[path_index + 1:query_index]
        fragment = remaining[query_index + 1:]

        userinfo, host = cls.parse_authority(authority)
        hostname, port = cls.parse_host(host)
        username, password = cls.parse_userinfo(userinfo)

        if not hostname:
            raise ValueError('Hostname is empty: {}'.format(ascii(url)))

        info.raw = url
        info.scheme = scheme
        info.authority = authority
        info.path = normalize_path(path, encoding=encoding)
        info.query = normalize_query(query, encoding=encoding)
        info.fragment = normalize_fragment(fragment, encoding=encoding)

        info.userinfo = userinfo
        info.username = percent_decode(username, encoding=encoding)
        info.password = percent_decode(password, encoding=encoding)

        info.host = host
        info.hostname = hostname
        info.port = port or RELATIVE_SCHEME_DEFAULT_PORTS[scheme]

        info.resource = resource

        return info

    @classmethod
    def parse_authority(cls, authority):
        '''Parse the authority part and return userinfo and host.'''
        userinfo, sep, host = authority.partition('@')

        if not sep:
            return '', userinfo
        else:
            return userinfo, host

    @classmethod
    def parse_userinfo(cls, userinfo):
        '''Parse the userinfo and return username and password.'''
        username, sep, password = userinfo.partition(':')

        return username, password

    @classmethod
    def parse_host(cls, host):
        '''Parse the host and return hostname and port.'''
        if host.endswith(']'):
            return cls.parse_hostname(host), None
        else:
            hostname, sep, port = host.rpartition(':')

        if sep:
            if port != '':
                port = int(port)
                if port < 0 or port > 65535:
                    raise ValueError('Port number invalid')
        else:
            hostname = port
            port = None

        return cls.parse_hostname(hostname), port

    @classmethod
    def parse_hostname(cls, hostname):
        '''Parse the hostname and normalize.'''
        if hostname.startswith('['):
            return cls.parse_ipv6_hostname(hostname)
        else:
            try:
                new_hostname = normalize_ipv4_address(hostname)
            except ValueError:
                # _logger.debug('', exc_info=True)
                new_hostname = hostname

            new_hostname = normalize_hostname(new_hostname)

            if any(char in new_hostname for char in FORBIDDEN_HOSTNAME_CHARS):
                raise ValueError('Invalid hostname: {}'
                                 .format(ascii(hostname)))

            return new_hostname

    @classmethod
    def parse_ipv6_hostname(cls, hostname):
        '''Parse and normalize a IPv6 address.'''
        if not hostname.startswith('[') or not hostname.endswith(']'):
            raise ValueError('Invalid IPv6 address: {}'
                             .format(ascii(hostname)))

        hostname = ipaddress.IPv6Address(hostname[1:-1]).compressed

        return hostname

    @property
    def query_map(self):
        if self._query_map is None:
            self._query_map = query_to_map(self.query)
        return self._query_map

    @property
    def url(self):
        if self._url is None:
            if self.scheme not in RELATIVE_SCHEME_DEFAULT_PORTS:
                self._url = self.raw
                return self._url

            parts = [self.scheme, '://']

            if self.username:
                parts.append(normalize_username(self.username))

            if self.password:
                parts.append(':')
                parts.append(normalize_password(self.password))

            if self.username or self.password:
                parts.append('@')

            if self.is_ipv6():
                parts.append('[{}]'.format(self.hostname))
            else:
                parts.append(self.hostname)

            if RELATIVE_SCHEME_DEFAULT_PORTS[self.scheme] != self.port:
                parts.append(':{}'.format(self.port))

            parts.append(self.path)

            if self.query:
                parts.append('?')
                parts.append(self.query)

            self._url = ''.join(parts)

        return self._url

    def to_dict(self):
        '''Return a dict of the attributes.'''
        return dict(
            raw=self.raw,
            scheme=self.scheme,
            authority=self.authority,
            netloc=self.authority,
            path=self.path,
            query=self.query,
            fragment=self.fragment,
            userinfo=self.userinfo,
            username=self.username,
            password=self.password,
            host=self.host,
            hostname=self.hostname,
            port=self.port,
            resource=self.resource,
            url=self.url,
            encoding=self.encoding,
        )

    def is_port_default(self):
        '''Return whether the URL is using the default port.'''
        if self.scheme in RELATIVE_SCHEME_DEFAULT_PORTS:
            return RELATIVE_SCHEME_DEFAULT_PORTS[self.scheme] == self.port

    def is_ipv6(self):
        '''Return whether the URL is IPv6.'''
        if self.host:
            return self.host.startswith('[')

    @property
    def hostname_with_port(self):
        '''Return the host portion but omit default port if needed.'''
        default_port = RELATIVE_SCHEME_DEFAULT_PORTS.get(self.scheme)
        if not default_port:
            return ''

        assert '[' not in self.hostname
        assert ']' not in self.hostname

        if self.is_ipv6():
            hostname = '[{}]'.format(self.hostname)
        else:
            hostname = self.hostname

        if default_port != self.port:
            return '{}:{}'.format(hostname, self.port)
        else:
            return hostname

    def split_path(self):
        '''Return the directory and filename from the path.

        The results are not percent-decoded.
        '''
        return posixpath.split(self.path)

    def __repr__(self):
        return '<URLInfo at 0x{:x} url={} raw={}>'.format(
            id(self), self.url, self.raw)

    def __hash__(self):
        return hash(self.raw)

    def __eq__(self, other):
        return self.raw == other.raw

    def __ne__(self, other):
        return self.raw != other.raw


def parse_url_or_log(url, encoding='utf-8'):
    '''Parse and return a URLInfo.

    This function logs a warning if the URL cannot be parsed and returns
    None.
    '''
    try:
        url_info = URLInfo.parse(url, encoding=encoding)
    except ValueError as error:
        _logger.warning(__(
            _('Unable to parse URL ‘{url}’: {error}.'),
            url=wpull.string.printable_str(url), error=error))
    else:
        return url_info


def normalize(url, **kwargs):
    '''Normalize a URL.

    This function is a convenience function that is equivalent to::

        >>> URLInfo.parse('http://example.com').url
        'http://example.com'

    :seealso: :func:`URLInfo.parse`.
    '''
    return URLInfo.parse(url, **kwargs).url


@functools.lru_cache()
def normalize_hostname(hostname):
    '''Normalizes a hostname so that it is ASCII and valid domain name.'''
    try:
        new_hostname = hostname.encode('idna').decode('ascii').lower()
    except UnicodeError as error:
        raise UnicodeError('Hostname {} rejected: {}'.format(hostname, error)) from error

    if hostname != new_hostname:
        # Check for round-trip. May raise UnicodeError
        new_hostname.encode('idna')

    return new_hostname


def parse_ipv4_int(text):
    if text.startswith('0x'):
        base = 16
    elif text.startswith('0'):
        base = 8
    else:
        base = 10

    return int(text, base)


def normalize_ipv4_address(address):
    num_decimals = address.count('.')

    if num_decimals == 0:
        return ipaddress.IPv4Address(parse_ipv4_int(address)).compressed
    elif num_decimals == 3:
        return ipaddress.IPv4Address(
            sum(
                parse_ipv4_int(part) << (24 - index * 8)
                for index, part in enumerate(address.split('.'))
            )
        ).compressed
    else:
        raise ValueError('Not an IPv4 address')


def normalize_path(path, encoding='utf-8'):
    '''Normalize a path string.

    Flattens a path by removing dot parts,
    percent-encodes unacceptable characters and ensures percent-encoding is
    uppercase.
    '''
    if not path.startswith('/'):
        path = '/' + path
    path = percent_encode(flatten_path(path), encoding=encoding)
    return uppercase_percent_encoding(path)


def normalize_query(text, encoding='utf-8'):
    '''Normalize a query string.

    Percent-encodes unacceptable characters and ensures percent-encoding is
    uppercase.
    '''
    path = percent_encode_plus(text, encoding=encoding)
    return uppercase_percent_encoding(path)


def normalize_fragment(text, encoding='utf-8'):
    '''Normalize a fragment.

    Percent-encodes unacceptable characters and ensures percent-encoding is
    uppercase.
    '''
    path = percent_encode(text, encoding=encoding, encode_set=FRAGMENT_ENCODE_SET)
    return uppercase_percent_encoding(path)


def normalize_username(text, encoding='utf-8'):
    '''Normalize a username

    Percent-encodes unacceptable characters and ensures percent-encoding is
    uppercase.
    '''
    path = percent_encode(text, encoding=encoding, encode_set=USERNAME_ENCODE_SET)
    return uppercase_percent_encoding(path)


def normalize_password(text, encoding='utf-8'):
    '''Normalize a password

    Percent-encodes unacceptable characters and ensures percent-encoding is
    uppercase.
    '''
    path = percent_encode(text, encoding=encoding, encode_set=PASSWORD_ENCODE_SET)
    return uppercase_percent_encoding(path)


class PercentEncoderMap(collections.defaultdict):
    '''Helper map for percent encoding.'''
    # This class is based on urllib.parse.Quoter
    def __init__(self, encode_set):
        super().__init__()
        self.encode_set = encode_set

    def __missing__(self, char):
        if char < 0x20 or char > 0x7E or char in self.encode_set:
            result = '%{:02X}'.format(char)
        else:
            result = chr(char)
        self[char] = result
        return result


_percent_encoder_map_cache = {}
'''Cache of :class:`PercentEncoderMap`.'''


def percent_encode(text, encode_set=DEFAULT_ENCODE_SET, encoding='utf-8'):
    '''Percent encode text.

    Unlike Python's ``quote``, this function accepts a blacklist instead of
    a whitelist of safe characters.
    '''
    byte_string = text.encode(encoding)

    try:
        mapping = _percent_encoder_map_cache[encode_set]
    except KeyError:
        mapping = _percent_encoder_map_cache[encode_set] = PercentEncoderMap(
            encode_set).__getitem__

    return ''.join([mapping(char) for char in byte_string])


def percent_encode_plus(text, encode_set=QUERY_ENCODE_SET,
                        encoding='utf-8'):
    '''Percent encode text for query strings.

    Unlike Python's ``quote_plus``, this function accepts a blacklist instead
    of a whitelist of safe characters.
    '''
    if ' ' not in text:
        return percent_encode(text, encode_set, encoding)
    else:
        result = percent_encode(text, encode_set, encoding)
        return result.replace(' ', '+')


def percent_encode_query_value(text, encoding='utf-8'):
    '''Percent encode a query value.'''
    result = percent_encode_plus(text, QUERY_VALUE_ENCODE_SET, encoding)
    return result

percent_decode = urllib.parse.unquote
percent_decode_plus = urllib.parse.unquote_plus


def schemes_similar(scheme1, scheme2):
    '''Return whether URL schemes are similar.

    This function considers the following schemes to be similar:

    * HTTP and HTTPS

    '''
    if scheme1 == scheme2:
        return True

    if scheme1 in ('http', 'https') and scheme2 in ('http', 'https'):
        return True

    return False


def is_subdir(base_path, test_path, trailing_slash=False, wildcards=False):
    '''Return whether the a path is a subpath of another.

    Args:
        base_path: The base path
        test_path: The path which we are testing
        trailing_slash: If True, the trailing slash is treated with importance.
            For example, ``/images/`` is a directory while ``/images`` is a
            file.
        wildcards: If True, globbing wildcards are matched against paths
    '''
    if trailing_slash:
        base_path = base_path.rsplit('/', 1)[0] + '/'
        test_path = test_path.rsplit('/', 1)[0] + '/'
    else:
        if not base_path.endswith('/'):
            base_path += '/'

        if not test_path.endswith('/'):
            test_path += '/'

    if wildcards:
        return fnmatch.fnmatchcase(test_path, base_path)
    else:
        return test_path.startswith(base_path)


def uppercase_percent_encoding(text):
    '''Uppercases percent-encoded sequences.'''
    if '%' not in text:
        return text

    return re.sub(
        r'%[a-f0-9][a-f0-9]',
        lambda match: match.group(0).upper(),
        text)


def split_query(qs, keep_blank_values=False):
    '''Split the query string.

    Note for empty values: If an equal sign (``=``) is present, the value
    will be an empty string (``''``). Otherwise, the value will be ``None``::

        >>> list(split_query('a=&b', keep_blank_values=True))
        [('a', ''), ('b', None)]

    No processing is done on the actual values.
    '''
    items = []
    for pair in qs.split('&'):
        name, delim, value = pair.partition('=')

        if not delim and keep_blank_values:
            value = None

        if keep_blank_values or value:
            items.append((name, value))

    return items


def query_to_map(text):
    '''Return a key-values mapping from a query string.

    Plus symbols are replaced with spaces.
    '''
    dict_obj = {}

    for key, value in split_query(text, True):
        if key not in dict_obj:
            dict_obj[key] = []

        if value:
            dict_obj[key].append(value.replace('+', ' '))
        else:
            dict_obj[key].append('')

    return query_to_map(text)


@functools.lru_cache()
def urljoin(base_url, url, allow_fragments=True):
    '''Join URLs like ``urllib.parse.urljoin`` but allow scheme-relative URL.'''
    if url.startswith('//') and len(url) > 2:
        scheme = base_url.partition(':')[0]
        if scheme:
            return urllib.parse.urljoin(
                base_url,
                '{0}:{1}'.format(scheme, url),
                allow_fragments=allow_fragments
            )

    return urllib.parse.urljoin(
        base_url, url, allow_fragments=allow_fragments)


def flatten_path(path, flatten_slashes=False):
    '''Flatten an absolute URL path by removing the dot segments.

    :func:`urllib.parse.urljoin` has some support for removing dot segments,
    but it is conservative and only removes them as needed.

    Arguments:
        path (str): The URL path.
        flatten_slashes (bool): If True, consecutive slashes are removed.

    The path returned will always have a leading slash.
    '''
    # Based on posixpath.normpath

    # Fast path
    if not path or path == '/':
        return '/'

    # Take off leading slash
    if path[0] == '/':
        path = path[1:]

    parts = path.split('/')
    new_parts = collections.deque()

    for part in parts:
        if part == '.' or (flatten_slashes and not part):
            continue
        elif part != '..':
            new_parts.append(part)
        elif new_parts:
            new_parts.pop()

    # If the filename is empty string
    if flatten_slashes and path.endswith('/') or not len(new_parts):
        new_parts.append('')

    # Put back leading slash
    new_parts.appendleft('')

    return '/'.join(new_parts)
