import copy
from typing import Iterator, Tuple, Union
from wpull.application.plugin import PluginFunctions, hook_interface
from wpull.application.hook import HookableMixin, HookDisconnected
from wpull.pipeline.item import URLRecord
from wpull.url import URLInfo
from wpull.urlfilter import BaseURLFilter


class URLPrioritiser(HookableMixin):
    '''Uses multiple URL filters to determine a URL's priority.'''
    def __init__(self, priorities: Iterator[Tuple[BaseURLFilter, int]]):
        super().__init__()
        self._priorities = priorities
        self.hook_dispatcher.register(PluginFunctions.get_priority)

    @property
    def priorities(self) -> Iterator[Tuple[BaseURLFilter, int]]:
        return self._priorities

    @staticmethod
    @hook_interface(PluginFunctions.get_priority)
    def plugin_get_priority(url_info: URLInfo, url_record: URLRecord) -> Union[int, None]:
        '''Return the priority for this URL.

        Args:
            url_info (URLInfo): A representation of the URL in question
            url_record (URLRecord): Information about the URL in the context of the crawl.
                Note that the priority attribute will always be ``None``
                because the hook is called *before* the internal rules.

        Returns:
            An integer to set the priority to that value, or None if the normal priorisation rules shall be consulted.
        '''
        return None

    def _get_priority_from_hook(self, url_info: URLInfo, url_record: URLRecord) -> Union[int, None]:
        '''Tries to call the get_priority hook. The hook can either return
        an int or None. If the hook is not connected, None is returned.
        '''
        try:
            # Only pass copies of the URLInfo and URLRecord instances to the hook to prevent modification.
            # A deep copy is not actually needed as of writing this code because all attributes of both classes are immutable.
            # However, to prevent future breakage if something changes in those classes, a deep copy is used anyway.
            priority = self.hook_dispatcher.call(PluginFunctions.get_priority, copy.deepcopy(url_info), copy.deepcopy(url_record))
        except HookDisconnected:
            priority = None
        return priority

    def _get_priority_from_filters(self, url_info: URLInfo, url_record: URLRecord) -> int:
        '''Returns the priority for a URL based on the rules in self.priorities.'''

        for url_filter, priority in self._priorities:
            if url_filter.test(url_info, url_record):
                return priority
        return 0

    def get_priority(self, url_info: URLInfo, url_record: URLRecord) -> int:
        '''Returns the priority for a URL.'''
        priority = self._get_priority_from_hook(url_info, url_record)
        if priority is None:
            priority = self._get_priority_from_filters(url_info, url_record)
        return priority
