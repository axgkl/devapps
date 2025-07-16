from __future__ import annotations
from typing import TYPE_CHECKING
from interactive.tools import g
from interactive.app import die, FLG
import rx as Rx
from interactive.data import Items, FifoMsg
from interactive.render import item_renderers, find_best_renderer, ItemsRenderer, Preview
import os

if TYPE_CHECKING:
    from interactive.pipeline import App


class Menu:
    d_tmp: str = ''
    renderer = 'auto'
    renderer_instance: ItemsRenderer = None
    preview_win_pos: str = None  # default left
    preview_win_size: str = None  # default 50%
    # TODO: no-hscroll / fully searchable

    @classmethod
    def produced_items(M, app: App):
        """The main stream source"""

        def produce(Obsrvr, _, app=app):
            if not M.is_streaming():
                app.items = Items(items=M.produce())
                Obsrvr.on_next(app)
            else:
                items = []
                app.items = i = Items(items=items)
                for chunk in M.produce_iter():
                    l = len(items)
                    items.append(chunk)
                    i.cur_chunk_start = l
                    Obsrvr.on_next(app)
            # causes stop feeding (proc.stdin.close) into fzf:
            i.is_completed = True
            Obsrvr.on_next(app)
            Obsrvr.on_completed()

        return Rx.create(produce)

    def have_no_more_items(app):
        return app.items.is_completed is True

    def is_first_items_chunk(app):
        return app.items.cur_chunk_start == 0

    is_streaming = classmethod(lambda M, _=None: bool(g(M, 'produce_iter')))
    has_format_spec = classmethod(lambda M, _=None: isinstance(g(M, 'format'), dict))

    @classmethod
    def set_menu_tmp_dir(M, app: App):
        M.d_tmp = FLG.d_tmp + '/' + M.__name__
        os.makedirs(M.d_tmp, exist_ok=True)

    @classmethod
    def setup(M, A: App):
        """possibility to set state before first items are produced"""
        return A

    @classmethod
    def preview(M, item, app):
        if isinstance(item, (dict, list)):
            return Preview.to_yaml(item)
        return f'preview {item}'

    @classmethod
    def find_and_instantiate_renderer(M, app: App):
        """We are first item chunk"""
        n = M.renderer
        if n == 'auto':
            r = find_best_renderer(M, app.items.items[0])
        else:
            r = g(item_renderers, n)()
        if not r:
            die('No item renderer', configured_name=n)
        M.renderer_instance = r

    @classmethod
    def parse_format_spec(M, app: App):
        M.renderer_instance.parse_format_spec(M, app)

    @classmethod
    def set_renderer_layout(M, app: App):
        return M.renderer_instance.set_layout(app)  # sets up the renderer

    @classmethod
    def build_fzf_res(M, app: App):
        # default is to return the selected original items:
        i = app.items.items
        app.fzf_res.items = [i[nr] for nr in app.items.fzf_res.nrs]

    @classmethod
    def create_fifo_msg_res(M, msg: FifoMsg):
        item = msg.app.items.items[msg.item_nr]
        msg.res = M.preview(item, msg.app)
        return msg

    @classmethod
    def on_accept(M, msg: FifoMsg):
        breakpoint()  # FIXME BREAKPOINT

    # @classmethod
    # def get_methods(M, starts_with=''):
    #     r = [f for f in props(M) if f[0].startswith(starts_with) and callable(f[1])]
    #     return r
    #     return r
