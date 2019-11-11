import asyncio
import logging

from typing import Optional, List, Iterable

from wpull.pipeline.pipeline import ItemTask, ItemSource, Pipeline, ItemQueue, \
    PipelineSeries
from wpull.testing.async import AsyncTestCase
import wpull.testing.async

_logger = logging.getLogger(__name__)


class MyItem(object):
    def __init__(self, value):
        super().__init__()
        self.value = value
        self.processed_value = None

    def __repr__(self):
        return '<MyItem at {:x} value {}>'.format(id(self), self.value)


class MyItemSourceError(Exception):
    pass


class MySource(ItemSource[MyItem]):
    def __init__(self, items: Iterable[MyItem], test_error=False):
        self._items = list(items)
        self._test_error = test_error

    @asyncio.coroutine
    def get_item(self) -> Optional[MyItem]:
        if self._items:
            if self._test_error and len(self._items) == 1:
                raise MyItemSourceError()

            return self._items.pop(0)


class MyItemTaskError(Exception):
    pass


class MyItemTask(ItemTask[MyItem]):
    def __init__(self, callback=None, test_error=False):
        super().__init__()
        self.callback = callback
        self._test_error = test_error
        self._current_work = 0
        self._peak_work = 0
        self._item_count = 0

    @property
    def peak_work(self):
        return self._peak_work

    def reset_peak_work(self):
        self._peak_work = 0

    @property
    def item_count(self):
        return self._item_count

    @asyncio.coroutine
    def process(self, work_item: MyItem):
        self._item_count += 1

        if self._test_error and self._item_count == 3:
            raise MyItemTaskError()

        self._current_work += 1
        self._peak_work = max(self._peak_work, self._current_work)

        if self.callback:
            self.callback()

        work_item.processed_value = work_item.value * 2

        if work_item.value % 2 == 0:
            yield from asyncio.sleep(0.01)
        else:
            yield from asyncio.sleep(0.1)

        self._current_work -= 1


class TestPipeline(AsyncTestCase):
    def _new_items(self, count):
        return list(MyItem(index + 1) for index in range(count))

    def _check_item_values(self, items):
        for item in items:
            self.assertEqual(item.value * 2, item.processed_value)

    @wpull.testing.async.async_test()
    def test_simple_items(self):
        items = self._new_items(4)
        pipeline = Pipeline(MySource(items), [MyItemTask()])

        yield from pipeline.process()

        self._check_item_values(items)

    @wpull.testing.async.async_test()
    def test_item_source_error(self):
        items = self._new_items(4)
        pipeline = Pipeline(MySource(items, test_error=True), [MyItemTask()])

        with self.assertRaises(MyItemSourceError):
            yield from pipeline.process()

    @wpull.testing.async.async_test()
    def test_item_task_error(self):
        items = self._new_items(4)
        pipeline = Pipeline(MySource(items), [MyItemTask(test_error=True)])

        with self.assertRaises(MyItemTaskError):
            yield from pipeline.process()

    @wpull.testing.async.async_test()
    def test_concurrency_under(self):
        items = self._new_items(100)
        item_queue = ItemQueue()
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task], item_queue)
        pipeline.concurrency = 2

        yield from pipeline.process()

        self._check_item_values(items)
        self.assertEqual(2, task.peak_work)

    @wpull.testing.async.async_test()
    def test_concurrency_equal(self):
        items = self._new_items(100)
        item_queue = ItemQueue()
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task], item_queue)
        pipeline.concurrency = 100

        yield from pipeline.process()

        self._check_item_values(items)
        self.assertGreaterEqual(100, task.peak_work)
        self.assertLessEqual(10, task.peak_work)

    @wpull.testing.async.async_test()
    def test_concurrency_over(self):
        items = self._new_items(100)
        item_queue = ItemQueue()
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task], item_queue)
        pipeline.concurrency = 200

        yield from pipeline.process()

        self._check_item_values(items)
        self.assertGreaterEqual(100, task.peak_work)
        self.assertLessEqual(10, task.peak_work)

    @wpull.testing.async.async_test()
    def test_stopping(self):
        items = self._new_items(10)
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task])

        def task_callback():
            if task.item_count == 5:
                pipeline.stop()

        task.callback = task_callback

        yield from pipeline.process()

        self.assertEqual([i.processed_value for i in items], [2, 4, 6, 8, 10, None, None, None, None, None])

    @wpull.testing.async.async_test()
    def test_stopping_concurrency(self):
        @asyncio.coroutine
        def run(concurrency):
            items = self._new_items(10)
            task = MyItemTask()
            pipeline = Pipeline(MySource(items), [task])
            pipeline.concurrency = concurrency

            def task_callback():
                if task.item_count == 5:
                    pipeline.stop()

            task.callback = task_callback

            yield from pipeline.process()

            self.assertEqual([i.processed_value for i in items], [2, 4, 6, 8, 10, None, None, None, None, None])

        for concurrency in [2, 4, 5, 6, 10, 15]:
            yield from run(concurrency)

    @wpull.testing.async.async_test()
    def test_concurrency_step_up(self):
        items = self._new_items(100)
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task], ItemQueue())

        def task_callback():
            if task.item_count == 20:
                _logger.debug('Set concurrency 10')
                pipeline.concurrency = 10

        task.callback = task_callback

        yield from pipeline.process()

        self._check_item_values(items)
        self.assertEqual(10, task.peak_work)

    @wpull.testing.async.async_test()
    def test_concurrency_step_down(self):
        items = self._new_items(100)
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task], ItemQueue())
        pipeline.concurrency = 10

        def task_callback():
            if task.item_count == 19:
                self.assertEqual(10, task.peak_work)

            if task.item_count == 20:
                _logger.debug('Set concurrency 1')
                pipeline.concurrency = 1

            if task.item_count == 30:
                task.reset_peak_work()

        task.callback = task_callback

        yield from pipeline.process()

        self._check_item_values(items)
        self.assertEqual(1, task.peak_work)

    @wpull.testing.async.async_test()
    def test_concurrency_zero(self):
        items = self._new_items(100)
        task = MyItemTask()
        pipeline = Pipeline(MySource(items), [task], ItemQueue())
        pipeline.concurrency = 5

        def task_callback():
            if task.item_count == 10:
                _logger.debug('Set concurrency to 0')
                pipeline.concurrency = 0

                def callback():
                    _logger.debug('Set concurrency to 10')
                    pipeline.concurrency = 10

                asyncio.get_event_loop().call_later(0.5, callback)

        task.callback = task_callback

        yield from pipeline.process()

        self._check_item_values(items)
        self.assertEqual(10, task.peak_work)

    def test_pipeline_series(self):
        items = self._new_items(100)
        item_queue = ItemQueue()
        task = MyItemTask()
        pipeline_1 = Pipeline(MySource(items), [task], item_queue)
        pipeline_2 = Pipeline(MySource(items), [task], item_queue)

        series = PipelineSeries((pipeline_1, pipeline_2))
        series.concurrency_pipelines.add(pipeline_2)

        self.assertEqual(1, series.concurrency)

        series.concurrency = 2

        self.assertEqual(2, series.concurrency)
        self.assertEqual(1, pipeline_1.concurrency)
        self.assertEqual(2, pipeline_2.concurrency)
