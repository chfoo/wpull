# encoding=utf-8
'''Application support.'''
import gettext
import logging
import sys
from http.cookiejar import CookieJar

from wpull.application.tasks.conversion import LinkConversionSetupTask, \
    LinkConversionTask, QueuedFileSource
from wpull.application.tasks.database import DatabaseSetupTask
from wpull.application.tasks.database import InputURLTask
from wpull.application.tasks.download import ProcessTask, ParserSetupTask, ClientSetupTask, ProcessorSetupTask, \
    BackgroundAsyncTask, ProxyServerSetupTask, CoprocessorSetupTask, \
    CheckQuotaTask
from wpull.application.tasks.log import LoggingSetupTask, LoggingShutdownTask
from wpull.application.tasks.network import NetworkSetupTask
from wpull.application.tasks.plugin import PluginSetupTask
from wpull.application.tasks.resmon import ResmonSetupTask, ResmonSleepTask
from wpull.application.tasks.rule import URLFiltersSetupTask, \
    URLFiltersPostURLImportSetupTask, URLPrioritiserSetupTask
from wpull.application.tasks.sslcontext import SSLContextTask
from wpull.application.tasks.stats import StatsStartTask, StatsStopTask
from wpull.application.tasks.warc import WARCRecorderSetupTask, \
    WARCRecorderTeardownTask, WARCVisitsTask
from wpull.application.tasks.writer import FileWriterSetupTask

from wpull.application.app import Application
from wpull.application.factory import Factory
from wpull.application.tasks.shutdown import BackgroundAsyncCleanupTask, \
    AppStopTask, CookieJarTeardownTask
from wpull.converter import BatchDocumentConverter
from wpull.cookie import DeFactoCookiePolicy
from wpull.database.sqltable import URLTable as SQLURLTable
from wpull.database.wrap import URLTableHookWrapper
from wpull.driver.phantomjs import PhantomJSDriver
from wpull.network.bandwidth import BandwidthLimiter
from wpull.network.dns import Resolver
from wpull.network.pool import ConnectionPool
from wpull.path import PathNamer
from wpull.pipeline.app import AppSource, AppSession
from wpull.pipeline.pipeline import Pipeline, PipelineSeries
from wpull.pipeline.session import URLItemSource
from wpull.processor.coprocessor.phantomjs import PhantomJSCoprocessor
from wpull.processor.coprocessor.proxy import ProxyCoprocessor
from wpull.processor.coprocessor.youtubedl import YoutubeDlCoprocessor
from wpull.processor.delegate import DelegateProcessor
from wpull.processor.ftp import FTPProcessor, FTPProcessorFetchParams
from wpull.processor.rule import FetchRule, ResultRule, ProcessingRule
from wpull.processor.web import WebProcessor, WebProcessorFetchParams
from wpull.protocol.ftp.client import Client as FTPClient
from wpull.protocol.http.client import Client as HTTPClient
from wpull.protocol.http.redirect import RedirectTracker
from wpull.protocol.http.request import Request
from wpull.protocol.http.robots import RobotsTxtChecker
from wpull.protocol.http.web import WebClient
from wpull.proxy.hostfilter import HostFilter as ProxyHostFilter
from wpull.proxy.server import HTTPProxyServer
from wpull.resmon import ResourceMonitor
from wpull.robotstxt import RobotsTxtPool
from wpull.scraper.base import DemuxDocumentScraper
from wpull.scraper.css import CSSScraper
from wpull.scraper.html import HTMLScraper, ElementWalker
from wpull.scraper.javascript import JavaScriptScraper
from wpull.scraper.sitemap import SitemapScraper
from wpull.stats import Statistics
from wpull.url import URLInfo
from wpull.urlfilter import DemuxURLFilter
from wpull.urlprioritiser import URLPrioritiser
from wpull.urlrewrite import URLRewriter
from wpull.waiter import LinearWaiter
from wpull.warc.recorder import WARCRecorder
from wpull.cookiewrapper import CookieJarWrapper
from wpull.writer import (NullWriter)

_logger = logging.getLogger(__name__)
_ = gettext.gettext


