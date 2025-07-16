from absl import flags

# import tempfile
from interactive.tools import os, sys, json, time, env

exe = sys.argv[0]  # preview command
argv0 = exe.rsplit('/', 1)[-1].split('.py', 1)[0]

mn = 'Notification app. Called with 2 args: msg and kws'
mt = 'Application temp dir for caches and log'
flags.DEFINE_string('d_tmp', f'/tmp/{argv0}_{env["USER"]}', mt)
flags.DEFINE_boolean('log_append', False, 'Append to logfile')
flags.DEFINE_integer('log_level', 20, 'Log level', short_name='ll')
flags.DEFINE_string('notifier', 'notify-send -t 5', mn)
FLG = flags.FLAGS

now = time.time
t0 = now()

widechars = set()


class LogState:
    logfile = None


def notify(msg, kw):
    cmd = FLG.notifier
    os.system(f'{cmd} "{msg}" "{kw}"')


def kwstr(kw, col=True):
    if not col:
        return ','.join([f'{i}:{j}' for i, j in kw.items()])
    return ','.join([f'\x1b[32m{i}\x1b[0m:\x1b[{31}m{j}\x1b[0m' for i, j in kw.items()])


def dolog(level, msg, logger, kw, _dumps=json.dumps):
    if level == 60:
        msg = 'FATAL: ' + msg
    if level < FLG.log_level:
        return
    logger = logger or FLG.app_name
    l = [level, round(now() - t0, 1), logger, msg]
    if kw:
        l.append(kw)
    LogState.logfile.write(_dumps(l) + '\n')
    LogState.logfile.flush()
    if level == 50:
        notify(msg, kwstr(kw, col=False))
    if level == 60:
        print(f'\x1b[1m{msg}\x1b[0m', kwstr(kw), file=sys.stderr)
        log.notify(msg, **kw)
        sys.exit(1)


class log:
    def dbg(msg, logger=None, **kw):
        dolog(10, msg, logger, kw)

    def info(msg, logger=None, **kw):
        dolog(20, msg, logger, kw)

    def warn(msg, logger=None, **kw):
        dolog(30, msg, logger, kw)

    def error(msg, logger=None, **kw):
        dolog(40, msg, logger, kw)

    def notify(msg, logger=None, **kw):
        dolog(50, msg, logger, kw)

    def die(msg, logger=None, **kw):
        dolog(60, msg, logger, kw)


def open_log_file():
    fn = f'{FLG.d_tmp}/log.json'
    os.makedirs(FLG.d_tmp, exist_ok=True)
    LogState.logfile = open(fn, 'a' if FLG.log_append else 'w')
