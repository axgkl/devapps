from dataclasses import dataclass
from queue import Queue
from interactive.conf import FLG
from interactive.tools import os, exists, create_fifo
import rx as Rx
from interactive import preview_args_sep
from threading import current_thread
from interactive.preview_process import fifo
from interactive.data import Items, FifoMsg
import time

# from interactive.tools import Items


class Fifo:
    """
    We read as fast as we can(1) from the in fifo
    so that we get always the newest preview ids into
    our process.

    Since we also process them, and that processing may take
    longer than user selects a new item to preview, we can't
    process while reading.
    We send back results only when that queue is empty, i.e.
    we have processed most recent item.

    => reader and processor are two different streams,
    connected by a queue - did not find a suitable higher level
    rx operator to do that (don't want buffer_with_time, since
    that would delay)
    """

    q = Queue()

    def observe(M):
        """M is Menu type"""
        fifos = fifo.fns(M.d_tmp)

        def listen_fifo(Obs, _, fifos=fifos):
            for _, fn in fifos.items():
                create_fifo(fn)

            while True:
                with open(fifos['q']) as fd:
                    raw_msg = fd.readline().strip()
                    if raw_msg:
                        Obs.on_next(raw_msg)

        return Rx.create(listen_fifo)

    def push_q(raw_msg):
        Fifo.q.put(raw_msg)
        return raw_msg

    def read_q():
        def q_reader(Obs, _):
            while True:
                # we want LIFO processing:
                raw_msg = Fifo.q.get()  # the oldest
                if Fifo.have_no_newer(raw_msg):
                    Obs.on_next(raw_msg)

        return Rx.create(q_reader)

    def to_fifo_msg(raw_msg, app):
        cmd, _, nr = raw_msg.split(preview_args_sep)
        return FifoMsg(raw_msg=raw_msg, app=app, item_nr=int(nr), cmd=cmd)

    def have_no_newer(msg: FifoMsg):
        """filter"""
        return msg and Fifo.q.empty()

    def send_result(msg: FifoMsg):
        app = msg.app
        # items = app.items
        # k = items.items[msg.item_nr]
        # m = app.menu
        t0 = time.time()
        # res = m.preview(k)
        res = msg.res
        res += debug_infos(t0)
        fifo.write(app.menu.d_tmp, 'a', res)


def debug_infos(t0):
    dt = int((time.time() - t0) * 1000)
    tn = current_thread().name
    return f'\n\n\n\x1b[35m{tn} [{dt}ms]\x1b[0m\n'
