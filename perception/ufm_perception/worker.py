"""One active CPU process, no waiting jobs; wall-clock deadlines are explicit."""
import copy
import math
import multiprocessing
import time

from .engine import UntrustedInputError


def _execute(connection, engine, bundle):
    try:
        connection.send(engine.process(bundle))
    finally:
        connection.close()


class BoundedPerceptionWorker:
    """A busy input is unavailable; its older in-flight result is never published later.

    Capacity is exactly one active job and zero queued jobs. This optional CPU
    mechanism does not establish cancellation safety for future GPU backends.
    """
    def __init__(self, engine, deadline_s):
        if (isinstance(deadline_s, bool) or not isinstance(deadline_s, (int, float)) or
                not math.isfinite(deadline_s) or deadline_s <= 0):
            raise ValueError('worker deadline_s must be finite and positive')
        self.engine, self.deadline_s = engine, float(deadline_s)
        self._context = multiprocessing.get_context('spawn')
        self._active = None
        self._last_input = -1
        self._last_output = -1
        self.closed = False
        self.discarded_results = 0

    @property
    def active_pid(self):
        return self._active[0].pid if self._active else None

    def submit(self, bundle):
        if self.closed:
            raise RuntimeError('perception worker is closed')
        self.engine._trusted(bundle)
        stamp = bundle['header']['timestamp']
        if stamp <= self._last_input:
            raise UntrustedInputError('worker input timestamp must increase')
        self._last_input = stamp
        if self._active is not None:
            self._last_output = stamp
            return self.engine.failure(bundle, 'perception_backend_busy')
        reader, writer = self._context.Pipe(duplex=False)
        process = self._context.Process(target=_execute, args=(writer, self.engine, bundle))
        expires = time.monotonic() + self.deadline_s
        try:
            process.start()
        except Exception:
            reader.close()
            writer.close()
            raise
        writer.close()
        self._active = process, reader, copy.deepcopy(bundle), expires
        return None

    def _release(self):
        if self._active is None:
            return
        process, reader, _, _ = self._active
        if process.is_alive():
            process.terminate()
        process.join(timeout=.2)
        if process.is_alive():
            process.kill()
            process.join(timeout=.2)
        reader.close()
        if process.is_alive():
            raise RuntimeError('perception worker did not stop')
        process.close()
        self._active = None

    def poll(self):
        if self._active is None:
            return None
        process, reader, bundle, expires = self._active
        if time.monotonic() >= expires:
            result = self.engine.failure(bundle, 'perception_backend_timeout')
        elif reader.poll():
            try:
                result = reader.recv()
            except (EOFError, OSError):
                result = self.engine.failure(bundle, 'perception_worker_exited')
        elif not process.is_alive():
            result = self.engine.failure(bundle, 'perception_worker_exited')
        else:
            return None
        self._release()
        stamp = bundle['header']['timestamp']
        if stamp <= self._last_output:
            self.discarded_results += 1
            return None
        self._last_output = stamp
        return result

    def close(self):
        self._release()
        self.closed = True
