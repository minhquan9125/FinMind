"""Request-local provider usage. Reservations and token estimates are never billing usage."""
from contextvars import ContextVar

generation_calls = ContextVar('generation_calls', default=None)


def begin_generation(model):
    calls = generation_calls.get()
    if calls is None:
        return None
    call = {'model': model, 'usage': None}
    calls.append(call)
    return call


def capture_usage(call, metadata):
    if call is None or not isinstance(metadata, dict):
        return
    values = [metadata.get(k) for k in ('promptTokenCount', 'candidatesTokenCount', 'totalTokenCount')]
    if all(type(v) is int and v >= 0 for v in values) and values[2] >= values[0] + values[1]:
        call['usage'] = dict(zip(('input_tokens', 'output_tokens', 'total_tokens'), values))
