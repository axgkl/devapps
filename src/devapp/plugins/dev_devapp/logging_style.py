#!/usr/bin/env python
"""
Logging Style

"""

import os
import sys


# Could be done far smaller.
from importlib import import_module

from devapp.app import FLG, app, do, run_app
from devapp.tools import exists

# ran these & return the output of the last one (links function):
from json import dumps, loads
import devapp
from theming.colorhilite import formatter_by_style


class Flags:
    autoshort = ''

    class Actions:
        class show:
            d = True

        class list:
            d = False

        class select:
            s = 's'
            d = False


from pygments.styles import get_all_styles
from structlogging.sl import log_levels


def all_styles():
    r = ['light', 'dark', 'ax']
    r.extend(sorted(list(get_all_styles())))
    R = []
    while r:
        k = r.pop()
        R.append(k)
        if k not in {'light', 'dark'}:
            R.append(f'true:{k}')
    return R


import time

now = time.time


from theming.colorhilite import formatter_by_style


def show():
    _, F = formatter_by_style('get')
    if hasattr(F, 'style_string'):
        ss = F.style_string
        for k, v in ss.items():
            print(f'{v[0]}{k}\x1b[0m')
        print()
    json = {'foo': {'bar': 'baz', 'baz': 42}}
    [
        getattr(app, k)(f'A {k} event', key='value', num=42, payload=json)
        for k in log_levels
    ]
    app.die('foo', silent=True)


def select():
    def k(s):
        l = s.split(':')
        L = '\x1b[0;38;5;245m'
        return f'{L}1 256c\x1b[0m {l[1]}' if len(l) - 1 else f'{L}0 true\x1b[0m {l[0]}'

    r = reversed([k(i) for i in all_styles()])
    s = '\n'.join(r)
    cmd = (
        'dev logging_style --log_dev_coljson_style {3} --log_dev_coljson_no_truecolor={1}'
    )
    cmd = f"""echo -e "{s}" | fzf --query="!256" --ansi --preview-window='right,80%' --preview='{cmd}'"""
    r = os.popen(cmd).read().strip()
    if not r:
        return
    print('Put this into your flagsfile to get the selected colorscheme:\n')
    s = r.split()
    print(f'--log_dev_coljson_style={s[2]}')
    if s[0] == '1':
        print(f'--log_dev_coljson_no_truecolor={s[0]}')
    _ = '\n\nOn the CLI you can as well use alias shortcuts. Check <appname> -hf coljson'
    print(_)


class ActionNS:
    def _pre():
        app.log._logger.level = 10


ActionNS.show = show
ActionNS.list = all_styles
ActionNS.select = select


def main():
    from structlogging.sl import flags

    sys.argv.append('--log_fmt=2')

    flags.log_level.d = '10'
    return run_app(ActionNS, flags=Flags)


if __name__ == '__main__':
    main()
