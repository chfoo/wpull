.. _scripting-hooks:

Plugin Scripting Hooks
======================

Wpull's scripting support is modelled after `alard's Wget with Lua
hooks <https://github.com/alard/wget-lua/wiki/Wget-with-Lua-hooks>`_.

Scripts are installed using the `YAPSY plugin
<http://yapsy.sourceforge.net/>`_ architecture. To create your plugin
script, subclass :py:class:`wpull.application.plugin.WpullPlugin` and
load it with ``--plugin-script`` option.

The plugin interface provides two type of callbacks: hooks and events.

Callbacks receive a number of internal objects from wpull, e.g.
:py:class:`wpull.url.URLInfo` and
:py:class:`wpull.pipeline.session.ItemSession`. It is strongly
recommended not to modify these objects in any way in the callbacks.
Doing so results in undefined behaviour.


Hook
++++

Hooks change the behavior of the program. When the callback is
registered to the hook, it is required to provide a return value
typically one of :py:class:`wpull.application.hook.Actions`. Only
one callback may be registered to a hook.

To register your callback, decorate your callback with
:py:func:`wpull.application.plugin.hook`.


Event
+++++

Events are points in the program that occur and are notified to
registered listeners.

To register your callback, decorate your callback with
:py:func:`wpull.application.plugin.event`.


Interfaces
++++++++++

The global hooks and events constants are located at
:py:class:`wpull.application.plugin.PluginFunctions`.

.. include:: scripting_interfaces_include.rst

Example
+++++++

Here is a example Python script. It

* Prints hello on start up
* Refuses to download anything with the word "dog" in the URL
* Scrapes URLs on a hypothetical homepage
* Stops the program execution when the server returns HTTP 429

::

    import datetime
    import re

    from wpull.application.hook import Actions
    from wpull.application.plugin import WpullPlugin, PluginFunctions, hook
    from wpull.protocol.abstract.request import BaseResponse
    from wpull.pipeline.session import ItemSession


    class MyExamplePlugin(WpullPlugin):
        def activate(self):
            super().activate()
            print('Hello world!')

        def deactivate(self):
            super().deactivate()
            print('Goodbye world!')

        @hook(PluginFunctions.accept_url)
        def my_accept_func(self, item_session: ItemSession, verdict: bool, reasons: dict) -> bool:
            return 'dog' not in item_session.request.url

        @event(PluginFunctions.get_urls)
        def my_get_urls(self, item_session: ItemSession):
            if item_session.request.url_info.path != '/':
                return

            matches = re.finditer(
                r'<div id="profile-(\w+)"', item_session.response.body.content
            )
            for match in matches:
                url = 'http://example.com/profile.php?username={}'.format(
                    match.group(1)
                )
                item_session.add_child_url(url)

        @hook(PluginFunctions.handle_response)
        def my_handle_response(item_session: ItemSession):
            if item_session.response.response_code == 429:
                return Actions.STOP
