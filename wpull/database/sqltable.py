'''SQLAlchemy table implementations.'''
import abc
import contextlib
import enum
import logging

import sqlalchemy.event
from sqlalchemy import func
from sqlalchemy.engine import create_engine
from sqlalchemy.orm.session import sessionmaker
from sqlalchemy.pool import SingletonThreadPool
from sqlalchemy.sql.expression import insert, update, select, delete, \
    bindparam

from wpull.database.base import BaseURLTable, NotFound
from wpull.database.sqlmodel import QueuedURL, URLString, DBBase, WARCVisit, \
    Hostname, QueuedFile, indexedby
from wpull.pipeline.item import Status
from wpull.url import URLInfo

_logger = logging.getLogger(__name__)


class BaseSQLURLTable(BaseURLTable):
    @abc.abstractproperty
    def _session_maker(self):
        pass

    @contextlib.contextmanager
    def _session(self):
        """Provide a transactional scope around a series of operations."""
        # Taken from the session docs.
        session = self._session_maker()
        try:
            yield session
            session.commit()
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def count(self):
        with self._session() as session:
            return session.query(QueuedURL).count()

    def get_one(self, url):
        with self._session() as session:
            result = session.query(QueuedURL).filter_by(url=url).order_by(QueuedURL.priority.desc(), QueuedURL.id).first()

            if not result:
                raise NotFound()
            else:
                return result.to_plain()

    def get_all(self):
        with self._session() as session:
            for item in session.query(QueuedURL):
                yield item.to_plain()

    def add_many(self, new_urls):
        assert not isinstance(new_urls, (str, bytes)), \
            'Expected a list-like. Got {}'.format(new_urls)

        new_urls = tuple(new_urls)

        if not new_urls:
            return ()

        assert isinstance(new_urls[0][0], str), type(new_urls[0][0])

        url_strings = []

        for url, properties, data in new_urls:
            url_strings.append(url)

            if properties:
                if properties.parent_url:
                    url_strings.append(properties.parent_url)
                if properties.root_url:
                    url_strings.append(properties.root_url)

        with self._session() as session:
            URLString.add_urls(session, url_strings)

            bind_values = {}

            bind_values['url_string_id'] = select([URLString.id])\
                .where(URLString.url == bindparam('url'))
            bind_values['parent_url_string_id'] = select([URLString.id]) \
                .where(URLString.url == bindparam('parent_url'))
            bind_values['root_url_string_id'] = select([URLString.id]) \
                .where(URLString.url == bindparam('root_url'))

            query = insert(QueuedURL).prefix_with('OR IGNORE').values(bind_values)

            all_row_values = []
            column_names = set()

            for url, url_properties, url_data in new_urls:
                row_values = {
                    'url': url,
                }

                if url_properties:
                    row_values.update(url_properties.database_items())
                else:
                    row_values['root_url'] = url
                    row_values['parent_url'] = url

                if url_data:
                    row_values.update(url_data.database_items())

                convert_dict_enum_values(row_values)

                all_row_values.append(row_values)
                column_names.update(row_values.keys())

            for row_value in all_row_values:
                for name in column_names:
                    if name not in row_value:
                        row_value[name] = None

            with QueuedURL.watch_urls_inserted(session) as get_inserted_urls:
                session.execute(query, all_row_values)

                added_urls = get_inserted_urls()

            hostnames = (URLInfo.parse(url).hostname for url in added_urls)
            session.execute(
                insert(Hostname).prefix_with('OR IGNORE'),
                [{'hostname': hostname} for hostname in hostnames]
            )

        return added_urls

    def check_out(self):
        with self._session() as session:
            table = indexedby(QueuedURL, 'ix_queued_urls_priority_status_id')
            url_record = session.query(table) \
                .filter(table.status.in_((Status.todo.value, Status.error.value))) \
                .order_by(table.priority.desc(), table.status.desc(), table.id) \
                .first()

            if not url_record:
                raise NotFound()

            url_record.status = Status.in_progress.value

            return url_record.to_plain()

    def check_in(self, url, new_status, increment_try_count=True,
                 url_result=None):
        with self._session() as session:
            values = {
                QueuedURL.status: new_status.value
            }

            if url_result:
                values.update(url_result.database_items())

            if increment_try_count:
                values[QueuedURL.try_count] = QueuedURL.try_count + 1

            # TODO: rewrite as a join for clarity
            subquery = select([URLString.id]).where(URLString.url == url)\
                .limit(1)
            query = update(QueuedURL).values(values)\
                .where(QueuedURL.url_string_id == subquery)

            session.execute(query)

            if new_status == Status.done and url_result and url_result.filename:
                query = insert(QueuedFile).prefix_with('OR IGNORE').values({
                    'queued_url_id': subquery
                })
                session.execute(query)

    def update_one(self, url, **kwargs):
        with self._session() as session:
            values = {}

            for key, value in kwargs.items():
                values[getattr(QueuedURL, key)] = value

            # TODO: rewrite as a join for clarity
            subquery = select([URLString.id]).where(URLString.url == url)\
                .limit(1)
            query = update(QueuedURL).values(values)\
                .where(QueuedURL.url_string_id == subquery)

            session.execute(query)

    def release(self):
        with self._session() as session:
            query = update(QueuedURL).values({QueuedURL.status: Status.todo.value})\
                .where(QueuedURL.status==Status.in_progress.value)
            session.execute(query)
            query = update(QueuedFile).values({QueuedFile.status: Status.todo.value}) \
                .where(QueuedFile.status==Status.in_progress.value)
            session.execute(query)

    def remove_many(self, urls):
        assert not isinstance(urls, (str, bytes)), \
            'Expected list-like. Got {}.'.format(urls)

        with self._session() as session:
            for url in urls:
                url_str_id = session.query(URLString.id)\
                    .filter_by(url=url).scalar()
                query = delete(QueuedURL).where(QueuedURL.url_string_id == url_str_id)
                session.execute(query)

    def add_visits(self, visits):
        with self._session() as session:
            WARCVisit.add_visits(session, visits)

    def get_revisit_id(self, url, payload_digest):
        with self._session() as session:
            return WARCVisit.get_revisit_id(session, url, payload_digest)

    def get_hostnames(self):
        hostnames = []
        with self._session() as session:
            for row in session.query(Hostname.hostname):
                hostnames.append(row[0])

        return hostnames

    def get_root_url_todo_count(self):
        with self._session() as session:
            return session.query(func.count(QueuedURL.id))\
                .filter_by(status=Status.todo.value)\
                .filter_by(level=0).scalar()

    def convert_check_out(self):
        with self._session() as session:
            queued_file = session.query(QueuedFile).filter_by(
                status=Status.todo.value).first()

            if not queued_file:
                raise NotFound()

            queued_file.status = Status.in_progress.value

            return queued_file.id, queued_file.queued_url.to_plain()

    def convert_check_in(self, file_id, status):
        with self._session() as session:
            values = {
                'status': status.value
            }

            query = update(QueuedFile).values(values) \
                .where(QueuedFile.id == file_id)

            session.execute(query)


