"""
Tools around flag handling
"""
from inspect import signature

g = getattr


class Empty:
    pass


def new(name, mod, p=None):
    p = {} if p is None else p
    n = type(name, (Empty,), p)
    n.__module__ = mod
    return n


def add_action(Flags, f, into, mod):
    n = f.__name__
    if isinstance(f, type):
        if not g(f, 'run', None):
            return
        # a class with a run method
        f.__module__ = mod
        flag = f
    else:
        d = g(f, '__doc__', '')
        p = {}
        if d:
            p['n'] = d
        flag = new(n, mod, p)
    setattr(into, n, flag)


def build_action_flags(Flags, Actions):
    """From Actions functions built the flags"""
    mod = Actions.__module__
    Flags.__module__ = mod
    FA = g(Flags, 'Actions', None)
    if not FA:
        FA = Flags.Actions = new('Actions', mod)

    As = [g(Actions, i) for i in dir(Actions) if i[0] != '_']
    [add_action(Flags, f, into=FA, mod=mod) for f in As if callable(f)]
