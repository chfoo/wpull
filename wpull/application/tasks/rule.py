import gettext
import logging

import asyncio

from wpull.urlfilter import HTTPSOnlyFilter, SchemeFilter, RecursiveFilter, \
    FollowFTPFilter, SpanHostsFilter, ParentFilter, BackwardDomainFilter, \
    HostnameFilter, TriesFilter, RegexFilter, DirectoryFilter, \
    BackwardFilenameFilter, LevelFilter
from wpull.pipeline.pipeline import ItemTask
from wpull.pipeline.app import AppSession

_logger = logging.getLogger(__name__)
_ = gettext.gettext


class URLFiltersSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        self._build_url_rewriter(session)
        session.factory.new('DemuxURLFilter', self._build_url_filters(session))

    @classmethod
    def _build_url_rewriter(cls, session: AppSession):
        '''Build URL rewriter if needed.'''
        if session.args.escaped_fragment or session.args.strip_session_id:
            return session.factory.new(
                'URLRewriter',
                hash_fragment=session.args.escaped_fragment,
                session_id=session.args.strip_session_id
            )

    @classmethod
    def _build_url_filters(cls, session: AppSession):
        '''Create the URL filter instances.

        Returns:
            A list of URL filter instances
        '''
        args = session.args

        filters = [
            HTTPSOnlyFilter() if args.https_only else SchemeFilter(),
            RecursiveFilter(
                enabled=args.recursive, page_requisites=args.page_requisites
            ),
            FollowFTPFilter(follow=args.follow_ftp),
        ]

        if args.no_parent:
            filters.append(ParentFilter())

        if args.domains or args.exclude_domains:
            filters.append(
                BackwardDomainFilter(args.domains, args.exclude_domains)
            )

        if args.hostnames or args.exclude_hostnames:
            filters.append(
                HostnameFilter(args.hostnames, args.exclude_hostnames)
            )

        if args.tries:
            filters.append(TriesFilter(args.tries))

        if args.level and args.recursive or args.page_requisites_level:
            filters.append(
                LevelFilter(args.level,
                            inline_max_depth=args.page_requisites_level)
            )

        if args.accept_regex or args.reject_regex:
            filters.append(RegexFilter(args.accept_regex, args.reject_regex))

        if args.include_directories or args.exclude_directories:
            filters.append(
                DirectoryFilter(
                    args.include_directories, args.exclude_directories
                )
            )

        if args.accept or args.reject:
            filters.append(BackwardFilenameFilter(args.accept, args.reject))

        return filters


class URLFiltersPostURLImportSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        args = session.args
        span_hosts_filter = SpanHostsFilter(
            tuple(session.factory['URLTable'].get_hostnames()),
            enabled=args.span_hosts,
            page_requisites='page-requisites' in args.span_hosts_allow,
            linked_pages='linked-pages' in args.span_hosts_allow,
        )

        demux_url_filter = session.factory['DemuxURLFilter']
        demux_url_filter.url_filters.append(span_hosts_filter)


class URLPrioritiserSetupTask(ItemTask[AppSession]):
    @asyncio.coroutine
    def process(self, session: AppSession):
        session.factory.new('URLPrioritiser', self._build_priorities(session))

    @classmethod
    def _build_priorities(cls, session: AppSession):
        '''Create the URL filter instances.

        Returns:
            A list of URL filter instances
        '''
        args = session.args

        filters = []
        for filter_type, filter_arg, filter_priority in args.priority_filters:
            if filter_type == 'regex':
                filters.append((RegexFilter(accepted = filter_arg), filter_priority))
            elif filter_type == 'domain':
                filters.append((BackwardDomainFilter(accepted = [filter_arg]), filter_priority))

        return filters
