'''Base table class.'''
import abc

import typing
from typing import Iterator, Optional

from wpull.pipeline.item import URLRecord, URLProperties, URLData, Status, \
    URLResult


class DatabaseError(Exception):
    '''Any database error.'''


class NotFound(DatabaseError):
    '''Item not found in the table.'''


AddURLInfo = typing.NamedTuple('_AddURLInfo', [
    ('url', str),
    ('properties', URLProperties),
    ('data', URLData)
])


class BaseURLTable(object, metaclass=abc.ABCMeta):
    '''URL table.'''

    @abc.abstractmethod
    def count(self) -> int:
        '''Return the number of URLs in the table.

        This call may be expensive.
        '''

    @abc.abstractmethod
    def get_one(self, url: str) -> URLRecord:
        '''Return a URLRecord for the URL.

        Raises:
            NotFound
        '''

    def contains(self, url: str):
        '''Return whether the URL is in the table.'''

        try:
            self.get_one(url)
        except NotFound:
            return False
        else:
            return True

    @abc.abstractmethod
    def get_all(self) -> Iterator[URLRecord]:
        '''Return all URLRecord.'''

    @abc.abstractmethod
    def add_many(self, new_urls: Iterator[AddURLInfo]) -> Iterator[str]:
        '''Add the URLs to the table.

        Args:
            new_urls: URLs to be added.

        Returns:
            The URLs added. Useful for tracking duplicates.
        '''

    def add_one(self, url: str,
                url_properties: Optional[URLProperties]=None,
                url_data: Optional[URLData]=None):
        '''Add a single URL to the table.

        Args:
            url: The URL to be added
            url_properties: Additional values to be saved
            url_data: Additional data to be saved
        '''
        self.add_many([AddURLInfo(url, url_properties, url_data)])

    @abc.abstractmethod
    def check_out(self) -> URLRecord:
        '''Find a URL, mark it in progress, and return it.

        Raises:
            NotFound
        '''

    @abc.abstractmethod
    def check_in(self, url: str, new_status: Status,
                 increment_try_count: bool=True,
                 url_result: Optional[URLResult]=None):
        '''Update record for processed URL.

        Args:
            url: The URL.
            new_status: Update the item status to `new_status`.
            increment_try_count: Whether to increment the try counter
                for the URL.
            url_result: Additional values.
        '''

    @abc.abstractmethod
    def update_one(self, url, **kwargs):
        '''Arbitrarily update values for a URL.'''

    @abc.abstractmethod
    def release(self):
        '''Mark any ``in_progress`` URLs to ``todo`` status.'''

    @abc.abstractmethod
    def remove_many(self, urls):
        '''Remove the URLs from the database.'''

    def remove_one(self, url):
        '''Remove a URL from the database.'''
        self.remove_many([url])

    @abc.abstractmethod
    def close(self):
        '''Run any clean-up actions and close the table.'''

    @abc.abstractmethod
    def add_visits(self, visits):
        '''Add visited URLs from CDX file.

        Args:
            visits (iterable): An iterable of items. Each item is a tuple
                containing a URL, the WARC ID, and the payload digest.
        '''

    @abc.abstractmethod
    def get_revisit_id(self, url, payload_digest):
        '''Return the WARC ID corresponding to the visit.

        Returns:
            str, None
        '''

    @abc.abstractmethod
    def get_hostnames(self):
        '''Return list of hostnames
        '''

    @abc.abstractmethod
    def get_root_url_todo_count(self) -> int:
        pass

    @abc.abstractmethod
    def convert_check_out(self) -> (int, URLRecord):
        pass

    @abc.abstractmethod
    def convert_check_in(self, file_id: int, status: Status):
        pass
