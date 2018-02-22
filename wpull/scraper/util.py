'''Misc functions.'''

import functools
import gettext
import itertools
import logging
import mimetypes
import re
import string

import wpull.url
from wpull.backport.logging import BraceMessage as __
from wpull.pipeline.item import LinkType

_ = gettext.gettext
_logger = logging.getLogger(__name__)


def parse_refresh(text):
    '''Parses text for HTTP Refresh URL.

    Returns:
        str, None
    '''
    match = re.search(r'url\s*=(.+)', text, re.IGNORECASE)

    if match:
        url = match.group(1)

        if url.startswith('"'):
            url = url.strip('"')
        elif url.startswith("'"):
            url = url.strip("'")

        return clean_link_soup(url)


def clean_link_soup(link):
    '''Strip whitespace from a link in HTML soup.

    Args:
        link (str): A string containing the link with lots of whitespace.

    The link is split into lines. For each line, leading and trailing
    whitespace is removed and tabs are removed throughout. The lines are
    concatenated and returned.

    For example, passing the ``href`` value of::

        <a href=" http://example.com/

                blog/entry/

            how smaug stole all the bitcoins.html
        ">

    will return
    ``http://example.com/blog/entry/how smaug stole all the bitcoins.html``.

    Returns:
        str: The cleaned link.
    '''
    return ''.join(
        [line.strip().replace('\t', '') for line in link.splitlines()]
    )


def urljoin_safe(base_url, url, allow_fragments=True):
    '''urljoin with warning log on error.

    Returns:
        str, None'''
    try:
        return wpull.url.urljoin(
            base_url, url.translate({ord(c): None for c in '\r\n\t'}), allow_fragments=allow_fragments
        )
    except ValueError as error:
        _logger.warning(__(
            _('Unable to parse URL ‘{url}’: {error}.'),
            url=url, error=error
        ))


def is_likely_inline(link):
    '''Return whether the link is likely to be inline.'''
    file_type = mimetypes.guess_type(link, strict=False)[0]

    if file_type:
        top_level_type, subtype = file_type.split('/', 1)

        return top_level_type in ('image', 'video', 'audio') or subtype == 'javascript'


_mimetypes_db = mimetypes.MimeTypes()
MIMETYPES = frozenset(
    itertools.chain(
        _mimetypes_db.types_map[0].values(),
        _mimetypes_db.types_map[1].values(),
        ['text/javascript']
    )
)
ALPHANUMERIC_CHARS = frozenset(string.ascii_letters + string.digits)
NUMERIC_CHARS = frozenset(string.digits)
COMMON_TLD = frozenset(['com', 'org', 'net', 'int', 'edu', 'gov', 'mil'])
HTML_TAGS = frozenset([
    "a", "abbr", "acronym", "address",
    "applet", "area", "article", "aside", "audio", "b",
    "base", "basefont", "bdi", "bdo", "big", "blockquote",
    "body", "br", "button", "canvas", "caption", "center",
    "cite", "code", "col", "colgroup", "command",
    "datalist", "dd", "del", "details", "dfn", "dir",
    "div", "dl", "dt", "em", "embed", "fieldset",
    "figcaption", "figure", "font", "footer", "form",
    "frame", "frameset", "head", "header", "hgroup", "h1",
    "h2", "h3", "h4", "h5", "h6", "hr", "html", "i",
    "iframe", "img", "input", "ins", "kbd", "keygen",
    "label", "legend", "li", "link", "map", "mark", "menu",
    "meta", "meter", "nav", "noframes", "noscript",
    "object", "ol", "optgroup", "option", "output", "p",
    "param", "pre", "progress", "q", "rp", "rt", "ruby",
    "s", "samp", "script", "section", "select", "small",
    "source", "span", "strike", "strong", "style", "sub",
    "summary", "sup", "table", "tbody", "td", "textarea",
    "tfoot", "th", "thead", "time", "title", "tr", "track",
    "tt", "u", "ul", "var", "video", "wbr"
    ])
FIRST_PART_TLD_PATTERN = re.compile(r'[^/][a-zA-Z0-9.-]+\.({})/.'.format('|'.join(COMMON_TLD)), re.IGNORECASE)


# These "likely link" functions are based from
# https://github.com/internetarchive/heritrix3/
# blob/339e6ec87a7041f49c710d1d0fb94be0ec972ee7/commons/src/
# main/java/org/archive/util/UriUtils.java


def is_likely_link(text):
    '''Return whether the text is likely to be a link.

    This function assumes that leading/trailing whitespace has already been
    removed.

    Returns:
        bool
    '''
    text = text.lower()

    # Check for absolute or relative URLs
    if (
        text.startswith('http://')
        or text.startswith('https://')
        or text.startswith('ftp://')
        or text.startswith('/')
        or text.startswith('//')
        or text.endswith('/')
        or text.startswith('../')
    ):
        return True

    # Check if it has a alphanumeric file extension and not a decimal number
    dummy, dot, file_extension = text.rpartition('.')

    if dot and file_extension and len(file_extension) <= 4:
        file_extension_set = frozenset(file_extension)

        if file_extension_set \
           and file_extension_set <= ALPHANUMERIC_CHARS \
           and not file_extension_set <= NUMERIC_CHARS:
            if file_extension in COMMON_TLD:
                return False

            file_type = mimetypes.guess_type(text, strict=False)[0]

            if file_type:
                return True
            else:
                return False


def is_unlikely_link(text):
    '''Return whether the text is likely to cause false positives.

    This function assumes that leading/trailing whitespace has already been
    removed.

    Returns:
        bool
    '''
    # Check for string concatenation in JavaScript
    if text[:1] in ',;+:' or text[-1:] in '.,;+:':
        return True

    # Check for unusual characters
    if re.search(r'''[\\$()'"[\]{}|<>`]''', text):
        return True

    if text[:1] == '.' \
       and not text.startswith('./') \
       and not text.startswith('../'):
        return True

    if text in ('/', '//'):
        return True

    if '//' in text and '://' not in text and not text.startswith('//'):
        return True

    # Forbid strings like mimetypes
    if text in MIMETYPES:
        return True

    tag_1, dummy, tag_2 = text.partition('.')
    if tag_1 in HTML_TAGS and tag_2 != 'html':
        return True

    # Forbid things where the first part of the path looks like a domain name
    if FIRST_PART_TLD_PATTERN.match(text):
        return True


@functools.lru_cache()
def identify_link_type(filename):
    '''Return link type guessed by filename extension.

    Returns:
        str: A value from :class:`.item.LinkType`.
    '''
    mime_type = mimetypes.guess_type(filename)[0]

    if not mime_type:
        return

    if mime_type == 'text/css':
        return LinkType.css
    elif mime_type == 'application/javascript':
        return LinkType.javascript
    elif mime_type == 'text/html' or mime_type.endswith('xml'):
        return LinkType.html
    elif mime_type.startswith('video') or \
            mime_type.startswith('image') or \
            mime_type.startswith('audio') or \
            mime_type.endswith('shockwave-flash'):
        return LinkType.media
