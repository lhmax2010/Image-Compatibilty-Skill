"""Phase RSS sampler for the full repository CLI, with optional peak attribution."""
from functools import wraps
import io
import json
from pathlib import Path
import resource
import sys
import threading
import time
import tracemalloc

source, inputs, destination, count, trace = sys.argv[1:]
if not Path(destination).resolve().is_relative_to(Path.cwd().resolve()):
    raise SystemExit('Use a new report directory inside the workspace.')
sys.path.insert(0, source)
import tizen_compat as cli
from compat import repository, requirements

phase = 'startup'
maxima = {}
endpoints = {}
sites = {}
done = threading.Event()

def sample():
    with open('/proc/self/status') as status:
        rss = next(int(line.split()[1]) for line in status if line.startswith('VmRSS:'))
    label = phase
    maxima[label] = max(rss, maxima.get(label, 0))
    return rss

def sampler():
    while not done.wait(0.02):
        sample()

def checkpoint(label, attribution=False):
    global phase
    endpoints[phase] = sample()
    if trace == 'trace' and attribution:
        snapshot = tracemalloc.take_snapshot()
        sites[phase] = [{'site':str(site.traceback[0]).replace(source+'/',''),
                         'size':site.size,'count':site.count}
                        for site in snapshot.statistics('lineno')[:12]]
        del snapshot
    phase = label
    sample()

def wrap(container, name, label, afterward=None, attribution=False):
    original = getattr(container,name)
    @wraps(original)
    def call(*args,**kwargs):
        if label != phase:
            checkpoint(label)
        try:
            return original(*args,**kwargs)
        finally:
            if afterward:
                checkpoint(afterward, attribution)
    setattr(container,name,call)

wrap(cli, 'collect', 'collection')
wrap(repository,'compare_repository','pairing')
wrap(repository,'Importers','comparison')
wrap(requirements,'check_available_set','requirements','comparison',True)
wrap(cli,'build_results','report assembly')
if trace == 'trace':
    wrap(cli,'generate','report assembly','report finalization',True)
    # Capture retained allocations while the caller still owns both manifests and the report.
    orig = repository.compare_repository
    @wraps(orig)
    def enter(*args,**kw):
        checkpoint('pairing', True)
        return orig(*args,**kw)
    repository.compare_repository = enter
    tracemalloc.start()
t = threading.Thread(target=sampler,daemon=True)
t.start()
started=time.monotonic()
path=Path(inputs)
try:
    code=cli.main(['--baseline',str(path/('base-'+count)),'--candidate',str(path/('cand-'+count)),
                   '--output',destination,'--objective','EXPORT_SYMBOLS'])
finally:
    checkpoint('done', trace=='trace')
    done.set()
    t.join()
out=dict(samples_kib=maxima,endpoints_kib=endpoints,peak_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss,
         wall_seconds=round(time.monotonic()-started,2),code=code,attribution=sites)
print(json.dumps(out),file=sys.stderr)
if code!=1:
    sys.exit(code or 5)
