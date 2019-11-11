# encoding=utf-8
'''DNS resolution.'''
import datetime
import enum
import itertools
import logging
import random
import socket
import functools
import asyncio

import dns.resolver
import dns.exception
import dns.rdatatype
import dns.rrset
from typing import List, Sequence, Optional, Iterable, NamedTuple

from wpull.application.plugin import PluginFunctions, hook_interface, \
    event_interface
from wpull.backport.logging import BraceMessage as __
from wpull.cache import FIFOCache
from wpull.errors import DNSNotFound, NetworkError
from wpull.application.hook import HookableMixin, HookDisconnected
import wpull.util
import wpull.application.hook


_logger = logging.getLogger(__name__)


AddressInfo = NamedTuple(
    '_AddressInfo', [
        ('ip_address', str),
        ('family', int),
        ('flow_info', Optional[int]),
        ('scope_id', Optional[int])
    ])
'''Socket address.'''

_DNSInfo = NamedTuple(
    '_DNSInfo', [
        ('fetch_date', datetime.datetime),
        ('resource_records', List[dns.rrset.RRset])
    ])


class DNSInfo(_DNSInfo):
    '''DNS resource records.'''
    __slots__ = ()

    def to_text_format(self):
        '''Format as detached DNS information as text.'''
        return '\n'.join(itertools.chain(
            (self.fetch_date.strftime('%Y%m%d%H%M%S'), ),
            (rr.to_text() for rr in self.resource_records),
            (),
        ))


class ResolveResult(object):
    '''DNS resolution information.'''
    def __init__(self, address_infos: List[AddressInfo],
                 dns_infos: Optional[List[DNSInfo]]=None):
        self._address_infos = address_infos
        self._dns_infos = dns_infos

    @property
    def addresses(self) -> Sequence[AddressInfo]:
        '''The socket addresses.'''
        return self._address_infos

    @property
    def dns_infos(self) -> List[DNSInfo]:
        '''The DNS resource records.'''
        return self._dns_infos

    @property
    def first_ipv4(self) -> Optional[AddressInfo]:
        '''The first IPv4 address.'''
        for info in self._address_infos:
            if info.family == socket.AF_INET:
                return info

    @property
    def first_ipv6(self) -> Optional[AddressInfo]:
        '''The first IPV6 address.'''
        for info in self._address_infos:
            if info.family == socket.AF_INET6:
                return info

    def shuffle(self):
        '''Shuffle the addresses.'''
        random.shuffle(self._address_infos)

    def rotate(self):
        '''Move the first address to the last position.'''
        item = self._address_infos.pop(0)
        self._address_infos.append(item)


@enum.unique
class IPFamilyPreference(enum.Enum):
    '''IPv4 and IPV6 preferences.'''

    any = 'any'
    ipv4_only = socket.AF_INET
    ipv6_only = socket.AF_INET6


