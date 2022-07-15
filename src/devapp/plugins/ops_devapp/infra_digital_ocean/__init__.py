#!/usr/bin/env python
"""
# Digital Ocean Infrastructure Tool

## Purpose
Low level Operations on the DO Cloud, using their REST API
E.g. when terraform destroy fails, you can delete droplets using this.

## Requirements
- API Token

## Examples:

### Listing
- ops ido
- ops ido --since 10h
- ops ido -m "*foo*"

### Creation
- ops ido dc -n mydroplet                             # create a minimal droplet
- ops ido dc -n mydroplet -sac -f k3s -s m-2vcpu-16gb # create a droplet with this size, name foo, with k3s feature

### Deletion
- ops ido dd --since 1h # delete all created within the last hour (-f skips confirm)

## Misc

See Actions at -h

"""
# Could be done far smaller.
import time
import pycond
from devapp import gevent_patched

# from gevent import monkey

# monkey.patch_all()
import json
import os

from tempfile import NamedTemporaryFile
from rich.console import Console
from rich.table import Table
import requests
from devapp.app import FLG, app, run_app, do, system
from devapp.time_tools import times
from fnmatch import fnmatch
from devapp.tools import confirm, exists, read_file, write_file, dirname

from devapp.app import app, run_app, FLG

DROPS = {}
have_droplet_ips = [0]  # save unneccessary API hits.

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))

# even with accept-new on cloud infra you run into problems since host keys sometimes change for given ips:
# so:
ssh = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '


def d_boostrap_feats():
    here = os.path.abspath(os.path.dirname(__file__))
    return here + '/bootstrap_features'


def all_feats():
    return [
        f
        for f in os.listdir(d_boostrap_feats())
        if not '.local' in f and ':' in f and f.endswith('.sh')
    ]


def show_features():
    fs = all_feats()
    r = [i.rsplit('.sh', 1)[0].split(':', 1) for i in fs]
    return ', '.join([i[1] for i in r])


# fmt:off
alias_sizes = [
    ['XXS'      , 's-1vcpu-1gb']    ,
    ['XS'       , 's-1vcpu-2gb']    ,
    ['S'        , 's-2vcpu-4gb']    ,
    ['M'        , 's-8vcpu-16gb']   ,
    ['L'        , 'c2-16vcpu-32gb'] ,
    ['XL'       , 'c2-32vcpu-64gb'] ,
]
# fmt:on
size_aliases = lambda: ', '.join([f'{i}:{k}' for i, k in alias_sizes])


class Flags:
    autoshort = ''

    class token_cmd:
        n = 'personal access token acquistion command'
        d = 'pass show DO/pat'

    class image:
        d = 'fedora-36-x64'

    class match:
        n = 'Further Filter, applied to any value for name-matching droplets, e.g. region. Embedded within *<value>*'
        d = ''

    class name:
        n = 'Name parameter for various commands, e.g. droplet name. Wildcards from some actions like delete accepted.'
        d = '*'

    class since:
        n = 'Further Filter. E.g. "1h" filters out all droplets created longer ago than one hour'
        d = ''

    class size:
        s = 'S'
        n = 'aliases: ' + size_aliases()
        d = 'XXS'

    class region:
        d = 'fra1'

    class tags:
        n = 'Set tags when creating or use as filter for list / delete'
        d = []

    class ssh_key:
        n = 'Must be present on DO. Can be id or name (slower then, add. API call, to find id)'
        d = os.environ['USER']

    class user:
        n = 'Username to create additionally to root at create (with sudo perms)'
        d = os.environ['USER']

    class features:
        n = 'Configure features via SSH (as root).'
        n += 'Have: %s. Filename accepted.' % show_features()
        n += 'You may supply numbers only.'
        d = []

    class force:
        n = 'No questions asked'
        d = False

    class range:
        n = 'Placeholder "{}" in name will be replaced with these.'
        d = []

    class Actions:
        class billing_list:
            d = False

        class billing:
            n = 'Show current balance'

        class billing_pdf:
            n = 'download invoice as pdf'

            class uuid:
                n = 'run billing_list to see uuid'
                d = ''

        class ssh_keys:
            n = 'show configured ssh keys'

        class droplet_bootstrap:
            n = 'configure features at existing droplet'

        class list:
            n = 'list all'
            d = True

        class database_list:
            s = 'dal'

        class database_delete:
            s = 'dad'

        class droplet_list:
            s = 'dl'

        class droplet_sizes:
            n = 'List sizes'

        class droplet_create:
            pass
            # class ssh_add_config:
            #     n = 'write the host into your ssh config'

            # class no_bootstrap:
            #     n = 'Do not wait for droplet up. No bootstrap'
            #     d = False

        class droplet_delete:
            s = 'dd'
            n = 'Deletes all matching droplets. --name must be given, "*" accepted.'
            n = "Example: Delete all created within the last hour: \"dd --since 1h -n '*'"


