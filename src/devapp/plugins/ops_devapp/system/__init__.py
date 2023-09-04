#!/usr/bin/env python
"""
# System Building
"""
# TODO: set up ssh -R to tinyproxy for airight deploys in ssh mode
import devapp.gevent_patched
from .tools import run_app, do, FLG, load_spec, app, g, waitfor, spawn, time, workdir, os
from .tools import write_file, read_file, out_table, api, have_all, partial, system
from .tools import exists, dir_of, now, json, organize_bzip2, no_node
from .tools import prep_make_workdir_and_abspath_flags, tar_any_project_files
from .tools import single_node_cmds
from hashlib import md5
from shutil import copyfile
from devapp.tools import abspath


class Flags:
    autoshort = ''

    class cache_expiry:
        d = 10

    class user:
        n = 'leave empty to log in as user given in spec'
        d = ''

    class user_home_dir:
        n = 'leave empty to set /home/<user>'
        d = ''

    class dbg_non_parallel:
        n = 'Non parallel execution'
        d = False

    class system_spec:
        n = 'File which contains your system spec - absolute or relative to project root'
        d = 'conf/system.py'

    class node_mappings:
        n = ''
        d = ''

    class deploy_mode:
        t = ['ssh', 'infra_hetzner', 'k8s']
        d = 'ssh'

    class node:
        n = 'Node mapping'
        t = 'multi_string'

    class transfer_install_local_dirs:
        t = 'multi_string'

    class transfer_project_files:
        n = 'Comma sepped local files or dirs to be tar piped into project folder. E.g. tpf="conf/hub/flows.json,conf/functions.py"'

    class with_pds:
        n = 'Point to a lazyvim config repo (gh default). Example: AXGKl/pds_lazy.git (or full repo url). lazy is alias for LazyVim/starter'
        d = ''

    class Actions:
        class deploy:
            d = True

        class login:
            d = False

            class count:
                n = 'If > 1 we will login into different tmux windows, not panes'
                d = 1


class Node:
    name = None
    mem_gb_tot = None
    cores = None
    have_ssh_user_login = None

    def __repr__(self):
        return self.name


def instantiate_nodes(spec, api):
    """run all spec funcs"""

    def make_instance(f):
        host, n = f.split(':')
        N = g(spec, n, ('Not in spec', 'node'))
        n = type(n, (N, Node), {'ip': host, 'type': n})()
        svcs = ' '.join([s.__name__ for s in n.svcs])
        n.name = f'Node {n.type} {n.ip} [{svcs}]'
        N.instances = getattr(N, 'instances', [])
        n.nr = len(N.instances)
        N.instances.append(n)
        api.instances.append(n)

    [make_instance(f) for f in FLG.node]


def pull_private_pips(spec):
    pp = g(spec, 'priv_pips')
    if not pp:
        return pp
    d = f'{workdir}/pips'
    cmd = f"ops pkgs fetch --into {workdir}/priv_pips --private_pips '{pp}'"
    do(system, cmd)


def lc_hubs():
    hub = api.spec.hub
    p = int((hub.bind + ':1880').rsplit(':', 1)[-1])
    H = [f'{i.ip}:{p}' for i in api.instances if hub in i.svcs]
    return ','.join(H)


