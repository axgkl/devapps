"""
Process is the Preview Process.


We do not want to import expensive libs, so main app has to format all for us, we only
print it out.
"""

import interactive
import sys
import os
import time

esep = interactive.execute_args_sep
asep = interactive.cb_args_sep


def serialize_fzf_execute_cmd(menu, d_tmp, name):
    return 'fui ' + esep.join(('', d_tmp, name, '{+1}'))


brk = {'{', '[', ']', '}', '},', '],'}
import re

ansi_escape = re.compile(r'\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])')
ansi_stripped = lambda s: ansi_escape.sub('', s)


class fifo:
    """
    Running the communication with the main process from the preview process.


    The main process counterpart is a descendant of this:
    It listens on our queries and replies from the main proc, formatted already - we
    simply print it out, and not load expensive formatter libs.

    Remember:

    This proc is simply killed and restarted with another item nr by FZF,
    every time when the user tem selection changes or fzf exits.


    TODO: build in support for answers which are

    - static
    - streaming (fzf can handle that - displays what we print, in the preview window)

    """

    def fns(d_tmp):
        return {'q': d_tmp + '/fifo.q', 'a': d_tmp + '/fifo.a'}

    def write(d_tmp, which, s):
        with open(fifo.fns(d_tmp)[which], 'w') as fd:
            fd.write(s + '\n')

    def sub_proc_to_app(d_tmp, to_app):
        while not os.path.exists(d_tmp):
            # main proc creates the dir - we should not be faster, but just in case:
            time.sleep(0.1)

        fifo.write(d_tmp, 'q', to_app)
        with open(fifo.fns(d_tmp)['a']) as fdanswer:
            while True:
                s = fdanswer.readline()
                if not s:
                    break
                j = s.strip()
                # if ansi_stripped(s).strip() in brk: continue
                if j == 'cancelled':
                    os.kill(os.getppid(), 9)
                    sys.exit(0)
                if j == 'done':
                    sys.exit(0)
                if s:
                    print(s, end='')


# debug:
def n(*msg, c=[-1], **kw):
    c[0] += 1
    nr, a = c[0], ' '.join(msg)
    os.system(f'notify-send "preview {nr} {a} {kw}"')


class execute:
    def main(argv):
        # from interactive import fzf_ctrl

        # fzf_ctrl.app.notify('exec ', args=str(argv))
        # os.popen('ls / |fzf').read()
        _, d_tmp, name, itemnr = argv[1].split(esep)
        if len(argv) > 2:
            itemnr = ' '.join([itemnr] + argv[2:])
        return fifo.sub_proc_to_app(d_tmp, name, itemnr, want='exec')


def main(argv):
    # argv like ['/home/gk/miniconda3/envs/devapps_py3.7/bin/fui', 'p', '/tmp/fui_gk/DirView', '1']

    _, cmd, d_tmp, args = argv

    # with open('/tmp/a', 'a') as fd:
    #     fd.write(str(argv))
    # return

    return fifo.sub_proc_to_app(d_tmp, interactive.preview_args_sep.join(argv[1:]))
