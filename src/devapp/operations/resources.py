from devapp.tools import offset_port, exists, project
import os
from devapp.app import app
# from devapp.operations import binenv, asdf


class tool:
    conda_env = 'lctools'


redis_pre = """
test "$1" == "cli" && { shift; redis-cli "$@"; exit $?; }
test -n "$1" && { redis-server "$@"; exit $?; }
test -e "$host_conf_dir/redis.conf" && { redis-server "$host_conf_dir/redis.conf"; exit $?; }

"""


def redis_server(**kw):
    if kw.get('cmd') == 'redis-cli':
        m = {'cmd': ':redis-cli -p %s' % offset_port(kw['rsc'].port)}
    else:
        m = {'cmd': ':redis-server --port %s' % offset_port(kw['rsc'].port)}
        m['cmd_pre'] = redis_pre
    return m


def verify_tools(path, rsc, **kw):
    for p in rsc.provides:
        d = path + '/' + p
        if not exists(d):
            app.error('Not found', cmd=d)
            return False
    return True


def lc_tools(*a, **kw):
    cmd = kw['cmd']
    if cmd == 'tmux':
        d = project.root() + '/tmp/tmux'
        os.makedirs(d, exist_ok=True)
        return {'cmd_pre': 'export TMUX_TMPDIR="%s"; ' % d, 'cmd': 'tmux'}
    return cmd


def slc(**kw):
    os.environ.get('slc_lc_hubs')
    return {'cmd': ':ops slc connect'}


class rsc:
    """For services we change dir to project."""

    class slc:
        cmd = slc
        pkg = False
        environ = ['lc_hubs']

    class redis_server:
        provides = ['redis-server', 'redis-cli']
        cmd = 'redis-server'
        run = redis_server
        pkg = 'redis-server'
        port = 6379
        systemd = 'redis-server'

    class lc_tools:
        # httpd for rotatelogs
        provides = ['git', 'fzf', 'jq', 'rg', 'fd', 'http', 'htop', 'tmux']
        conda_chan = 'conda-forge'
        conda_pkg = (
            ' '.join(provides)
            .replace(' rg ', ' ripgrep ')
            .replace(' fd ', ' fd-find ')
            .replace(' http ', ' httpie ')
        )
        run = lc_tools
        verify_present = verify_tools

    class lc_tools_kf:
        # httpd for rotatelogs
        provides = ['rotatelogs']
        conda_chan = 'kalefranz'
        conda_pkg = 'httpd'
        verify_present = verify_tools


# rsc.binenv = binenv.binenv
# rsc.asdf = asdf.asdf
