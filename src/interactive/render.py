from __future__ import annotations
from typing import TYPE_CHECKING
from interactive.tools import g, is_, perc, get_deep, ansi_color
from interactive.conf import widechars
from interactive.data import const, Term
import json as Json
from dataclasses import dataclass
from interactive.app import die
from interactive import struct_hilite

# just for the IDE:
if TYPE_CHECKING:
    from interactive.menu import Menu, Items
    from rich.console import Console as RichConsole
    from rich.table import Table as RichTable
    from rich.json import JSON as RichJSON
    from rich.live import Live as RichLive
    from interactive.pipeline import App

    class RichModules:
        Console: RichConsole
        Table: RichTable
        JSON: RichJSON


class ItemsRenderer:
    def parse_format_spec(self, M, app: App):
        """Builds data access methods and styles dicts from the format spec"""
        spec = self.format
        getters = []
        kws = []
        for d in spec['columns']:
            if is_(d, str):
                d = {'v': d}
            for k, dflt in (
                ('width', 'auto'),
                ('color', 0),
                ('padding_left', 1),
                ('justify', 'left'),
                ('has_icos', 0),
            ):
                d[k] = d.get(k, dflt)
            v = d['v']
            if is_(v, str):
                # a path to the real value in a dict:
                f = lambda item, _, pth=v.split('.'): get_deep(item, pth)
                t = v.rsplit('.', 1)[-1].capitalize()
            else:
                f = v
                t = v.__name__.capitalize()
            d['title'] = d.get('title', t)
            getters.append(f)
            kws.append(d)
        self.getters = getters
        self.styles = kws

    def set_layout(app: App):
        """items often needed to calculate optimal widths"""
        return

    def peak_first_value_widths(self, items: Items):
        """When column widths are not given exactly we check the first item values and see"""
        I = items.items
        icg = const.item_col_getter_values
        for item in I:
            item[icg] = [f(item, items) for f in self.getters]
        cols = len(self.getters)
        widths = []
        for j in range(cols):
            widths.append(max([len(i[icg][j]) for i in I]))
        return widths

    def render(self, items_chunk, app: App):
        raise NotImplementedError  # check descendants


def format_cell(val, style, item, is_last):
    # if val == '📁': breakpoint()     # FIXME BREAKPOINT
    val = str(val)
    w = style['width']
    if style['justify'] == 'right':
        v = val.rjust(w)
    else:
        pl = style['padding_left'] * ' '
        v = (pl + val).ljust(w)
    if not is_last:
        if not style['has_icos']:
            v = v[:w]
        else:
            wides = len([c for c in val if c in widechars])
            w = w - wides
            v = v[:w]
    c = style['color']
    if c:
        if callable(c):
            v = c(v, item)
        else:
            v = ansi_color(v, c)
    return v


@dataclass
class StreamingItemRenderer(ItemsRenderer):
    format: dict = None
    getters: list = None
    styles: list = None
    formatters: list = None

    def set_layout(self, app: App):
        S = self.styles
        val_widths = None
        if not is_(S[-1]['width'], int):
            # last one is not cut anyway and we want a reasonable size for the preview win pos calc
            S[-1]['width'] = 20
        for s in S:
            if not is_(s['width'], int):
                val_widths = self.peak_first_value_widths(app.items)
                break
        cols = len(S)
        if val_widths:
            [
                set_best_width(S[i]['width'], have=val_widths[i], conf=S[i])
                for i in range(cols)
            ]
        set_fzf_preview_win_pos_and_size(S, app)

    def render(self, items_chunk, app: App):
        if not items_chunk:
            return []
        _ = const.item_col_getter_values
        # avoiding to call the getters twice on the first chunk. it was run for the width estimates already:
        items = app.items
        if 0 and (app.menu.is_first_items_chunk(items) and _ in items_chunk[0]):
            matrix = [i[_] for i in items_chunk]
        else:
            matrix = [[g(i, items) for g in self.getters] for i in items_chunk]
        lines = []
        cols = len(self.styles)

        for row in matrix:
            item = items_chunk[len(lines)]
            nr = []
            for i, s in zip(range(cols), self.styles):
                val = row.pop(0)
                nr.append(format_cell(val, s, item=item, is_last=i == cols - 1))
            lines.append(''.join(nr))
        return lines


def set_fzf_preview_win_pos_and_size(S, app: App):
    W = app.Term.columns
    M = app.menu
    pp = M.preview_win_pos
    ps = M.preview_win_size
    if not ps:
        ps = '50%'
    if is_(ps, str):
        # availalb pane width:
        WP = perc(ps, W)
        WP = W - WP
    if not pp:
        pp = 'right'
        if sum([s['width'] for s in S]) > WP:
            pp = 'down'
    app.fzf.preview_win_pos = pp
    app.fzf.preview_win_size = ps


def set_best_width(w, have, conf):
    # configured width is including padding
    pl = conf['padding_left']
    have += pl
    if is_(w, int):
        W = max(w, have)
    else:
        W = have
    conf['width'] = W
    return W


@dataclass
class RichTableItemRenderer(ItemsRenderer):
    RichModules: RichModules = None
    format: dict = None
    table: RichTable = None
    console: RichConsole = None
    getters: list = None

    def set_layout(self, app: App):
        R = self.RichModules
        self.table = R.Table()
        [self.table.add_column(**kw) for kw in self.styles]
        width = app.fzf.layout.total_width(app)
        self.console = R.Console(width=width)
        app.fzf.header_lines = 3
        return app

    def render(self, items_chunk, app: App):
        """called by Menu"""
        items = app.items
        if not items.cur_chunk_start == 0:
            # https://github.com/Textualize/rich/issues/312
            die('No items streaming possible for rich tables')
        T = self.table
        for row in items_chunk:
            r = [g(row) for g in self.getters]
            T.add_row(*r)
        self.console.begin_capture()
        self.console.print(self.table)
        s = self.console.end_capture()
        return s.splitlines()[:-1]


class PlainItemRenderer:
    def render(self, items, app: App):
        return [str(i) for i in items.items]


class JsonItemRenderer:
    def render(self, items, app: App):
        return [Json.dumps(i, default=str) for i in items.items]


class item_renderers:
    """allowing to say renderer = "..." in Menu"""

    rich_table = RichTableItemRenderer
    plain = PlainItemRenderer
    json = JsonItemRenderer
    stream = StreamingItemRenderer


def find_best_renderer(M: Menu, item):
    f = g(M, 'format')
    if f:
        if is_(f, dict):
            if g(M, 'produce'):
                return RichTableItemRenderer(format=f, RichModules=rich())
            if g(M, 'produce_iter'):
                return StreamingItemRenderer(format=f)

        if callable(f):
            return f()
    if is_(item, str):
        return PlainItemRenderer()
    return JsonItemRenderer()


def rich(c=[0]):
    """Imports and returns a RichModules class
    saves time / dep mgmt if NOT needed"""
    if c[0]:
        return c[0]

    from rich.console import Console as RichConsole
    from rich.table import Table as RichTable
    from rich.json import JSON as RichJSON

    class C:
        Console = RichConsole
        Table = RichTable
        JSON = RichJSON

    c[0] = C
    return C


class Preview:
    """Preview rendering"""

    def to_yaml(o):
        return struct_hilite.colyhighlight(o)
