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
from devapp import gevent_patched
import json
import os

from rich.console import Console
from rich.table import Table
import requests
from devapp.app import FLG, app, run_app, do, system
from devapp.time_tools import times
from fnmatch import fnmatch
from devapp.tools import (
    confirm,
    exists,
    read_file,
    write_file,
)

from devapp.app import app, run_app, FLG


def dci():
    here = os.path.abspath(os.path.dirname(__file__))
    return here + '/cloud_init_features'


def all_feats():
    return [
        f
        for f in os.listdir(dci())
        if not '.local' in f and ':' in f and f.endswith('.sh')
    ]


def show_features():
    fs = all_feats()
    r = [i.rsplit('.sh', 1)[0] for i in fs]
    return ', '.join(r)


alias_sizes = [
    ['XXS', 's-1vcpu-1gb'],
    ['XS', 's-1vcpu-2gb'],
    ['S', 's-2vcpu-4gb'],
    ['M', 's-8vcpu-16gb'],
    ['L', 'c2-16vcpu-32gb'],
    ['XL', 'c2-32vcpu-64gb'],
]

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

    class Actions:
        class ssh_keys:
            n = 'show configured ssh keys'

        class droplet_cloud_init:
            n = 'configure features at existing droplet'

        class list:
            n = 'list all'
            d = True

        class database_list:
            s = 'dal'

        class database_delete:
            s = 'dad'

            class force:
                n = 'No questions asked'

        class droplet_list:
            s = 'dl'

        class droplet_sizes:
            n = 'List sizes'

        class droplet_create:
            class ssh_add_config:
                n = 'write the host into your ssh config'

            class enter:
                n = 'ssh into it when ready'

        class droplet_delete:
            s = 'dd'
            n = 'Deletes all matching droplets. --name must be given, "*" accepted.'
            n = "Example: Delete all created within the last hour: \"dd --since 1h -n '*'"

            class force:
                n = 'No questions asked'


syst = lambda s: os.popen(s).read().strip()
pat = [0]


def set_token():
    if not pat[0]:
        pat[0] = syst(FLG.token_cmd)
    if not pat[0]:
        app.die('Token command failed', cmd=FLG.token_cmd)


def die(msg):
    app.die(msg)


def API(ep, meth, data=None):
    data = data if data is not None else {}
    token = pat[0]
    url = f'https://api.digitalocean.com/v2/{ep}'
    app.debug(f'API: {meth} {ep}', **data)
    meth = getattr(requests, meth)
    h = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    r = meth(url, data=json.dumps(data), headers=h) if data else meth(url, headers=h)
    if not r.status_code < 300:
        die(r.text)
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
    r = API('account/keys', 'get')
    i = [k['id'] for k in r['ssh_keys'] if k['name'] == id]
    if not i:
        app.die('key not found matching name', name=id)
    return i[0]


import time

now = lambda: int(time.time())


def wait_for_ip(name, dt=5, cnt=100):
    """name must match ONE droplet"""
    t0 = now()
    for i in range(cnt):
        ds = ActionNS.droplet_list(name=name)['droplets']
        assert len(ds) < 2, 'Name must match ONE droplet'
        try:
            ips = ds[0]['ip']
            assert ips
            return ips.split(',', 1)[0]
        except:
            pass
        time.sleep(dt)
        w = now() - t0
        app.info('waiting for ip of droplet', nr=f'{i}/{cnt}', name=name, since=f'{w}sec')
    app.die('creation failed')


def wait_for_ssh(ip, dt=1, cnt=10):
    t0 = now()
    for i in range(cnt):
        time.sleep(dt)
        w = now() - t0
        app.info('waiting for ssh droplet', nr=f'{i}/{cnt}', ip=ip, since=f'{w}sec')
        cmd = f'ssh -o StrictHostKeyChecking=accept-new root@{ip} touch /tmp/ssh_check'
        if not system(cmd, no_fail=True):
            return
    app.die('no ssh login')


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


def list_resources(name, typ, simplifier, headers):
    """droplet or database"""
    name = FLG.name if name is None else name
    match = FLG.match
    since = FLG.since
    tags = FLG.tags
    # for list user expects this. All others will set it:

    def matches(d, name=name, match=match, since=since, tags=tags):
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

    total = [simplifier(d) for d in API(typ, 'get')[typ]]
    all = [d for d in total if matches(d)]

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
        API(f'{typ}/{id}', 'delete')
    return d


