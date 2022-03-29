#!/usr/bin/env python
"""
Install (Neo)Vim Editor

We only offer Astrovim at this time
"""

import os

# Could be done far smaller.
from importlib import import_module

import time
from devapp import gevent_patched, tools
from devapp.app import FLG, app, do, run_app, system
from devapp.tools import exists
from devapp.tools_http import download
from structlogging import sl
import requests

here = os.path.dirname(__file__)

H = os.environ['HOME']
url_astro = 'https://github.com/kabinspace/AstroVim'
url_nvim = 'https://github.com/neovim/neovim/releases/download/v0.6.1/nvim.appimage'
d_share = H + '/.local/share/nvim'
d_cfg = H + '/.config'
d_cfg_nvim = d_cfg + '/nvim'
d_cfg_nvim_p = d_cfg + '/nvim.personal'
nvim = H + '/.local/share/nvim.6.1.appimage'


class Flags:
    """Install a Developer NeoVim

    We only offer nvim + AstroVim + some custom stuff at this time
    """

    autoshort = ''

    class distri:
        t = ['astrovim']
        d = 'astrovim'

    class flavor:
        d = 'gk'

    class set_alias:
        n = 'Adds an alias to your .bashrc or .zshrc. Will check for presence of a $HOME/.aliases file. Set to empty string to not install an alias'
        d = 'vi'

    class backup:
        n = 'Backup all existing $HOME/.config/nvim'
        d = True


def ensure_d_avail(d):
    app.die('Target exists. Use --backup', dir=d) if exists(d) else 0


class inst:
    def neovim():
        do(download, url_nvim, to=nvim, chmod='u+x', store=True)

    def astrovim():
        os.makedirs(H + '/.config', exist_ok=True)
        ensure_d_avail(d_cfg_nvim)
        cmd = 'git clone "%s" "%s"' % (url_astro, d_cfg_nvim)
        do(system, cmd, store=True)

    def flavor(check=False):
        d = '/'.join([here, 'flavors', FLG.flavor])
        if not exists(d):
            app.die('flavor ot found', dir=d)
        if check:
            return
        ensure_d_avail(d_cfg_nvim_p)
        cmd = 'cp -a "%s" "%s"' % (d, d_cfg_nvim_p)
        do(system, cmd, store=True)
        s = d_cfg_nvim_p + '/setup.sh'
        if exists(s):
            do(system, s, store=True)


def backup():
    if not FLG.backup:
        return app.warn('No backup')
    for k in d_cfg_nvim, d_cfg_nvim_p, d_share:
        if exists(k):
            do(os.rename, k, k + '.backup.%s' % time.time(), store=True)


def run():
    sl.enable_log_store()
    inst.flavor(check=True)
    cmds = ['neovim', FLG.distri, 'flavor']
    do(backup)
    [do(getattr(inst, k), store=True) for k in cmds]
    do(system, '"%s" +PackerSync' % nvim)
    sl.print_log_store()


main = lambda: run_app(run, flags=Flags)


if __name__ == '__main__':
    main()
