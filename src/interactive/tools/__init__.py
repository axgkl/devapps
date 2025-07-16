import os
import sys
import yaml
import json
import time
from functools import partial
import traceback
from threading import current_thread

# ------------------------------------------------------------------- general utils:
env = os.environ
abspath = os.path.abspath
exists = os.path.exists
d = dict
g = lambda o, k, d=None: getattr(o, k, d)
is_ = isinstance
props = lambda o: [(k, g(o, k)) for k in sorted(dir(o)) if not k[0] == '_']


# ------------------------------------------------------------------- rendering utils:
def perc(perc: str, of: int):
    perc = int(perc[:-1])
    return int(of * perc / 100.0)


def get_deep(item: dict, pth):
    for i in range(len(pth)):
        item = item.get(pth[i])
        if not is_(item, dict):
            break
    return str(item)


class color:
    """convenience for ide completion"""

    black = 'black'
    red = 'red'
    green = 'green'
    yellow = 'yellow'
    blue = 'blue'
    purple = 'purple'
    cyan = 'cyan'
    white = 'white'
    darkgray = 239
    gray = 242
    lightgray = 245
    full_red = 196


colors = [
    color.black,
    color.red,
    color.green,
    color.yellow,
    color.blue,
    color.purple,
    color.cyan,
    color.white,
]
colors = {c: i for c, i in zip(colors, range(30, 30 + len(colors)))}
colors[color.darkgray] = 239
colors[color.gray] = 244
colors[color.lightgray] = 250


def ansi_color(s, c, bold=False):
    bold = '' if not bold else '1;'
    if not c:
        return s
    c = colors.get(c, c)
    if c < 30 or c > 38:
        return f'\x1b[{bold}38;5;{c}m{s}\x1b[0m'
    return f'\x1b[{bold}{c}m{s}\x1b[0m'


from pygments import highlight
from pygments.lexers import JsonLexer, YamlLexer
from yaml import dump, safe_dump
from io import StringIO


ysl = ytermf = jsl = ''
from pygments.formatters.terminal import TerminalFormatter


def colyhighlight(s, style='colorful'):
    global ysl, ytermf
    if not ysl:
        ysl = YamlLexer()
    if not ytermf:
        ytermf = TerminalFormatter(bg='dark')

    io = StringIO()
    if not isinstance(s, str):
        try:
            s = safe_dump(s, allow_unicode=True)
        except Exception:
            s = dump(s, default_flow_style=False, allow_unicode=True)
    highlight(s, ysl, ytermf, io)
    res = io.getvalue()
    io.close()
    return res


# -------------------------------------------------------------------  debug utils
def wrap(func, log):
    def f(evt, func=func, **kw):
        try:
            # p(func.__name__)
            # p(func.__name__, evt.typ)
            log.info(func.__qualname__)
            r = func(evt, **kw)
            return evt if r is None else r
        except Exception:
            # no exceptions in a stream func may happen:
            traceback_output = traceback.format_exc()
            log.error('Exception', func=str(func), tb=traceback_output)
            # when we are excepting in the fifo processor,
            # we have to kill any running fzf, since we
            # would not see anything.
            from interactive.fzf import Fzf

            Fzf.dbgstop(tb=traceback_output)

            p = partial(print, file=sys.stderr)
            # Now you can p it, or send it, or save it in a file
            p('Event: ', evt)
            p('Func: ', func)
            p(traceback_output)
            p('breakpoint set')
            breakpoint()
            keep_ctx = True

    return f


# -------------------------------------------------------------------  file utils
def create_fifo(fn):
    os.unlink(fn) if exists(fn) else 0
    os.mkfifo(fn)


# stolen from devapp tools most not needed:
def read_file(fn, dflt=None, mkfile=False, bytes=-1, strip_comments=False):
    """
    API function.
    read a file - return a default if it does not exist"""
    if not exists(fn):
        if dflt is not None:
            if mkfile:
                write_file(fn, dflt, mkdir=1)
            return dflt
        if mkfile:
            raise Exception(fn, 'Require dflt to make non existing file')
        raise Exception(fn, 'does not exist')
    with open(fn) as fd:
        # no idea why but __etc__hostname always contains a linesep at end
        # not present in source => rstrip(), hope this does not break templs
        res = fd.read(bytes)
        res = res if not res.endswith('\n') else res[:-1]
        if strip_comments:
            lines = res.splitlines()
            res = '\n'.join([l for l in lines if not l.startswith('#')])
        return res


def write_file(fn, s, log=0, mkdir=0, chmod=None, mode='w'):
    """API: Write a file. chmod e.g. 0o755 (as octal integer)"""

    fn = os.path.abspath(fn)

    if isinstance(s, (list, tuple)) and s and isinstance(s[0], str):
        s = '\n'.join(s)
    elif isinstance(s, (dict, tuple, list)):  # think of bytes, mode wb
        s = json.dumps(s, default=str)

    if log > 1:
        sep = '\n----------------------\n'
        ps = (
            s
            if 'key' not in fn and 'assw' not in fn and 'ecret' not in fn
            else '<hidden>'
        )
    e = None
    for i in 1, 2:
        try:
            with open(fn, mode) as fd:
                fd.write(s)
            if chmod:
                if not isinstance(chmod, (list, tuple)):
                    chmod = [int(chmod)]
                for s in chmod:
                    os.chmod(fn, s)
            return fn
        except IOError as ex:
            if mkdir:
                d = os.path.dirname(fn)
                os.makedirs(d)
                continue
            e = ex
        except Exception as ex:
            e = ex
        raise Exception('Could not write file: %s %s' % (fn, e))


def require_pip(package):
    import importlib

    try:
        p = importlib.import_module(package)
        return p
    except Exception:
        cmd = f'pip install {package}'
        print(f'\x1b[32mInstalling required package: {package}\x1b[0m')
        if not input(f'{cmd}\nProceed [y/N]? ').lower() == 'y':
            print('bye')
            sys.exit(1)
        os.system(cmd)
        return importlib.import_module(package)