class ActionNS:
    def _pre():
        app.out_formatter = formatter
        set_token()

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
            t = int(sum([d['$'] for d in all]))
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
        return resource_delete('databases', A.database_list, FLG.database_delete_force)

    def droplet_list(name=None):
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
            t = int(sum([d['$'] for d in all]))
            return [
                ['name', {'style': 'green'}],
                ['ip'],
                ['$', {'style': 'red', 'justify': 'right', 'title': f'{t}$'}],
                ['since', {'justify': 'right'}],
                ['tags'],
                ['size_slug'],
                ['volume_ids'],
            ]

        return list_resources(name, 'droplets', simplify_values, headers)

    def ssh_keys():
        def format(res):
            headers = [
                ['name', {'style': 'green'}],
                'fingerprint',
                'id',
                'public_key_end',
            ]
            return setup_table('SSH Keys', headers, dicts=res['ssh_keys'])

        ks = API('account/keys', 'get')['ssh_keys']

        def f(d):
            d['public_key_end'] = '...' + d.get('public_key')[-30:]
            return d

        return {'ssh_keys': [f(k) for k in ks], 'formatter': format}

    def droplet_create():
        name = FLG.name
        if not name or '*' in name or '?' in name or '[' in name:
            app.die('Require "--name" with an exact value')

        tags = FLG.tags
        set_features()
        tags.extend(FLG.features)
        size = FLG.size
        size = dict(alias_sizes).get(size, size)

        d = dict(
            name=name,
            image=FLG.image,
            region=FLG.region,
            size=FLG.size,
            ssh_keys=[get_ssh_id()],
            tags=tags,
        )
        d = dd('post', d)
        ip = wait_for_ip(name)
        wait_for_ssh(ip)
        if FLG.droplet_create_ssh_add_config:
            do(add_ssh_config, ip=ip, name=name)
        ActionNS.droplet_cloud_init(name=name, ip=ip)
        return ActionNS.droplet_list(name=name)

    @classmethod
    def droplet_delete(A):
        return resource_delete('droplets', A.droplet_list, FLG.droplet_delete_force)

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

        all = API('sizes?per_page=100', 'get')
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
        dr = ActionNS.droplet_list()
        formatter(dr)
        da = ActionNS.database_list()
        if da['databases']:
            formatter(da)
        return ''

    def droplet_cloud_init(name=None, ip=None):
        set_features()
        name = name or FLG.name
        if not ip:
            ip = wait_for_ip(name)
        feats = FLG.features
        feats.insert(0, 'add_user')  # always
        user = FLG.user
        I = ['#!/bin/bash', f'export user="{user}"']
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
                fn = dci() + '/' + fn[0]
            t = os.path.basename(fn)
            fns.append(fn)
            app.info('adding feature', feat=t)
            I.append('\necho "----  %s ----"' % t)
            I.append(read_file(fn))

        init = '\n\n'.join(I)
        fnt = '/tmp/cloud_init_%s.sh' % os.getpid()
        write_file(fnt, init)
        system('scp "%s" "root@%s:cloud_init.sh"' % (fnt, ip))
        os.unlink(fnt)
        system('ssh "root@%s" chmod +x /root/cloud_init.sh' % ip)
        system('ssh "root@%s" /root/cloud_init.sh' % ip)
        os.environ['ip'] = ip
        for fn in fns:
            fnp = fn.replace('.sh', '.post.local.sh')
            if exists(fnp):
                do(system, fnp, log_level='info')
        app.info('initted', ip=ip, name=name, user=user)


def set_features():
    """featuers may have short forms - here we set the full ones"""
    feats = FLG.features
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
    FLG.features = r


def setup_table(title, headers, dicts=None):
    tble = Table(title=title)
    headers = [[i] if isinstance(i, str) else i for i in headers]
    headers = [[h[0], {} if len(h) == 1 else h[1]] for h in headers]
    [tble.add_column(h[1].pop('title', h[0]), **h[1]) for h in headers]
    if dicts is not None:
        for d in dicts:
            tble.add_row(*[str(d.get(h[0], '')) for h in headers])
    return tble


def main():
    run_app(ActionNS, flags=Flags)


if __name__ == '__main__':
    main()
