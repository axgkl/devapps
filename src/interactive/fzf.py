from __future__ import annotations
from interactive import fzf_forkpty_flag
from interactive.tools import os, current_thread, is_, create_fifo
from dataclasses import dataclass, asdict
from interactive.conf import FLG, argv0, log
from interactive import preview_cmd_flag, item_delimiter
import subprocess as sp
from interactive.data import const

# from interactive.tools import g, json, os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from interactive.menu import Menu, Items
    from interactive.render import ItemsRenderer
    from interactive.pipeline import App


@dataclass
class FzfResult:
    exitcode: int
    items: list = None
    nrs: list = None


class FzfLayout:
    def total_width(items: Items):
        W = items.Term.columns
        # TODO: check if preview is left or not
        return W


# TODO
@dataclass
class default_opts:
    def preview_window(app: App):
        fzf = app.fzf
        return ','.join([fzf.preview_win_pos, fzf.preview_win_size])


@dataclass
class Fzf:
    cmd: str = ''
    result: list = None
    result_type: int = 0
    proc: object = None  # the fzf process while running
    preview: str = ''

    preview_cmd: str = ''
    preview_win_pos: str = 'right'
    preview_win_size: str = '50%'
    res_raw: list = None
    res: FzfResult = None
    layout: FzfLayout = FzfLayout
    header_lines: int = 0

    opts = default_opts()

    class opt:
        def preview_window(app: App):
            fzf = app.fzf
            return ','.join([fzf.preview_win_pos, fzf.preview_win_size])

    @classmethod
    def dbgstop(pdb=None, tb=None):
        """good for interactive debugs of preview thread"""
        from interactive.pipeline import App

        app = App.get_app()
        app.stopped_debug = True
        app.fzf.kill_proc(signal=9)
        os.system('reset')  # fzf screwed up terminal
        if tb:
            print(tb)
        print('resetted terminal')
        print(f'Thread {current_thread().name} - App sleeping.')
        if pdb:
            # say 's' to get to the stopping code frame:
            breakpoint()

    def build_binds(self, app: App):
        # M = items.menu
        # ofs = M.get_methods(starts_with='on_')
        # breakpoint()   # FIXME BREAKPOINT
        pass

    def kill_proc(self, evt=None, signal=15):
        # so that run, which has self.proc (and normally blocks for fzf to get closed by user)
        # knows what happened (proc then an int)
        proc, self.proc = self.proc, signal
        if not proc:
            return evt
        if signal == 9:
            proc.terminate()
        else:
            proc.kill()
        return evt

    def set_binds(self, evt):
        return evt

    def set_opts(self, evt):
        return evt

    def build_preview_cmd(self, app: App):
        self.preview_cmd = f'{argv0} {preview_cmd_flag} {app.menu.d_tmp} {{1}}'

    def build_cmd(self, app: App):
        pw = self.opt.preview_window(app)
        l = [
            'fzf',
            '--preview="echo {}"',
            f'--preview-window="{pw}"',
            '--ansi',
            '--cycle',
            f'--delimiter="{item_delimiter}"',
            '--reverse',
            '--height="50%"',
            '--multi',
            f'--preview="{self.preview_cmd}"',
            '--print0',
            '--print-query',
            '--read0',
            '--with-nth="2..2"',
            '--bind="alt-X:change-preview-window(up|down|left|right)"',
        ]
        hl = self.header_lines
        if hl:
            l.append(f'--header-lines={hl}')
        self.cmd = ' '.join(l)

    # def wrap_cmd_into_pty_forker(self, items: Items):
    #     return items
    #     fn_fifo = items.menu.d_tmp + '/send_to_forked_pty.fifo'
    #     create_fifo(fn_fifo)
    #     T = items.Term
    #     size = f'{T.rows}x{T.columns}'
    #     self.cmd = f"'{argv0}' {fzf_forkpty_flag} '{size}' '{fn_fifo}' '{self.cmd}'"
    #     return items

    def popen_fzf(self, app: App):
        cmd = self.cmd
        if FLG.dbg_fzf_sleep:
            cmd = 'sleep 1000'
        # time.sleep(1000)
        self.proc = sp.Popen(f'{cmd}', shell=True, stdin=sp.PIPE, stdout=sp.PIPE)

    def feed(self, app: App):
        items = app.items
        pos = items.cur_chunk_start
        lines = app.menu.renderer_instance.render(items.items[pos:], app=app)
        hl = self.header_lines
        counted = zip(range(pos - hl, pos + len(lines) - hl), lines)
        d = item_delimiter
        l = [bytes(f' {i}{d}{r}', 'utf-8') for i, r in counted]
        b = b'\x00'.join(l) + b'\x00'
        self.proc.stdin.write(b)
        self.proc.stdin.flush()

    def close_feed(self, app: App):
        self.proc.stdin.close()

        # count[0] += 1
        # return items
        # breakpoint()   # FIXME BREAKPOINT
        # p = self.proc
        # for k in items.rendered[items.cur_chunk_start :]:
        #     p.stdin.write(bytes(k, 'utf-8') + b'\x00')
        # p.stdin.flush()
        # return items

    def wait_stopped(self, items: Items):
        p = self.proc
        p.stdin.close()
        res = str(p.stdout.read(), 'utf-8')
        res = res.split('\x00')
        if is_(p, int):
            # killed from elsewhere
            exitcode = p
        else:
            exitcode = _ = p._wait(None)
        self.proc = None
        res.insert(0, exitcode)
        self.res_raw = res
        return items

    def parse_result(self, items: Items):
        rres = self.res_raw
        ec = rres.pop(0)  # exit code
        res = FzfResult(exitcode=ec)
        if ec != const.ec_130_ctrl_c:
            res.nrs = [int(l.split(item_delimiter, 1)[0]) for l in rres[1:-1]]
        self.res = res
        return items
