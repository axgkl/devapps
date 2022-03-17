"""
Stracktrace Tools

for console and json
"""
import sys
from functools import partial
from io import StringIO
from traceback import walk_stack, walk_tb

# populated after flag parsing by sl.py, with the pycond func and the expression string:
log_stack_filter = [0]


class flags:
    class log_stack_filter:
        """Example: fn contains project and frame lt 1"""

        n = (
            'When logging tracebacks this is an optional filter. Keywords:'
            'fn: filename, frame: frame nr, line: line nr, name: name of callable'
        )
        t = 'pycond'
        d = 'frame eq 1'


frame = lambda f, nr, fnr: {
    'frame': fnr,
    'fn': f.f_code.co_filename,
    'line': nr,
    'name': f.f_code.co_name,
}


def tb_walk(pycnd, json=False):
    tb = sys.exc_info()[2]
    return walk(tb, walk_tb, pycnd, False, json)


def frame_walk(pycnd, json=False):
    tb = sys._getframe().f_back.f_back.f_back.f_back.f_back
    return walk(tb, walk_stack, pycnd, True, json)


def walk(o, walker, pycnd, reverse, json):
    r = []
    l = [i for i in walker(o)]
    l = reversed(l) if reverse else l
    fnr = len(l) + 1
    # TODO: if frame eq 1 remains most sensible default, then check for it and do NOT
    # convert all into frames, just to skip them, except the last:
    for f, line_nr in l:
        fnr += -1
        fd = frame(f, line_nr, fnr)
        if not pycnd or pycnd(fd):
            r.append(fd if json else (f, line_nr))
    return r


# -------------------------------------------------------------------------- SL Pipeline
def stack_info(dest):
    """Returns a structlog processor, depending of type to json or to term"""
    lsf = log_stack_filter[0]

    def _stack_info(_, __, ev, dest=dest, pycnd=lsf[0], expr=lsf[1]):
        si = ev.pop('stack_info', None)
        e = ev.pop('exc', None)
        if e is not None and not isinstance(e, Exception):
            ev['exc'] = e  # just print
            e = None
        h = si or e
        if not h:
            return ev
        if dest != 'json':
            ev['stack'] = h
            return ev
        # json:
        if e:
            f, expr = log_stack_filter[0]
            ev['exc'] = [e.__class__.__name__, e.args]
            l = tb_walk(pycnd, json=True)
        elif si:
            l = frame_walk(pycnd, json=True)
        ev['stack'] = {'expr': expr, 'stack': list(l)}
        return ev

    return _stack_info


# -------------------------------------------------------------------- Terminal Renderer


def my_frames_walker(tb_or_frame, pycnd):
    """patched into rich, as walk_tb - so that it can also walk frames"""
    if hasattr(tb_or_frame, 'tb_next'):
        return tb_walk(pycnd)
    else:
        return frame_walk(pycnd)


def rich_stack(colors):
    """Prints a call stack or traceback

    Called at import time of the console renderer (which must be after Flags are parsed)

    """

    try:
        import rich
        from rich import traceback as rt

        # monkey patch rich to also loop over stacktraces w/o exceptions;
        rt.walk_tb = partial(my_frames_walker, pycnd=log_stack_filter[0][0])
        Traceback = rt.Traceback

        from rich.console import Console
    except:
        return lambda exc: str(exc)

    class StackFilter(Exception):
        pass

    def fmt(exc_or_frame, Console=Console, Traceback=Traceback):
        if isinstance(exc_or_frame, Exception):
            si = sys.exc_info()
        else:
            si = [StackFilter, StackFilter(log_stack_filter[0][1]), exc_or_frame]
        rich_io = StringIO()
        t = Traceback.from_exception(*si, show_locals=True)
        Console(file=rich_io, no_color=not colors, color_system='truecolor').print(t)
        return '\n' + rich_io.getvalue()

    return fmt
