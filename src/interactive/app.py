from interactive.conf import open_log_file, log, argv0
from interactive.tools import exists, os, sys, read_file, partial, colyhighlight
from absl import flags
import importlib

fn_app_ctrl_fifo = [0]


def g(o, k, d=None):
    return getattr(o, k, d)


FLG = flags.FLAGS
d_builtin_mods = os.path.dirname(__file__) + '/apps'
die = log.die

flags.DEFINE_string('app_name', argv0, 'Application name in logs')

_ = os.environ.get
d_user_conf = _(argv0.upper() + '_CONF', _('HOME') + f'/.config/{argv0}')


def moddoc(s):
    """mods may import stuff not required for others -> load their doc w/o needing to import them"""
    for i in range(10):
        line, s = s.split('\n', 1)
        if not line.strip() or line[0] == '#':
            continue
        for sep in '"""', "'''":
            if sep in line:
                return s.split(sep, 1)[0]
    return ''


def available_apps():
    r = {}
    for n, d in ('user', d_user_conf + '/apps'), ('builtin', d_builtin_mods):
        l = {'📂': d}
        r[n] = l
        if not exists(d):
            continue
        for fn in os.listdir(d):
            ffn = f'{d}/{fn}'
            fnp = fn.split('.py', 1)[0]
            if not ffn.endswith('.py') or fnp[0] == '_' or fnp[-1] == '_':
                continue
            s = read_file(ffn)
            l[fnp] = moddoc(s) or '(no documentation)'

    return r


def load_app(modname):
    """pre flag parse time"""
    sys.path.insert(0, d_builtin_mods)
    du = d_user_conf + '/apps'
    sys.path.insert(0, du)
    try:
        mod = importlib.import_module(modname)
    except ModuleNotFoundError as ex:
        # show rough exception when real mod has import probs:
        for k in modname, modname + '.py':
            for d in d_builtin_mods, du:
                if exists(d):
                    if k in os.listdir(d):
                        raise

        # show nice available mods when not found:
        p = partial(print, file=sys.stderr)
        p(f'USAGE: {argv0} <app> [flags]\n')
        aa = available_apps()
        p('Apps Available:\n ')
        p(colyhighlight(aa))
        sys.exit(1)

    return mod


def setup_app():
    open_log_file()


CODING = os.environ.get('CODING')
if CODING:
    from .apps import files as mod
else:
    mod = None


def start(mod=mod):
    def start_(argv, mod=mod):
        argv = argv[2:]
        setup_app()
        log.warn('Starting up', args=argv, mod=mod.__name__)
        return mod.run_cli(argv)

    return start_


# def items_formatter(Menu, items):
#     if not isinstance(items, list):
#         log.die('Items must be list', have=items)
#     f = g(Menu, 'items_fmt')
#     if callable(f):
#         return f
#     if isinstance(f, dict):
#         return table_formatter(Menu, f, items)
#     log.die('Require items formatter', menu=Menu)


# def dflt_preview_formatter():
#     pass
