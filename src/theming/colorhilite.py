# GK: For dumping, json is well faster than simplejson.
# For loading, simplejson is faster.
# tried with big request dumps, and even we have
# bool(getattr(simplejson, '_speedups', False))
from json import dumps

from pygments import highlight
from pygments.lexers import JsonLexer, YamlLexer
from yaml import dump, safe_dump
from io import StringIO

#
# try:
#     from pygments.formatters import (
#         Terminal256Formatter,
#         TerminalFormatter,
#     )
# except Exception:
#     from pygments.formatters.terminal import TerminalFormatter
#
#     Terminal256Formatter = TerminalFormatter
#

from pygments.formatters.terminal import TerminalFormatter  # dark/light
from pygments.formatters.terminal256 import Terminal256Formatter  # rest

# from pygments.styles import get_style_by_name

ysl = ytermf = jsl = ''
# formatters by style:
_fmts = {}

Style = {}


def _fmt(style):
    if style in {'light', 'dark'}:
        return TerminalFormatter(bg={'light': 'light'}.get(style, 'dark'))
    else:
        r = Terminal256Formatter(style=style)
        # their bg coloring for unparsable json is super annoying (payload="asdf...)
        r.style_string['Token.Error'] = r.style_string['Token.Generic.Error']
        return r


def get_fmt(style):
    termf = _fmts.get(style)
    if not termf:
        termf = _fmts[style] = _fmt(style)
    return termf


# ready to make partials for changing the defaults:
def coljhighlight(
    s,
    style=None,
    indent=4,
    sort_keys=True,
    add_line_seps=True,
    # logger might be set to colors off, e.g. at no tty dest:
    colorize=True,
    # automatic indent only for long stuff?
    no_indent_len=0,
    _checked=[0],
):
    global jsl
    if not jsl:
        jsl = JsonLexer()
    if not isinstance(s, str):
        if indent and no_indent_len:
            if len(str(s)) < no_indent_len:
                indent = None
        try:
            s = dumps(s, indent=indent, sort_keys=sort_keys, default=str)
        except Exception:
            try:
                # the sort may fail: TypeError: '<' not supported between instances of 'int' and 'str'
                s = dumps(s, indent=indent, default=str)
            except Exception:
                _ = '🟥🟥🟥🟥🟥🟥 could not dumps to json %s [%s]🟥🟥🟥🟥🟥🟥'
                return _ % (s, __file__)

    if colorize:
        # we may be called by structlog, then with style (from
        # FLG.log_dev_coljson_style)
        # or direct
        style = Style.get('style', style)
        if not style and not _checked[0]:
            try:
                from devapp.app import FLG

                style = FLG.log_dev_coljson_style
            except Exception:
                # use the 16 base colors and leave to the terminal palette how to render:
                style = 'dark'
            Style['style'] = style
            _checked = [1]
        res = highlight(s, jsl, get_fmt(style))
    else:
        res = s

    if add_line_seps:
        res = res.replace('\\n', '\n')

    return res


def colyhighlight(s, style='colorful'):
    global ysl, ytermf
    if not ysl:
        ysl = YamlLexer()

    ytermf = get_fmt(style)
    io = StringIO()
    if not isinstance(s, str):
        try:
            s = safe_dump(s, allow_unicode=True)
        except Exception:
            s = dump(s, default_flow_style=False, allow_unicode=True)
    highlight(s, ysl, ytermf, io)
    res = io.getvalue()
    io.close()
    return res


if __name__ == '__main__':
    print(colyhighlight({'a': {'b': [1, 2, 'foo', {'c': 23}]}}))
