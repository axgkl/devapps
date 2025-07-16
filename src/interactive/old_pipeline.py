import rx as Rx
from rx.subject.subject import Subject
import time
import sys
import subprocess as sp
from interactive.conf import FLG, argv0
from rx import operators as rx
from functools import partial
from interactive import item_delimiter
from dataclasses import dataclass, asdict

# from dataclasses import dataclass, field, asdict
from interactive.tools import wrap, json
from interactive import fifo, preview_args_sep, execute_args_sep


g = lambda o, k, d=None: getattr(o, k, d)
is_ = isinstance
props = lambda o: [(k, g(o, k)) for k in sorted(dir(o)) if not k[0] == '_']


pipeline = lambda *ops: lambda s, ops=ops: s.pipe(*[rx.map(i) for i in ops])

is_rx = lambda f: 'rx.' in f.__module__
is_dbg = lambda: True


def pipeline(*ops):
    def stream(s, ops=ops):
        p = []
        for o in ops:
            if not is_rx(o):
                if is_dbg:
                    o = wrap(o)
                p.append(rx.map(o))
            else:
                p.append(o)

        return s.pipe(*p)

    return stream


class const:
    resized = 0
    killed = 1
    interrupted = 2
    auto = 'auto'

    # evt types:
    signal = 'signal'
    app_start = 'app_start'
    first_items = 'first_items'  # different stream then stream updates
    fzf_keyb_interrupt = 'fzf ctrl-c pressed'


import os

import signal

#
# class Evt:
#     # evt types:
#
#     typ = None
#     data = None
#
#     def __init__(self, typ, data):
#         self.typ = typ
#         self.data = data
#
#     def __repr__(self):
#         return f'Event [{self.typ}] {self.data}'
#
#
# def start_signal_handler():
#     for sig in [
#         signal.SIGTERM,
#         signal.SIGINT,
#         signal.SIGWINCH,
#     ]:
#         signal.signal(sig, lambda signr, _: push_new_event(Evt.signal, signr))
#
#
# class app:
#     def die(msg, **kw):
#         print(msg, kw) or sys.exit(1)
#
#
Events = Subject()


# ---------------------------------------------------------------
class S:
    App = None  # having subclasses for the various lists
    app_disposable = None


class DataObj:
    @classmethod
    def make_data_obj(F, UserClass):
        breakpoint()  # FIXME BREAKPOINT
        f = set(F.__dataclass_fields__.keys())
        kw = {k: g(UserClass, k) for k in dir(UserClass) if k in f}
        kw['name'] = kw.get('name') or UserClass.__name__
        return UserClass(**kw)


@dataclass
class App(DataObj):
    name: str = ''
    default_menu: str = ''

    @classmethod
    def add_dflt_menu(A, evt):
        assert evt.typ == const.app_start
        a = evt.app
        n = a.default_menu
        if not n:
            ms = [(n, o) for n, o in props(a) if is_(o, type) and hasattr(o, 'produce')]
            n = ms[0][0]
        usermenu = g(a, n)
        evt.menu = Menu.make_data_obj(usermenu)
        return evt


@dataclass
class Menu(DataObj):
    first_items: list = field(default_factory=list)
    fzf_lines: list = field(default_factory=list)
    name: str = ''
    d_tmp: str = ''  # menu specific tempdir for fifos and cache

    @classmethod
    def prepare_fs(M, evt):
        m = evt.menu
        m.d_tmp = _ = FLG.d_tmp + '/' + m.name
        os.makedirs(_, exist_ok=True)
        return evt

    @classmethod
    def produce_first_items(M, evt):
        m = evt.menu
        m.first_items.clear()
        m.first_items.extend(m.produce())
        push_new_event(const.first_items, evt=evt)
        return evt

    @classmethod
    def pre_render(M, evt):
        return evt

    @classmethod
    def render(M, evt):
        m = evt.menu
        items = m.first_items
        counted = zip(range(len(items)), items)
        d = item_delimiter
        # space needed at beginning, otherwise --read0 fails, no detection of item seps:
        s = [f' {i}{d}{r}' for i, r in counted]
        m.fzf_lines = s
        return evt

    @classmethod
    def cleanup(M, evt):
        """any cleanup tasks at app end"""
        print('cleanup, bye')
        return evt


@dataclass
class Term:
    rows: int = 0
    columns: int = 0

    clear_screen = classmethod(lambda _, x: print(ansi_cls) or x)

    @classmethod
    def measure_size(T, evt):
        t = evt.term
        _ = os.get_terminal_size()
        t.rows, t.columns = [_.lines, _.columns]
        return evt


@dataclass
class Preview:
    fifo_in: str = ''  # sent FROM the fzf spawned preview subproc

    @classmethod
    def start_fifos(P, evt):
        d_tmp = evt.menu.d_tmp
        cb = partial(P.handle_fifo_incomming, evt=evt)
        fifo.fifo_thread.start_listen(d_tmp, cb)
        return evt

    @classmethod
    def handle_fifo_incomming(P, msg, evt):
        Fzf.kill_proc(evt)
        breakpoint()  # FIXME BREAKPOINT
        i = 23


