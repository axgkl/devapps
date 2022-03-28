#!/usr/bin/env python
"""
Repolinks

Say your_repo depends on packages devapps and docutools.

You have those checked out next to your_repo:

├── devapps
│       ├── src
│            ├── devapp
│            ├── tree_builder
├── docutools
│       ├── src
│            ├── lcdoc
└── your_repo

Since you installed the package version, lcdoc is installed e.g. in

`$HOME/miniconda3/envs/devapps_py3.7/lib/python3.7/site-packages/lcdoc/`

Saying:

    dev mrsl -r devapps,docutool

- will move all importable(!) package folders from devapps and docutools to backup dirs (.orig)
- symlink the repo versions into your site-packages dir 

Result:

> You can work on many repos at the same time w/o having to change your pyproject.yaml file.


"""

import os

# Could be done far smaller.
from datetime import datetime
from importlib import import_module

from devapp import gevent_patched, tools
from devapp.app import FLG, app, do, run_app, system
from devapp.tools import exists

path = os.path
dirs = os.listdir
here = os.getcwd()


class Flags:
    autoshort = ''

    class repos:
        n = 'Comma sep. repo sibling to this one where we should look for packages'
        t = list


todos = {}

msg_deb = 'delete existing backup'


def inspect(repo):
    if not '.git' in dirs(here):
        app.die('Need to be in repo root')
    dr = path.abspath('../' + repo)
    if dr == here:
        app.info('Ignoring our own repo', dir=dr)
        return
    todos[repo] = mods = {}
    if not (exists(dr + '/.git') and exists(dr + '/src')):
        app.die('No repo to link', dir=dr)
    dr += '/src'
    for k in dirs(dr):
        ddr = dr + '/' + k
        if not path.isdir(ddr):
            continue
        try:
            mods[ddr] = {'mod': import_module(k)}
        except:
            app.debug('Ignoring (not importable)', dir=k, within=dr)
    rms = []

    for ddr in mods:
        m = mods[ddr].pop('mod')
        d = m.__file__.rsplit('/', 1)[0]
        if path.islink(d):
            rms.append(ddr)
            app.info('already linked', dir=d, to=os.readlink(d))
            continue
        mods[ddr]['target_dir'] = d
        mods[ddr]['src'] = ddr
        mods[ddr]['backup'] = dcp = d + '.orig'
        if path.exists(dcp):
            app.warn('will delete existing backup', backup=dcp)
            mods[ddr][msg_deb] = True
        app.info('todo', **mods[ddr])
    [mods.pop(d) for d in rms]
    if not mods:
        todos.pop(repo)
    return mods


def report(repo, c=[0]):
    if c[0]:
        return
    if not todos:
        app.die('Nothing to do')
    c[0] += 1
    msg = 'Will create the following symlinks'
    app.warn(msg)
    app.info('spec', json=todos)
    if not 'y' in input('Confirm todos [y|Q] ').lower():
        app.die('Unconfirmed...')


links = lambda repo: [do(link, spec=v) for v in todos[repo].values()]


def link(spec):
    s, t, db, b = spec['src'], spec['target_dir'], spec.get(msg_deb), spec['backup']
    if b:
        app.warn('unlinking existing', backup=b)
        os.system('/bin/rm -rf "%s"' % b)
    app.info('moving to backup', frm=t, to=b)
    os.rename(t, b)
    app.info('symlinking', frm=s, to=t)
    os.symlink(s, t)
    return {'Linked': '%s->%s' % (s, t)}


# ran these & return the output of the last one (links function):
modes = inspect, report, links


def run():
    r = [do(mode, repo=r, ll=10) for mode in modes for r in FLG.repos]
    if r:
        return r[-1]
    else:
        return app.warn('Please specify repos')


main = lambda: run_app(run, flags=Flags)


if __name__ == '__main__':
    main()