syst = lambda s: os.popen(s).read().strip()
pat = [0]


def set_token():
    if not pat[0]:
        pat[0] = syst(FLG.token_cmd)
    if not pat[0]:
        app.die('Token command failed', cmd=FLG.token_cmd)


def die(msg):
    app.die(msg)


from devapp.tools import cache


@cache(3)
def GET(ep, **kw):
    return API(ep, 'get', **kw)


def API(ep, meth, data=None, plain=False):
    app.info(f'API: {meth} {ep}')
    data = data if data is not None else {}
    token = pat[0]
    url = f'https://api.digitalocean.com/v2/{ep}'
    app.debug(f'API: {meth} {ep}', **data)
    meth = getattr(requests, meth)
    h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    r = meth(url, data=json.dumps(data), headers=h) if data else meth(url, headers=h)
    if not r.status_code < 300:
        die(r.text)
    if plain:
        return r
    t = r.text or '{}'
    r = json.loads(t)
    app.debug('Result', json=r)
    return r


def dd(meth, data=None):
    return API('droplets', meth, data)


def get_ssh_id():
    id = FLG.ssh_key
    if id.isdigit():
        return id
    r = GET('account/keys')
    i = [k['id'] for k in r['ssh_keys'] if k['name'] == id]
    if not i:
        app.die('key not found matching name', name=id)
    return i[0]


import time

now = lambda: int(time.time())


def wait_for_ip(name):
    """name must match ONE droplet"""

    def waiter(name=name):
        ds = Actions.droplet_list(name=name)['droplets']
        # if len(ds) != 1: app.die('Name must match ONE droplet', have=ds, name=name)
        try:
            ips = ds[0]['ip']
            assert ips
            return ips.split(',', 1)[0]
        except:
            pass

    return wait_for(f'droplet {name} ip', waiter, tmout=300, dt=4)


def wait_for_ssh(ip=None, name=None):
    assert name
    if not ip:
        ip = wait_for_ip(name)
    kw = {'tmout': 60, 'dt': 2}
    wait_for_remote_cmd_output(f'droplet {name}@{ip} ssh', 'ls /', ip=ip, **kw)
    return ip


@cache(0)
def wait_for_remote_cmd_output(why, cmd, ip, user='root', tmout=60, dt=3):
    def waiter():
        return os.popen(f'{ssh} {user}@{ip} {cmd} 2>/dev/null').read().strip()

    return wait_for(why, waiter, tmout=tmout, dt=dt)


def wait_for(why, waiter, tmout=60, dt=3):
    t0 = now()
    tries = int(tmout / dt)
    i = 0
    l = getattr(threading.current_thread(), 'logger', app.name)
    log = app.info
    tm, still = t0, ''
    while now() - t0 < tmout:
        i += 1
        res = waiter()
        if res:
            return res
        log(f'{still}waiting for: {why}', nr=f'{i}/{tries}', logger=l)
        log = app.debug  # second...n times: debug mode
        if now() - tm > 60:
            log = app.info
            tm = now()
            still = 'still '
        time.sleep(dt)
        if DIE:
            app.die('abort')
    app.die(f'Timeout waiting for {why}', logger=l)


