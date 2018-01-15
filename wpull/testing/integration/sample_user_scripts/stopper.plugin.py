# encoding=utf-8
from wpull.application.hook import Actions
from wpull.application.plugin import WpullPlugin, PluginFunctions, hook
from wpull.pipeline.session import ItemSession


class MyPlugin(WpullPlugin):
    @hook(PluginFunctions.handle_response)
    def stop(self, item_session: ItemSession):
        print('stop')
        return Actions.STOP
