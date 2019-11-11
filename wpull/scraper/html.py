'''HTML link extractor.'''
import collections
import gettext
import itertools
import logging
import re

import wpull.util
from wpull.backport.logging import StyleAdapter
from wpull.document.html import HTMLReader
from wpull.document.htmlparse.element import Element
from wpull.document.util import detect_response_encoding
from wpull.pipeline.item import LinkType
from wpull.scraper.base import BaseHTMLScraper, ScrapeResult, LinkContext
from wpull.scraper.util import urljoin_safe, clean_link_soup, parse_refresh, \
    is_likely_inline, is_likely_link, is_unlikely_link, identify_link_type
from wpull.url import percent_decode

_ = gettext.gettext
_logger = StyleAdapter(logging.getLogger(__name__))


_BaseLinkInfo = collections.namedtuple(
    'LinkInfoType',
    [
        'element', 'tag', 'attrib', 'link',
        'inline', 'linked', 'base_link', 'value_type',
        'link_type'
    ]
)

class LinkInfo(_BaseLinkInfo):
    def __hash__(self):
        return self.link.__hash__()

'''Information about a link in a lxml document.  Comparable on link only.

Attributes:
    element: An instance of :class:`.document.HTMLReadElement`.
    tag (str): The element tag name.
    attrib (str, None): If ``str``, the name of the attribute. Otherwise,
        the link was found in ``element.text``.
    link (str): The link found.
    inline (bool): Whether the link is an embedded object (like images or
        stylesheets).
    linked (bool): Whether the link is a link to another page.
    base_link (str, None): The base URL.
    value_type (str): Indicates how the link was found. Possible values are

        * ``plain``: The link was found plainly in an attribute value.
        * ``list``: The link was found in a space separated list.
        * ``css``: The link was found in a CSS text.
        * ``refresh``: The link was found in a refresh meta string.
        * ``script``: The link was found in JavaScript text.
        * ``srcset``: The link was found in a ``srcset`` attribute.

    link_type: A value from :class:`item.LinkInfo`.
'''


