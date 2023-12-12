"""
Inspects an api class recursively

Generates:

- documentation
-  
"""
import inspect
from devapp.tools import deindent


def func(f, skip_func_params=None, **_):
    if skip_func_params is None:
        skip_func_params = {}
    r = {}
    r['params'] = s = {}
    for k, v in inspect.signature(f).parameters.items():
        if k in skip_func_params:
            continue
        if v.kind == 4:
            continue
        s[k] = v.default
    r['doc'] = deindent(f.__doc__ or '').splitlines()
    return r


def walk(api, r=None, prefix='', **kw):
    if r is None:
        r = {}
    for k in sorted(dir(api)):
        if k[0] == '_':
            continue
        v = getattr(api, k)
        if not callable(v):
            continue
        if isinstance(v, type):
            r[prefix + k] = deindent(api.__doc__ or '').splitlines()
            walk(v, r, prefix=k + '/', **kw)
        else:
            r[prefix + k] = func(v, **kw)
    return r


def inspect_api(api, **kw):
    kw['skip_func_params'] = getattr(api, '_doc_skip_params', [])
    r = getattr(api, '_inspected', 0)
    if not r:
        r = walk(api, **kw)
        api._inspected = r
    return r


def md_doc(api, r=None):
    r = inspect_api(api) if r is None else r
    md = [f'# {api.__name__}', '## Functions']
    add = md.append
    for k, v in sorted(r.items()):
        if 'params' not in v:
            add(f'{k} (group)')
            add(''.join(v))  # class doc
            continue
        add(f'### {k}')
        add(''.join(v['doc']))
        for fk, fv in v['params'].items():
            add(f'- {fk}: {fv}')
        if v['params']:
            add('')
    return '\n'.join(md)
