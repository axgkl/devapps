"""
Tools around flag handling
"""
from inspect import signature
from functools import partial

g = getattr


def new(name, mod, p=None):
    p = {} if p is None else p
    n = type(name, (object,), p)
    n.__module__ = mod
    return n


def add_action(Flags, n, f, into, mod, sigdef):
    if isinstance(f, type):
        if not g(f, 'run', None):
            return

        # a class with a run method
        f.__module__ = mod
        flag = f
    else:
        p = params(f, mod, sigdef)
        flag = new(n, mod, p)
    setattr(into, n, flag)


def params(f, mod, sigdef):
    '''
    Example:
    class Actions:
        def apply(filename=('', 'fn'), s='a'):
            """apply a filename or url"""

    'fn' is the short for the filename parameter of action 'apply' (short 'a')
    '''
    p = {}
    d = g(f, '__doc__', '')
    if d:
        p['n'] = d
    if not sigdef:
        return p
    # H
    for k, v in signature(f).parameters.items():
        if k == 's':
            p['s'] = v.default
        else:
            v = v.default
            if isinstance(v, tuple):
                m = {'d': v[0]}
                if len(v) > 1 and v[1]:
                    m['s'] = v[1]
                if len(v) > 2 and v[2]:
                    m['n'] = v[2]
            else:
                m = {'d': v}

            p[k] = new(k, mod, m)
    return p

def set_action_func_param_values(Actions, app, FLG): 
        a = app.selected_action
        f = getattr(Actions, a, None)
        if not f:
            return
        kw = {}
        for p in signature(f).parameters:
            if len(p) < 2: continue
            v = getattr(FLG, f'{a}_{p}', None)
            if v is None:
                v = getattr(FLG, f'{p}', None)
            if v is None:
                app.die('Missing param', param=p)
            kw[p] = v
        if kw:
            return partial(f, **kw)

def build_action_flags(Flags, Actions, define_from_signatures=False):
    """From Actions functions built the flags"""
    mod = Actions.__module__
    Flags.__module__ = mod
    FA = g(Flags, 'Actions', None)
    if not FA:
        FA = Flags.Actions = new('Actions', mod)

    As = [(i, g(Actions, i)) for i in dir(Actions) if i[0] != '_']
    [
        add_action(Flags, n, f, into=FA, mod=mod, sigdef=define_from_signatures)
        for n, f in As
        if callable(f)
    ]