def add_ssh_config(ip, name):
    fn = os.environ['HOME'] + '/.ssh/config'

    def filter_host(c, name=name):
        r = []
        c = c.splitlines()
        while c:
            l = c.pop(0)
            if l == f'Host {name}':
                while c:
                    l = c.pop(0)
                    if not l.strip():
                        break
                continue
            r.append(l)
        return '\n'.join(r)

    c = filter_host(read_file(fn))
    user = FLG.user
    c += f'\nHost {name}\n    User {user}\n    HostName {ip}\n\n'
    write_file(fn, c, log=1)


def formatter(res):
    if not isinstance(res, dict):
        return
    f = res.get('formatter')
    if f:
        console = Console(markup=False, emoji=False)
        console.print(f(res))
        return 1


def list_resources(name, typ, simplifier, headers, filtered=True):
    """droplet or database"""
    name = name
    match = FLG.match
    since = FLG.since
    tags = FLG.tags
    # for list user expects this. All others will set it:

    def matches(d, name=name, match=match, since=since, tags=tags):
        # creating?
        if not d.get('id'):
            return True

        if not fnmatch(d['name'], name):
            return
        if not fnmatch(str(d), f'*{match}*'):
            return
        if tags:
            for t in tags:
                if not t in d.get('tags', '').split(','):
                    return
        if not since:
            return True
        dt = times.to_sec(since)
        if times.utcnow() - times.iso_to_unix(d['created_at']) < dt:
            return True

    if typ == 'droplets':
        if have_droplet_ips[0]:
            total = DROPS.values()
        else:
            total = [simplifier(d) for d in GET(typ)[typ]]
            [DROPS.setdefault(d['name'], {}).update(d) for d in total]
        have_droplet_ips[0] = not any([d for d in total if not d.get('ip')])
    else:
        total = [simplifier(d) for d in GET(typ)[typ]]

    all = [d for d in total if matches(d)] if filtered else total

    def formatter(res, typ=typ, headers=headers, matching=len(all), total=len(total)):
        headers = headers(res[typ])
        taglist = ','.join(tags)
        T = typ.capitalize()
        return setup_table(
            f'{matching}/{total} {T} (name={name}, matching={match}, since={since}, tags={taglist})',
            headers,
            dicts=res[typ],
        )

    return {typ: all, 'formatter': formatter}


def resource_delete(typ, lister, force):
    name = FLG.name
    if not name:
        app.die('Supply a name', hint='--name="*" to delete all is accepted')
    d = lister(name=name)
    formatter(d)
    ds = d[typ]
    if not ds:
        app.die(f'No {typ} matching', name=name)
    app.info(f'Delete %s {typ}?' % len(ds))
    if not force:
        confirm(f'Proceed to delete %s {typ}?' % len(ds))
    for dr in ds:
        app.warn('deleting', **dr)
        id = dr['id']
        Thread(target=API, args=(f'{typ}/{id}', 'delete')).start()
    return d


def assert_sane_name(name):
    if not name or '*' in name or '?' in name or '[' in name:
        app.die('Require "name" with chars only from a-z, A-Z, 0-9, . and -')


import sys

# abort while in any waiting loop (concurrent stuff failed):
DIE = []


def run_this(cmd):
    a = ' '.join(list(sys.argv[:2]))
    a += ' ' + cmd
    if do(system, a, log_level='info', no_fail=True):
        DIE.append(True)


from threading import Thread


# def bg_proc(cmd, **kw):
#     for k, v in kw.items():
#         cmd += f' --{k}="{v}"'
#     Thread(target=run_this, args=(cmd,), daemon=False).start()


from functools import partial
import threading


def run_parallel(f, range_, kw):
    n = kw['name']
    names = [n.replace('{}', i) for i in range_]
    t = []
    for n in names:
        k = dict(kw)
        k['name'] = n
        app.info('Background', **k)
        # time.sleep(1)
        t.append(Thread(target=f, kwargs=k, daemon=False))
        t[-1].start()

    while any([d for d in t if d.isAlive()]):
        time.sleep(0.5)

    return Actions.droplet_list()


tmp_dir = [0]


def make_temp_dir(prefix):
    dnt = NamedTemporaryFile(prefix=f'{prefix}_').name
    user = FLG.user
    os.makedirs(dnt, exist_ok=True)
    sm = dirname(dnt) + f'/{prefix}.{user}'  # convenience
    os.unlink(sm) if exists(sm) else 0
    os.symlink(dnt, sm, target_is_directory=True)
    tmp_dir[0] = sm


