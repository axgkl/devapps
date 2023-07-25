from devapp.app import app, FLG
from devapp.tools import exists, project, write_file, read_file, dir_of, download_file
from devapp.tools import abspath
from devapp.app import FLG, app, run_app, do, system
import sys
from functools import partial
import time
import json

now = time.time


class Api:
    """passed into the system funcs, offering methods"""

    instances = []
    err = []

    @property
    def resources(_):
        breakpoint()   # FIXME BREAKPOINT
        i = 23


api = Api()   # want properties


R = project.root
from importlib import import_module


def g(o, k, errmsg=None):
    v = getattr(o, k, None)
    if not v and errmsg:
        app.die(errmsg[0], **{errmsg[1]: k})
    return v


def organize_bzip2():
    fn = f'{workdir}/static/bzip2'
    if not exists(fn):
        url = 'https://github.com/AXGKl/static_binaries/raw/master/x86x64/bzip2'
        download_file(url, f'{workdir}/static/bzip2')
    if not exists(fn):
        app.die('could not download bzip2', url=url)


def load_spec():
    fn = FLG.system_spec
    if fn[0] != '/':
        fn = R() + '/' + fn
    if not exists(fn):
        app.die('Not found', system_spec=fn)
    sys.path.insert(0, R())
    fnm = fn.rsplit('.py', 1)[0].rsplit('/', 1)[-1]
    return import_module(f'conf.{fnm}')


import time

now = time.time


def die_on_api_err():
    for e in api.err:
        app.error(e[0], **e[1])
    if api.err:
        sys.exit(1)


def waitfor(what, f, timeout=10, dt=0):
    die_on_api_err()
    api.err.clear()

    dt = dt or timeout / 100.0
    t0 = now()
    while True:
        die_on_api_err()
        if f():
            return api.err.clear()
        if now() > t0 + timeout:
            app.die('Timeout', waiting_for=what)
        time.sleep(dt)


def have_all(qualifier):
    all = api.instances
    return 0 if any([n for n in all if not qualifier(n)]) else 1


import os

USER = os.environ['USER']
workdir = f'/tmp/ops_system_{USER}'

from threading import Thread


def spawn(f, *a, **kw):
    app.info(f.__qualname__, args=a)
    if FLG.dbg_non_parallel or len(FLG.node) == 1:
        f(*a, **kw)
        return

    def k(f=f, a=a, kw=kw):
        try:
            f(*a, **kw)
        except Exception as ex:
            api.err.append(ex.args)

    t = Thread(target=k)
    t.start()


no_node = 'XX'


def single_node_cmds(as_str=False):
    def r(a):
        for n in FLG.node:
            a = a.replace(n, no_node)
        return a

    l = [r(i) for i in list(sys.argv)]
    cmds = []
    for n in FLG.node:
        f = list(l)
        f.extend(['--node', n])
        if as_str:
            f = ' '.join([f'"{i}"' for i in f])
        cmds.append(f)
    return cmds


def prep_make_workdir_and_abspath_flags():
    FLG.node = [i for i in FLG.node if not i == no_node]
    os.makedirs(workdir, exist_ok=True)
    l = [abspath(i) for i in FLG.transfer_install_local_dirs]
    FLG.transfer_install_local_dirs = l
    FLG.system_spec = abspath(FLG.system_spec)


def tar_any_project_files():
    f = [i.strip() for i in FLG.transfer_project_files.split(',')]
    if not f or not f[0]:
        FLG.transfer_project_files = None
        return
    if any([i for i in f if not exists(i)]):
        app.die('Not found', files=f)
    cmd = f'tar cfvz proj_files.tgz {" ".join(f)}'
    do(system, cmd)
    FLG.transfer_project_files = abspath(f'./proj_files.tgz')


import sys

from rich.console import Console
from rich.table import Table


def out_table(*attrs, title=''):
    if not sys.stderr.isatty():
        return
    attrs = ['type', 'ip'] + [a for a in attrs]
    table = Table(title=title)
    [table.add_column(i, justify='center') for i in attrs]
    for n in Api.instances:
        v = [str(getattr(n, i)) for i in attrs]
        table.add_row(*v)
    console = Console()
    console.print(table)
