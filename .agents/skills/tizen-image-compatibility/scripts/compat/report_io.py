"""Bounded report-only I/O. This module never opens an image or runs a collector."""
from __future__ import annotations

import csv
import gzip
import hashlib
import io
import json
import os
from pathlib import Path
import resource
import time


def evidence_path(source, ref):
    """Resolve legacy and gzip evidence inside the same report evidence root."""
    source = Path(source).resolve()
    root = source / 'evidence'
    if (not isinstance(ref, str) or not ref.startswith('evidence/')
            or any(part in ('', '.', '..') for part in ref.split('/')) or root.is_symlink()):
        raise ValueError('Invalid evidence reference')
    relative = source / ref
    for candidate in (relative, relative.with_name(relative.name + '.gz')):
        path = candidate.resolve()
        if not path.is_relative_to(root) or candidate.is_symlink():
            raise ValueError('Evidence reference escapes evidence subtree')
        if path.is_file():
            return path
    return relative.resolve()


def open_payload(path):
    return gzip.open(path, 'rb') if path.suffix == '.gz' else path.open('rb')


def manifest_path(path):
    compressed = path.with_suffix(path.suffix + '.gz')
    return compressed if not path.exists() and path.suffix == '.json' and compressed.is_file() else path


def canonical(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(',', ':'))


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def write_json(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')


def hash_file(path, check=lambda: None):
    h = hashlib.sha256()
    with open(path, 'rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
            check()
    return h.hexdigest()


def cell(value):
    if value is None:
        return 'UNKNOWN'
    text = canonical(value) if isinstance(value, (dict, list)) else str(value)
    return "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text


FINDING_COLUMNS = ('id', 'dimension', 'component', 'interface', 'baseline', 'candidate', 'status',
                   'severity', 'confidence', 'evidence', 'detection_method', 'potential_impact',
                   'recommended_action')
FINDING_DETAIL_COLUMNS = FINDING_COLUMNS + ('reason_code', 'roots', 'search_context')


def finding_cells(finding, columns):
    result = {}
    for key in columns:
        value = finding.get(key, '')
        text = canonical(value) if isinstance(value, (dict, list)) else str(value)
        result[key] = "'" + text if text.startswith(('=', '+', '-', '@', '\t', '\r')) else text
    return result


def csv_rows(path, columns, rows, check=lambda: None):
    with open(path, 'w', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: cell(row.get(k)) for k in columns})
            check()


class ResourceLimit(RuntimeError):
    pass


def memory_pressure_sample(host_available):
    try:
        return Path('/proc/pressure/memory').read_text(), host_available, {}
    except OSError:
        pass
    try:
        group = next(line[3:] for line in Path('/proc/self/cgroup').read_text().splitlines() if line.startswith('0::'))
        hierarchy = Path('/sys/fs/cgroup')
        root = hierarchy / group.lstrip('/')
        if '..' in root.relative_to(hierarchy).parts:
            return 'NOT_AVAILABLE', host_available, {}
        current = int((root/'memory.current').read_text())
        raw_limit = (root/'memory.max').read_text().strip()
        limit = None if raw_limit=='max' else int(raw_limit)
        available = host_available if limit is None else min(host_available,max(0,limit-current))
        return 'NOT_AVAILABLE', available, {'cgroup_memory_current_bytes':current,'cgroup_memory_max_bytes':limit}
    except (OSError, ValueError, StopIteration):
        return 'NOT_AVAILABLE', host_available, {}


class ResourceGuard:
    """Linux experiment limits; frequent checkpoints include SQLite VM operations."""
    def __init__(self, output, disk_budget=None):
        self.output = Path(output)
        self.disk_budget = disk_budget
        self.started = time.monotonic()
        self.last = -100.0
        self.low_since = None
        self.peak_tree_rss = 0
        self.samples = []
        self.last_snapshot = {}

    def check(self, force=False):
        now = time.monotonic()
        if not force and now - self.last < 2:
            return
        self.last = now
        mem = {line.split(':')[0]: int(line.split()[1]) * 1024
               for line in Path('/proc/meminfo').read_text().splitlines()
               if len(line.split()) == 3 and line.split()[2] == 'kB'}
        processes = {}
        for path in Path('/proc').iterdir():
            if not path.name.isdigit():
                continue
            try:
                fields = (path / 'stat').read_text().rsplit(')', 1)[1].split()
                processes[int(path.name)] = (int(fields[1]), int(fields[21]) * os.sysconf('SC_PAGE_SIZE'))
            except (OSError, ValueError, IndexError):
                continue
        selected = {os.getpid()}
        while True:
            more = {pid for pid, (parent, _) in processes.items() if parent in selected}
            if more <= selected:
                break
            selected |= more
        rss = sum(processes.get(pid, (0, 0))[1] for pid in selected)
        self.peak_tree_rss = max(self.peak_tree_rss, rss)
        allocated = sum(p.stat().st_blocks * 512 for p in self.output.rglob('*') if p.is_file())
        fs = os.statvfs(self.output)
        usage = resource.getrusage(resource.RUSAGE_SELF)
        pressure, available, cgroup = memory_pressure_sample(mem['MemAvailable'])
        sample = dict(elapsed_seconds=now - self.started, mem_available_bytes=available,
                      swap_free_bytes=mem['SwapFree'], tree_rss_bytes=rss,
                      process_peak_rss_bytes=usage.ru_maxrss * 1024,
                      cpu_seconds=usage.ru_utime + usage.ru_stime,
                      allocated_bytes=allocated, disk_free_bytes=fs.f_bavail * fs.f_frsize,
                      memory_pressure=pressure, **cgroup)
        self.last_snapshot = sample
        if force or not self.samples or now - self.samples[-1]['monotonic'] >= 10:
            with (self.output / 'resource-samples.jsonl').open('a') as stream:
                stream.write(canonical(sample) + '\n')
            self.samples.append(dict(sample, monotonic=now))
        self.low_since = (self.low_since or now) if available < 3 * 1024**3 else None
        if self.low_since and now - self.low_since >= 10:
            raise ResourceLimit('MemAvailable below 3 GiB for at least 10 seconds')
        if max(rss, usage.ru_maxrss * 1024) > 3 * 1024**3:
            raise ResourceLimit('Task process-tree RSS or process high-water RSS exceeds 3 GiB')
        if allocated > 15 * 1024**3:
            raise ResourceLimit('New report allocation exceeds 15 GiB')
        if self.disk_budget is None:
            if sample['disk_free_bytes'] < 100 * 1024**3:
                raise ResourceLimit('Available disk below 100 GiB')
        else:
            remaining = max(0, self.disk_budget - allocated)
            required = remaining + 1024**3
            sample.update(disk_estimated_work_bytes=self.disk_budget, disk_required_free_bytes=required)
            if sample['disk_free_bytes'] < required:
                raise ResourceLimit(f'Available disk below estimated remaining report allocation plus 1 GiB reserve ({required} bytes)')


class _HashReader(io.RawIOBase):
    def __init__(self, path):
        self.raw = open(path, 'rb')
        self.hash = hashlib.sha256()

    def readable(self):
        return True

    def readinto(self, buffer):
        n = self.raw.readinto(buffer)
        self.hash.update(memoryview(buffer)[:n])
        return n

    def close(self):
        self.raw.close()
        super().close()


class ReportStream:
    """Decode one selected array record at a time; split large containers by path.

    ``arrays`` names record arrays, ``objects`` names container objects. Other
    values must fit max_record_chars. A malformed/oversized input fails visibly.
    Empty arrays are retained in metadata as counts, not invented observations.
    """
    def __init__(self, path, arrays, objects, callback, check=lambda: None,
                 chunk_chars=1024 * 1024, max_record_chars=64 * 1024 * 1024):
        self.reader = _HashReader(path)
        self.buffered = io.BufferedReader(self.reader)
        payload = gzip.GzipFile(fileobj=self.buffered) if Path(path).suffix == '.gz' else self.buffered
        self.stream = io.TextIOWrapper(payload, encoding='utf-8')
        self.arrays, self.objects = set(arrays), set(objects)
        self.callback, self.check = callback, check
        self.chunk, self.limit = chunk_chars, max_record_chars
        self.buffer, self.position, self.eof = '', 0, False
        self.decoder = json.JSONDecoder()

    def fill(self, size=None):
        self.check()
        self.buffer = self.buffer[self.position:]
        self.position = 0
        if len(self.buffer) >= self.limit:
            raise ValueError('JSON record exceeds bounded decoder limit')
        block = self.stream.read(min(size or self.chunk, self.limit - len(self.buffer)))
        self.buffer += block
        if not block:
            self.eof = True

    def peek(self):
        while True:
            while self.position < len(self.buffer) and self.buffer[self.position].isspace():
                self.position += 1
            if self.position < len(self.buffer):
                return self.buffer[self.position]
            if self.eof:
                return ''
            self.fill()

    def take(self, expected):
        if self.peek() != expected:
            raise ValueError('Malformed JSON: expected ' + expected)
        self.position += 1

    def value(self):
        self.peek()
        size = self.chunk
        while True:
            try:
                value, end = self.decoder.raw_decode(self.buffer, self.position)
            except json.JSONDecodeError:
                if self.eof:
                    raise
                self.fill(size)
                size = min(size * 2, 16 * 1024 * 1024)
                continue
            if end == len(self.buffer) and not self.eof:
                self.fill()
                continue
            self.position = end
            return value

    def object(self, path=()):
        self.take('{')
        result = {}
        if self.peek() == '}':
            self.position += 1
            return result
        while True:
            key = self.value()
            if not isinstance(key, str) or key in result:
                raise ValueError('Invalid or duplicate object key')
            self.take(':')
            child = path + (key,)
            if child in self.objects and self.peek() == '{':
                value = self.object(child)
            elif child in self.arrays and self.peek() == '[':
                value = self.array(child)
            else:
                value = self.value()
            result[key] = value
            char = self.peek()
            self.position += 1
            if char == '}':
                return result
            if char != ',':
                raise ValueError('Malformed JSON object')

    def array(self, path):
        self.take('[')
        count = 0
        if self.peek() == ']':
            self.position += 1
            return {'record_count': 0}
        while True:
            self.callback(path, self.value())
            count += 1
            char = self.peek()
            self.position += 1
            if char == ']':
                return {'record_count': count}
            if char != ',':
                raise ValueError('Malformed JSON array')

    def read(self):
        try:
            result = self.object()
            if self.peek():
                raise ValueError('Trailing JSON data')
            return result, self.reader.hash.hexdigest()
        finally:
            self.stream.close()
            self.buffered.close()