class deploy_modes:
    class ssh:
        @classmethod
        def deploy(ssh):
            tar_any_project_files()
            api.spec = spec = load_spec()
            u = FLG.user or getattr(spec, 'user')
            setattr(FLG, 'user', u)
            pull_private_pips(spec)
            instantiate_nodes(spec, api)
            [spawn(ssh.run_get_resources, host) for host in api.instances]
            waitfor('check host resources', partial(have_all, lambda n: n.mem_gb_tot))
            out_table('mem_gb_tot', 'cores')
            if any([h for h in api.instances if not h.have_bzip2]):
                do(organize_bzip2)
            [spawn(ssh.copy_files, host) for host in api.instances]
            [spawn(ssh.run_installer_script, host) for host in api.instances]

        @classmethod
        def run_get_resources(ssh, host):
            cmds = [
                'cat /proc/meminfo',
                'cat /proc/cpuinfo',
                'ls $HOME/.cache/priv_pips 2>/dev/null',
                'type bzip2',
            ]
            res = ssh.run_cmd(cmds, host)
            _ = res[0].split('MemTotal:', 1)[1].split('\n', 1)[0]
            _ = _.replace(' kB', '').strip()
            host.mem_gb_tot = int(int(_) / 1024 / 1024 + 0.5)
            host.cores = len(('\n' + res[1]).split('\nprocessor')) - 1
            host.have_priv_pips = res[2]
            host.have_bzip2 = res[3]

        @classmethod
        def copy_files(ssh, host):
            # rsync ~/SourceDirectory/* username@192.168.56.100:~/Destination

            for d in FLG.transfer_install_local_dirs:
                cmd = f'rsync -e "{SSH}" -a "{d}" {ssh_user()}@{host.ip}:~/repos'
                err = do(os.system, cmd)
                if err:
                    raise Exception('rsync error', {'files': d, 'host': host})
            render_installer_script_and_scp_files(host)

        @classmethod
        def run_installer_script(ssh, host):
            cmds = ['chmod +x installer.sh', './installer.sh']
            res = ssh.run_cmd(cmds, host)

        @classmethod
        def login(ssh, host):
            os.system(SSH + f' {FLG.user}@{host}')

        @classmethod
        def run_cmd(ssh, cmds, host, as_root=False, sep='!!cmd output!!'):
            def arr(res):
                return [i.strip() for i in res.split(sep)[1:]]

            nfo = app.warn if as_root else app.debug
            nfo(f'ssh {ssh_user(as_root)} {host.ip}', host=host, cmds=cmds)

            h = md5(str(cmds).encode('utf-8')).hexdigest()
            dw = f'{workdir}/{host.ip}/{h}'
            fn = f'{dw}/cmd'
            fnr = f'{dw}/cmd.res'
            fnt = f'{dw}/cmd.ts'
            os.makedirs(dw, exist_ok=True)
            if now() - float(read_file(fnt, '0')) < FLG.cache_expiry:
                nfo('from cache')
                return arr(read_file(fnr))

            t = ['#!/usr/bin/env bash']
            for cmd in cmds:
                t.append(f'echo "{sep}"')
                t.append(cmd)
            write_file(fn, '\n'.join(t))
            os.unlink(fnr) if exists(fnr) else 0
            cmd = f'cat "{fn}" | {SSH} {ssh_user(as_root)}@{host.ip} > {fnr}'
            os.popen(cmd).read()
            res = read_file(fnr).strip()
            if not res:
                if host.have_ssh_user_login:
                    msg, kw = ('Could not log in', dict(host=host, cmds=cmds, user=user))
                    raise Exception(msg, kw)
                host.have_ssh_user_login = True
                ssh.create_user(host=host)
                return ssh.run_cmd(cmds, host)
            write_file(fnt, str(now()))
            return arr(res)

        @classmethod
        def create_user(ssh, host):
            user = FLG.user
            d = FLG.user_home_dir or f'/home/{user}'
            app.info('Creating user', user=user, host=host)
            cmds = [
                f'adduser --home-dir {d} {user}',
                f'mkdir -p {d}/.ssh',
                f'cp -a /root/.ssh/authorized_keys {d}/.ssh/',
                f'chown -R {user}:{user} {d}/.ssh/',
            ]
            ssh.run_cmd(cmds, host=host, as_root=True)


SSH = 'ssh -q -o PasswordAuthentication=no -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null'


