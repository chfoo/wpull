# encoding=utf-8
'''URL items.'''
import enum
import gettext
import logging

from wpull.url import URLInfo

_ = gettext.gettext
_logger = logging.getLogger(__name__)


class Status(enum.Enum):
    '''URL status.'''
    todo = 'todo'
    '''The item has not yet been processed.'''
    in_progress = 'in_progress'
    '''The item is in progress of being processed.'''
    done = 'done'
    '''The item has been processed successfully.'''
    error = 'error'
    '''The item encountered an error during processing.'''
    skipped = 'skipped'
    '''The item was excluded from processing due to some rejection filters.'''


class LinkType(enum.Enum):
    '''The type of contents that a link is expected to have.'''
    html = 'html'
    '''HTML document.'''
    css = 'css'
    '''Stylesheet file. Recursion on links is usually safe.'''
    javascript = 'javascript'
    '''JavaScript file. Possible to recurse links on this file.'''
    media = 'media'
    '''Image or video file. Recursion on this type will not be useful.'''
    sitemap = 'sitemap'
    '''A Sitemap.xml file.'''
    file = 'file'
    '''FTP File.'''
    directory = 'directory'
    '''FTP directory.'''


class URLDatabaseMixin:
    def database_items(self):
        for name in self.database_attributes:
            value = getattr(self, name)

            if value is not None:
                yield name, value


class URLProperties(URLDatabaseMixin):
    '''URL properties that determine whether a URL is fetched.

    Attributes:
        parent_url (str): The parent or referral URL that linked to this URL.
        root_url (str): The earliest ancestor URL of this URL. This URL
            is typically the URL supplied at the start of the program.
        status (Status): Processing status of this URL.
        try_count (int): The number of attempts on this URL.
        level (int): The recursive depth of this URL. A level of ``0``
            indicates the URL was initially supplied to the program (the
            top URL).
            Level ``1`` means the URL was linked from the top URL.
        inline_level (int): Whether this URL was an embedded object (such as an
            image or a stylesheet) of the parent URL.

            The value represents the recursive depth of the object. For
            example, an iframe is depth 1 and the images in the iframe
            is depth 2.
        link_type (LinkType): Describes the expected document type.
    '''
    database_attributes = ('parent_url', 'root_url', 'status', 'try_count',
                           'level', 'inline_level', 'link_type', 'priority')

    def __init__(self):
        super().__init__()
        self.parent_url = None
        self.root_url = None
        self.status = None
        self.try_count = None
        self.level = None
        self.inline_level = None
        self.link_type = None
        self.priority = None

    @property
    def parent_url_info(self):
        '''Return URL Info for the parent URL'''
        return URLInfo.parse(self.parent_url)

    @property
    def root_url_info(self):
        '''Return URL Info for the root URL'''
        return URLInfo.parse(self.parent_url)


class URLData(URLDatabaseMixin):
    '''Data associated fetching the URL.

    post_data (str): If given, the URL should be fetched as a
        POST request containing `post_data`.
    '''
    database_attributes = ('post_data',)

    def __init__(self):
        super().__init__()
        self.post_data = None


class URLResult(URLDatabaseMixin):
    '''Data associated with the fetched URL.

    status_code (int): The HTTP or FTP status code.
    filename (str): The path to where the file was saved.
    '''
    database_attributes = ('status_code', 'filename')

    def __init__(self):
        super().__init__()
        self.status_code = None
        self.filename = None


class URLRecord(URLProperties, URLData, URLResult):
    '''An entry in the URL table describing a URL to be downloaded.

    Attributes:
        url (str): The URL.
    '''
    def __init__(self):
        super().__init__()
        self.url = None

    @property
    def url_info(self) -> URLInfo:
        '''Return URL Info for this URL'''
        return URLInfo.parse(self.url)

    @classmethod
    def root_record(cls, url):
        '''Generate a URLRecord instance for a root entry'''
        record = cls()
        record.url = url
        record.parent_url = url
        record.root_url = url
        record.status = Status.todo
        record.try_count = 0
        record.level = 0
        record.inline_level = None
        record.link_type = None
        record.priority = None
        record.post_data = None
        record.status_code = None
        record.filename = None
        return record
