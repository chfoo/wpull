import asyncio
import gettext
import json
import logging

import sys

from wpull.backport.logging import BraceMessage as __
from wpull.pipeline.app import AppSession
from wpull.pipeline.pipeline import ItemTask
from wpull.warc.recorder import WARCRecorder, WARCRecorderParams
import wpull.processor.coprocessor.youtubedl
import wpull.warc.format


_logger = logging.getLogger(__name__)
_ = gettext.gettext


class WARCRecorderSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        args = session.args

        assert args.verbosity, \
            'Expect logging level. Got {}.'.format(args.verbosity)

        if not args.warc_file:
            return

        extra_fields = [
            ('robots', 'on' if args.robots else 'off'),
            ('wpull-arguments', str(args)),
            ('wpull-argv', json.dumps(sys.argv[1:])),
        ]

        for header_string in args.warc_header:
            name, value = header_string.split(':', 1)
            name = name.strip()
            value = value.strip()
            extra_fields.append((name, value))

        software_string = WARCRecorder.DEFAULT_SOFTWARE_STRING

        if args.youtube_dl:
            software_string += ' youtube-dl/{0}'.format(
                wpull.processor.coprocessor.youtubedl.get_version(exe_path=args.youtube_dl_exe)
            )

        url_table = session.factory['URLTable'] if args.warc_dedup else None

        warc_recorder = session.factory.new(
            'WARCRecorder',
            args.warc_file,
            params=WARCRecorderParams(
                compress=not args.no_warc_compression,
                extra_fields=extra_fields,
                temp_dir=args.warc_tempdir,
                log=args.warc_log,
                appending=args.warc_append,
                digests=args.warc_digests,
                cdx=args.warc_cdx,
                max_size=args.warc_max_size,
                move_to=args.warc_move,
                url_table=url_table,
                software_string=software_string,
            ),
        )
        warc_recorder.listen_to_http_client(session.factory['HTTPClient'])
        warc_recorder.listen_to_ftp_client(session.factory['FTPClient'])


class WARCRecorderTeardownTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        warc_recorder = session.factory.get('WARCRecorder')

        if warc_recorder:
            warc_recorder.close()


class WARCVisitsTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        '''Populate the visits from the CDX into the URL table.'''
        if not session.args.warc_dedup:
            return

        iterable = wpull.warc.format.read_cdx(
            session.args.warc_dedup,
            encoding=session.args.local_encoding or 'utf-8'
        )

        missing_url_msg = _('The URL ("a") is missing from the CDX file.')
        missing_id_msg = _('The record ID ("u") is missing from the CDX file.')
        missing_checksum_msg = \
            _('The SHA1 checksum ("k") is missing from the CDX file.')

        counter = 0

        def visits():
            nonlocal counter
            checked_fields = False

            for record in iterable:
                if not checked_fields:
                    if 'a' not in record:
                        raise ValueError(missing_url_msg)
                    if 'u' not in record:
                        raise ValueError(missing_id_msg)
                    if 'k' not in record:
                        raise ValueError(missing_checksum_msg)

                    checked_fields = True

                yield record['a'], record['u'], record['k']
                counter += 1

        url_table = session.factory['URLTable']
        url_table.add_visits(visits())

        _logger.info(__(
            gettext.ngettext(
                'Loaded {num} record from CDX file.',
                'Loaded {num} records from CDX file.',
                counter
            ),
            num=counter
        ))
