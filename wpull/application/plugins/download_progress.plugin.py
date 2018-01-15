from typing import cast

from wpull.application.options import LOG_VERBOSE, LOG_DEBUG
from wpull.application.plugin import WpullPlugin
from wpull.pipeline.app import new_encoded_stream
from wpull.pipeline.progress import BarProgress, DotProgress
from wpull.protocol.http.client import Client as HTTPClient
from wpull.protocol.http.client import Session as HTTPSession
from wpull.protocol.ftp.client import Client as FTPClient
from wpull.protocol.ftp.client import Session as FTPSession


class DownloadProgressPlugin(WpullPlugin):
    def __init__(self):
        super().__init__()

        self._progress = None

    def activate(self):
        super().activate()
        args = self.app_session.args

        if args.verbosity in (LOG_VERBOSE, LOG_DEBUG) and args.progress != 'none':
            stream = new_encoded_stream(args, self.app_session.stderr)

            bar_style = args.progress == 'bar'

            if not stream.isatty():
                bar_style = False

            if bar_style:
                self._progress = BarProgress(stream=stream)
            else:
                self._progress = DotProgress(stream=stream)

            self._attach_event_listeners()

    def _attach_event_listeners(self):
        class ProgressHTTPClient(self.app_session.factory.class_map['HTTPClient']):
            def __init__(client_self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                client_self.event_dispatcher.add_listener(client_self.ClientEvent.new_session, self._http_session_callback)
        self.app_session.factory.class_map['HTTPClient'] = ProgressHTTPClient

        class ProgressFTPClient(self.app_session.factory.class_map['FTPClient']):
            def __init__(client_self, *args, **kwargs):
                super().__init__(*args, **kwargs)
                client_self.event_dispatcher.add_listener(client_self.ClientEvent.new_session, self._ftp_session_callback)
        self.app_session.factory.class_map['FTPClient'] = ProgressFTPClient

    def _http_session_callback(self, http_session: HTTPSession):
        http_session.event_dispatcher.add_listener(
            HTTPSession.Event.begin_request,
            self._progress.update_from_begin_request
        )
        http_session.event_dispatcher.add_listener(
            HTTPSession.Event.begin_response,
            self._progress.update_from_begin_response
        )
        http_session.event_dispatcher.add_listener(
            HTTPSession.Event.end_response,
            self._progress.update_from_end_response
        )
        http_session.event_dispatcher.add_listener(
            HTTPSession.Event.response_data,
            self._progress.update_with_data
        )

    def _ftp_session_callback(self, ftp_session: FTPSession):
        ftp_session.event_dispatcher.add_listener(
            FTPSession.Event.begin_control,
            lambda request, connection_reused:
            self._progress.update_from_begin_request(request))
        ftp_session.event_dispatcher.add_listener(
            FTPSession.Event.begin_transfer,
            self._progress.update_from_begin_response)
        ftp_session.event_dispatcher.add_listener(
            FTPSession.Event.end_transfer,
            self._progress.update_from_end_response)
        ftp_session.event_dispatcher.add_listener(
            FTPSession.Event.transfer_receive_data,
            self._progress.update_with_data
        )
