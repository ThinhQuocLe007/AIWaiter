import threading
from queue import Queue

_stream_queue_tls = threading.local()


def set_stream_queue(queue: Queue | None) -> None:
    _stream_queue_tls.queue = queue


def get_stream_queue() -> Queue | None:
    return getattr(_stream_queue_tls, "queue", None)
