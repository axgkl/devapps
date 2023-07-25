#!/usr/bin/env python
"""
Installs Developer Tools

The tools currently work only on Linux, i.e. intended for server setups
"""

from devapp.tools import write_file, confirm, FLG, exists, abspath, download_file
from devapp.app import app, run_app, do, system
from time import ctime
import os

# Could be done far smaller.
H = os.environ.get('HOME', '')
_ = lambda i: i if isinstance(i, list) else [i, i]
mamba_pkgs = [
    _(i)
    for i in [
        ['rg', 'ripgrep'],
        'lazygit',
        ['fd', 'fd-find'],
        'fzf',
        ['npm', 'nodejs'],
        'unzip',
        'gcc',
        'zig',
    ]
]


class Flags:
    """Install a PDS"""

    autoshort = ''

    class nvim_config_repo:
        n = 'Repo to nvim config. GH url may be omitted. E.g. AXGKl/pds_lazy'
        d = 'LazyVim/starter'

    class Actions:
        class status:
            d = True

        class install:
            n = (
                'Installs neovim as appimage into ~/.local/bin/vi and into (activated) micromamba or conda: '
                + ', '.join([i[0] for i in mamba_pkgs])
            )

            class force:
                d = False


class tools:
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


class nvim:
    url_nvim = 'https://github.com/neovim/neovim/releases/download/stable/nvim.appimage'
    d = H + '/.local/bin'
    vi = d + '/vi'

    @classmethod
    def status(t):
        return {
            'installed': exists(t.vi),
            'exe': t.vi,
        }

    @classmethod
    def install(t):
        if not t.status()['installed']:
            conf = FLG.nvim_config_repo
            if not conf.startswith('http'):
                conf = 'https://github.com/' + conf
            app.info('Using config', repo=conf)
            d = H + '/.config/nvim'
            if os.path.exists(d):
                app.warn('nvim config exists, moving away', d=d)
                do(system, f'mv "{d}" "{d}.backup.{ctime()}"')
            do(system, f'git clone "{conf}" "{d}"')
            os.makedirs(t.d, exist_ok=True)
            os.chdir(t.d)
            os.system('rm -rf squashfs-root vi nvim.appimage')
            download_file(t.url_nvim, 'nvim.appimage', auto_extract=False)
            os.system('chmod u+x nvim.appimage && ./nvim.appimage --appimage-extract')
            # zig is the better compiler. E.g.
            s = f'#!/usr/bin/env bash\nexport CC=zig\n{t.d}/squashfs-root/usr/bin/nvim "$@"'
            write_file(t.vi, s, chmod=0o755)
        app.info(f'{t.vi} present')
        return {'nvim': t.status()}


have = lambda cmd: system(f'type "{cmd}"', no_fail=True) == 0


class mamba_tools:
    def status():
        return {k[0]: have(k[0]) for k in mamba_pkgs}

    def install():
        ret = []
        for cmd, pkg in mamba_pkgs:
            if not have(cmd):
                ret.append(pkg)
        if ret:
            mamba = None
            for mamba in 'micromamba', 'mamba', 'conda':
                if have(mamba):
                    break
            if not mamba:
                app.die('No mamba')

            do(system, f'{mamba} install -y {" ".join(ret)}')
        return {'tools': {'installed': ret, 'have': [i[0] for i in mamba_pkgs]}}


class Action:
    def status():
        return {'nvim': nvim.status(), 'tools installed': mamba_tools.status()}

    def install():
        return [nvim.install(), mamba_tools.install()]


def main():
    return run_app(Action, flags=Flags)


if __name__ == '__main__':
    main()
