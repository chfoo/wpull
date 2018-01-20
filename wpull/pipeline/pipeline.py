import abc
import asyncio
import enum
import gettext
import logging

import time
from typing import Optional, Sequence, TypeVar, Generic, Iterator, Tuple, Set
from wpull.backport.logging import BraceMessage as __

_logger = logging.getLogger(__name__)

class _PoisonPill:
    pass
POISON_PILL = _PoisonPill()
ITEM_PRIORITY = 1
POISON_PRIORITY = 0


@asyncio.coroutine
def poison_pill_coro():
    return POISON_PILL


WorkItemT = TypeVar('WorkItemT')


class ItemTask(Generic[WorkItemT], metaclass=abc.ABCMeta):
    '''A class representing a task to be performed on an item.'''

    @abc.abstractmethod
    @asyncio.coroutine
    def process(self, work_item: WorkItemT):
        '''Perform the task.

        Args:
            work_item: The item to be processed.
        '''
        pass


class ItemSource(Generic[WorkItemT], metaclass=abc.ABCMeta):
    '''An object generating new items for the pipeline.'''

    @abc.abstractmethod
    @asyncio.coroutine
    def get_item(self) -> Optional[WorkItemT]:
        '''Generate an item

        Returns:
           An item to be processed through the pipeline using this ItemSource, or None if there are currently no items.
        '''
        pass


class ItemQueue(Generic[WorkItemT]):
    '''A queue of items

    This queue deals in coroutines. Add a coroutine returning an item to the queue with put_item_coro(), and retrieve it with get().

    put_item_coro() also expects a producer future, which will be cancelled if the queue is drain()ed before the item is retrieved with get() to forward this information to the producer.
    (The future is never marked as done by the queue; the item coroutine should do that.)

    In addition, the queue allows adding poison pills with put_poison_nowait(), which will take preference over any item currently in the queue. Poison pills are not counted as items.
    '''

    def __init__(self):
        self._queue = asyncio.PriorityQueue()
        self._unfinished_items = 0
        self._worker_ready_condition = asyncio.Condition()
        self._entry_count = 0

    @asyncio.coroutine
    def put_item_coro(self, item_coro: WorkItemT, producer_future: asyncio.Future):
        '''Push a new item along with its producer future to the queue. If the queue is currently non-empty, wait until it becomes empty before adding the item.'''
        while self._queue.qsize() > 0:
            yield from self.wait_for_worker()

        self._unfinished_items += 1
        self._queue.put_nowait((ITEM_PRIORITY, self._entry_count, item_coro, producer_future))
        self._entry_count += 1

    def put_poison_nowait(self):
        '''Put a poison pill in the queue.'''
        self._queue.put_nowait((POISON_PRIORITY, self._entry_count, poison_pill_coro, None))
        self._entry_count += 1

    @asyncio.coroutine
    def get(self) -> WorkItemT:
        '''Retrieve an item coroutine from the queue. This function will wait for an item coroutine if the queue is currently empty.'''
        priority, entry_count, item_coro, producer_future = yield from self._queue.get()

        yield from self._worker_ready_condition.acquire()
        self._worker_ready_condition.notify_all()
        self._worker_ready_condition.release()

        return item_coro

    @asyncio.coroutine
    def item_done(self):
        '''Mark an item as done. This shall be called by the caller of get() exactly once per item.'''
        self._unfinished_items -= 1
        assert self._unfinished_items >= 0

        yield from self._worker_ready_condition.acquire()
        self._worker_ready_condition.notify_all()
        self._worker_ready_condition.release()

    @property
    def unfinished_items(self) -> int:
        '''The number of currently unfinished items.'''
        return self._unfinished_items

    @asyncio.coroutine
    def wait_for_worker(self):
        '''Wait until a worker gets an item from the queue or marks an item as done.'''
        yield from self._worker_ready_condition.acquire()
        yield from self._worker_ready_condition.wait()
        self._worker_ready_condition.release()

    @asyncio.coroutine
    def drain(self):
        '''Drain the queue: remove all items from the queue, consider them as completed, and cancel the producer futures.'''
        while self._queue.qsize() > 0:
            priority, entry_count, item_coro, producer_future = yield from self._queue.get()
            yield from self.item_done()
            if producer_future is not None:
                producer_future.cancel()
            _logger.debug('Drained {!r} ({!r}), {} remaining, {} unfinished'.format(item_coro, producer_future, self._queue.qsize(), self._unfinished_items))