@dataclass
class Fzf:
    cmd: str = ''
    result: list = field(default_factory=list)
    result_type: int = 0
    proc: object = None  # the fzf process while running
    preview: str = ''

    @classmethod
    def kill_proc(F, evt, signal=15):
        proc = evt.fzf.proc
        evt.fzf.proc = signal  # so that run knows what happened
        if not proc:
            return evt
        if signal == 9:
            proc.terminate()
        else:
            proc.kill()
        return evt

    @classmethod
    def set_layout_pre_fmt(F, evt):
        """anything to hint to the items formatter?"""
        return evt

    @classmethod
    def set_layout(F, evt):
        return evt

    def set_preview_cmd(self, evt):
        foo = self.previewx
        i = foo
        c = preview_args_sep.join(('', evt.menu.d_tmp, 'N', '{1}'))
        c = f'{argv0} {c}'
        F.preview = c
        return evt

    @classmethod
    def set_binds(F, evt):
        return evt

    @classmethod
    def set_opts(F, evt):
        return evt

    @classmethod
    def build_cmd(F, evt):
        breakpoint()  # FIXME BREAKPOINT
        f = evt.fzf
        l = [
            'fzf',
            '--preview="echo {}"',
            '--ansi',
            '--cycle',
            f'--delimiter="{item_delimiter}"',
            '--height="50%"',
            '--multi',
            '--print0',
            '--print-query',
            '--read0',
            '--with-nth="2..2"',
        ]
        f.cmd = ' '.join(l)
        return evt

    @classmethod
    def run(F, evt):
        cmd = evt.fzf.cmd
        p = evt.fzf.proc = sp.Popen(f'{cmd}', shell=True, stdin=sp.PIPE, stdout=sp.PIPE)
        for k in evt.menu.fzf_lines:
            p.stdin.write(bytes(k, 'utf-8') + b'\x00')
        p.stdin.flush()
        p.stdin.close()
        res = str(p.stdout.read(), 'utf-8')
        res = res.split('\x00')
        if is_(p, int):
            # killed from elsewhere
            exitcode = p
        else:
            exitcode = _ = p._wait(None)
        evt.fzf.proc = None
        res.insert(0, exitcode)
        evt.fzf.result = res
        return evt

    @classmethod
    def qualify_result(F, evt):
        typ = const.fzf_keyb_interrupt
        evt.fzf.result_type = typ
        return evt

    @classmethod
    def push_result(F, evt):
        typ = evt.fzf.result_type
        push_new_event(typ, evt=evt)
        return evt


@dataclass
class Event:
    typ: int
    term: Term
    app: App
    fzf: Fzf
    preview: Preview
    menu: Menu = None

    def __repr__(self):
        d = asdict(self)
        return json.dumps(d, indent=4)


def push_new_event(typ, evt=None, app=None):
    kw = {}
    if app:
        kw['app'] = App.make_data_obj(app)
        kw['term'] = Term()
        kw['preview'] = Preview()
        kw['fzf'] = Fzf()
    elif evt:
        kw = {
            'app': evt.app,
            'menu': evt.menu,
            'fzf': evt.fzf,
            'term': evt.term,
            'preview': evt.preview,
        }
    evt = Event(typ=typ, **kw)
    Events.on_next(evt)


Pipelines = {
    const.app_start: [
        Term.clear_screen,
        App.add_dflt_menu,
        Menu.prepare_fs,
        Menu.produce_first_items,
    ],
    const.first_items: [
        Term.measure_size,
        Fzf.set_layout_pre_fmt,
        Menu.pre_render,
        Menu.render,
        Fzf.set_layout,
        Preview.start_fifos,
        Fzf.set_preview_cmd,
        Fzf.set_binds,
        Fzf.set_opts,
        Fzf.build_cmd,
        Fzf.run,
        Fzf.qualify_result,
        Fzf.push_result,
    ],
    const.fzf_keyb_interrupt: [Menu.cleanup],
}
#         Menu.fzf_items_setup,
#         Fzf.set_layout_post_data,
#         Menu.fzf_item_lines,
#         Fzf.set_binds,
#         Fzf.set_opts,
#         Fzf.run,
#     ],
# }


def build_main_stream():
    return Events.pipe(
        rx.group_by(lambda evt: evt.typ),
        rx.flat_map(lambda s: pipeline(*Pipelines[s.key])(s)),
    )


def start(App):
    S.App = App
    s = build_main_stream()
    S.app_disposable = s.subscribe(print, print, print)
    push_new_event(const.app_start, app=App)


ansi_cls = '\x1b[2J'
# if __name__ == '__main__':
#
#     class MyApp(App):
#         class L1(Menu):
#             def produce(self):
#                 return [{'name': 'foo'}, {'name': 'bar'}]
#
#     start(MyApp)
#

# being_archive


# name: str
# by_evt = lambda evt: evt.data['cur_menu']
# cur_cls = lambda evt: Menu.by_evt(evt)['cls']
#
# class Defaults:
#     streaming = False
#     preview_pos = const.auto
#     items_width_min = 10
#
# def add_defaults(evt):
#     # settings things we want to rely on:
#     M = Menu.cur_cls(evt)
#     for k, v in props(Menu.Defaults):
#         setattr(M, k, g(M, k, v))
#     return evt
#
# def start_items_stream(evt):
#     m = Menu.by_evt(evt)
#     M = Menu.cur_cls(evt)
#     if not M.streaming:
#         m['items'] = M.items()
#         push(Evt.first_items, evt.data)
#     else:
#         app.die('No streaming yet')
#     return evt
#
# def fzf_items_setup(evt):
#     m = Menu.by_evt(evt)
#     foo({'a': 23}).a
#     breakpoint()   # FIXME BREAKPOINT
#     return evt
#
# def fzf_item_lines(evt):
#     m = Menu.by_evt(evt)
#
#     breakpoint()   # FIXME BREAKPOINT
#
#
# @classmethod
# def get_dflt_menu(A):
#     breakpoint()   # FIXME BREAKPOINT
#
