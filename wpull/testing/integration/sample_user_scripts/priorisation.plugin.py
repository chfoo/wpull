# encoding=utf-8
import os.path

from typing import cast, Optional

from wpull.application.hook import Actions
from wpull.application.plugin import WpullPlugin, hook, PluginFunctions, event
from wpull.network.dns import ResolveResult
from wpull.pipeline.app import AppSession
from wpull.pipeline.item import URLRecord
from wpull.pipeline.session import ItemSession
from wpull.stats import Statistics
from wpull.url import URLInfo
from wpull.protocol.http.request import Response as HTTPResponse


class Plugin(WpullPlugin):
    def __init__(self):
        self._set_priorities_in_get_urls = False
        self._get_priority_enabled = False

    @event(PluginFunctions.get_urls)
    def get_urls(self, item_session: ItemSession):
        filename = item_session.response.body.name
        url_info = item_session.request.url_info

        if url_info.resource == '/blog/?get_urls_with_prio=1':
            self._set_priorities_in_get_urls = True
        if url_info.resource == '/blog/?enable_get_priority=1':
            self._get_priority_enabled = True

        if url_info.resource in ('/blog/', '/blog/?get_urls_with_prio=1', '/blog/?enable_get_priority=1'):
            for i in range(1, 4):
                item_session.add_child_url('http://localhost:' + str(url_info.port) + '/blog/?tab=' + str(i), priority = 1 if self._set_priorities_in_get_urls else None)
        elif url_info.resource == '/blog/?page=3':
            for i in range(1, 4):
                item_session.add_child_url('http://localhost:' + str(url_info.port) + '/blog/?page=3&tab=' + str(i), priority = 3 if self._set_priorities_in_get_urls else None)

    @hook(PluginFunctions.get_priority)
    def get_priority(self, url_info: URLInfo, url_record: URLRecord):
        if not self._get_priority_enabled:
            return None
        if '?tab=' in url_info.resource:
            return 1
        if '?page=3&tab=' in url_info.resource:
            return 3
        return None
