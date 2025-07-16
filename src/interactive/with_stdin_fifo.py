#!/usr/bin/env python
"""
Starts a command within a pty from a controlling process, which reads "keystrokes" from a fifo
and forwards into the child.
"""

import os
import sys
import tempfile
import termios
import fcntl
import pty
import select
import signal
import struct
import time
import threading
from tty import setraw

fd_pty = None

fd_tty_stdin = sys.stdin.fileno()
fd_tty_stdout = sys.stdout.fileno()


def log(msg):
    with open('/tmp/debug', 'a') as fd:
        fd.write(f'{msg}\n')


class fifo_reader(threading.Thread):
    """fake keyboard input into the child - from a fifo, from outside"""

    def run(self):
        while 1:
            fd = os.open(self.fn_fifo, os.O_RDONLY)
            s = os.read(fd, 1024)  # blocks, waiting
            into_pty(s) if s else None

    @classmethod
    def setup_and_run_in_thread(FR):
        fr = FR(daemon=True)
        fr.fn_fifo = tempfile.NamedTemporaryFile().name
        os.mkfifo(fr.fn_fifo)
        fr.start()
        return fr.fn_fifo


def into_pty(data: bytes):
    for c in data:
        log(c)
    while data:
        n = os.write(fd_pty, data)
        data = data[n:]


def start_select_loop_over_input_fds():
    fd_inputs = [fd_pty, fd_tty_stdin]

    while True:
        try:
            polled_fds, _, _ = select.select(fd_inputs, [], [])
        except KeyboardInterrupt:
            break

        if fd_pty in polled_fds:
            # typing into the terminal:
            try:
                data = os.read(fd_pty, 1024)
            except OSError:
                data = 0
            if data:
                os.write(fd_tty_stdout, data)
            else:
                return  # EOF, stop program

        if fd_tty_stdin in polled_fds:
            # piped into this parent process:
            data = os.read(fd_tty_stdin, 1024)
            if data:
                into_pty(data)
                continue
            # got EOF
            fd_inputs.remove(fd_tty_stdin)


def term_size_into_pty(signal=0, _=0):
    """called at beginning and when we(parent) get WINCH
    The forked pty has no idea about size changes, otherwise
    """
    if signal:
        assert signal == 28  # WINCH, we are signal handler
    if fd_pty is None:
        return
    try:
        cols, rows = os.get_terminal_size()
    except Exception as _:
        f = os.popen('stty size').read().strip()  # works in tee
        rows, cols = [int(i) for i in f.split()] if f else [25, 80]
    # https://stackoverflow.com/a/6420070/4583360 - and yes, the child gets sigwinch :-)
    size = struct.pack('HHHH', rows, cols, 0, 0)
    fcntl.ioctl(fd_pty, termios.TIOCSWINSZ, size)


def run(args):
    global fd_pty
    if not args[1:]:
        args.append(os.environ.get('SHELL', '/bin/bash'))

    os.environ['STDIN_FIFO'] = fn_fifo = fifo_reader.setup_and_run_in_thread()
    signal.signal(signal.SIGWINCH, term_size_into_pty)

    pid, fd_pty = pty.fork()

    if pid == 0:
        # We are in forked pty, run the actual program therein, in a shell:
        cmd = ' '.join([f'"{i}"' for i in args[1:]])
        os.execvpe('sh', ['sh', '-c', cmd], os.environ)

    term_size_into_pty()
    try:
        cooked_attrs_before = termios.tcgetattr(fd_tty_stdin)
        setraw(fd_tty_stdin)
        was_cooked = True  # 'canonical mode'
    except termios.error:
        # e.g. when in a pipe we are already raw:
        was_cooked = False
    try:
        # blocking the master until EOF:
        start_select_loop_over_input_fds()
        os.close(fd_pty)
    finally:
        os.unlink(fn_fifo) if os.path.exists(fn_fifo) else 0
        if was_cooked:
            time.sleep(0.05)  # receive all into the term, before we switch back
            termios.tcsetattr(fd_tty_stdin, termios.TCSAFLUSH, cooked_attrs_before)

    os.waitpid(pid, 0)


if __name__ == '__main__':
    run(sys.argv)