def parametrized_workflow(parallel={'droplet_create', 'droplet_bootstrap'}):
    action = app.selected_action
    if action in parallel:
        # utillity for temporary files - at the same place:
        make_temp_dir(action)
        f = getattr(Actions, action)
        from inspect import signature

        sig = signature(f).parameters
        kw = {}
        for k in sig:
            v = getattr(FLG, k, None)
            if v is None:
                v = getattr(FLG, f'{action}_{k}', None)
            if v is None:
                app.die(f'Missing parameter {k}')
            kw[k] = v

        if '{}' in FLG.name:
            range_ = FLG.range
            if not range_:
                app.die('Missing range', name=FLG.name)
            return partial(run_parallel, f, range_, kw)
        else:
            return partial(f, **kw)


droplet = lambda name: Actions.droplet_list(name=name)
unalias_size = lambda s: dict(alias_sizes).get(s, s)


class Actions:
    def _pre():
        app.out_formatter = formatter
        set_token()
        # XL to real size:
        # size_alias_to_real('size')
        return parametrized_workflow()

    def billing():
        return GET('customers/my/balance')

    def billing_pdf():
        uid = FLG.billing_pdf_uuid
        r = GET(f'customers/my/invoices/{uid}/pdf', plain=True)
        fn = 'digital_ocean_invoice.pdf'
        write_file(fn, r.content, mode='wb')
        return f'created {fn}'

    def billing_list():
        r = GET('customers/my/billing_history?per_page=100')
        for d in r['billing_history']:
            d['date'] = times.dt_human(d['date'])

        def formatter(res):
            h = list(reversed(res['billing_history']))
            t = [float(d['amount']) for d in h]
            t = int(sum([i for i in t if i < 0]))
            head = [
                ['amount', {'title': f'{t}$', 'justify': 'right'}],
                'description',
                'invoice_uuid',
                'date',
                'type',
            ]
            return setup_table('Billing history', head, dicts=h)

        r['formatter'] = formatter
        return r

        # breakpoint()  # FIXME BREAKPOINT
        # app.info('history', json=r)
        # breakpoint()  # FIXME BREAKPOINT
        # r = API('customers/my/invoices/cc485dfc-e041-4b85-a52d-4b282bf24508/pdf', 'get')
        # r = API('customers/my/balance', 'get')
        # return r

    def database_list(name=None):
        def simplify_values(d):
            r = {}
            for k in (
                'id',
                'size',
                'created_at',
                'status',
                'tags',
                'name',
                'nodes',
                'id',
            ):
                r[k] = d.get(k, 'n.a.')
            r['$'] = 100
            r['since'] = times.dt_human(d['created_at'])
            r['region'] = d['region']
            r['con'] = '{host}:{port}'.format(**d['connection'])
            for l in ('tags',):
                v = ','.join([k for k in r.get(l) or []])
                if not v:
                    r.pop(l)
                else:
                    r[l] = v
            return r

        def headers(all):
            t = int(sum([d.get('$', 0) for d in all]))
            return [
                ['name', {'style': 'green'}],
                ['$', {'style': 'red', 'justify': 'right', 'title': f'{t}$ (estimated)'}],
                ['since', {'justify': 'right'}],
                ['tags'],
                ['size'],
                ['con'],
            ]

        return list_resources(name, 'databases', simplify_values, headers)

    @classmethod
    def database_delete(A):
        return resource_delete('databases', A.database_list, FLG.force)

    def droplet_list(name=None, filtered=True):
        if name is None:
            name = FLG.name.replace('{}', '*')
        # if name and name.endswith('2'): breakpoint()  # FIXME BREAKPOINT

        def simplify_values(d):
            r = {}
            for k in (
                'size_slug',
                'created_at',
                'status',
                'tags',
                'volume_ids',
                'name',
                'id',
            ):
                r[k] = d.get(k, 'n.a.')
            r['$'] = int(d['size']['price_monthly'])
            r['since'] = times.dt_human(d['created_at'])
            r['region'] = d['region']['slug']
            n = d.get('networks')
            try:
                r['ip'] = [
                    k['ip_address']
                    for k in n['v4']
                    if not k['ip_address'].startswith('10.')
                ]
            except:
                pass
            for l in 'ip', 'volume_ids', 'tags':
                v = ','.join([k for k in r.get(l, [])])
                if not v:
                    r.pop(l)
                else:
                    r[l] = v
            return r

        def headers(all):
            t = int(sum([d.get('$', 0) for d in all]))
            return [
                ['name', {'style': 'green'}],
                ['ip'],
                ['$', {'style': 'red', 'justify': 'right', 'title': f'{t}$'}],
                ['since', {'justify': 'right'}],
                ['tags'],
                ['size_slug'],
                ['volume_ids'],
            ]

        r = list_resources(name, 'droplets', simplify_values, headers, filtered=filtered)
        return list_resources(
            name, 'droplets', simplify_values, headers, filtered=filtered
        )

    def ssh_keys():
        def format(res):
            headers = [
                ['name', {'style': 'green'}],
                'fingerprint',
                'id',
                'public_key_end',
            ]
            return setup_table('SSH Keys', headers, dicts=res['ssh_keys'])

        ks = GET('account/keys')['ssh_keys']

        def f(d):
            d['public_key_end'] = '...' + d.get('public_key')[-30:]
            return d

        return {'ssh_keys': [f(k) for k in ks], 'formatter': format}

    def droplet_create(name, image, region, size, tags, features):
        threading.current_thread().logger = name
        d = dict(locals())
        app.info('Dropplet create', **d)
        d['size'] = unalias_size(d['size'])
        name = d['name']
        assert_sane_name(name)
        droplet(name)

        if name in DROPS:
            app.warn(f'Droplet {name} exists already')
            return DROPS[name]
        have_droplet_ips[0] = False
        DROPS[name] = {'name': name}
        feats = validate_features(d.pop('features'))
        d['tags'] = t = list(d['tags'])
        t.extend(feats)
        d['ssh_keys'] = [get_ssh_id()]
        r = dd('post', d)
        # if FLG.droplet_create_no_bootstrap:
        #     app.info('Created. No bootstrap', **d)
        #     return 'created'
        # if FLG.droplet_create_ssh_add_config:
        #     do(add_ssh_config, ip=ip, name=name)
        Actions.droplet_bootstrap(name=name, features=feats)
        # wait_for_ssh(name=name)
        return Actions.droplet_list(name=name)

    @classmethod
    def droplet_delete(A):
        return resource_delete('droplets', A.droplet_list, FLG.force)

    def droplet_sizes():
        A = {k: v for v, k in dict(alias_sizes).items()}

        def s(s, A=A):
            return [
                A.get(s['slug'], ''),
                s['slug'],
                int(s['price_monthly']),
                s['disk'],
                int(s['memory'] / 1024.0),
                s['description'],
            ]

        all = GET('sizes?per_page=100')
        l = [s(i) for i in reversed(all['sizes'])]

        def formatter(res):
            tble = setup_table(
                'Droplet Sizes',
                [
                    ['', {'justify': 'center'}],
                    ['name', {'style': 'green'}],
                    ['$/Month', {'justify': 'right', 'style': 'red'}],
                    ['Disk T', {'justify': 'right'}],
                    ['RAM GB', {'justify': 'right'}],
                    ['Descr', {'style': 'cyan'}],
                ],
            )
            for d in res['sizes']:
                tble.add_row(*[str(i) for i in d])
            return tble

        return {'sizes': l, 'formatter': formatter}

    def list():
        dr = Actions.droplet_list()
        formatter(dr)
        da = Actions.database_list()
        if da['databases']:
            formatter(da)
        a = Actions.billing()
        app.info('month to date usage', amount=a['month_to_date_usage'])

    def droplet_bootstrap(name, features):
        threading.current_thread().logger = name
        feats = validate_features(features)
        if not feats:
            app.warn('no bootstrap features')
            return
        app.info(f'bootstrapping', name=name, feats=feats, logger=name)
        user = FLG.user
        feats = FLG.features
        if user != 'root' and not 'add_sudo_user' in feats:
            feats.insert(0, 'add_sudo_user')

        I = []
        fns = []
        for f in feats:
            if '/' in f:
                assert exists(f)
                fn = f
            else:
                fn = [
                    t for t in all_feats() if f == t.split(':', 1)[1].rsplit('.sh', 1)[0]
                ]
                assert len(fn) == 1
                fn = d_boostrap_feats() + '/' + fn[0]
            t = os.path.basename(fn)
            fns.append(fn)
            app.info('adding feature', feat=t, logger=name)
            I.append('\necho "----  %s ----"' % t)
            s = read_file(fn).lstrip()
            if s.startswith('#!/bin/bash'):
                s = s.split('\n', 1)[1]
            I.append(s)
            # otherwise a local part in file1, followed by server feature would run *both* local:
            I.append('# part:\n')

        I = '\n\n'.join(I)
        parts = find_my_bootstrap_parts(name, I)

        [run_bootstrap_part(name, part, nr) for part, nr in zip(parts, range(len(parts)))]
        app.info('initted', logger=name)