class Worker(object):
    '''A worker or consumer of the item queue, performing a sequence of tasks on an item retrieved from the queue.'''

    def __init__(self, item_queue: ItemQueue, tasks: Sequence[ItemTask]):
        self._item_queue = item_queue
        self._tasks = tasks
        self._worker_id_counter = 0

    @asyncio.coroutine
    def process_one(self, _worker_id=None):
        '''Retrieve a single item from the queue, run it through all tasks, and return the item.'''
        item_coro = yield from self._item_queue.get()
        _logger.debug('worker {} processing {!r}'.format(_worker_id, item_coro))
        item = yield from item_coro()
        _logger.debug('worker {} got: {!r}'.format(_worker_id, item))

        if item == POISON_PILL:
            return item

        if item is None:
            yield from self._item_queue.item_done()
            return item

        _logger.debug(__('Worker id {} Processing item {}', _worker_id, item))

        for task in self._tasks:
            _logger.debug('Worker {} processing item {}, task {}'.format(_worker_id, item, task))
            yield from task.process(item)

        _logger.debug(__('Worker id {} Processed item {}', _worker_id, item))

        yield from self._item_queue.item_done()

        return item

    @asyncio.coroutine
    def process(self):
        '''Run a worker loop until a poison pill is retrieved from the item queue.'''
        worker_id = self._worker_id_counter
        self._worker_id_counter += 1

        _logger.debug('Worker process id=%s', worker_id)

        while True:
            item = yield from self.process_one(_worker_id=worker_id)

            if item == POISON_PILL:
                _logger.debug('Worker quitting.')
                break


class Producer(object):
    '''A producer of items, which puts (coroutines getting) items from the item_source into the item queue.'''

    def __init__(self, item_source: ItemSource, item_queue: ItemQueue):
        self._item_source = item_source
        self._item_queue = item_queue
        self._running = False

    def _make_get_item_from_source(self, future):
        @asyncio.coroutine
        def _get_item_from_source():
            _logger.debug('Get item from source')
            item = yield from self._item_source.get_item()
            future.set_result(item)
            return item
        return _get_item_from_source

    @asyncio.coroutine
    def process_one(self):
        '''Put an item generation coroutine into the queue, wait until it is resolved (i.e. retrieved from the queue by a worker and yielded from), and return the resulting item or None if the item queue got drained before the item got processed.'''
        future = asyncio.Future()
        yield from self._item_queue.put_item_coro(self._make_get_item_from_source(future), future)
        try:
            item = yield from future
        except asyncio.CancelledError:
            item = None
        return item

    @asyncio.coroutine
    def process(self):
        '''Run the producer loop until there are no more items or stop() is called.'''
        self._running = True

        while self._running:
            item = yield from self.process_one()

            if item is None:
                if self._item_queue.unfinished_items == 0:
                    self.stop()
                    break
                else:
                    yield from self._item_queue.wait_for_worker()
                    if self._item_queue.unfinished_items == 0:
                        # If this was the last worker, stop immediately instead of going through another item.
                        self.stop()
                        break

    def stop(self):
        '''Stop the producer.'''
        if self._running:
            _logger.debug('Producer stopping.')
            self._running = False


class PipelineState(enum.Enum):
    stopped = 'stopped'
    running = 'running'
    stopping = 'stopping'


