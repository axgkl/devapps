#!/usr/bin/env python
"""
Since entr always requires 2 terminals, one for entr, one for the reloader,
we've put filewatching capabilities into the devapp itself - spawned as back
ground process - this one.

Usage:
    See devapp.app.py, search dirwatch
"""
signal_handled = 1   # here app will continue
import os
import sys
import time
from fnmatch import fnmatch
from functools import partial
import signal

WD = 'WATCHDOG: '

out = partial(print, file=sys.stderr)
die = [0]
now = time.time


def last(c=[0]):
    t0 = c[0]
    c[0] = now()
    return t0


def start_dir_watch(dir_pid_match_rec):
    dir, pid, match, recursive, sig, freq = dir_pid_match_rec.split(':')
    recursive = bool(recursive)
    sig = int(sig or signal_handled)
    freq = int(freq or 1)
    pid = int(pid)
    if not '*' in match:
        match = ('*' + match + '*').replace('**', '*')
    l = dict(locals())
    l.pop('dir_pid_match_rec')

    out(WD + 'starting. %s' % str(l)[1:-1].replace("'", ''))
    from watchdog.observers import Observer
    from watchdog.events import FileSystemEventHandler

    class H(FileSystemEventHandler):
        def on_modified(self, event, pid=pid):
            # out(WD + 'match' + self.match + '.')
            if self.match:
                if not fnmatch(event.src_path, self.match):
                    return
            if now() - last() < freq:
                return
            time.sleep(0.1)   # give app time to finish write
            _ = f' => Sending signal {sig}!'
            out(WD + f'Matching event: {event.event_type}  path : {event.src_path} {_}')
            try:
                os.kill(int(pid), sig)
            except Exception:
                pass
            if sig != signal_handled:
                out(WD + 'Exitting watchdog')
                die[0] = 1
                sys.exit(0)

    o, h = Observer(), H()
    if isinstance(match, str):
        h.match = match
    else:
        raise Exception('spec not supported')

    o.schedule(h, path=dir, recursive=recursive)
    o.start()
    while not die[0]:
        time.sleep(0.2)


if __name__ == '__main__':
    start_dir_watch(sys.argv[1])
