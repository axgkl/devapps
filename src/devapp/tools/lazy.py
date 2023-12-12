"""
trick to get lazy loading AND gd in the editor
"""

from importlib import import_module
from devapp.app import app

# Usage:
#
# Lazy = LazyLoad()
# Lazy.tracing = 'operators.tracing'
#
# if os.environ.get('x_x'):
#     from operators import tracing
#
#     class Lazy(LazyLoad):
#         tracing = tracing
#
# in the code then:
# def foo(): Lazy.tracing.do_sth() # will work and gd will work as well


class LazyLoad:
    def __getattribute__(self, k):
        m = super().__getattribute__(k)
        if isinstance(m, str):
            app.info('lazy import', mod=m, name=k)
            m = import_module(m)
            setattr(self, k, m)
        return m
