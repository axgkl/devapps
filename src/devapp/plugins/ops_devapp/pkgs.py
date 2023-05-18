#!/usr/bin/env python
"""
Package Operations

Currently only: Fetch private pips into a folder and create an index.

ops pkgs fetch --into=./d --private_pips lc-wifi=1.2.3 lc-python
"""


# Could be done far smaller.
from devapp.app import FLG, app, run_app, do, system
import json
import os
import shutil


from devapp.tools import read_file, write_file
import json
import sys


class Flags:
    autoshort = ''

    class into:
        n = 'target folder'
        d = ''

    class private_pips:
        n = 'list pips in pip install format, e.g. "foo bar==1.2.3" => must be listed at end of args!'
        d = ''

    class Actions:
        class fetch:
            """Downloads private pips"""


fn_pips = lambda: FLG.into + '/pips.json'
read_pips = lambda d: json.loads(read_file(fn_pips(), dflt='{}'))


import tempfile


def fetch_pips(pips):
    d = FLG.into
    pks = read_pips(d)

    with tempfile.TemporaryDirectory() as d_tmp:
        try:
            for pip in pips:
                fn = pks.get(pip, 'xx')
                if os.path.exists(d + '/' + fn):
                    continue
                cmd = f'cd "{d_tmp}" && python -m pip download --no-deps --no-build-isolation "{pip}"'
                err = os.system(cmd)
                if err:
                    app.die('Download pip err', cmd=cmd)
                pks[pip] = p = os.listdir(d_tmp)[0]
                shutil.move(d_tmp + '/' + p, d + '/' + p)
        finally:
            shutil.rmtree(d_tmp) if os.path.exists(d_tmp) else 0
    # small race condition here, when many procs read an update the file:
    pks.update(read_pips(d))
    write_file(fn_pips(), json.dumps(pks, indent=2))
    return {d: pks}


def fetch():
    os.makedirs(FLG.into, exist_ok=True)
    pips = FLG.private_pips
    if not pips:
        app.die('Nothing to fetch')
    # we allow chaining of pips at end
    return {'pips': fetch_pips(pips.split(' '))}


def run():
    # os.system(f'notify-send "{sys.argv[3:]}"')
    FLG.into = os.path.abspath(FLG.into)
    if FLG.fetch:
        return fetch()


main = lambda: run_app(run, flags=Flags)


if __name__ == '__main__':
    main()
