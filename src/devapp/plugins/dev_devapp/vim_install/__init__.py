#!/usr/bin/env python
"""
Install (Neo)Vim Editor

We only offer Astrovim at this time
"""

import os

# Could be done far smaller.
from importlib import import_module

import sys
import time, json
from devapp import gevent_patched, tools
from devapp.app import FLG, app, do, run_app, system
from devapp.tools import exists
from devapp.tools_http import download
from structlogging import sl
import requests
from . import utils

here = os.path.dirname(__file__)

H = os.environ['HOME']
api_nvim = 'https://api.github.com/repos/neovim/neovim/releases'
ver_nvim = 'v0.6.1'
url_astro = 'https://github.com/kabinspace/AstroVim'
d_share = H + '/.local/share/nvim'
d_cfg = H + '/.config'
d_cfg_nvim = d_cfg + '/nvim'
d_cfg_nvim_p = lambda: d_cfg + '/nvim.%s' % FLG.flavor
nvim = H + '/.local/share/nvim.%s.appimage' % ver_nvim
h = lambda s: s.replace(H, '~')


def status():
    r = {'nvim': {'installed': exists(nvim), 'exe': h(nvim)}}
    r['astrovim'] = {'installed': exists(d_cfg_nvim), 'dir': h(d_cfg_nvim)}
    r['flavor'] = {
        'installed': exists(d_cfg_nvim_p()),
        'name': FLG.flavor,
        'dir': h(d_cfg_nvim_p()),
    }
    if not FLG.status_verbose:
        return r
    r['nvim']['versions'] = do(utils.vim_infos, api_nvim)
    return r


class Flags:
    """Install a Developer NeoVim

    We only offer nvim + AstroVim + some custom stuff at this time
    """

    autoshort = ''

    class nvim_version:
        d = 'v0.6.1'

    class distri:
        t = ['astrovim']
        d = 'astrovim'

    class flavor:
        d = 'gk'

    class flavor_install_mode:
        n = 'symlink (to devapps) will keep it updatable with git pulls or pip updates of devapps. copy decouples.'
        t = ['symlink', 'copy']
        d = 'symlink'

    class set_alias:
        n = 'Adds an alias to your .bashrc or .zshrc. Will check for presence of a $HOME/.aliases file. Set to empty string to not install an alias'
        d = 'vi'

    class backup:
        n = 'Backup all existing $HOME/.config/nvim'
        d = True

    class Actions:
        class install:
            d = False

        class status:
            d = False

            class verbose:
                s = 'sv'
                d = False

        class run:
            d = True


def ensure_d_avail(d):
    app.die('Target exists. Use --backup', dir=d) if exists(d) else 0


class inst:
    def do():
        inst.flavor(check=True)
        cmds = ['neovim', FLG.distri, 'flavor']
        do(backup)
        [do(getattr(inst, k), store=True) for k in cmds]
        do(inst.packer_sync)
        sl.print_log_store()

    def neovim():
        v = FLG.nvim_version
        url_nvim = vim_infos().get(v)
        if not url_nvim:
            app.die('Not existing nvim release', rel=v)
        url_nvim = url_nvim['appimg']['browser_download_url']
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
        ensure_d_avail(d_cfg_nvim_p())
        cmd = ' "%s" "%s"' % (d, d_cfg_nvim_p())
        if FLG.flavor_install_mode == 'copy':
            cmd = 'copy -a ' + cmd
        else:
            cmd = 'ln -s ' + cmd
        do(system, cmd, store=True)
        s = d_cfg_nvim_p() + '/setup.sh'
        if exists(s):
            do(system, s, store=True)

    def packer_sync():
        """Non interactive install
        (https://github.com/wbthomason/packer.nvim/issues/502)
        setup_mode allows the init.lua to only install plugins, so that nothing requiring
        them crashes.
        """
        cmd = 'export setup_mode=true; ' + nvim
        cmd += " --headless -c 'autocmd User PackerComplete quitall' -c 'PackerSync'"
        do(system, cmd)


def backup():
    if not FLG.backup:
        return app.warn('No backup')
    for k in d_cfg_nvim, d_cfg_nvim_p(), d_share:
        if exists(k):
            do(os.rename, k, k + '.backup.%s' % time.time(), store=True)


class S:
    is_installed = []


class Action:
    def _pre():
        sl.enable_log_store()
        return

    install = inst.do

    status = status

    def run():
        argv = sys.argv[2:]
        if argv[0] == '--run':  # this is default
            argv.pop(0)
        cmd = nvim + ' ' + ' '.join(['"%s"' % a for a in argv])
        sys.exit(os.system(cmd))


main = lambda: run_app(Action, flags=Flags)
# main = lambda: run_app(run, flags=Flags)


if __name__ == '__main__':
    main()
