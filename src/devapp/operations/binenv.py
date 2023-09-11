"""
Default installation of binenv

=> Only req: path has to be set to ~/.binenv

Otherwise the tools themselves would not work, w/o export binenv... stuff

FS changes: ~/.config/binenv and ~/.bindir
"""

from devapp.tools import offset_port, exists, project
import os
import platform
from devapp.app import app, system
from devapp.tools import download_file, write_file, abspath, read_file
import json
from . import tools_help


def verify_present(path, rsc, **kw):
    return exists(path + '/binenv')


# T = """#!/usr/bin/env bash
# #export BINENV_BINDIR={envs[0]}
# #export BINENV_LINKDIR={envs[1]}
# """
inst = """
./tmp/binenv -v update
./tmp/binenv -v install binenv
"""

ENVIRON_FILE = """
test -e bin/binenv && { echo "$PATH" | grep -q binenv || PATH="$HOME/.binenv:$PATH"; binenv versions -f | grep -v '^#'; }
"""

PATCHES = """
  lazygit:
    description: A simple terminal UI for git commands.
    url: https://github.com/jesseduffield/lazygit/
    map:
      amd64: x86_64
      "386": 32-bit
      darwin: Darwin
      linux: Linux
      windows: Windows
    list:
      type: github-releases
      url: https://api.github.com/repos/jesseduffield/lazygit/releases
    fetch:
      url: https://github.com/jesseduffield/lazygit/releases/download/v{{ .Version }}/lazygit_{{ .Version }}_{{ .OS }}_{{ .Arch }}.tar.gz
    install:
      type: tgz
      binaries:
        - lazygit


  fx:
    description: Terminal JSON viewer
    url: https://github.com/antonmedv/fx/
    list:
      type: github-releases
      url: https://api.github.com/repos/antonmedv/fx/releases/
    fetch:
      url: https://github.com/antonmedv/fx/releases/download/{{ .Version }}/fx_{{ .OS }}_{{ .Arch }}
    install:
      type: direct
      binaries:
        - fx

"""

CACHEADDS = {'fx': ['24.1.0']}


def write_patches():
    fn = os.environ['HOME'] + '/.config/binenv/distributions.yaml'
    app.info(f'patching {fn}', patches=PATCHES)
    s = read_file(fn)
    sep = '  # PATCHES DEVAPP'
    s = s.split(sep)
    if s[-1] == s[0]:
        s.append('')
    s = f'{s[0].rstrip()}\n{sep}\n{PATCHES}\n{sep}\n{s[-1].rstrip()}'
    write_file(fn, s)
    write_file(fn, s)
    if CACHEADDS:
        fn = os.environ['HOME'] + '/.cache/binenv/cache.json'
        j = json.loads(read_file(fn))
        j.update(CACHEADDS)
        app.info(f'updating {fn}', patches=CACHEADDS)
        write_file(fn, json.dumps(j))


def binenv(rsc, **kw):
    R = project.root()
    fn = R + '/tmp/binenv'
    if not exists(fn):
        archi = platform.machine().replace('x86_', 'amd').lower()
        url = f'https://github.com/devops-works/binenv/releases/download/v0.19.8/binenv_{platform.uname()[0]}_{archi}'
        download_file(url, fn)
        os.chmod(fn, 0o755)

    # def r(i):
    #     d = R + '/bin/.binenv'
    #     return abspath(os.environ.get(f'binenv_{i}dir', d))
    #
    # envs = [r(i) for i in ['bin', 'link', 'cache', 'config']]
    # pre = T.format(envs=envs)

    pre = 'export PATH="$HOME/.binenv:$PATH"\n'
    fni = R + '/tmp/bininst'
    write_file(fni, pre + inst, chmod=0o755)
    system(fni)
    tools_help.write_environ(ENVIRON_FILE, match='binenv')
    write_patches()
    tools_help.write_tools_cmd()
    return {'cmd': ':' + os.environ['HOME'] + '/.binenv/binenv', 'cmd_pre': pre}


class binenv:
    """*FAST* installed version managed binary resources"""

    # environ = ['bindir', 'linkdir', 'cachedir', 'configdir']
    verify_present = verify_present
    pkg = False
    cmd = binenv
