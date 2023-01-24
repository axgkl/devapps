"""
Tools around flag handling
"""
from inspect import signature, _empty
from functools import partial
import sys
from devapp.tools import autoshort

g = getattr


def new(name, mod, p=None):
    p = {} if p is None else p
    n = type(name, (object,), p)
    n.__module__ = mod
    return n


def cli_flag_defs(n, cli, d='', action=None):
    """Actions may have a _cli class definining action function flag params"""
    h = getattr(cli, n, None)
    if callable(h):
        h = h(action=action)
    if not h:
        h = autoshort(n, '', 5)
    if not isinstance(h, tuple):
        h = (h,)
    s = h[0]
    if len(h) > 1:
        d = h[1]
    if len(h) > 2:
        n = h[2]
    return s, d, n


def add_action(Flags, n, f, into, mod, cli, cli_args=set(sys.argv[1:])):
    # we check if user stated the action on cli, it might change default of main flag
    is_cli = False
    if n in cli_args:
        is_cli = True
    short, d, N = cli_flag_defs(n, cli, d=False)
    if N == n and f.__doc__:
        N = f.__doc__

    if short in cli_args:
        is_cli = True

    if isinstance(f, type):
        if not g(f, 'run', None):
            return

        # a class with a run method
        f.__module__ = mod
        flag = f
    else:
        # if n == 'droplet_list': breakpoint()
        p = params(n, f, mod, Flags, cli) if is_cli else {}
        flag = new(n, mod, p)
    flag.s = short
    flag.d = d
    flag.n = N
    setattr(into, n, flag)


def is_main_flag_change_its_default(Flags, k, v, empties={None, _empty}):
    """only done, when given in cli"""
    f = getattr(Flags, k, None)
    if f and isinstance(f, type):
        if v.default not in empties:
            f.d = v.default
        return True


def params(act_name, f, mod, Flags, cli):
    """
    Example:

    class Actions:
        def apply(filename=('', 'fn'), s='a'):
            'apply a filename or url'

    'fn' is the short for the filename parameter of action 'apply' (short 'a')
    """
    Flags._cli_action = act_name
    p = {}
    d = g(f, '__doc__', '')
    if d:
        p['n'] = d
    # H
    ps = signature(f).parameters
    for k, v in ps.items():
        # if k == 'private_network': breakpoint()   # FIXME BREAKPOINT
        if int(v.kind) == 4:
            # **kw
            continue
        if k[0] == '_':
            continue
        if is_main_flag_change_its_default(Flags, k, v):
            # action sig param is already a main flag, e.g. --name
            continue
        s, d, n = cli_flag_defs(k, cli, action=act_name)
        v, t = v.default, None
        if v == _empty or v == None:
            # ('default', ['own', 'default'])
            if isinstance(d, tuple):
                v = d[0]
                t = d[1]
            else:
                v = d
        m = {'d': v, 'n': n, 's': s}
        if t:
            m['t'] = t
        p[k] = new(k, mod, m)
    return p


class empty:
    pass


import time


def build_action_flags(Flags, Actions):
    """From Actions functions built the flags"""
    mod = Actions.__module__
    Flags.__module__ = mod
    FA = g(Flags, 'Actions', None)
    if not FA:
        FA = Flags.Actions = new('Actions', mod)
    cli = g(Actions, '_cli', empty)
    As = [(i, g(Actions, i)) for i in dir(Actions) if i[0] != '_']
    [add_action(Flags, n, f, into=FA, mod=mod, cli=cli) for n, f in As if callable(f)]


def set_action_func_param_values(Actions, app, FLG):
    """called in Actions._pre, i.e. post parse"""
    a = app.selected_action
    f = getattr(Actions, a, None)
    if not f:
        return
    kw = {}
    for p, d in signature(f).parameters.items():
        if p[0] == '_':
            continue
        if d.kind == 4:
            continue
        v = getattr(FLG, f'{a}_{p}', None)
        if v is None:
            v = getattr(FLG, f'{p}', None)
        if v is None:
            v = d.default
            if v == _empty or v == None:
                app.die('Missing param', param=p)
        kw[p] = v
    if kw:
        return partial(f, **kw)