class Pipeline(object):
    '''A pipeline is a combination of an item source and a series of tasks. The items generated by the item source are processed by the tasks in the order given with support for parallelism.'''

    def __init__(self, item_source: ItemSource, tasks: Sequence[ItemTask],
                 item_queue: Optional[ItemQueue]=None):
        self._item_queue = item_queue or ItemQueue()
        self._tasks = tasks
        self._producer = Producer(item_source, self._item_queue)
        self._worker = Worker(self._item_queue, tasks)

        self._state = PipelineState.stopped
        self._concurrency = 1
        self._producer_task = None
        self._worker_tasks = set()
        self._unpaused_event = asyncio.Event()

        self.skippable = False

    @property
    def tasks(self):
        return self._tasks

    @asyncio.coroutine
    def process(self):
        '''Run the pipeline loop: start the producer if necessary, wait until the workers are done, shut down.'''
        _logger.debug('pipeline processing: {!r}'.format(self._tasks))

        if self._state == PipelineState.stopped:
            self._state = PipelineState.running
            self._producer_task = asyncio.get_event_loop().create_task(self._run_producer_wrapper())
            self._unpaused_event.set()

        while self._state == PipelineState.running:
            yield from self._process_one_worker()

        yield from self._shutdown_processing()

    @asyncio.coroutine
    def _process_one_worker(self):
        '''Create the specified number of workers and wait until at least one of them finishes. Alternatively, if the concurrency is set to zero, wait until it is modified.'''
        assert self._state == PipelineState.running, self._state

        while len(self._worker_tasks) < self._concurrency:
            _logger.debug('Creating worker')
            worker_task = asyncio.get_event_loop().create_task(self._worker.process())
            self._worker_tasks.add(worker_task)

        if self._worker_tasks:
            wait_coroutine = asyncio.wait(
                self._worker_tasks, return_when=asyncio.FIRST_COMPLETED)
            done_tasks = (yield from wait_coroutine)[0]

            _logger.debug('%d worker tasks completed', len(done_tasks))

            for task in done_tasks:
                task.result()
                self._worker_tasks.remove(task)
        else:
            yield from self._unpaused_event.wait()

    @asyncio.coroutine
    def _shutdown_processing(self):
        '''Shut down the pipeline: wait for all workers to finish, drain the item queue, and wait for the producer to stop.'''
        assert self._state == PipelineState.stopping

        _logger.debug('Exited workers loop.')

        if self._worker_tasks:
            _logger.debug('Waiting for workers to stop.')
            yield from asyncio.wait(self._worker_tasks)
        self._worker_tasks.clear()

        _logger.debug('Draining item queue')
        yield from self._item_queue.drain()

        _logger.debug('Waiting for producer to stop.')
        yield from self._producer_task

        self._state = PipelineState.stopped

    def stop(self):
        '''Stop the pipeline.'''
        if self._state == PipelineState.running:
            self._state = PipelineState.stopping
            self._producer.stop()
            self._kill_workers()

    @asyncio.coroutine
    def _run_producer_wrapper(self):
        '''Run the producer, if exception, stop engine.'''
        try:
            yield from self._producer.process()
        except Exception as error:
            if not isinstance(error, StopIteration):
                # Stop the workers so the producer exception will be handled
                # when we finally yield from this coroutine
                _logger.debug('Producer died.', exc_info=True)
                self.stop()
            raise
        else:
            self.stop()

    def _kill_workers(self):
        '''Kill the workers by putting a poison pill for each of them.'''
        for dummy in range(len(self._worker_tasks)):
            _logger.debug('Put poison pill.')
            self._item_queue.put_poison_nowait()

    @property
    def concurrency(self) -> int:
        return self._concurrency

    @concurrency.setter
    def concurrency(self, new_concurrency: int):
        '''Set the concurrency of this pipeline. The value has to be a non-negative integer. If zero, the pipeline is paused until the concurrency is modified again.'''
        if new_concurrency < 0:
            raise ValueError('Concurrency cannot be negative')

        change = new_concurrency - self._concurrency
        self._concurrency = new_concurrency

        if self._state != PipelineState.running:
            return

        if change < 0:
            for dummy in range(abs(change)):
                _logger.debug('Put poison pill for less workers.')
                self._item_queue.put_poison_nowait()
        elif change > 0:
            _logger.debug('Put 1 poison pill to trigger more workers.')
            self._item_queue.put_poison_nowait()

        if self._concurrency:
            self._unpaused_event.set()
        else:
            self._unpaused_event.clear()

    def _warn_discarded_items(self):
        _logger.warning(__(
            gettext.ngettext(
                'Discarding {num} unprocessed item.',
                'Discarding {num} unprocessed items.',
                self._item_queue.unfinished_items
            ),
            num=self._item_queue.unfinished_items
        ))


class PipelineSeries(object):
    '''A pipeline series is a sequence of pipelines to be processed in order. The concurrency is forwarded to all pipelines which are listed in concurrency_pipelines.'''

    def __init__(self, pipelines: Iterator[Pipeline]):
        self._pipelines = tuple(pipelines)
        self._concurrency = 1
        self._concurrency_pipelines = set()

    @property
    def pipelines(self) -> Tuple[Pipeline]:
        return self._pipelines

    @property
    def concurrency(self) -> int:
        return self._concurrency

    @concurrency.setter
    def concurrency(self, new_concurrency: int):
        '''Set the concurrency for all pipelines in the concurrency_pipelines set.'''
        self._concurrency = new_concurrency

        for pipeline in self._pipelines:
            if pipeline in self._concurrency_pipelines:
                pipeline.concurrency = new_concurrency

    @property
    def concurrency_pipelines(self) -> Set[Pipeline]:
        return self._concurrency_pipelines
