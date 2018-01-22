import enum
import functools
import inspect

import collections

import typing
from typing import Any, Iterator
from yapsy.IPlugin import IPlugin


class PluginFunctionCategory(enum.Enum):
    hook = 'hook'
    event = 'event'


PluginClientFunctionInfo = typing.NamedTuple(
    '_PluginClientFunctionInfo', [
        ('func', Any),
        ('name', Any),
        ('category', PluginFunctionCategory)
    ])


class WpullPlugin(IPlugin):
    def __init__(self):
        super().__init__()
        self.app_session = None

    def should_activate(self) -> bool:
        return True

    def get_plugin_functions(self) -> Iterator[PluginClientFunctionInfo]:
        funcs = inspect.getmembers(self)

        for name, func in funcs:
            if hasattr(func, 'plugin_attach_name'):
                yield PluginClientFunctionInfo(
                    func, func.plugin_attach_name, func.plugin_attach_category)


def _plugin_attach_decorator(name: Any, category: PluginFunctionCategory):
    def decorator(func):
        func.plugin_attach_name = name
        func.plugin_attach_category = category

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def hook(name: Any):
    return _plugin_attach_decorator(name, category=PluginFunctionCategory.hook)


def event(name: Any):
    return _plugin_attach_decorator(name, category=PluginFunctionCategory.event)


class InterfaceRegistry(collections.Mapping):
    def __init__(self):
        super().__init__()
        self._interfaces = {}

    def __len__(self):
        return len(self._interfaces)

    def __getitem__(self, key):
        return self._interfaces[key]

    def __iter__(self):
        return iter(self._interfaces)

    def register(self, name: Any, interface: Any, category: PluginFunctionCategory):
        if name in self._interfaces:
            raise ValueError('Interface already registered')

        self._interfaces[name] = (interface, category)


global_interface_registry = InterfaceRegistry()


def _plugin_interface_decorator(
        name: Any, category: PluginFunctionCategory,
        interface_registry: InterfaceRegistry=global_interface_registry):
    def decorator(func):
        interface_registry.register(name, func, category)

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)

        return wrapper

    return decorator


def hook_interface(
        name: Any,
        interface_registry: InterfaceRegistry=global_interface_registry):
    return _plugin_interface_decorator(name, PluginFunctionCategory.hook,
                                       interface_registry)


def event_interface(
        name: Any,
        interface_registry: InterfaceRegistry=global_interface_registry):
    return _plugin_interface_decorator(name, PluginFunctionCategory.event,
                                       interface_registry)


class PluginFunctions(enum.Enum):
    queued_url = 'queued_url'
    dequeued_url = 'dequeued_url'
    resolve_dns = 'resolve_dns'
    resolve_dns_result = 'resolve_dns_result'
    accept_url = 'accept_url'
    wait_time = 'wait_time'
    handle_response = 'handle_response'
    handle_pre_response = 'handle_pre_response'
    handle_error = 'handle_error'
    get_urls = 'get_urls'
    get_priority = 'get_priority'
    finishing_statistics = 'finishing_statistics'
    exit_status = 'exit_status'
