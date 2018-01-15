import asyncio
from unittest.mock import MagicMock, patch

from wpull.application.hook import HookDispatcher, HookAlreadyConnectedError, \
    HookDisconnected, EventDispatcher, HookableMixin
from wpull.application.plugin import WpullPlugin, event, hook
from wpull.testing.async import AsyncTestCase
import wpull.testing.async


class MyClass(HookableMixin):
    def __init__(self):
        super().__init__()
        self.event_dispatcher.register('event_test')
        self.hook_dispatcher.register('hook_test')


class MyPlugin(WpullPlugin):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # TODO: Replace this mess with unittest.mock
        self.hook_calls = []
        self.event_notifications = []

    @event('event_test')
    def my_event_test_callback(self, *args, **kwargs):
        self.event_notifications.append((args, kwargs))

    @hook('hook_test')
    def my_hook_test_callback(self, *args, **kwargs):
        self.hook_calls.append((args, kwargs))


class MyPluginHookAsEvent(WpullPlugin):
    @event('hook_test')
    def my_hook_as_a_event_test_callback(self):
        pass


class MyPluginEventAsHook(WpullPlugin):
    @hook('event_test')
    def my_event_as_a_hook_test_callback(self):
        pass


class TestHook(AsyncTestCase):
    @wpull.testing.async.async_test()
    def test_hook_dispatcher(self):
        hook = HookDispatcher()

        hook.register('a')
        self.assertFalse(hook.is_connected('a'))
        self.assertTrue(hook.is_registered('a'))

        with self.assertRaises(ValueError):
            hook.register('a')

        with self.assertRaises(HookDisconnected):
            hook.call('a', 3)

        def my_callback(arg):
            self.assertEqual(3, arg)
            return 5

        hook.connect('a', my_callback)
        self.assertTrue(hook.is_connected('a'))

        with self.assertRaises(HookAlreadyConnectedError):
            hook.connect('a', my_callback)

        result = hook.call('a', 3)

        self.assertEqual(5, result)

        hook.disconnect('a')
        self.assertFalse(hook.is_connected('a'))

        hook.register('b')

        @asyncio.coroutine
        def my_callback_2():
            yield from asyncio.sleep(0)
            return 9

        hook.connect('b', my_callback_2)
        result = yield from hook.call_async('b')

        self.assertEqual(9, result)

    def test_hook_dispatcher_connects_plugin_hook_on_register(self):
        plugin = MyPlugin()

        hook = HookDispatcher(plugins = [plugin])
        hook.register('hook_test')
        self.assertTrue(hook.is_connected('hook_test'))
        hook.call('hook_test', 'arg1', 'arg2', kwarg1 = 'one', kwarg2 = 'two', kwarg3 = 'three')
        self.assertEqual(plugin.hook_calls, [(('arg1', 'arg2'), {'kwarg1': 'one', 'kwarg2': 'two', 'kwarg3': 'three'})])

        # Verify that this implicit connect doesn't happen without specifying the plugins
        hook = HookDispatcher()
        hook.register('hook_test')
        self.assertFalse(hook.is_connected('hook_test'))
        with self.assertRaises(HookDisconnected):
            hook.call('hook_test', 'a')

    def test_event_dispatcher(self):
        event = EventDispatcher()

        event.register('a')
        self.assertTrue(event.is_registered('a'))

        with self.assertRaises(ValueError):
            event.register('a')

        callback_result_1 = None
        callback_result_2 = None

        def callback1():
            nonlocal callback_result_1
            callback_result_1 = 5

        def callback2():
            nonlocal callback_result_2
            callback_result_2 = 7

        event.add_listener('a', callback1)
        event.add_listener('a', callback2)

        event.notify('a')

        self.assertEquals(5, callback_result_1)
        self.assertEquals(7, callback_result_2)

        event.remove_listener('a', callback1)

        event.unregister('a')

    def test_event_dispatcher_adds_plugin_event_listener_on_register(self):
        plugin = MyPlugin()

        event = EventDispatcher(plugins = [plugin])
        event.register('event_test')
        event.notify('event_test', 'arg1', 'arg2', kwarg1 = 'one', kwarg2 = 'two', kwarg3 = 'three')
        self.assertEqual(plugin.event_notifications, [(('arg1', 'arg2'), {'kwarg1': 'one', 'kwarg2': 'two', 'kwarg3': 'three'})])

        event = EventDispatcher()
        event.register('event_test')
        event.notify('event_test', 'a')
        self.assertEqual(plugin.event_notifications, [(('arg1', 'arg2'), {'kwarg1': 'one', 'kwarg2': 'two', 'kwarg3': 'three'})])

    def test_hook_as_event_dispatcher_transclusion(self):
        event_dispatcher = EventDispatcher()
        hook_dispatcher = HookDispatcher(
            event_dispatcher_transclusion=event_dispatcher)
        hook_dispatcher.register('test_hook')

        callback_mock = MagicMock()
        event_dispatcher.add_listener('test_hook', callback_mock)

        try:
            hook_dispatcher.call('test_hook', 'a')
        except HookDisconnected:
            pass

        callback_mock.assert_called_once_with('a')

    def test_plugin_connect(self):
        tester = MyClass()
        plugin = MyPlugin()

        tester.connect_plugin(plugin)

    def test_plugin_connect_hook_as_event(self):
        tester = MyClass()
        plugin = MyPluginHookAsEvent()

        tester.connect_plugin(plugin)

    def test_plugin_connect_event_as_hook(self):
        tester = MyClass()
        plugin = MyPluginEventAsHook()

        with self.assertRaises(RuntimeError):
            tester.connect_plugin(plugin)

    def test_set_plugins(self):
        plugin = MyPlugin()
        MyClass.set_plugins([plugin])

        try:
            tester = MyClass()

            tester.hook_dispatcher.call('hook_test', 'a', key = 'b')
            self.assertEqual(plugin.hook_calls, [(('a',), {'key': 'b'})])
            self.assertEqual(plugin.event_notifications, [])

            tester.event_dispatcher.notify('event_test', 'c', key = 'd')
            self.assertEqual(plugin.hook_calls, [(('a',), {'key': 'b'})])
            self.assertEqual(plugin.event_notifications, [(('c',), {'key': 'd'})])
        finally:
            MyClass.set_plugins([])

    def test_set_plugins_in_superclass(self):
        plugin = MyPlugin()
        HookableMixin.set_plugins([plugin])

        try:
            tester = MyClass()

            tester.hook_dispatcher.call('hook_test', 'a', key = 'b')
            self.assertEqual(plugin.hook_calls, [(('a',), {'key': 'b'})])
            self.assertEqual(plugin.event_notifications, [])

            tester.event_dispatcher.notify('event_test', 'c', key = 'd')
            self.assertEqual(plugin.hook_calls, [(('a',), {'key': 'b'})])
            self.assertEqual(plugin.event_notifications, [(('c',), {'key': 'd'})])
        finally:
            HookableMixin.set_plugins([])
