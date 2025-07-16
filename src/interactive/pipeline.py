import rx as Rx
from dataclasses import dataclass, asdict
from rx.scheduler.newthreadscheduler import NewThreadScheduler
from rx.subject.subject import Subject
import time
import sys
from interactive import app
from interactive.conf import FLG, argv0, log
from rx import operators as rx
from functools import partial
from interactive import item_delimiter
from interactive.fifo import Fifo
from interactive.menu import Menu, Items
from threading import current_thread  # debug
import signal

# from dataclasses import dataclass, field, asdict
from interactive.tools import wrap, json, os, exists, g, is_, props
from interactive import preview_cmd_flag, execute_args_sep, preview_args_sep
from interactive.data import Term, const, Items, Evt
from interactive.fzf import Fzf

from typing import Union
from absl import flags

flags.DEFINE_bool(
    'dbg_fzf_sleep',
    False,
    'Run sleep 10000 instead of fzf - good for breakpoints',
    short_name='dfs',
)


# ------------------- declarative pipeline building from lists


def is_rx(f):
    return 'rx.' in f.__module__


# handling ..., rx.group_by(<qual>), {res1: [<sub pipeline>], ...} -> the {} will result in a rx.flatmap(s) operation
# where s.key is the qualifier result:

# not found: do nothing


def flatmap(spec):
    return rx.flat_map(lambda s, spec=spec: s.pipe(*spec.get(s.key, ())))


def as_new_thread(name):
    """a convenience way to do this, incl. thread naming, used e.g. for fifo thread:"""

    def setn(x, n=name):
        current_thread().name = n
        return x

    return rx.pipe(rx.subscribe_on(NewThreadScheduler()), rx.map(setn))


def on_(qualifier: callable, groups: Union[dict, list], take=None):
    """if take is given this will end in the group by"""
    if isinstance(groups, list):
        groups = {True: groups}
    if take:
        qualifier = (qualifier, take)
    groups[const.group_by] = qualifier
    return groups


def build_pipeline(ops):
    """[func1, ..] -> pipeable rx operators"""
    p = []
    for o in ops:
        if is_(o, dict):
            # group.by -> flatmap (if else):
            # convenience, allwos to put the group by INTO the dict, not before rx.group_by:
            q = o.get(const.group_by)
            if q:
                if is_(q, tuple):
                    qual, take = q
                    p.append(rx.group_by(qual, take))
                else:
                    p.append(rx.group_by(q))
            spec = {k: build_pipeline(v) for k, v in o.items() if not k == const.group_by}
            p.append(flatmap(spec=spec))
        elif not is_rx(o):
            o = wrap(o, log)
            p.append(rx.map(o))
        else:
            p.append(o)
    return p


def pipeline(observable, ops):
    p = build_pipeline(ops)
    return observable.pipe(*p)


Disposable = Rx.disposable.disposable.Disposable

Render = Subject()


class App:
    pass


class Streams:
    fifo_reader: Disposable = None
    fifo_processor: Disposable = None
    ext_evts: Disposable = None
    menu_items: Disposable = None
    app: Disposable = None
    ext_evts = Subject()

    def start_app_stream(A: App):
        return Streams.start_menu(A)
        res = []
        p = pipeline(
            Streams.ext_evts,
            # [on_(lambda evt: evt.type, A.events(), take=lambda evt: evt.data)],
            [on_(lambda evt: evt.type, A.events(), take=lambda evt: evt.data)],
        )
        p.subscribe(lambda x: res.append(x))
        Streams.ext_evts.on_next(Evt(type=const.evt_app_start, data=A))
        return res[0]

        res = ['err in app pipeline']
        A.start_external_events_stream(A)
        p = pipeline(
            Rx.just(1),
        )
        Streams.app = p.subscribe(lambda x: res.append(x))
        if App.stopped_debug:
            print('App stopped')
            time.sleep(10000)
        time.sleep(10000)
        return res[-1]

    # def start_external_evts(A: App):
    #     Streams.ext_evts = p.subscribe(lambda x: x)

    def start_menu(A: App):
        fzf: Fzf = A.fzf
        M: Menu = A.menu
        res = ['err in items pipeline']
        p = pipeline(
            M.produced_items(A),
            [
                on_(
                    M.have_no_more_items,
                    {
                        False: [
                            # first item chunk?
                            on_(
                                M.is_first_items_chunk,
                                {
                                    True: [
                                        M.set_menu_tmp_dir,
                                        Streams.start_fifo_receiver_thread,
                                        M.find_and_instantiate_renderer,
                                        on_(M.has_format_spec, [M.parse_format_spec]),
                                        M.set_renderer_layout,
                                        fzf.build_preview_cmd,
                                        fzf.build_cmd,
                                        fzf.build_binds,
                                        fzf.popen_fzf,
                                    ],
                                },
                            ),
                            fzf.feed,
                        ],
                        True: [fzf.close_feed],
                    },
                ),
                #         M.render_to_fzf_lines,
                # Fzf.feed,
                # Fzf.wait_stopped,
                # Streams.stop_fifo_in,
                # Fzf.parse_result,
                # rx.group_by(lambda x: x.fzf.res.exitcode),
                # {
                #     const.ec_130_ctrl_c: [A.cancelled],
                #     0: [
                #         M.build_fzf_res,
                #         rx.group_by(A.have_next_menu),
                #         {True: [], False: [A.done]},
                #     ],
                # },
            ],
        )

        Streams.menu_items = p.subscribe(lambda x: res.append(x))
        return res[-1]

    def start_fifo_receiver_thread(app: App):
        """starts TWO streams actually - see FIFO class doc"""
        pusher = pipeline(
            Fifo.observe(app.menu),
            [
                as_new_thread('fifo_reader'),
                Fifo.push_q,
            ],
        )
        processor = pipeline(
            Fifo.read_q(),
            [
                as_new_thread('fifo processor'),
                rx.map(partial(Fifo.to_fifo_msg, app=app)),
                app.menu.create_fifo_msg_res,
            ],
        )

        Streams.fifo_reader = pusher.subscribe(lambda x: x)
        _ = processor.pipe(rx.filter(Fifo.have_no_newer))
        Streams.fifo_processor = _.subscribe(Fifo.send_result)

    def stop_fifo_in(app: App):
        [i.dispose() if i else 0 for i in (Streams.fifo_reader, Streams.fifo_processor)]


def start(UserApp):
    return Streams.start_app_stream(UserApp)
