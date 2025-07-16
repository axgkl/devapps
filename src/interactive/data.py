from __future__ import annotations
from dataclasses import dataclass, asdict
from interactive.tools import g, json, os
from copy import deepcopy
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from interactive.menu import Menu, Items
    from interactive.render import ItemsRenderer
    from interactive.pipeline import App
    from interactive.fzf import Fzf


class const:
    resized = 0
    killed = 1
    interrupted = 2
    auto = 'auto'
    group_by = '_qualify_'

    ec_130_ctrl_c = 130

    # evt types:
    signal = 'signal'
    app_start = 'app_start'
    first_items = 'first_items'  # different stream then stream updates
    item_col_getter_values = '.getter_results'
    fzf_keyb_interrupt = 'fzf ctrl-c pressed'

    evt_app_start = 'app start'
    evt_term_resized = 'winch'


class Term:
    rows: int = 0
    columns: int = 0

    @classmethod
    def get_dimensions(T, evt):
        _ = os.get_terminal_size()
        T.rows, T.columns = [_.lines, _.columns]
        return evt


@dataclass
class Evt:
    type: Any = None
    data: Any = None


@dataclass
class ItemColumnFmt:
    title: str
    min_width: int = 2
    max_width: int = 100
    justify: str = 'left'
    padding: int = 10


@dataclass
class Items:
    items: list = None
    cur_chunk_start: int = 0
    is_completed = False

    def __repr__(self):
        # r = self.menu.renderer_instance
        # self.menu.renderer_instance = self.menu.renderer_instance.__class__.__name__
        c = deepcopy(self)
        #  self.menu.renderer_instance = r
        for k in 'items', 'rendered':
            v = g(c, k)
            if v and len(v) > 5:
                l = v[0:5]
                l.append(f'...{len(v)} items')
                setattr(c, k, l)
        return json.dumps(asdict(c), indent=4, default=str)


@dataclass
class FifoMsg:
    app: App = None
    raw_msg: str = ''
    item_nr: int = 0
    cmd: str = ''  # preview or execute
    res: str = ''
