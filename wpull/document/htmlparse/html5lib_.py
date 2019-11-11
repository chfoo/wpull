'''Parsing using html5lib python.'''
from html5lib.treewalkers.dom import TreeWalker
import html5lib
import io
import os.path

from wpull.document.htmlparse.base import BaseParser
from wpull.document.htmlparse.element import Comment, Doctype, Element


class TreeWalkerAdapter(TreeWalker):
    """ Simple adapter for TreeWalker. Splits up EmptyTag into start/end tag,
    so the fragile logic of HTMLParser does not break """
    def emptyTag(self, namespace, name, attrs, hasChildren=False):
        yield self.startTag(namespace, name, attrs)
        if hasChildren:
            yield self.error("Void element has children")
        yield self.endTag(namespace, name)


class HTMLParser(BaseParser):
    @property
    def parser_error(self):
        return ValueError

    def parse(self, file, encoding=None):
        tokenizer = TreeWalkerAdapter(html5lib.parse(
            file, treebuilder='dom',
            override_encoding=encoding,
        ))

        tag = None
        attrib = None
        buffer = None
        tail_buffer = None

        for token in tokenizer:
            token_type = token['type']

            if token_type == 'StartTag':
                if buffer:
                    yield Element(tag, attrib, buffer.getvalue(), None, False)
                    buffer = None

                if tail_buffer:
                    yield Element(tag, dict(), None, tail_buffer.getvalue(), True)
                    tail_buffer = None

                tag = token['name']
                # html5lib returns node names as ((namespace, name), value),
                # but we expect just (name, value) pairs
                attrib = dict(map(lambda x: (x[0][1], x[1]), token['data'].items()))
                buffer = io.StringIO()

                # XXX: ?
                #if token['name'] == 'script':
                #    tokenizer.state = tokenizer.scriptDataState

            elif token_type in ('Characters', 'SpaceCharacters'):
                if buffer:
                    buffer.write(token['data'])
                if tail_buffer:
                    tail_buffer.write(token['data'])

            elif token_type == 'EndTag':
                if buffer:
                    yield Element(tag, attrib, buffer.getvalue(), None, False)
                    buffer = None

                if tail_buffer:
                    yield Element(tag, dict(), None, tail_buffer.getvalue(), True)
                    tail_buffer = None

                tail_buffer = io.StringIO()
                tag = token['name']

            elif token_type == 'Comment':
                yield Comment(token['data'])
            elif token_type == 'Doctype':
                yield Doctype('{} {} {}'.format(
                    token['name'], token['publicId'], token['systemId']))
            elif token_type == 'SerializeError':
                pass
            else:
                raise ValueError('Unhandled token {}'.format(token))

        if buffer:
            yield Element(tag, attrib, buffer.getvalue(), None, False)
            buffer = None

        if tail_buffer:
            yield Element(tag, dict(), None, tail_buffer.getvalue(), True)
            tail_buffer = None

if __name__ == '__main__':
    path = os.path.join(
        os.path.dirname(__file__), '..', '..',
        'testing', 'samples', 'xkcd_1.html'
        )
    with open(path, 'rb') as in_file:
        tokenizer = TreeWalkerAdapter(html5lib.parse(in_file, treebuilder='dom'))

        for token in tokenizer:
            print(token)
        html_parser = HTMLParser()
        for element in html_parser.parse(in_file):
            print(element)

