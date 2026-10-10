"""Small, dependency-free bounds for classic PC read-only inspectors."""
import math
from pathlib import Path

MAX_INPUT_BYTES = 64 * 1024 * 1024


def read_file(path):
    with Path(path).open('rb') as stream:
        data = stream.read(MAX_INPUT_BYTES + 1)
    if len(data) > MAX_INPUT_BYTES:
        raise ValueError('Inspection input exceeds the 64 MiB limit')
    return data


def span(data, at, size, label):
    if at < 0 or size < 0 or at > len(data) or size > len(data) - at:
        raise ValueError(f'{label}: table is outside the source file')


def finite(values, label):
    if not all(math.isfinite(value) for value in values):
        raise ValueError(f'{label}: non-finite value')
