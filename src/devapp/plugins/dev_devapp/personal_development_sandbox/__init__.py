#!/usr/bin/env python
"""
Installs https://github.com/AXGKl/pds on this (linux) host

- (Neo)Vim Editor
- AstroNVim Distribution
- Further customizations for python/markdown/js/...
- Tools for the IDE


The tool currently works only on Linux.
"""

from devapp.tools import confirm, FLG
from devapp.app import app, run_app
from importlib import import_module
import os

# Could be done far smaller.


class Flags:
    """Install a PDS

    We only offer nvim + AstroVim + some custom stuff at this time
    """

    autoshort = ''

    class Actions:
        class status:
            d = True

        class install:
            n = 'Installs pds - after completion you have a pds function in your shell'

            class force:
                d = False


class Action:
    def status():
        err = os.system('bash -c ". $HOME/.config/pds/setup/pds.sh source && status"')
        if err:
            app.die('pds is not installed')

    def install():
        cmds = [
            "wget 'https://raw.githubusercontent.com/AXGKl/pds/master/setup/pds.sh'",
            'chmod +x pds.sh',
            './pds.sh install',
            'rm -rf "$HOME/pds/pkgs"',
        ]
        if not FLG.install_force:
            app.info('Will run', json=cmds)
            confirm('Go?')

        for c in cmds:
            app.info(f'{c}')
            if os.system(c):
                app.die(f'Failed {c}')
        app.info('pds is installed - restart your shell')


def main():
    return run_app(Action, flags=Flags)


if __name__ == '__main__':
    main()
