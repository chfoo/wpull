'''URL table wrappers.'''
from wpull.application.plugin import event_interface, PluginFunctions
from wpull.database.base import BaseURLTable
from wpull.application.hook import HookableMixin, HookDisconnected
from wpull.pipeline.item import Status, URLRecord
from wpull.url import parse_url_or_log, URLInfo
import wpull.application.hook


class URLTableHookWrapper(BaseURLTable, HookableMixin):
    '''URL table wrapper with scripting hooks.

    Args:
        url_table: URL table.

    Attributes:
        url_table: URL table.
    '''

    def __init__(self, url_table):
        super().__init__()
        self.url_table = url_table
        self._queue_counter = 0

        self.event_dispatcher.register(PluginFunctions.queued_url)
        self.event_dispatcher.register(PluginFunctions.dequeued_url)

    def queue_count(self):
        '''Return the number of URLs queued in this session.'''
        return self._queue_counter

    def count(self):
        return self.url_table.count()

    def get_one(self, url):
        return self.url_table.get_one(url)

    def get_all(self):
        return self.url_table.get_all()

    def add_many(self, urls):
        added_urls = tuple(self.url_table.add_many(urls))

        for url in added_urls:
            url_info = parse_url_or_log(url)
            if url_info:
                self._queue_counter += 1
                self.event_dispatcher.notify(PluginFunctions.queued_url, url_info)

        return added_urls

    def check_out(self):
        url_record = self.url_table.check_out()
        self._queue_counter -= 1

        self.event_dispatcher.notify(PluginFunctions.dequeued_url, url_record.url_info, url_record)

        return url_record

    def check_in(self, url, new_status, increment_try_count=True,
                 url_result=None):
        if new_status == Status.error:
            self._queue_counter += 1
            url_info = parse_url_or_log(url)

            if url_info:
                self.event_dispatcher.notify(PluginFunctions.queued_url, url_info)

        return self.url_table.check_in(url, new_status, increment_try_count=increment_try_count, url_result=url_result)

    def update_one(self, *args, **kwargs):
        return self.url_table.update_one(*args, **kwargs)

    def release(self):
        return self.url_table.release()

    def remove_many(self, urls):
        return self.url_table.remove_many(urls)

    def close(self):
        return self.url_table.close()

    def add_visits(self, visits):
        return self.url_table.add_visits(visits)

    def get_revisit_id(self, url, payload_digest):
        return self.url_table.get_revisit_id(url, payload_digest)

    def get_hostnames(self):
        return self.url_table.get_hostnames()

    @staticmethod
    @event_interface(PluginFunctions.queued_url)
    def queued_url(url_info: URLInfo):
        '''Callback fired after an URL was put into the queue.
        '''

    @staticmethod
    @event_interface(PluginFunctions.dequeued_url)
    def dequeued_url(url_info: URLInfo, record_info: URLRecord):
        '''Callback fired after an URL was retrieved from the queue.
        '''

    def get_root_url_todo_count(self):
        return self.url_table.get_root_url_todo_count()

    def convert_check_out(self):
        return self.url_table.convert_check_out()

    def convert_check_in(self, file_id: int, status: Status):
        self.url_table.convert_check_in(file_id, status)