class HTMLScraper(HTMLReader, BaseHTMLScraper):
    '''Scraper for HTML documents.

    Args:
        html_parser (class:`.document.htmlparse.base.BaseParser`): An
            HTML parser such as the lxml or html5lib one.
        element_walker (class:`ElementWalker`): HTML element walker.
        followed_tags: A list of tags that should be scraped
        ignored_tags: A list of tags that should not be scraped
        robots: If True, discard any links if they cannot be followed
        only_relative: If True, discard any links that are not absolute paths
    '''

    def __init__(self, html_parser, element_walker,
                 followed_tags=None, ignored_tags=None,
                 robots=False,
                 only_relative=False, encoding_override=None):
        super().__init__(html_parser)
        self._element_walker = element_walker
        self._robots = robots
        self._only_relative = only_relative
        self._encoding_override = encoding_override

        if followed_tags is not None:
            self._followed_tags = frozenset(
                [tag.lower() for tag in followed_tags])
        else:
            self._followed_tags = None

        if ignored_tags is not None:
            self._ignored_tags = frozenset(
                [tag.lower() for tag in ignored_tags])
        else:
            self._ignored_tags = None

    def scrape(self, request, response, link_type=None):
        if not self.is_supported(request=request, response=response):
            return
        if link_type and link_type != LinkType.html:
            return

        base_url = request.url_info.url
        content_file = response.body
        encoding = self._encoding_override \
            or detect_response_encoding(response, is_html=True)
        link_contexts = set()

        try:
            with wpull.util.reset_file_offset(content_file):
                elements = self.iter_elements(content_file, encoding=encoding)

                result_meta_info = self._process_elements(
                    elements, response, base_url, link_contexts
                )

        except (UnicodeError, self._html_parser.parser_error) as error:
            _logger.warning(
                _('Failed to read document at ‘{url}’: {error}'),
                url=request.url_info.url, error=error
            )
            result_meta_info = {}

        if result_meta_info.get('robots_no_follow'):
            link_contexts.discard(frozenset(
                context for context in link_contexts if context.linked
            ))

        scrape_result = ScrapeResult(link_contexts, encoding)
        scrape_result['base_url'] = base_url
        return scrape_result

    def _process_elements(self, elements, response, base_url, link_contexts):
        robots_check_needed = self._robots
        robots_no_follow = False
        inject_refresh = True
        doc_base_url = None

        for element in elements:
            if not isinstance(element, Element):
                continue

            if robots_check_needed and ElementWalker.robots_cannot_follow(element):
                robots_check_needed = False
                robots_no_follow = True

            if not doc_base_url and element.tag == 'base':
                doc_base_url = urljoin_safe(
                    base_url, clean_link_soup(element.attrib.get('href', ''))
                )

            link_infos = self._element_walker.iter_links_element(element)

            if inject_refresh and 'Refresh' in response.fields:
                link = parse_refresh(response.fields['Refresh'])

                if link:
                    link_info = LinkInfo(
                        element=None, tag='_refresh', attrib=None,
                        link=link,
                        inline=False, linked=True,
                        base_link=None, value_type='refresh',
                        link_type=None  # treat it as a redirect
                    )
                    link_infos = itertools.chain(link_infos, [link_info])

                inject_refresh = False
            else:
                inject_refresh = False

            for link_info in link_infos:
                if self._only_relative:
                    if link_info.base_link or '://' in link_info.link:
                        continue

                if not self._is_accepted(link_info.tag):
                    continue

                element_base_url = doc_base_url or base_url

                if link_info.base_link:
                    clean_base_url = clean_link_soup(link_info.base_link)

                    if clean_base_url:
                        element_base_url = urljoin_safe(
                            base_url, clean_base_url
                        ) or base_url

                cleaned_url = clean_link_soup(link_info.link)

                if not cleaned_url:
                    continue

                url = urljoin_safe(
                    element_base_url,
                    cleaned_url,
                    allow_fragments=False
                )

                if url:
                    link_contexts.add(LinkContext(
                        url,
                        inline=link_info.inline,
                        linked=link_info.linked,
                        link_type=link_info.link_type,
                        extra=link_info,
                    ))

        return {'robots_no_follow': robots_no_follow}

    def scrape_file(self, file, encoding=None, base_url=None):
        '''Scrape a file for links.

        See :meth:`scrape` for the return value.
        '''
        elements = self.iter_elements(file, encoding=encoding)

        link_contexts = set()

        link_infos = self._element_walker.iter_links(elements)

        for link_info in link_infos:
            element_base_url = base_url

            if link_info.base_link:
                clean_base_url = clean_link_soup(link_info.base_link)

                if element_base_url and base_url:
                    element_base_url = urljoin_safe(
                        base_url, clean_base_url
                    ) or base_url

            if element_base_url:
                url = urljoin_safe(
                    element_base_url,
                    clean_link_soup(link_info.link),
                    allow_fragments=False
                )
            else:
                url = clean_link_soup(link_info.link)

            if url:
                link_contexts.add(LinkContext(
                    url,
                    inline=link_info.inline,
                    linked=link_info.linked,
                    link_type=link_info.link_type,
                    extra=link_info
                ))

        scrape_result = ScrapeResult(link_contexts, encoding)
        scrape_result['base_url'] = base_url
        return scrape_result

    def _is_accepted(self, element_tag):
        '''Return if the link is accepted by the filters.'''
        element_tag = element_tag.lower()

        if self._ignored_tags is not None \
           and element_tag in self._ignored_tags:
            return False

        if self._followed_tags is not None:
            return element_tag in self._followed_tags
        else:
            return True


