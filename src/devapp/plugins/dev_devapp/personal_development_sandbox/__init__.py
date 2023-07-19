#!/usr/bin/env python
"""
Installs Developer Tools

The tools currently work only on Linux, i.e. intended for server setups
"""

from devapp.tools import confirm, FLG, exists, abspath, download_file
from devapp.app import app, run_app, do, system
from importlib import import_module
import os

# Could be done far smaller.


class Flags:
    """Install a PDS

    We only offer nvim + AstroVim + some custom stuff at this time
    """

    autoshort = ''

    class kv:
        t = 'multi_string'

    class tool:
        t = ['none']
        d = 'none'

    class Actions:
        class status:
            d = True

        class install:
            n = 'Installs tool'

            class force:
                d = False


H = os.environ.get('HOME', '')
from time import ctime


class tools:
    _url_nvim = 'https://github.com/neovim/neovim/releases/download/stable/nvim.appimage'

    class lazyvim:
        @classmethod
        def doc(t):
            return [
                'LazyVim IDE',
                f'Installs nvim as extracted appimage into ~/.local/bin/',
                'Source: {tools._url_nvim}',
                'kv usage: Repo url (default: github) for the lazy config in --kv. Default is LazyVim/starter',
                'Example: dev pds i -t lazyvim -k AXGKl/pds_lazy.git',
            ]

        d = H + '/.local/bin'
        vi = d + '/vi'

        @classmethod
        def status(t):
            return {
                'installed': exists(t.vi),
                'exe': t.vi,
                'tool': t.__name__,
                'doc': t.doc(),
            }

        @classmethod
        def install(t):
            if not t.status()['installed']:
                conf = FLG.kv[0] if (FLG.kv and FLG.kv[0]) else 'LazyVim/starter'
                if not conf.startswith('http'):
                    conf = 'https://github.com/' + conf
                app.info('Using config', repo=conf)
                d = H + '/.config/nvim'
                if os.path.exists(d):
                    app.warn('config exists', d=d)
                    do(system, f'mv "{d}" "{d}.backup.{ctime()}"')
                do(system, f'git clone "{conf}" "{d}"')
                os.makedirs(t.d, exist_ok=True)
                os.chdir(t.d)
                os.system('rm -rf squashfs-root vi nvim.appimage')
                download_file(tools._url_nvim, 'nvim.appimage', auto_extract=False)
                os.system('chmod u+x nvim.appimage && ./nvim.appimage --appimage-extract')
                os.symlink(t.d + '/squashfs-root/usr/bin/nvim', t.d + '/vi')
            return t.status()


Flags.tool.t.extend([getattr(tools, i).__name__ for i in dir(tools) if i[0] != '_'])
import sys


class Action:
    def status():
        all = []
        if FLG.tool == 'none':
            all = Flags.tool.t
            all.remove('none')
        else:
            all = [FLG.tool]
        return [getattr(tools, t).status() for t in all]

    def install():
        if FLG.tool == 'none':
            sys.exit(app.error('no tool chosen') or 1)
        t = getattr(tools, FLG.tool)
        return t.install()
        # breakpoint()   # FIXME BREAKPOINT
        # cmds = [
        #     "wget 'https://raw.githubusercontent.com/AXGKl/pds/master/setup/pds.sh'",
        #     'chmod +x pds.sh',
        #     './pds.sh install',
        #     'rm -rf "$HOME/pds/pkgs"',
        # ]
        # if not FLG.install_force:
        #     app.info('Will run', json=cmds)
        #     confirm('Go?')
        #
        # for c in cmds:
        #     app.info(f'{c}')
        #     if os.system(c):
        #         app.die(f'Failed {c}')
        # app.info('pds is installed - restart your shell')


def main():
    return run_app(Action, flags=Flags)


if __name__ == '__main__':
    main()
