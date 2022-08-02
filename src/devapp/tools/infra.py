import time
import os, sys
from devapp.app import app, FLG, system
import threading
from devapp.tools import exists
from functools import partial

# abort while in any waiting loop (concurrent stuff failed):
DIE = []
secrets = {}

now = lambda: int(time.time())
DROPS = {}
local_drop = {'name': 'local', 'ip': '127.0.0.1'}


def run_parallel(f, range_, kw, after):
    n = kw['name']
    n = n if '{}' in n else (n + '-{}')
    names = [n.replace('{}', str(i)) for i in range_]
    t = []
    names.insert(0, 'local')   # for local tasks
    for n in names:
        k = dict(kw)
        k['name'] = n
        app.info('Background', **k)
        # time.sleep(1)
        t.append(threading.Thread(target=f, kwargs=k, daemon=False))
        t[-1].start()
    while any([d for d in t if d.isAlive()]):
        time.sleep(0.5)
    return after()


def require_tools(*tools):
    for t in tools:
        if system(f'type {t}', no_fail=True):
            at = 'https://github.com/alexellis/arkade#catalog-of-clis'
            app.error(
                f'Missing tool: {t}',
                hint=f'Consider installing arkade, which can "arkade get" these tools: {at}',
            )
            sys.exit(1)


def set_environ_vars(name=None, range=None):
    """sig: used by other scripts"""
    name = name if not name is None else FLG.name
    range = range if not range is None else FLG.range
    rl, nodes = 1, [name]
    k = lambda r: name.replace('{}', r)
    if '{}' in name:
        rl = len(range)
        nodes = [k(r) for r in range]
    os.environ['cluster_name'] = k('').replace('-', '')
    os.environ['rangelen'] = str(rl)
    os.environ['nodes'] = ' '.join(nodes)
    os.environ['dir_project'] = os.getcwd()


def wait_for(why, waiter, tmout=60, dt=3):
    t0 = now()
    tries = int(tmout / dt)
    i = 0
    l = getattr(threading.current_thread(), 'logger', app.name)
    log = app.info
    tm, still = t0, ''
    while now() - t0 < tmout:
        i += 1
        res = waiter()
        if res:
            return res
        log(f'{still}waiting for: {why}', nr=f'{i}/{tries}', logger=l)
        log = app.debug  # second...n times: debug mode
        if now() - tm > 60:
            log = app.info
            tm = now()
            still = 'still '
        time.sleep(dt)
        if DIE:
            app.die('abort')
    app.die(f'Timeout waiting for {why}', logger=l)