class ElementWalker(object):
    LINK_ATTRIBUTES = frozenset([
        'action', 'archive', 'background', 'cite', 'classid',
        'codebase', 'data', 'href', 'longdesc', 'profile', 'src',
        'poster',
        'usemap',
        'dynsrc', 'lowsrc',
    ])
    '''HTML element attributes that may contain links.'''
    ATTR_INLINE = 1
    '''Flag for embedded objects (like images, stylesheets) in documents.'''
    ATTR_HTML = 2
    '''Flag for links that point to other documents.'''
    TAG_ATTRIBUTES = {
        'a': {'href': ATTR_HTML},
        'applet': {'code': ATTR_INLINE},
        'area': {'href': ATTR_HTML},
        'bgsound': {'src': ATTR_INLINE},
        'body': {'background': ATTR_INLINE},
        'embed': {'href': ATTR_HTML, 'src': ATTR_INLINE | ATTR_HTML},
        'fig': {'src': ATTR_INLINE},
        'form': {'action': ATTR_HTML},
        'frame': {'src': ATTR_INLINE | ATTR_HTML},
        'iframe': {'src': ATTR_INLINE | ATTR_HTML},
        'img': {
            'href': ATTR_INLINE, 'lowsrc': ATTR_INLINE, 'src': ATTR_INLINE},
        'input': {'src': ATTR_INLINE},
        'layer': {'src': ATTR_INLINE | ATTR_HTML},
        'object': {'data': ATTR_INLINE},
        'overlay': {'src': ATTR_INLINE | ATTR_HTML},
        'script': {'src': ATTR_INLINE},
        'table': {'background': ATTR_INLINE},
        'td': {'background': ATTR_INLINE},
        'th': {'background': ATTR_INLINE},
        'video': {'src': ATTR_INLINE, 'poster': ATTR_INLINE},
        'audio': {'src': ATTR_INLINE, 'poster': ATTR_INLINE},
        'source': {'src': ATTR_INLINE},
    }
    '''Mapping of element tag names to attributes containing links.'''
    DYNAMIC_ATTRIBUTES = ('onkey', 'oncli', 'onmou')
    '''Attributes that contain JavaScript.'''
    OPEN_GRAPH_MEDIA_NAMES = (
        'og:image', 'og:audio', 'og:video',
        'twitter:image:src', 'twitter:image0', 'twitter:image1',
        'twitter:image2', 'twitter:image3', 'twitter:player:stream',
    )
    OPEN_GRAPH_LINK_NAMES = (
        'og:url', 'twitter:player'
    )

    '''Iterate elements looking for links.

    Args:
        css_scraper (:class:`.scraper.css.CSSScraper`): Optional CSS scraper.
        javascript_scraper (:class:`.scraper.javascript.JavaScriptScraper):
            Optional JavaScript scraper.
    '''
    def __init__(self, css_scraper=None, javascript_scraper=None):
        self.css_scraper = css_scraper
        self.javascript_scraper = javascript_scraper

    def iter_links(self, elements):
        '''Iterate the document root for links.

        Returns:
            iterable: A iterator of :class:`LinkedInfo`.
        '''
        for element in elements:
            if not isinstance(element, Element):
                continue

            for link_infos in self.iter_links_element(element):
                yield link_infos

    def iter_links_element(self, element):
        '''Iterate a HTML element.'''
        # reference: lxml.html.HtmlMixin.iterlinks()
        attrib = element.attrib
        tag = element.tag

        if tag == 'link':
            iterable = self.iter_links_link_element(element)
        elif tag == 'meta':
            iterable = self.iter_links_meta_element(element)
        elif tag in ('object', 'applet'):
            iterable = self.iter_links_object_element(element)
        elif tag == 'param':
            iterable = self.iter_links_param_element(element)
        elif tag == 'style':
            iterable = self.iter_links_style_element(element)
        elif tag == 'script':
            iterable = self.iter_links_script_element(element)
        else:
            iterable = self.iter_links_plain_element(element)

        # RSS/Atom
        if tag in ('link', 'url', 'icon'):
            iterable = itertools.chain(
                iterable, self.iter_links_element_text(element)
            )

        for link_info in iterable:
            yield link_info

        if 'style' in attrib and self.css_scraper:
            for link in self.css_scraper.scrape_links(attrib['style']):
                yield LinkInfo(
                    element=element, tag=element.tag, attrib='style',
                    link=link,
                    inline=True, linked=False,
                    base_link=None,
                    value_type='css',
                    link_type=LinkType.media,
                )

    @classmethod
    def iter_links_element_text(cls, element):
        '''Get the element text as a link.'''
        if element.text:
            link_type = identify_link_type(element.text)
            yield LinkInfo(
                element=element, tag=element.tag, attrib=None,
                link=element.text,
                inline=False, linked=True,
                base_link=None,
                value_type='plain',
                link_type=link_type
            )

    def iter_links_link_element(self, element):
        '''Iterate a ``link`` for URLs.

        This function handles stylesheets and icons in addition to
        standard scraping rules.
        '''
        rel = element.attrib.get('rel', '')
        stylesheet = 'stylesheet' in rel
        icon = 'icon' in rel
        inline = stylesheet or icon

        if stylesheet:
            link_type = LinkType.css
        elif icon:
            link_type = LinkType.media
        else:
            link_type = None

        for attrib_name, link in self.iter_links_by_attrib(element):
            yield LinkInfo(
                element=element, tag=element.tag, attrib=attrib_name,
                link=link,
                inline=inline, linked=not inline,
                base_link=None,
                value_type='plain',
                link_type=link_type
            )

    @classmethod
    def iter_links_meta_element(cls, element):
        '''Iterate the ``meta`` element for links.

        This function handles refresh URLs.
        '''
        if element.attrib.get('http-equiv', '').lower() == 'refresh':
            content_value = element.attrib.get('content')

            if content_value:
                link = parse_refresh(content_value)

                if link:
                    yield LinkInfo(
                        element=element, tag=element.tag, attrib='http-equiv',
                        link=link,
                        inline=False, linked=True,
                        base_link=None,
                        value_type='refresh',
                        link_type=None  # treat it as a redirect
                    )
        else:
            for link_info in cls.iter_links_open_graph_meta(element):
                yield link_info

    @classmethod
    def iter_links_open_graph_meta(cls, element):
            name = element.attrib.get('property', '').lower()

            if name in cls.OPEN_GRAPH_LINK_NAMES or \
                    name in cls.OPEN_GRAPH_MEDIA_NAMES:
                link = element.attrib.get('content')

                if link:
                    if name in cls.OPEN_GRAPH_MEDIA_NAMES:
                        link_type = LinkType.media
                    else:
                        link_type = None

                    yield LinkInfo(
                        element=element, tag=element.tag, attrib='property',
                        link=link,
                        inline=False, linked=True,
                        base_link=None,
                        value_type='plain',
                        link_type=link_type
                    )

    @classmethod
    def iter_links_object_element(cls, element):
        '''Iterate ``object`` and ``embed`` elements.

        This function also looks at ``codebase`` and ``archive`` attributes.
        '''
        base_link = element.attrib.get('codebase', None)

        if base_link:
            # lxml returns codebase as inline
            link_type = element.attrib.get(base_link)
            yield LinkInfo(
                element=element, tag=element.tag, attrib='codebase',
                link=base_link,
                inline=True, linked=False,
                base_link=None,
                value_type='plain',
                link_type=link_type
            )

        for attribute in ('code', 'src', 'classid', 'data'):
            if attribute in element.attrib:
                link_type = identify_link_type(element.attrib.get(attribute))
                yield LinkInfo(
                    element=element, tag=element.tag, attrib=attribute,
                    link=element.attrib.get(attribute),
                    inline=True, linked=False,
                    base_link=base_link,
                    value_type='plain',
                    link_type=link_type
                )

        if 'archive' in element.attrib:
            for match in re.finditer(r'[^ ]+', element.attrib.get('archive')):
                value = match.group(0)
                link_type = identify_link_type(value)
                yield LinkInfo(
                    element=element, tag=element.tag, attrib='archive',
                    link=value,
                    inline=True, linked=False,
                    base_link=base_link,
                    value_type='list',
                    link_type=link_type
                )

    @classmethod
    def iter_links_param_element(cls, element):
        '''Iterate a ``param`` element.'''
        valuetype = element.attrib.get('valuetype', '')

        if valuetype.lower() == 'ref' and 'value' in element.attrib:
            link_type = identify_link_type(element.attrib.get('value'))

            yield LinkInfo(
                element=element, tag=element.tag, attrib='value',
                link=element.attrib.get('value'),
                inline=True, linked=False,
                base_link=None,
                value_type='plain',
                link_type=link_type
            )

    def iter_links_style_element(self, element):
        '''Iterate a ``style`` element.'''
        if self.css_scraper and element.text:
            link_iter = self.css_scraper.scrape_links(element.text,
                                                      context=True)
            for link, context in link_iter:
                if context == 'import':
                    link_type = LinkType.css
                else:
                    link_type = LinkType.media

                yield LinkInfo(
                    element=element, tag=element.tag, attrib=None,
                    link=link,
                    inline=True, linked=False,
                    base_link=None,
                    value_type='css',
                    link_type=link_type
                )

    def iter_links_script_element(self, element):
        '''Iterate a ``script`` element.'''
        if self.javascript_scraper and element.text:
            link_iter = self.javascript_scraper.scrape_links(element.text,
                                                             context=True)

            for link, context in link_iter:
                inline = is_likely_inline(link)

                if context is True:
                    link_type = None
                else:
                    link_type = context

                yield LinkInfo(
                    element=element, tag=element.tag, attrib=None,
                    link=link,
                    inline=inline, linked=not inline,
                    base_link=None,
                    value_type='script',
                    link_type=link_type
                )

        for link in self.iter_links_plain_element(element):
            yield link

    def iter_links_plain_element(self, element):
        '''Iterate any element for links using generic rules.'''
        for attrib_name, link in self.iter_links_by_attrib(element):
            if attrib_name in self.LINK_ATTRIBUTES:
                inline = self.is_link_inline(element.tag, attrib_name)
                linked = self.is_html_link(element.tag, attrib_name)
            else:
                inline = is_likely_inline(link)
                linked = not inline

            link_type = identify_link_type(link)

            yield LinkInfo(
                element=element, tag=element.tag, attrib=attrib_name,
                link=link,
                inline=inline, linked=linked,
                base_link=None,
                value_type='plain',
                link_type=link_type
            )

    def iter_links_by_attrib(self, element):
        '''Iterate an element by looking at its attributes for links.'''
        for attrib_name in element.attrib.keys():
            attrib_value = element.attrib.get(attrib_name)

            if attrib_name in self.LINK_ATTRIBUTES:
                if self.javascript_scraper and \
                        attrib_value.lstrip().startswith('javascript:'):
                    for link in self.iter_links_by_js_attrib(
                            attrib_name, percent_decode(attrib_value)):
                        yield link
                else:
                    yield attrib_name, attrib_value

            elif self.javascript_scraper and \
                    attrib_name[:5] in self.DYNAMIC_ATTRIBUTES:
                for link in self.iter_links_by_js_attrib(attrib_name,
                                                         attrib_value):
                    yield link

            elif attrib_name.startswith('data-'):
                if is_likely_link(attrib_value) \
                        and not is_unlikely_link(attrib_value):
                    yield attrib_name, attrib_value

            elif attrib_name == 'srcset':
                items = self.iter_links_by_srcset_attrib(
                    attrib_name, attrib_value)

                for item in items:
                    yield item

    def iter_links_by_js_attrib(self, attrib_name, attrib_value):
        '''Iterate links of a JavaScript pseudo-link attribute.'''
        links = self.javascript_scraper.scrape_links(attrib_value)

        for link in links:
            yield attrib_name, link

    @classmethod
    def iter_links_by_srcset_attrib(cls, attrib_name, attrib_value):
        images = attrib_value.split(',')
        links = [value.lstrip().split(' ', 1)[0] for value in images]

        for link in links:
            yield attrib_name, link

    @classmethod
    def is_link_inline(cls, tag, attribute):
        '''Return whether the link is likely to be inline object.'''
        if tag in cls.TAG_ATTRIBUTES \
           and attribute in cls.TAG_ATTRIBUTES[tag]:
            attr_flags = cls.TAG_ATTRIBUTES[tag][attribute]
            return attr_flags & cls.ATTR_INLINE

        return attribute != 'href'

    @classmethod
    def is_html_link(cls, tag, attribute):
        '''Return whether the link is likely to be external object.'''
        if tag in cls.TAG_ATTRIBUTES \
           and attribute in cls.TAG_ATTRIBUTES[tag]:
            attr_flags = cls.TAG_ATTRIBUTES[tag][attribute]
            return attr_flags & cls.ATTR_HTML

        return attribute == 'href'

    @classmethod
    def robots_cannot_follow(cls, element):
        '''Return whether we cannot follow links due to robots.txt directives.
        '''
        return (
            element.tag == 'meta'
            and element.attrib.get('name', '').lower() == 'robots'
            and 'nofollow' in element.attrib.get('value', '').lower()
        )