class SQLiteURLTable(BaseSQLURLTable):
    '''URL table with SQLite storage.

    Args:
        path: A SQLite filename
    '''
    def __init__(self, path=':memory:'):
        super().__init__()
        # We use a SingletonThreadPool always because we are using WAL
        # and want SQLite to handle the checkpoints. Otherwise NullPool
        # will open and close the connection rapidly, defeating the purpose
        # of WAL.
        escaped_path = path.replace('?', '_')
        self._engine = create_engine(
            'sqlite:///{0}'.format(escaped_path), poolclass=SingletonThreadPool)
        sqlalchemy.event.listen(
            self._engine, 'connect', self._apply_pragmas_callback)
        DBBase.metadata.create_all(self._engine)
        self._session_maker_instance = sessionmaker(bind=self._engine)

    @classmethod
    def _apply_pragmas_callback(cls, connection, record):
        '''Set SQLite pragmas.

        Write-ahead logging, synchronous=NORMAL is used.
        '''
        _logger.debug('Setting pragmas.')
        connection.execute('PRAGMA journal_mode=WAL')
        connection.execute('PRAGMA synchronous=NORMAL')

    @property
    def _session_maker(self):
        return self._session_maker_instance

    def close(self):
        self._engine.dispose()


class GenericSQLURLTable(BaseSQLURLTable):
    '''URL table using SQLAlchemy without any customizations.

    Args:
        url: A SQLAlchemy database URL.
    '''
    def __init__(self, url):
        super().__init__()
        self._engine = create_engine(url)
        DBBase.metadata.create_all(self._engine)
        self._session_maker_instance = sessionmaker(bind=self._engine)

    @property
    def _session_maker(self):
        return self._session_maker_instance

    def close(self):
        self._engine.dispose()


URLTable = SQLiteURLTable
'''The default URL table implementation.'''


def convert_dict_enum_values(dict_):
    for key, value in dict_.items():
        if isinstance(value, enum.Enum):
            value = value.value
            dict_[key] = value


__all__ = (
    'BaseSQLURLTable', 'SQLiteURLTable', 'GenericSQLURLTable', 'URLTable',
    'convert_dict_enum_values'
)