def find_my_bootstrap_parts(name, script):
    I = script.split('\n# part:')
    I[0] = 'name\n' + I[0]
    r = []
    for part in I:
        cond, body = part.split('\n', 1)
        if not body.strip():
            continue
        local = False
        if cond.startswith('local:'):
            cond = cond.split(':', 1)[1]
            local = True
        cond = cond.strip()
        if not cond:
            cond = 'name'  # always there
        if pycond.pycond(cond)(state=ItemGetter(name=name)):
            r.append({'local': local, 'body': body})
    return r


def run_bootstrap_part(name, part, nr):
    marker = '-RES-'
    pre = '\n'.join(
        [
            '#!/bin/bash',
            'ip="%(ip)s"',
            f'name="{name}"',
            f'function add_result {{ echo "{marker} $1 $2"; }}',
            f'function ssh_ {{ ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"; }}',
            f'function scp_ {{ scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"; }}',
            '',
        ]
    )
    ctx = ItemGetter(name=name)
    body = pre + part['body']
    script = preproc_bootstrap_script(body, ctx) % ctx
    d_tmp = tmp_dir[0]
    fnt = f'{d_tmp}/{name}.{nr}'
    ip = DROPS[name]['ip']
    fntr = f'root@{ip}:/root/' + os.path.basename(fnt)
    fntres = f'{fnt}.res'
    where = 'locally' if part['local'] else 'remotely'
    app.info(f'Running script {nr} {where}', logger=name)
    write_file(fnt, script, chmod=0o755)
    system(f'cat "{fnt}"')
    if not part['local']:
        scp = ssh.replace('ssh', 'scp')
        cmd = f'{scp} "{fnt}" "{fntr}"'
        if os.system(cmd):
            app.info('waiting for ssh', logger=name)
            wait_for_ssh(ip, name)
            if system(cmd):
                app.die('Bootstrap failed', name=name)
        fntr = '/root/' + fntr.split('/root/', 1)[1]
        cmd = f'{ssh} "root@{ip}" "{fntr}"'
    else:
        cmd = f'"{fnt}"'
    cmd += f' | tee >(grep -e {marker} --color=never > "{fntres}")'
    print('running', cmd)
    if system(cmd):
        app.die('cmd failed')
    res = {}

    def parse(res_line, name=name, res=res):
        l = res_line.split(' ', 2)
        DROPS[name][l[1]] = l[2]
        res[l[1]] = l[2]

    [parse(l) for l in read_file(f'{fntres}', dflt='').splitlines()]
    if res:
        app.info(f'{name} bootstrap result', **res)
    # os.unlink(fnt)
    # os.unlink(fntres)


