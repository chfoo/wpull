# encoding=utf-8


import time
import unittest

from wpull.database.base import NotFound, AddURLInfo
from wpull.database.sqltable import SQLiteURLTable
from wpull.pipeline.item import Status, URLProperties, URLResult


class TestDatabase(unittest.TestCase):
    def get_url_table(self):
        return SQLiteURLTable(':memory:')

    def test_url_add_and_update(self):
        url_table = self.get_url_table()

        urls = [
            'http://example.com',
            'http://example.com/kitteh',
            'http://example.com/doge',
        ]
        url_properties = URLProperties()
        url_properties.parent_url = 'http://example.com'
        url_properties.level = 0
        url_properties.root_url = 'http://example.net'

        url_table.add_many(
            [AddURLInfo(url, url_properties, None) for url in urls],

        )

        self.assertTrue(url_table.contains(urls[0]))
        self.assertTrue(url_table.contains(urls[1]))
        self.assertTrue(url_table.contains(urls[2]))
        self.assertEqual(3, url_table.count())
        self.assertEqual(3, url_table.get_root_url_todo_count())

        for i in range(3):
            url_record = url_table.get_one(urls[i])

            self.assertEqual(urls[i], url_record.url)
            self.assertEqual(Status.todo, url_record.status)
            self.assertEqual(0, url_record.try_count)
            self.assertEqual('http://example.com', url_record.parent_url)
            self.assertEqual('http://example.net', url_record.root_url)

        url_record = url_table.check_out()

        self.assertEqual(Status.in_progress, url_record.status)

        url_result = URLResult()
        url_result.status_code = 200

        url_table.check_in(url_record.url, Status.done,
                           increment_try_count=True, url_result=url_result)

        url_record = url_table.get_one(url_record.url)

        self.assertEqual(200, url_record.status_code)
        self.assertEqual(Status.done, url_record.status)
        self.assertEqual(1, url_record.try_count)
        self.assertEqual(2, url_table.get_root_url_todo_count())

        hostnames = tuple(url_table.get_hostnames())
        self.assertEqual(1, len(hostnames))
        self.assertEqual('example.com', hostnames[0])

    def test_order_priority_status(self):
        url_table = self.get_url_table()

        urls = [
            # (URL, priority, status)
            ('http://example.org/', 1, Status.error.value),
            ('http://example.org/foo', 0, Status.todo.value),
            ('http://example.org/bar', 1, Status.todo.value),
            ('http://example.org/baz', 2, Status.error.value),
        ]
        add = []
        for url, priority, status in urls:
            url_properties = URLProperties()
            url_properties.parent_url = 'http://example.com'
            url_properties.level = 0
            url_properties.root_url = 'http://example.net'
            url_properties.priority = priority
            url_properties.status = status
            add.append(AddURLInfo(url, url_properties, None))

        url_table.add_many(add)

        self.assertEqual(
            [url_table.check_out().url for i in range(4)],
            [
                'http://example.org/baz',
                'http://example.org/bar',
                'http://example.org/',
                'http://example.org/foo',
            ]
        )

    def test_warc_visits(self):
        url_table = self.get_url_table()

        self.assertFalse(
            url_table.get_revisit_id('http://example.com/1', 'digest123')
        )

        url_table.add_visits([
            ('http://example.com/1', 'id123', 'digest123'),
            ('http://example.com/2', 'id456', 'digest456'),
        ])

        self.assertEqual(
            'id123',
            url_table.get_revisit_id('http://example.com/1', 'digest123')
        )
        self.assertEqual(
            'id456',
            url_table.get_revisit_id('http://example.com/2', 'digest456')
        )
        self.assertFalse(
            url_table.get_revisit_id('http://example.com/1', 'digestbad')
        )
        self.assertFalse(
            url_table.get_revisit_id('http://example.com/2', 'digestbad')
        )
        self.assertFalse(
            url_table.get_revisit_id('http://example.com/asdf', 'digest123')
        )

