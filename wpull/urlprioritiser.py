from typing import Iterator, Tuple
from wpull.urlfilter import BaseURLFilter


class URLPrioritiser:
    '''Uses multiple URL filters to determine a URL's priority.'''
    def __init__(self, priorities: Iterator[Tuple[BaseURLFilter, int]]):
        self._priorities = priorities

    @property
    def priorities(self) -> Iterator[Tuple[BaseURLFilter, int]]:
        return self._priorities

    def get_priority(self, url_info, url_record) -> int:
        '''Returns the priority for a URL'''

        for url_filter, priority in self._priorities:
            if url_filter.test(url_info, url_record):
                return priority
        return 0