def preproc_bootstrap_script(init, ctx):
    """ filter blocks by pycond statements
    # cond: name not contains server
    ...
    # else
    ...
    # end cond

    exit ends the parsing if not in negated condition.
    """
    r = []
    lines = init.splitlines()
    pyc = None
    while lines:
        line = lines.pop(0)
        if line.startswith('# end cond'):
            assert pyc is not None
            pyc = None
            continue
        if line.startswith('# else'):
            assert pyc is not None
            pyc = not pyc
            continue
        if not line.startswith('# cond:'):
            if pyc in (None, True):
                r.append(line)
                if line.startswith('exit '):
                    return '\n'.join(r)
            continue
        assert pyc == None
        pyc = pycond.pycond(line.split(':', 1)[1].strip())(state=ctx)
    return '\n'.join(r)


class ItemGetter(dict):
    def __getitem__(self, k):
        tmout = 120
        if k.startswith('wait:'):
            _, tmout, k = k.split(':', 2)
        l = k.split('.')
        if l[0] == 'flag':
            return getattr(FLG, l[1])
        if l[0] == 'env':
            return os.environ.get(l[2], '')
        name = self.get('name')
        if l[0] in DROPS or l[0] == 'match:key':
            drop, k = l[0], l[1]
        elif l[0] == 'matched':
            return self.get('matched')[l[1]]
        else:
            drop = name

        def waiter(name=drop, k=k, self=self):
            if name == 'match:key':
                h = [d for d in DROPS.values() if k in d]
                if not h:
                    return
                self['matched'] = h[0]
                return h[0][k]
            if not have_droplet_ips[0]:
                Actions.droplet_list(name=name)
            d = DROPS.get(name)
            if not d:
                app.die(
                    f'Droplet {name} expected but not present.', hint='was it created?'
                )
            return d.get(k)

        v = waiter()
        if v:
            return v
        t0 = now()
        r = wait_for(f'{k} of {drop}', waiter, tmout=int(tmout))
        # print('ret', r, 'for', k)
        app.info(f'got {k}', dt=now() - t0, logger=name)
        return r


