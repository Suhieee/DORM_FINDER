import contextvars
import logging


_request_id_context = contextvars.ContextVar("request_id", default="-")


def get_request_id():
    return _request_id_context.get()


def set_request_id(request_id):
    return _request_id_context.set(request_id)


def reset_request_id(token):
    _request_id_context.reset(token)


class RequestIDLogFilter(logging.Filter):
    """Inject request_id into all log records for traceability."""

    def filter(self, record):
        if not hasattr(record, "request_id"):
            record.request_id = get_request_id()
        return True
