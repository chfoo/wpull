'''Database SQLAlchemy model.'''
import contextlib

import sqlalchemy.ext.declarative
from sqlalchemy import insert, select, and_, func
from sqlalchemy.ext.associationproxy import association_proxy
from sqlalchemy.orm import relationship
from sqlalchemy.sql.schema import Column, ForeignKey
from sqlalchemy.sql.sqltypes import Integer, Enum, String
from typing import Iterable

from wpull.pipeline.item import Status, URLRecord, LinkType

DBBase = sqlalchemy.ext.declarative.declarative_base()


class URLString(DBBase):
    '''Table containing the URL strings.

    The :class:`URL` references this table.
    '''
    __tablename__ = 'url_strings'

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(String, nullable=False, unique=True, index=True)

    @classmethod
    def add_urls(cls, session, urls: Iterable[str]):
        query = insert(URLString).prefix_with('OR IGNORE')
        session.execute(query, [{'url': url} for url in urls])


class QueuedURL(DBBase):
    __tablename__ = 'queued_urls'

    id = Column(Integer, primary_key=True, autoincrement=True)

    # -- URLs --
    url_string_id = Column(
        Integer, ForeignKey(URLString.id),
        nullable=False, unique=True, index=True,
        doc='Target URL to fetch'
    )
    url_string = relationship(
        URLString, uselist=False, foreign_keys=[url_string_id]
    )
    url = association_proxy('url_string', 'url')

    parent_url_string_id = Column(
        Integer, ForeignKey(URLString.id),
        doc='Optional referral URL'
    )
    parent_url_string = relationship(
        URLString, uselist=False, foreign_keys=[parent_url_string_id])
    parent_url = association_proxy('parent_url_string', 'url')

    root_url_string_id = Column(
        Integer, ForeignKey(URLString.id),
        doc='Optional root URL'
    )
    root_url_string = relationship(
        'URLString', uselist=False, foreign_keys=[root_url_string_id])
    root_url = association_proxy('root_url_string', 'url')

    # -- Fetch parameters --
    status = Column(
        Enum(*list(member.value for member in Status)),
        index=True,
        default=Status.todo.value,
        nullable=False,
        doc='Status of the completion of the item.'
    )
    try_count = Column(
        Integer, nullable=False, default=0,
        doc='Number of attempts made in order to process the item.'
    )
    level = Column(
        Integer, nullable=False, default=0,
        doc='Recursive depth of the item. 0 is root, 1 is child of root, etc.'
    )
    inline_level = Column(
        Integer,
        doc='Depth of the page requisite object. '
            '0 is the object, 1 is the object\'s dependency, etc.'
    )
    link_type = Column(
        Enum(*list(member.value for member in LinkType)),
        doc='Expected content type of extracted link.'
    )
    priority = Column(
        Integer, nullable=False, default=0, index = True,
        doc='Priority of item.'
    )

    # -- Fetch extra data --
    post_data = Column(String, doc='Additional percent-encoded data for POST.')

    # -- Fetch result info --
    status_code = Column(Integer, doc='HTTP status code or FTP rely code.')
    filename = Column(String, doc='Local filename of the item.')

    @classmethod
    @contextlib.contextmanager
    def watch_urls_inserted(cls, session):
        last_primary_key = session.query(func.max(QueuedURL.id)).scalar() or 0

        def get_urls():
            query = select([URLString.url]).where(
                and_(QueuedURL.id > last_primary_key,
                     QueuedURL.url_string_id == URLString.id)
            )
            return [row[0] for row in session.execute(query)]

        yield get_urls

    def to_plain(self) -> URLRecord:
        record = URLRecord()
        record.url = self.url
        record.parent_url = self.parent_url
        record.root_url = self.root_url
        record.status = Status(self.status)
        record.try_count = self.try_count
        record.level = self.level
        record.inline_level = self.inline_level
        record.link_type = LinkType(self.link_type) if self.link_type else None
        record.priority = self.priority
        record.post_data = self.post_data
        record.status_code = self.status_code
        record.filename = self.filename

        return record


class WARCVisit(DBBase):
    '''Standalone table for ``--cdx-dedup`` feature.'''
    __tablename__ = 'warc_visits'

    url = Column(String, primary_key=True, nullable=False)
    warc_id = Column(String, nullable=False)
    payload_digest = Column(String, nullable=False)

    @classmethod
    def add_visits(cls, session, visits):
        for url, warc_id, payload_digest in visits:
            session.execute(
                insert(WARCVisit).prefix_with('OR IGNORE'),
                dict(
                    url=url,
                    warc_id=warc_id,
                    payload_digest=payload_digest
                )
            )

    @classmethod
    def get_revisit_id(cls, session, url, payload_digest):
        query = select([WARCVisit.warc_id]).where(
            and_(
                WARCVisit.url == url,
                WARCVisit.payload_digest == payload_digest
            )
        )

        row = session.execute(query).first()

        if row:
            return row.warc_id


class Hostname(DBBase):
    __tablename__ = 'hostnames'

    id = Column(Integer, primary_key=True, autoincrement=True)
    hostname = Column(String, nullable=False, unique=True)


class QueuedFile(DBBase):
    __tablename__ = 'queued_files'

    id = Column(Integer, primary_key=True, autoincrement=True)
    queued_url_id = Column(Integer, ForeignKey(QueuedURL.id),
                           nullable=False, unique=True)
    queued_url = relationship(
        QueuedURL, uselist=False, foreign_keys=[queued_url_id]
    )
    status = Column(
        Enum(*list(member.value for member in Status)),
        index=True,
        default=Status.todo.value,
        nullable=False,
    )


__all__ = ('DBBase', 'QueuedURL', 'URLString', 'WARCVisit', 'Hostname',
           'QueuedFile')
