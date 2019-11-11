# encoding=utf-8
'''Python and Lua scripting support.

See :ref:`scripting-hooks` for an introduction.
'''
import collections.abc
import enum
import functools
import gettext
import logging

import asyncio

from typing import Optional, Iterable

from wpull.application.plugin import WpullPlugin, PluginFunctionCategory
from wpull.backport.logging import BraceMessage as __

_ = gettext.gettext
_logger = logging.getLogger(__name__)


class HookDisconnected(RuntimeError):
    '''No callback is connected.'''


class HookAlreadyConnectedError(ValueError):
    '''A callback is already connected to the hook.'''


class HookDispatcher(collections.abc.Mapping):
    '''Dynamic callback hook system.'''
    def __init__(self, plugins: Optional[Iterable[WpullPlugin]] = [], event_dispatcher_transclusion: Optional['EventDispatcher'] = None):
        super().__init__()
        self._callbacks = {}
        self._plugins = plugins
        self._event_dispatcher = event_dispatcher_transclusion

    def __getitem__(self, key):
        return self._callbacks[key]

    def __iter__(self):
        return iter(self._callbacks)

    def __len__(self):
        return len(self._callbacks)

    def register(self, name: str):
        '''Register hooks that can be connected.'''
        if name in self._callbacks:
            raise ValueError('Hook already registered')

        self._callbacks[name] = None

        if self._event_dispatcher is not None:
            self._event_dispatcher.register(name)

        for plugin in self._plugins:
            for func, f_name, f_category in plugin.get_plugin_functions():
                if f_category == PluginFunctionCategory.hook and f_name == name:
                    self.connect(name, func)

    def unregister(self, name: str):
        '''Unregister hook.'''
        del self._callbacks[name]

        if self._event_dispatcher is not None:
            self._event_dispatcher.unregister(name)

    def connect(self, name, callback):
        '''Add callback to hook.'''
        if not self._callbacks[name]:
            self._callbacks[name] = callback
        else:
            raise HookAlreadyConnectedError('Callback hook already connected.')

    def disconnect(self, name: str):
        '''Remove callback from hook.'''
        self._callbacks[name] = None

    def call(self, name: str, *args, **kwargs):
        '''Invoke the callback.'''
        if self._event_dispatcher is not None:
            self._event_dispatcher.notify(name, *args, **kwargs)

        if self._callbacks[name]:
            return self._callbacks[name](*args, **kwargs)
        else:
            raise HookDisconnected('No callback is connected.')

    @asyncio.coroutine
    def call_async(self, name: str, *args, **kwargs):
        '''Invoke the callback.'''
        if self._event_dispatcher is not None:
            self._event_dispatcher.notify(name, *args, **kwargs)

        if self._callbacks[name]:
            return (yield from self._callbacks[name](*args, **kwargs))
        else:
            raise HookDisconnected('No callback is connected.')

    def is_connected(self, name: str) -> bool:
        '''Return whether the hook is connected.'''
        return bool(self._callbacks[name])

    def is_registered(self, name: str) -> bool:
        return name in self._callbacks


class EventDispatcher(collections.abc.Mapping):
    def __init__(self, plugins: Optional[Iterable[WpullPlugin]] = []):
        self._callbacks = {}
        self._plugins = plugins

    def __getitem__(self, key):
        return self._callbacks[key]

    def __iter__(self):
        return iter(self._callbacks)

    def __len__(self):
        return len(self._callbacks)

    def register(self, name: str):
        if name in self._callbacks:
            raise ValueError('Event already registered')

        self._callbacks[name] = set()

        for plugin in self._plugins:
            for func, f_name, f_category in plugin.get_plugin_functions():
                if f_category == PluginFunctionCategory.event and f_name == name:
                    self.add_listener(name, func)

    def unregister(self, name: str):
        del self._callbacks[name]

    def add_listener(self, name: str, callback):
        self._callbacks[name].add(callback)

    def remove_listener(self, name: str, callback):
        self._callbacks[name].remove(callback)

    def notify(self, name: str, *args, **kwargs):
        for callback in self._callbacks[name]:
            callback(*args, **kwargs)

    def is_registered(self, name: str) -> bool:
        return name in self._callbacks


class HookableMixin(object):
    _plugins = [] # type: Iterable[WpullPlugin]

    def __init__(self):
        super().__init__()
        self.event_dispatcher = EventDispatcher(plugins=self._plugins)
        self.hook_dispatcher = HookDispatcher(event_dispatcher_transclusion=self.event_dispatcher, plugins=self._plugins)

    def connect_plugin(self, plugin: WpullPlugin):
        for func, name, category in plugin.get_plugin_functions():
            if category == PluginFunctionCategory.hook:
                if self.hook_dispatcher.is_registered(name):
                    _logger.debug('Connected hook %s %s', name, func)
                    self.hook_dispatcher.connect(name, func)
                elif self.event_dispatcher.is_registered(name):
                    raise RuntimeError('Plugin event ‘{name}’ cannot be attached as a hook function.'.format(name=name))

            elif category == PluginFunctionCategory.event and self.event_dispatcher.is_registered(name):
                _logger.debug('Connected event %s %s', name, func)
                self.event_dispatcher.add_listener(name, func)

    @classmethod
    def set_plugins(cls, plugins: Iterable[WpullPlugin]):
        HookableMixin._plugins = plugins
        # Note that HookableMixin is hardcoded here as the plugin list is always defined at the level of this class.
        # If cls._plugins was used instead, calling set_plugins of a subclass would break unit tests, for example.


class HookStop(Exception):
    '''Stop the engine.

    Raise this exception as a more graceful alternative to ``sys.exit()``.
    '''


class Actions(enum.Enum):
    '''Actions for handling responses and errors.

    Attributes:
        NORMAL (normal): Use Wpull's original behavior.
        RETRY (retry): Retry this item (as if an error has occurred).
        FINISH (finish): Consider this item as done; don't do any further
            processing on it.
        STOP (stop): Raises :class:`HookStop` to stop the Engine from running.
    '''
    NORMAL = 'normal'
    RETRY = 'retry'
    FINISH = 'finish'
    STOP = 'stop'
