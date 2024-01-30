# FIXME: 2024-01-30: structlog meanwhile offers per columns formatter defs, incl. value formatter functions(!).
# Which means we can ditch most of the OUR features and switch to built in feats.

from functools import partial
from json import dumps

import structlog
from theming.colorhilite import coljhighlight as coljson
from theming.term import RESET, Cell, Theme, structlog_style
import re
# from theming.colorhilite import colyhighlight as colyaml

from structlogging.stacktrace import rich_stack

match_hl = {False: "🟧%s🟧", True: "\x1b[1;38;5;124;48;5;255m%s\x1b[0m"}


class formatters:
    coljson = partial(coljson, indent=2, no_indent_len=100, style=Theme.pygments_style)
    coljson_no_colors = partial(
        coljson,
        indent=2,
        no_indent_len=0,
        style=Theme.pygments_style,
        colorize=False,
    )

    # its done anyway key val based to single line, so we indent:
    json = partial(dumps, indent=4, default=str)
    stack = rich_stack(True)
    stack_no_colors = rich_stack(False)


def build_val_fmtter(key, cfg, CFG):
    """cfg: Parameters of the val_formatters. CFG: config of the class"""
    func = cfg.pop("formatter")
    func_no_col = func if CFG["colors"] else func + "_no_colors"
    func = getattr(formatters, func_no_col, getattr(formatters, func, None))
    if not func:
        raise Exception("Formatter not found: %s" % func)
    return partial(func, **cfg)


call = structlog.dev.ConsoleRenderer.__call__


class ThemeableConsoleRenderer(structlog.dev.ConsoleRenderer):
    """
    Features:
    - Coloring based on theming.term (semantic styles)
              and not colorama (colors only)
    - on the fly insertion of unknown levels
    - configurable formatting of specific values:

    """

    def __init__(self, **kw):
        self.cfg, sl_kw = kw, {}
        # extract structlog original kw:
        for k in "pad_event", "repr_native_str":
            if k in kw:
                sl_kw[k] = kw.pop(k)
        self.match = re.compile(kw["match"]) if kw["match"] else None
        self.dimm_no_match = kw["dimm_no_match"]
        colors = kw.get("colors")
        if colors:
            ax_style, ls = structlog_style(use_pygm=self.cfg["structlog_style"])
            _ = "level_styles"
            kw[_] = kw.get(_) or ls

        structlog.dev.ConsoleRenderer.__init__(self, colors=False, **sl_kw)

        # FIXME: structlog meanwhile offers per columns formatter defs, incl. value formatters. Which means we can ditch most of the OUR features and switch to built in feats.

        self.colorful = colors
        if colors:
            # now  set OUR theme colors into a copy of sl's PlainStyle:
            self._styles = ax_style(self._styles)
            # self._level_to_color = ls
            from structlog.dev import (
                Column,
                KeyValueColumnFormatter,
                LogLevelColumnFormatter,
            )

            S = ax_style(self._styles)
            self._default_column_formatter = KeyValueColumnFormatter(
                S.kv_key,
                S.kv_value,
                "",
                value_repr=str,
                width=0,
            )

            self._columns = [
                Column(
                    "timestamp",
                    KeyValueColumnFormatter(
                        key_style=None,
                        value_style=S.timestamp,
                        reset_style="",
                        value_repr=str,
                    ),
                ),
                Column(
                    "level",
                    LogLevelColumnFormatter(ls, reset_style=""),
                ),
                Column(
                    "event",
                    KeyValueColumnFormatter(
                        key_style=None,
                        value_style="\x1b[0m",
                        reset_style="",
                        value_repr=str,
                        width=30,
                    ),
                ),
                Column(
                    "logger",
                    KeyValueColumnFormatter(
                        key_style=None,
                        value_style=S.logger_name,
                        prefix="[",
                        postfix="\x1b[0m]",
                        reset_style="",
                        value_repr=str,
                    ),
                ),
            ]
        self.setup_value_formatters()

    def setup_value_formatters(self):
        """
        Example for value formatting:
        1. configure available formatters by name
            e.g. 'longj' might be a name for the coljson formatter with
            config: indent=2
        2. assign event dict keys to those names -> values will be formatted
        3. if you are ok with defaults you can point to the formatter funcname:
        renderer = ThemeableConsoleRenderer(
            val_formatters = {'longj': {'formatter': 'coljson', 'indent': 2}}
            # 'longj' is configured,  'json' is used as is:
            fmt_vals = {'result': 'longj', 'foo': 'json'}
            )
        """
        req_val_formatters = list(self.cfg.get("fmt_vals", {}).values())
        vf = dict(
            (k, build_val_fmtter(k, dict(v), self.cfg))
            for k, v in self.cfg.get("val_formatters", {}).items()
        )
        for k in req_val_formatters - vf.keys():
            vf[k] = build_val_fmtter(k, {"formatter": k}, self.cfg)
        self._val_formatters = vf

    def __call__(self, _, level, ev):
        if self.colorful:
            # every thread shows in unique color:
            try:
                tn = ev.pop("thread", None)
            except Exception:
                print("breakpoint set")
                breakpoint()
        by = ev.pop("by", None)
        stack = ""

        # configured value formatter functions?
        # let them do their work here and replace ev vals by formatted ones:
        # have to intermeditatly put into a placeholder, later replace back
        # reason: sl would screw the formatting:
        fvs = self.cfg.get("fmt_vals")
        if fvs:
            phs = []
            for k in fvs:
                v = ev.pop(k, None)
                if v is not None:
                    v = RESET + self._val_formatters[fvs[k]](v)
                    if k == "stack":
                        stack = v + RESET + "\n"
                    else:
                        phs.append(v)
                        ev[k] = "_sl_%s__" % len(phs)

        try:
            s1 = call(self, _, level, ev)
        except Exception as ex:
            # Auto-Adding of new log levels:
            # loglevel 'blather' was already seen...
            if isinstance(ex, KeyError):
                ltc = self._level_to_color
                if level not in ltc:
                    ltc[level] = ltc["error"]
                    return
            # Should never happen. To find this in the code should you get this:
            print("!" * 100, "ax_rx_log_error", ev, str(ex))
            return

        # replace back:
        if fvs:
            while phs:
                s1 = s1.replace("_sl_%s__" % len(phs), phs.pop())

        matches = None
        if self.match:
            matches = self.match.findall(s1)
            if matches:
                repl = match_hl[self.colorful]
                for h in set(matches):
                    s1 = s1.replace(h, repl % h)
            else:
                if self.dimm_no_match and self.colorful:
                    s1 = s1.replace("\x1b[", "\x1b[2;")
                    _ = s1.split("]", 1)
                    s1 = _[0] + "]\x1b[2;38;5;235m" + _[1]

        if not self.colorful or tn is None:
            return stack + s1

        # Thread: a unique looking cell in the terminal matrix:
        symb = Cell.unique(tn)
        s2 = s1
        # by is a special key
        if by:
            by = (by + " ").ljust(5)
            # loglevel in?
            l = s1.split("] ", 1)
            if len(l) == 2:
                s1 = l[0] + "] " + by + l[1]
            else:
                s1 = by + s1
        s = "\x1b[2m" + symb + " " + s2
        return stack + s
