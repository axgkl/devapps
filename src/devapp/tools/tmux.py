from hashlib import md5
from devapp.app import system, do, app
from devapp.tools import dir_of, exists
import os
import sys
import time

UID = os.environ.get('UID', '0')

fn_conf = f'{dir_of(__file__)}/assets/tmux.conf'
assert exists(fn_conf)


def sock(sess_name):
    return f'/tmp/devapp_tmux_{UID}_{sess_name}'


def tmux(sn):
    return f'tmux -S "{sock(sn)}" '


def have_session(sn):
    return os.system(tmux(sn) + 'has-session 1>/dev/null 2>/dev/null') == 0


# def have_pane(sn, nr):
#     ls = os.popen(tmux(sn) + 'list-panes').read().splitlines()
#     l = int([k.split(':')[0] for k in ls if 'active' in k][0])
#     return f'{panes}: ' in os.popen(tmux(sn) + 'list-panes 2>/dev/null').read()
#     # return os.system(tmux(sn) + 'list-panes 1>/dev/null 2>/dev/null') == 0


def kill_session(sess_name):
    while have_session(sess_name):
        os.system(tmux(sess_name) + 'kill-session')


def new_session(sn):
    T(sn, '-f', fn_conf, 'new-session', '-d', '/bin/bash')
    while not have_session(sn):
        print('have')
        time.sleep(0.01)
    return sn


def T(sess_name, *cmds):
    cmds = ' '.join([f"'{i}'" for i in cmds])
    system(tmux(sess_name) + cmds)


def S(sess_name, cmd):
    h = hex_(cmd)
    system(tmux(sess_name) + f'send-keys -H {h}')


def hex_(cmd):
    # cmd = 'ls'
    l = [hex(ord(c))[2:] for c in cmd]
    return ' '.join(l) + ' a'


from functools import partial

max_panes = 20


# def wait_pane(sn, nr):
#     while not have_pane(sn, nr):
#         time.sleep(0.1)

# def split_win(sn, h=False, perc=0):
#     perc = int(perc)
#     k = ['split-window', '-d', '/bin/bash']
#     if h:
#         k.insert(1, '-h')
#     if perc:
#         k.insert(1, f'{perc}%')
#         k.insert(1, '-l')
#     T(sn, *k)


def make_grid(sn, panes):
    if panes < 2:
        return
    assert panes < max_panes + 1

    [T(sn, 'split-window', '-h', '-l', '1', '-d', '/bin/bash') for i in range(panes - 1)]
    T(sn, 'select-layout', 'tiled')
    T(sn, 'select-pane', '-t', 1)
    #
    # # m = { 2: [1, 2], 3: [1, 3], 4: [2, 2], 5: [2, 3], 6: [2, 3], 7: [3, 3], 8: [3, 3], 9: [3, 3], }
    # # rows, cols = m.get(panes, (5, int((panes + 1) / 5)))
    # rows, cols = 5, int((panes + 1) / 5)   # just to avoid out of
    # split = partial(split_win, sn)
    #
    # for r in range(rows - 1):
    #     perc = int(100 / (rows - r))
    #     split(h=False, perc=perc)
    #     # wait_pane(sn, r + 2)
    # nr = 0
    # i = 0
    # while True:
    #     nr += 1
    #     print(nr, panes)
    #     if nr == 10:
    #         breakpoint()   # FIXME BREAKPOINT
    #     if nr == panes:
    #         break
    #     if float(nr) % cols == 0:
    #         i = 0   # new row
    #         continue
    #
    #     T(sn, 'select-pane', '-t', nr)
    #     p = int(100.0 / (cols - i)) * (cols - (i + 1))
    #     split(h=True, perc=100 - 100.0 / (cols - i))
    #     i += 1
    # T(sn, 'select-layout', 'tiled')
    # T(sn, 'select-pane', '-t', 1)


def make_session(cmds, sn, kill_existing):

    if sn == 'auto':
        sn = md5(str(cmds).encode('utf-8')).hexdigest()
    sn = 'devapp_' + sn
    if kill_existing:
        kill_session(sn)
    return new_session(sn)


def set_win_title(sn, title):
    T(sn, 'rename-window', title)


def run_cmds(
    cmds,
    session_name='auto',
    kill_existing=True,
    panes=True,
    attach=False,
    win_titles=None,
):
    sn = make_session(cmds, session_name, kill_existing)
    if not cmds:
        app.die('No commands', **locals())
    if isinstance(cmds[0], str):
        run_single_win_cmds(cmds, sn, panes)
    else:
        for group in cmds:
            if win_titles:
                set_win_title(sn, win_titles.pop(0))
            run_single_win_cmds(group, sn, panes)
            if group != cmds[-1]:
                T(sn, 'new-window', '/bin/bash')
        T(sn, 'select-window', '-t', '1')

    if attach:
        m = """display-popup  -E -h 5 -w 24 'echo -n "TMUX Meta: ctrl+p  "; sleep 2' &"""
        os.system('sleep 1.5 && ' + tmux(sn) + m)
        os.system(tmux(sn) + 'attach')


def run_single_win_cmds(cmds, sn, panes):
    if panes and len(cmds) <= max_panes:
        make_grid(sn, len(cmds))
        sel = 'select-pane'
    else:
        app.info('Using windows', panes=len(cmds), max=max_panes)
        [T(sn, 'new-window', '/bin/bash') for _ in range(len(cmds) - 1)]
        sel = 'select-window'

    for nr, cmd in zip(range(len(cmds)), cmds):
        # cmd += f'{nr}'
        T(sn, sel, '-t', nr + 1)
        S(sn, cmd)
        time.sleep(0.05)   # TODO otherwise noshow often
