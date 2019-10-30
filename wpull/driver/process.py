'''RPC processes.'''

import abc
import gettext
import json
import logging
import subprocess
import atexit
import errno
import time

import asyncio

from wpull.backport.logging import BraceMessage as __


_ = gettext.gettext
_logger = logging.getLogger(__name__)


class Process(object):
    '''Subprocess wrapper.'''
    def __init__(self, proc_args, stdout_callback=None, stderr_callback=None):
        self._proc_args = proc_args
        self._stdout_callback = stdout_callback
        self._stderr_callback = stderr_callback
        self._process = None
        self._stderr_reader = None
        self._stdout_reader = None

    @property
    def process(self):
        '''Return the underlying process.'''
        return self._process

    @asyncio.coroutine
    def start(self, use_atexit=True):
        '''Start the executable.

        Args:
            use_atexit (bool): If True, the process will automatically be
                terminated at exit.
        '''
        assert not self._process

        _logger.debug('Starting process %s', self._proc_args)

        process_future = asyncio.create_subprocess_exec(
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            *self._proc_args
        )
        self._process = yield from process_future

        _async=getattr(asyncio, 'async')
        self._stderr_reader = _async(self._read_stderr())
        self._stdout_reader = _async(self._read_stdout())

        if use_atexit:
            atexit.register(self.close)

    def close(self):
        '''Terminate or kill the subprocess.

        This function is blocking.
        '''
        if not self._process:
            return

        if self._process.returncode is not None:
            return

        _logger.debug('Terminate process.')

        try:
            self._process.terminate()
        except OSError as error:
            if error.errno != errno.ESRCH:
                raise

        for dummy in range(10):
            if self._process.returncode is not None:
                return

            time.sleep(0.05)

        _logger.debug('Failed to terminate. Killing.')

        try:
            self._process.kill()
        except OSError as error:
            if error.errno != errno.ESRCH:
                raise

    @asyncio.coroutine
    def _read_stdout(self):
        '''Continuously read the stdout for messages.'''
        try:
            while self._process.returncode is None:
                line = yield from self._process.stdout.readline()

                _logger.debug('Read stdout line %s', repr(line))

                if not line:
                    break

                if self._stdout_callback:
                    yield from self._stdout_callback(line)

        except Exception:
            _logger.exception('Unhandled read stdout exception.')
            raise

    @asyncio.coroutine
    def _read_stderr(self):
        '''Continuously read stderr for error messages.'''
        try:
            while self._process.returncode is None:
                line = yield from self._process.stderr.readline()

                if not line:
                    break

                if self._stderr_callback:
                    yield from self._stderr_callback(line)

        except Exception:
            _logger.exception('Unhandled read stderr exception.')
            raise
