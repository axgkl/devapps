#!/usr/bin/env python
"""
FZF based Directory browser.

Taken when the first argument is a directory.
"""

from interactive.tools import abspath, os, props, g, d, ansi_color, color

from interactive.tools.times import times
from interactive.tools.filesize import size, alternative
from interactive.pipeline import start, App, Menu
from interactive.data import Items, ItemColumnFmt
from interactive.conf import widechars, FLG
import time
from absl import flags

flags.DEFINE_bool(
    'icons',
    True,
    'Show icons (Requires capable font)',
)


class Files(App):
    name = 'Files Browser'
    default_menu = 'DirView'

    class DirView(Menu):
        dir: str = ''
        short_dir: str = ''

        @classmethod
        def setup(M, A: App):
            M.format = format()
            return A

        @classmethod
        def produce_iter(M):
            for fn in os.listdir(M.dir):
                yield file_infos(fn, M.dir)

        # @classmethod
        # def produce(M):
        #     return [file_infos(fn, M.dir) for fn in os.listdir(M.dir)]


def run(argv):
    Files.DirView.dir = abspath(argv[0])
    return start(Files)


run_cli = run

# ----------------------------------------------------------------------------- coloring
# Define various colorizer functions for different columns:


def col_if_dir(s, item):
    """We color the directory icon only"""
    _ = types.dir.color
    return ansi_color(s, _) if item['type'] == 'dir' else s


def col_by_type(s, item):
    return ansi_color(s, g(types, item['type']).color)


def col_since(s, item):
    u = s[-1]
    nr = times.since_unit_to_nr[u]
    col = 255 - (nr * 3)  # mappinig units to variations of gray
    return ansi_color(s, col)


# size coloring tool:
def _():
    mb = 1024 * 1024
    return [
        [1024, color.darkgray],
        [10 * 1024, color.gray],
        [mb, color.lightgray],
        [10 * mb, 0],
        [50 * mb, color.blue],
        [100 * mb, color.red],
    ]


hundred_mb = 50 * 1024**2


def col_size(s, item, cols=_()):
    b = item['size']
    c = color.full_red
    for S, C in cols:
        if b < S:
            c = C
            break
    return ansi_color(s, c, bold=b > hundred_mb)


def format():
    cols = [
        d(
            v='mtime_since',
            title='Since',
            width=6,
            justify='right',
            color=col_since,
        ),
        d(v='sizeh', title='Size', width=6, justify='right', color=col_size),
        d(v='type', width=6, color=238),
        d(v='name', color=col_by_type),  # last one is never cut
    ]
    if FLG.icons:
        ico = d(
            v='ico',
            title='',
            width=2,
            padding_left=0,
            has_icos=True,
            color=col_if_dir,
        )
        cols.insert(0, ico)

    return {'columns': cols}


stats = ('mode', 'ino', 'dev', 'nlink', 'uid', 'gid', 'size', 'atime', 'mtime', 'ctime')


class types:
    class dir:
        _ico = '📁'  # 2 chars wide. hard. pip install wcwidth
        widechars.add(_ico)
        color = 'blue'
        # _ico = ''

    class any:
        _ico = ' '
        color = 0

    class arch:
        _ico = '📦'
        widechars.add(_ico)
        color = 'yellow'
        # fmt:off
        br = rpm = dcm = epub = zip = tar = rar = gz = bz2 = sevenz = pdf = exe = swf = rtf = nes = crx = cab = eot = ps = xz = sqlite = deb = ar = z = lzop = lz = elf = lz4 = zstd = tgz = True
        # fmt:on

    class audio:
        _ico = ' 🎝 '
        color = 'yellow'
        aac = midi = mp3 = m4a = ogg = flac = wav = amr = aiff = True

    class clang:
        _ico = ' '
        color = 'green'
        c = cpp = True

    class markdn:
        _ico = ' '
        color = 'green'
        md = markdown = True

    class font:
        _ico = ' ✍'
        color = 'green'
        woff = woff2 = ttf = otf = True

    class html:
        _ico = ' '
        color = 'green'
        html = htm = True

    class image:
        _ico = ' '
        color = 'cyan'
        # fmt:off
        dwg = xcf = jpeg = jpx = apng = png = gif = webp = tiff = cr2 = bmp = jxr = psd = ico = heic = dcm = True
        # fmt:on

    class js:
        _ico = ' '
        color = 'green'
        js = javascript = True

    class pdf:
        _ico = ' '
        color = 'purple'
        pdf = True

    class python:
        _ico = '🐍'
        color = 'green'
        widechars.add(_ico)
        py = True

    class txt:
        _ico = ' '
        color = 'green'
        txt = True

    class video:
        _ico = '🎬'
        color = 'cyan'
        widechars.add(_ico)
        m3gp = mp4 = m4v = mkv = mov = avi = wmv = mpeg = webm = flv = True


extensions = {}  # {'aac': 'audio',...
typs = [t for t in props(types) if isinstance(t[1], type)]
[extensions.update({k[0]: t[0] for k in props(t[1])}) for t in typs]


def file_infos(fn, dir_, _a=stats, _e=extensions):
    ffn = f'{dir_}/{fn}'
    s = os.stat(ffn)
    r = {a: s[i] for a, i in zip(_a, range(len(_a)))}
    r['mtime_since'] = times.dt_human(r['mtime'])
    r['sizeh'] = size(r['size'], system=alternative)
    r['name'] = fn
    r['hidden'] = fn.startswith('.')
    if os.path.isdir(ffn):
        r['type'] = 'dir'
    else:
        ext = r['ext'] = fn.rsplit('.')[-1].lower()
        r['type'] = _e.get(ext, 'any')
    r['ico'] = g(types, r['type'])._ico
    return r
