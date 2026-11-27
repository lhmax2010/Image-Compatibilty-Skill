"""Compact, process-local retention for large repository symbol inventories."""
import json
import zlib


class PackedRows:
    """Hold one collected array. Each consumer expands only the array it uses."""

    __slots__ = ('_data', '_count')

    def __init__(self, rows):
        self._count = len(rows)
        self._data = zlib.compress(json.dumps(rows, ensure_ascii=True, separators=(',', ':')).encode(), 1)

    def __len__(self):
        return self._count

    def __iter__(self):
        return iter(self.unpack())

    def unpack(self):
        return json.loads(zlib.decompress(self._data))


def encode_packed_rows(value):
    """Write the original JSON array, with no new on-disk schema."""
    if isinstance(value, PackedRows):
        return value.unpack()
    raise TypeError(f'Object of type {type(value).__name__} is not JSON serializable')


def pack_symbol_inventory(obj):
    for key in ('exports', 'imports'):
        if obj.get(key):
            obj[key] = PackedRows(obj[key])
    for key, names in obj.get('cxx', {}).items():
        if names:
            obj['cxx'][key] = PackedRows(names)