class Resolver(HookableMixin):
    '''Asynchronous resolver with cache and timeout.

    Args:
        family: IPv4 or IPv6 preference.
        timeout: A time in seconds used for timing-out requests. If not
            specified, this class relies on the underlying libraries.
        bind_address: An IP address to bind DNS requests if possible.
        cache: Cache to store results of any query.
        rotate: If result is cached rotates the results, otherwise, shuffle
            the results.
    '''

    def __init__(
            self,
            family: IPFamilyPreference=IPFamilyPreference.any,
            timeout: Optional[float]=None,
            bind_address: Optional[str]=None,
            cache: Optional[FIFOCache]=None,
            rotate: bool=False):
        super().__init__()
        assert family in IPFamilyPreference, \
            'Unknown family {}.'.format(family)

        self._family = family
        self._timeout = timeout
        self._bind_address = bind_address
        self._cache = cache
        self._rotate = rotate

        self._dns_resolver = dns.resolver.Resolver()

        self.dns_python_enabled = True

        if timeout:
            self._dns_resolver.timeout = timeout

        self.hook_dispatcher.register(PluginFunctions.resolve_dns)
        self.event_dispatcher.register(PluginFunctions.resolve_dns_result)

    @classmethod
    def new_cache(cls) -> FIFOCache:
        '''Return a default cache'''
        return FIFOCache(max_items=100, time_to_live=3600)

    @asyncio.coroutine
    def resolve(self, host: str) -> ResolveResult:
        '''Resolve hostname.

        Args:
            host: Hostname.

        Returns:
            Resolved IP addresses.

        Raises:
            DNSNotFound if the hostname could not be resolved or
            NetworkError if there was an error connecting to DNS servers.

        Coroutine.
        '''

        _logger.debug(__('Lookup address {0}.', host))

        try:
            host = self.hook_dispatcher.call(PluginFunctions.resolve_dns, host
                                             ) or host
        except HookDisconnected:
            pass

        cache_key = (host, self._family)

        if self._cache and cache_key in self._cache:
            resolve_result = self._cache[cache_key]
            _logger.debug(__('Return by cache {0}.', resolve_result))

            if self._rotate:
                resolve_result.rotate()

            return resolve_result

        address_infos = []
        dns_infos = []

        if not self.dns_python_enabled:
            families = ()
        elif self._family == IPFamilyPreference.any:
            families = (socket.AF_INET, socket.AF_INET6)
        elif self._family == IPFamilyPreference.ipv4_only:
            families = (socket.AF_INET, )
        else:
            families = (socket.AF_INET6, )

        for family in families:
            datetime_now = datetime.datetime.utcnow()
            try:
                answer = yield from self._query_dns(host, family)
            except DNSNotFound:
                continue
            else:
                dns_infos.append(DNSInfo(datetime_now, answer.response.answer))
                address_infos.extend(self._convert_dns_answer(answer))

        if not address_infos:
            # Maybe the address is defined in hosts file or mDNS

            if self._family == IPFamilyPreference.any:
                family = socket.AF_UNSPEC
            elif self._family == IPFamilyPreference.ipv4_only:
                family = socket.AF_INET
            else:
                family = socket.AF_INET6

            results = yield from self._getaddrinfo(host, family)
            address_infos.extend(self._convert_addrinfo(results))

        _logger.debug(__('Resolved addresses: {0}.', address_infos))

        resolve_result = ResolveResult(address_infos, dns_infos)

        if self._cache:
            self._cache[cache_key] = resolve_result

        self.event_dispatcher.notify(PluginFunctions.resolve_dns_result, host, resolve_result)

        if self._rotate:
            resolve_result.shuffle()

        return resolve_result

    @asyncio.coroutine
    def _query_dns(self, host: str, family: int=socket.AF_INET) \
            -> dns.resolver.Answer:
        '''Query DNS using Python.

        Coroutine.
        '''
        record_type = {socket.AF_INET: 'A', socket.AF_INET6: 'AAAA'}[family]

        event_loop = asyncio.get_event_loop()
        query = functools.partial(
            self._dns_resolver.query, host, record_type,
            source=self._bind_address)

        try:
            answer = yield from event_loop.run_in_executor(None, query)
        except (dns.resolver.NXDOMAIN, dns.resolver.NoAnswer) as error:
            raise DNSNotFound(
                'DNS resolution failed: {error}'
                .format(error=str(error))
            ) from error
        except dns.exception.DNSException as error:
            raise NetworkError(
                'DNS resolution error: {error}'
                .format(error=str(error))
            ) from error
        else:
            return answer

    @asyncio.coroutine
    def _getaddrinfo(self, host: str, family: int=socket.AF_UNSPEC) \
            -> List[tuple]:
        '''Query DNS using system resolver.

        Coroutine.
        '''
        event_loop = asyncio.get_event_loop()
        query = event_loop.getaddrinfo(host, 0, family=family,
                                       proto=socket.IPPROTO_TCP)

        if self._timeout:
            query = asyncio.wait_for(query, self._timeout)

        try:
            results = yield from query
        except socket.error as error:
            if error.errno in (
                    socket.EAI_FAIL,
                    socket.EAI_NODATA,
                    socket.EAI_NONAME):
                raise DNSNotFound(
                    'DNS resolution failed: {error}'.format(error=error)
                ) from error
            else:
                raise NetworkError(
                    'DNS resolution error: {error}'.format(error=error)
                ) from error
        except asyncio.TimeoutError as error:
            raise NetworkError('DNS resolve timed out.') from error
        else:
            return results

    @classmethod
    def _convert_dns_answer(cls, answer: dns.resolver.Answer) \
            -> Iterable[AddressInfo]:
        '''Convert the DNS answer to address info.'''
        assert answer.rdtype in (dns.rdatatype.A, dns.rdatatype.AAAA)

        if answer.rdtype == dns.rdatatype.A:
            family = socket.AF_INET
        else:
            family = socket.AF_INET6

        for record in answer:
            ip_address = record.to_text()

            if family == socket.AF_INET6:
                flow_info, control_id = cls._get_ipv6_info(ip_address)
            else:
                flow_info = control_id = None

            yield AddressInfo(ip_address, family, flow_info, control_id)

    @classmethod
    def _convert_addrinfo(cls, results: List[tuple]) -> Iterable[AddressInfo]:
        '''Convert the result list to address info.'''
        for result in results:
            family = result[0]
            address = result[4]
            ip_address = address[0]

            if family == socket.AF_INET6:
                flow_info = address[2]
                control_id = address[3]
            else:
                flow_info = None
                control_id = None

            yield AddressInfo(ip_address, family, flow_info, control_id)

    @classmethod
    def _get_ipv6_info(cls, ip_address: str) -> tuple:
        '''Extract the flow info and control id.'''
        results = socket.getaddrinfo(
            ip_address, 0, proto=socket.IPPROTO_TCP,
            flags=socket.AI_NUMERICHOST)

        flow_info = results[0][4][2]
        control_id = results[0][4][3]

        return flow_info, control_id

    @staticmethod
    @hook_interface(PluginFunctions.resolve_dns)
    def resolve_dns(host: str) -> str:
        '''Resolve the hostname to an IP address.

        Args:
            host: The hostname.

        This callback is to override the DNS lookup.

        It is useful when the server is no longer available to the public.
        Typically, large infrastructures will change the DNS settings to
        make clients no longer hit the front-ends, but rather go towards
        a static HTTP server with a "We've been acqui-hired!" page. In these
        cases, the original servers may still be online.

        Returns:
            str, None: ``None`` to use the original behavior or a string
            containing an IP address or an alternate hostname.
        '''
        return host

    @staticmethod
    @event_interface(PluginFunctions.resolve_dns_result)
    def resolve_dns_result(host: str, result: ResolveResult):
        '''Callback when a DNS resolution has been made.'''
