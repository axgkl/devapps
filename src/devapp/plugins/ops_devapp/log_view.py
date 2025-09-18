"""
Process json logs into colorized ansi dev logs.

When lines cannot be json loaded we print them on stderr

-hf log_dev  flags supported, i.e. you can hilight, dimm, filter by level

Output format always set to plain
"""

import json
import re
import sys
import time

from structlog import PrintLogger

from devapp.app import FLG, app, run_app
from devapp.tools import color, exists

# skip_flag_defines.append('structlogging.sl')  # noqa: e402
from structlogging import sl

levels = sl.log_levels


class Flags:
    autoshort = ''

    class file_name:
        n = 'file name of log file with json. "-": read from stdin'
        d = '-'

    class from_journal:
        n = 'Input is from systemd journalctl in default format'
        d = False

    class from_compose:
        n = 'Input is from compose output' 
        d = False

    class add_proc:
        n = 'Set to a positive width and we will output it on the right of each line'
        d = 0

    class to_json:
        n = 'just print json loadable lines to stdout, rest to stderr. No ansi. Basically a filter, making jq work, when bogus lines are in.'
        d = False


def colorize(s, rend, p=PrintLogger(file=sys.stdout), levels=levels, proc=''):  # noqa: B008
    out = sys.stdout
    ap = FLG.add_proc
    try:
        s = json.loads(s)
        if not ap and proc:
            s['proc'] = proc
        l = s['level']
        if levels[l] < app.log_level:
            return
        s = rend(p, s['level'], s)
    except:
        if ap:
            out = sys.stderr # allows to filter out
    if ap:
        s = f'{proc.ljust(ap)} | {s}'
    out.write(s + '\n')
    # except Exception:
    #     sys.stdout.write(s + '\n')
    #     #print(s, file=sys.stderr)
    #
    #     #sys.stdout.write(f'{l[0]} | ')

sqr = '['

def compose_colorize(s, rend, clr=colorize):
    l = s.split(' | ')
    if len(l) == 1:
        l = ['', s]
    colorize(l[1], rend, proc=l[0].strip() )



def journalctl_colorize(s, rend, clr=colorize):
    l = s.split(': ', 1)
    try:
        s = l[1]
        pid = l[0].split(sqr, 1)[1][:-1]
    except Exception:
        pid ='' 
    clr(s, rend, proc=pid)


def run():
    fn = FLG.file_name
    if fn == '-':
        fd = sys.stdin
    else:
        if not exists(fn):
            app.die('not found', fn=fn)
        fd = open(fn)
    rend = sl.setup_logging(get_renderer=True)
    clr = colorize
    if FLG.from_journal: clr = journalctl_colorize
    if FLG.from_compose: clr = compose_colorize
    try:
        while True:
            s = fd.readline().strip()
            if s:
                clr(s, rend=rend)
                continue
            if not fn == sys.stdin:
                sys.stdout.flush()
                return
            time.sleep(0.1)
    except KeyboardInterrupt:
        sys.exit(1)


def main():
    sys.argv.extend(['--log_fmt=2', '--log_to_stdout'])
    return run_app(run, flags=Flags)