class Builder(object):
    '''Application builder.

    Args:
        args: Options from :class:`argparse.ArgumentParser`
    '''
    def __init__(self, args, unit_test=False):
        self._args = args
        self._factory = Factory({
            'Application': Application,
            'BatchDocumentConverter': BatchDocumentConverter,
            'BandwidthLimiter': BandwidthLimiter,
            'HTTPClient': HTTPClient,
            'CookieJar': CookieJar,
            'CookieJarWrapper': CookieJarWrapper,
            'CookiePolicy': DeFactoCookiePolicy,
            'ConnectionPool': ConnectionPool,
            'CSSScraper': CSSScraper,
            'DemuxDocumentScraper': DemuxDocumentScraper,
            'DemuxURLFilter': DemuxURLFilter,
            'FTPProcessor': FTPProcessor,
            'ElementWalker': ElementWalker,
            'FetchRule': FetchRule,
            'FileWriter': NullWriter,
            'FTPClient': FTPClient,
            'FTPProcessorFetchParams': FTPProcessorFetchParams,
            'HTTPProxyServer': HTTPProxyServer,
            'HTMLParser': NotImplemented,
            'HTMLScraper': HTMLScraper,
            'JavaScriptScraper': JavaScriptScraper,
            'PathNamer': PathNamer,
            'PhantomJSDriver': PhantomJSDriver,
            'PhantomJSCoprocessor': PhantomJSCoprocessor,
            'PipelineSeries': PipelineSeries,
            'ProcessingRule': ProcessingRule,
            'Processor': DelegateProcessor,
            'ProxyCoprocessor': ProxyCoprocessor,
            'ProxyHostFilter': ProxyHostFilter,
            'RedirectTracker': RedirectTracker,
            'Request': Request,
            'Resolver': Resolver,
            'ResourceMonitor': ResourceMonitor,
            'ResultRule': ResultRule,
            'RobotsTxtChecker': RobotsTxtChecker,
            'RobotsTxtPool': RobotsTxtPool,
            'SitemapScraper': SitemapScraper,
            'Statistics': Statistics,
            'URLInfo': URLInfo,
            'URLPrioritiser': URLPrioritiser,
            'URLTable': URLTableHookWrapper,
            'URLTableImplementation': SQLURLTable,
            'URLRewriter': URLRewriter,
            'Waiter': LinearWaiter,
            'WARCRecorder': WARCRecorder,
            'WebClient': WebClient,
            'WebProcessor': WebProcessor,
            'WebProcessorFetchParams': WebProcessorFetchParams,
            'YoutubeDlCoprocessor': YoutubeDlCoprocessor,
        })
        self._unit_test = unit_test

    @property
    def factory(self):
        '''Return the Factory.

        Returns:
            Factory: An :class:`.factory.Factory` instance.
        '''
        return self._factory

    def build(self) -> Application:
        '''Put the application together.
        '''

        pipelines = self._build_pipelines()
        self._factory.new('Application', pipelines)

        return self._factory['Application']

    def _build_pipelines(self) -> PipelineSeries:
        app_session = AppSession(self._factory, self._args, self.get_stderr())

        app_start_pipeline = Pipeline(
            AppSource(app_session),
            [
                LoggingSetupTask(),
                PluginSetupTask(),
                DatabaseSetupTask(),
                ParserSetupTask(),
                WARCVisitsTask(),
                SSLContextTask(),
                ResmonSetupTask(),
                StatsStartTask(),
                URLFiltersSetupTask(),
                URLPrioritiserSetupTask(),
                NetworkSetupTask(),
                ClientSetupTask(),
                WARCRecorderSetupTask(),
                FileWriterSetupTask(),
                ProcessorSetupTask(),
                ProxyServerSetupTask(),
                CoprocessorSetupTask(),
                LinkConversionSetupTask(),
                InputURLTask(),
                URLFiltersPostURLImportSetupTask(),
            ])

        url_item_source = URLItemSource(app_session)

        download_pipeline = Pipeline(
            url_item_source,
            [
                ProcessTask(),
                ResmonSleepTask(),
                BackgroundAsyncTask(),
                CheckQuotaTask(),
            ]
        )

        download_stop_pipeline = Pipeline(
            AppSource(app_session),
            [
                StatsStopTask()
            ])
        download_stop_pipeline.skippable = True

        queued_file_source = QueuedFileSource(app_session)

        conversion_pipeline = Pipeline(
            queued_file_source,
            [
                LinkConversionTask()
            ]
        )
        conversion_pipeline.skippable = True

        app_stop_pipeline = Pipeline(
            AppSource(app_session),
            [
                BackgroundAsyncCleanupTask(),
                AppStopTask(),
                WARCRecorderTeardownTask(),
                CookieJarTeardownTask(),
                LoggingShutdownTask(),
            ])

        pipeline_series = self._factory.new(
            'PipelineSeries',
            (
                app_start_pipeline, download_pipeline,
                download_stop_pipeline, conversion_pipeline, app_stop_pipeline
            ))
        pipeline_series.concurrency_pipelines.add(download_pipeline)

        return pipeline_series

    def build_and_run(self):
        '''Build and run the application.

        Returns:
            int: The exit status.
        '''
        app = self.build()
        exit_code = app.run_sync()
        return exit_code

    def get_stderr(self):
        '''Return stderr or something else if under unit testing.'''
        if self._unit_test:
            return sys.stdout
        else:
            return sys.stderr