def validate_features(feats):
    """featuers may have short forms - here we set the full ones"""
    r, cust = [], []
    all_features = all_feats()
    for f in feats:
        if exists(f):
            cust.append(os.path.abspath(f))
        else:
            fn = [t for t in all_features if f in t]
            if len(fn) == 0:
                app.die('Feature not found', given=f, known=all_features)
            if len(fn) != 1:
                app.die('Feature not exact', matches=fn, known=all_features)
            r.append(fn[0])
    r = sorted(r)
    r = [i.split(':', 1)[1].rsplit('.sh', 1)[0] for i in r]
    r.extend(cust)
    return r


def setup_table(title, headers, dicts=None):
    tble = Table(title=title)

    def auto(col, dicts=dicts):
        if dicts:
            try:
                float(dicts[0].get(col, ''))
                return [col, {'justify': 'right'}]
            except:
                pass
        return [col]

    headers = [auto(i) if isinstance(i, str) else i for i in headers]
    headers = [[h[0], {} if len(h) == 1 else h[1]] for h in headers]
    [tble.add_column(h[1].pop('title', h[0]), **h[1]) for h in headers]
    if dicts is not None:
        for d in dicts:
            tble.add_row(*[str(d.get(h[0], '')) for h in headers])
    return tble


def main():
    run_app(Actions, flags=Flags)


if __name__ == '__main__':
    main()


# begin_archive
# Demo for different flag style:
# class Workflows:
#     class k3s_cluster:
#         """Create a single server K3S cluster"""
#
#         class workers:
#             d = 2
#
#         class server_size:
#             d = 'XXS'
#
#         def run(workers, server_size):
#             pass
#
# def add_workflow_flags(name):
#     wf = getattr(Workflows, name)
#     if not isinstance(wf, type):
#         return
#     FA = Flags.Actions
#     A = Actions
#     setattr(FA, name, wf)
#     setattr(A, name, wf.run)
#
#
# [add_workflow_flags(w) for w in dir(Workflows) if not w[0] == '_']
#
#   ------------------ and in def _pre then:
#
# wf = getattr(Workflows, action, 0)
# if not wf:
#     return
# attrs = lambda c: [i for i in dir(c) if i[0] not in ['_', 'd', 'n'] and i != 'run']
# kw = {}
# for a in attrs(wf):
#     v = getattr(FLG, action + '_' + a, None)
#     if v is not None:
#         kw[a] = v
# return partial(wf.run, **kw)
