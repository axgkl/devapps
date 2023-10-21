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
from devapp.tools import exists

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

    class to_json:
        n = 'just print json loadable lines to stdout, rest to stderr. No ansi. Basically a filter, making jq work, when bogus lines are in.'
        d = False


def colorize(s, rend, p=PrintLogger(file=sys.stdout), levels=levels, pid=None):  # noqa: B008
    try:
        s = json.loads(s)
        if pid is not None:
            s['_pid'] = pid
        l = s['level']
        if levels[l] < app.log_level:
            return
        s = rend(p, s['level'], s)
        sys.stdout.write(s + '\n')
    except Exception:
        print(s, file=sys.stderr)


sqr = '['


def journalctl_colorize(s, rend, clr=colorize):
    l = s.split(': ', 1)
    try:
        s = l[1]
        pid = l[0].split(sqr, 1)[1][:-1]
    except Exception:
        pid = 0
    clr(s, rend, pid=pid)


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
    if FLG.from_journal:
        clr = journalctl_colorize
    try:
        while True:
            s = fd.readline()
            if s:
                clr(s, rend=rend)
                continue
            time.sleep(0.1)
    except KeyboardInterrupt:
        sys.exit(1)


def main():
    sys.argv.extend(['--log_fmt=2', '--log_to_stdout'])
    return run_app(run, flags=Flags)