def make_environ_file(host):
    f = []
    for s in host.svcs:
        p, c = '', getattr(s, 'environ', None)
        if c is None:
            p, c = 'environ_', s
        d = {
            k[len(p) :]: getattr(c, k)
            for k in dir(c)
            if k.startswith(p) and not k[0] == '_'
        }
        [f.append(f"{k}='{v}'") for k, v in d.items()]
    return '\n'.join(f)


def render_installer_script_and_scp_files(host):
    """identify files to send and scp using our ssh with a pipe"""
    files = []   # will copy
    pips = json.loads(read_file(f'{workdir}/priv_pips/pips.json', '{}')).values()
    first_pip = [i for i in pips][0].rsplit('-', 1)[0] if pips else ''
    dw = f'{workdir}/{host.ip}'
    dirs = [dw + '/.cache', dw + '/.cache/priv_pips', dw + '/.local/bin']
    [os.makedirs(d, exist_ok=True) for d in dirs]

    def cp(fn):
        if not exists(f'{dw}/{fn}'):
            copyfile(f'{workdir}/{fn}', f'{dw}/.cache/{fn}')
        return '.cache/' + fn

    files += [cp(f'priv_pips/{p}') for p in pips if not p in host.have_priv_pips]
    f, fn = FLG.transfer_project_files, dw + '/proj_files.tgz'
    os.unlink(fn) if exists(fn) else 0
    if f:
        copyfile(f, fn)
        files.append('proj_files.tgz')

    g = lambda k, d='': getattr(api.spec, k, d)
    tid = FLG.transfer_install_local_dirs
    copied_dirs = [f'$HOME/repos/{d.rsplit("/", 1)[-1]}' for d in tid]
    svcs = [s.__name__ for s in host.svcs]
    T = read_file(dir_of(__file__) + '/templates/inst_base.sh')
    environ_file = make_environ_file(host)
    if FLG.with_pds == 'lazy':
        FLG.with_pds = 'LazyVim/starter'
    ctx = dict(
        app_libs=g('app_libs'),
        copied_dirs=' '.join(copied_dirs),
        d_project=g('d_project'),
        lc_hubs=lc_hubs(),
        node=f'{host.type}.{host.nr}',
        inst_pds=FLG.with_pds,
        inst_ops=' '.join(svcs),
        pip_to_install=g('pip_to_install', first_pip),
        environ_file=environ_file,
    )
    app.info('ctx', json=ctx)
    write_file(f'{dw}/installer.sh', T % ctx)
    files.append('installer.sh')
    ss = read_file(FLG.system_spec)
    write_file(f'{dw}/system.py', ss)
    files.append('system.py')
    if not host.have_bzip2:
        copyfile(f'{workdir}/static/bzip2', f'{dw}/.local/bin/bzip2')
        files.append('.local/bin/bzip2')
    f = ' '.join(files)
    cmd = f'cd "{dw}"; tar cfvz - {f} | {SSH} {ssh_user()}@{host.ip} tar xfz -'
    err = os.system(cmd)
    if err:
        raise Exception('scp error', {'files': files, 'host': host})


def ssh_user(as_root=False):
    return 'root' if as_root else FLG.user


from devapp.tools import tmux


def login():
    if len(FLG.node) == 1:
        return deploy_modes.ssh.login(FLG.node[0].split(':', 1)[0])
    c = FLG.login_count
    cmds = single_node_cmds(as_str=True)
    if c > 1:
        cmds = [[cmd.replace('"--login"', 'login')] * c for cmd in cmds]
    return tmux.run_cmds(cmds, attach=True, win_titles=FLG.node)


def deploy():
    if len(FLG.node) == 1:
        return do(getattr(deploy_modes, FLG.deploy_mode).deploy)
    cmds = single_node_cmds(as_str=True)
    return tmux.run_cmds(cmds, attach=True)


def run():
    if not FLG.node:
        return 'no node'
    prep_make_workdir_and_abspath_flags()
    if FLG.login:
        return login()

    if FLG.deploy:
        return deploy()


main = lambda: run_app(run, flags=Flags)


if __name__ == '__main__':
    main()
