#!/usr/bin/env python
"""
# Digital Ocean Infrastructure Tool

## Purpose
Low level Operations on the DO Cloud, using their REST API
E.g. when terraform destroy fails, you can delete droplets using this.

## Caution

Most features are tested against a Fedora host filesystem (the default image)

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

See: https://github.com/DavidZisky/kloud3s
See: https://registry.terraform.io/modules/aigisuk/ha-k3s/digitalocean/latest
"""
# Could be done far smaller.
import sys
import time
import pycond
from devapp import gevent_patched

from devapp.tools.infra import (
    wait_for,
    set_environ_vars,
    DIE,
    require_tools,
    run_parallel,
    secrets,
    DROPS,
    local_drop,
)
import json
import os

import time
from tempfile import NamedTemporaryFile
from rich.console import Console
from rich.table import Table
from rich.text import Text
from rich.markdown import Markdown
import requests
from devapp.app import FLG, app, run_app, do, system
from operator import setitem
from devapp.tools.times import times
from fnmatch import fnmatch
from devapp.tools import confirm, exists, read_file, write_file, dirname, cast

from devapp.app import app, run_app, FLG


# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))

# even with accept-new on cloud infra you run into problems since host keys sometimes change for given ips:
# so:
# ssh = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
ssh = (
    lambda: f'ssh -o StrictHostKeyChecking=accept-new -o UserKnownHostsFile={tmp_dir[0]}/ssh_known_hosts '
)


def d_init_feats():
    here = os.path.abspath(os.path.dirname(__file__))
    return here + '/init_features'


def all_feats():
    h = []
    D = getattr(FLG, 'features_dir', '')
    for d in [D, d_init_feats()]:
        if not d or not exists(d):
            continue
        l = [
            f
            for f in os.listdir(d)
            if not '.local' in f
            and ':' in f
            and f.endswith('.sh')
            and not f in h
        ]
        h.extend(l)
    return h


def show_features():
    fs = all_feats()
    r = [i.rsplit('.sh', 1)[0].split(':', 1) for i in fs]
    return '- ' + '\n- '.join([i[1] for i in r])


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

    class domain:
        n = 'for resolvable host names'
        d = 'example.com'

    class email:
        n = 'email used for (lets)encrypt cert requests'
        d = 'info@example.com'

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
        n += 'Have:\n%s.\nFilename accepted.' % show_features()
        n += 'You may supply numbers only.'
        d = []

    class features_dir:
        s = 'fdir'
        n = 'Custom feature catalog directory, in addition to built in one'

    class force:
        n = 'No questions asked'
        d = False

    class range:
        n = 'Placeholder "{}" in name will be replaced with these.'
        d = []

    class Actions:
        class list_features:
            s = 'feats'
            n = 'describe features (given with -f or all). Supported: --list_features -m <match>, --list_features k3s (ident to --feature=k3s)'

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

        class list:
            n = 'list all'
            d = True

        class database_list:
            s = 'dal'

        class database_delete:
            s = 'dad'

        class domain_list:
            s = 'dol'

        class domain_delete:
            s = 'dod'

        class droplet_create:
            pass

        class droplet_delete:
            s = 'dd'
            n = 'Deletes all matching droplets. --name must be given, "*" accepted.'
            n = "Example: Delete all created within the last hour: \"dd --since 1h -n '*'"

        class droplet_init:
            s = 'di'
            n = 'configure basic (bootstrap) features of new or existing droplets'

        class droplet_list:
            s = 'dl'

        class droplet_list_no_cache:
            s = 'dlc'

        class droplet_sizes:
            n = 'List sizes'

        class loadbalancer_list:
            s = 'lbl'

        class loadbalancer_delete:
            s = 'lbd'


syst = lambda s: os.popen(s).read().strip()


def set_token():
    if not secrets.get('do_token'):
        secrets['do_token'] = syst(FLG.token_cmd)
    if not secrets['do_token']:
        app.die('Token command failed', cmd=FLG.token_cmd)


def die(msg):
    app.die(msg)


from devapp.tools import cache


@cache(3)
def GET(ep, **kw):
    r = API(ep, 'get', **kw)
    return r


def API(ep, meth, data=None, plain=False):
    """https://docs.digitalocean.com/reference/api/api-reference/"""
    app.info(f'API: {meth} {ep}')
    data = data if data is not None else {}
    token = secrets['do_token']
    url = f'https://api.digitalocean.com/v2/{ep}'
    app.debug(f'API: {meth} {ep}', **data)
    meth = getattr(requests, meth)
    h = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json',
    }
    r = (
        meth(url, data=json.dumps(data), headers=h)
        if data
        else meth(url, headers=h)
    )
    if not r.status_code < 300:
        die(r.text)
    if plain:
        return r
    t = r.text or '{}'
    r = json.loads(t)
    # app.debug('Result', json=r)
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
        return (
            os.popen(f'{ssh()} {user}@{ip} {cmd} 2>/dev/null').read().strip()
        )

    return wait_for(why, waiter, tmout=tmout, dt=dt)


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


def get_all(typ, simplifier, lister, logged={}):

    all_ = GET(typ)[typ] if lister is None else lister()
    try:
        [i['region'].pop('sizes') for i in all_]
    except:
        pass
    l = len(all_)
    if not logged.get(l):
        if app.log_level < 20:
            app.debug(f'all {typ}', json=all_)
        else:
            app.info(f'{l} {typ}', hint='--log_level=10 to see all data')
        logged[l] = True
    return [simplifier(d) for d in all_]


def list_resources(name, typ, simplifier, headers, filtered=True, lister=None):
    """droplet, domain, loadbalancer, database"""
    name = name
    match = FLG.match
    since = FLG.since
    tags = FLG.tags
    # for list user expects this. All others will set it:

    def matches(d, name=name, match=match, since=since, tags=tags):
        # creating?
        if not d.get('id'):
            return True
        if name == 'local':
            return

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
        try:
            dt = times.to_sec(since)
        except Exception as _:
            app.die(
                'Cannot convert to unixtime',
                given=since,
                hint='Wrong CLI flag? Try -h or --hf to see flag names',
            )
        if times.utcnow() - times.iso_to_unix(d['created_at']) < dt:
            return True

    if typ == 'droplets':
        if have_droplet_ips():
            total = DROPS.values()
        else:
            total = get_all(typ, simplifier, lister)
            [DROPS.setdefault(d['name'], {}).update(d) for d in total]
            write_file(fn_drops_cache, json.dumps(DROPS), mkdir=True)
    else:
        total = get_all(typ, simplifier, lister)

    all = [d for d in total if matches(d)] if filtered else total

    def formatter(
        res, typ=typ, headers=headers, matching=len(all), total=len(total)
    ):
        headers = headers(res[typ])
        taglist = ','.join(tags)
        T = typ.capitalize()
        return setup_table(
            f'{matching}/{total} {T} (name={name}, matching={match}, since={since}, tags={taglist})',
            headers,
            dicts=res[typ],
        )

    return {typ: all, 'formatter': formatter}


def resource_delete(typ, lister, force, pth=None):
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
        path = f'{typ}/{id}' if pth is None else pth(dr)
        Thread(target=API, args=(path, 'delete')).start()
    return d


def assert_sane_name(name):
    if not name or '*' in name or '?' in name or '[' in name:
        app.die('Require "name" with chars only from a-z, A-Z, 0-9, . and -')


have_droplet_ips = lambda: DROPS and not any(
    [d for d in DROPS.values() if not d.get('ip')]
)

fn_drops_cache = '/tmp/droplets.json'


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


tmp_dir = [0]


def make_temp_dir(prefix):
    dnt = NamedTemporaryFile(prefix=f'{prefix}_').name
    user = FLG.user
    os.makedirs(dnt, exist_ok=True)
    sm = dirname(dnt) + f'/{prefix}.{user}'  # convenience
    os.unlink(sm) if exists(sm) else 0
    os.symlink(dnt, sm, target_is_directory=True)
    tmp_dir[0] = sm


def parametrized_workflow(parallel={'droplet_create', 'droplet_init'}):
    """parallel -> threads are spawned for all names in a range"""
    action = app.selected_action
    app.info(action)
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
            return partial(
                run_parallel, f, range_, kw, after=Actions.droplet_list
            )
        else:
            return partial(f, **kw)


droplet = lambda name: Actions.droplet_list(name=name)
unalias_size = lambda s: dict(alias_sizes).get(s, s)


def parse_description_doc_str(c):
    try:
        c, b = c.split("'", 1)[1].split("\n'", 1)
        c = ('\n' + c).replace('\n#', '\n##')
    except:
        c, b = 'No description', c
    return c, b


class Actions:
    def _pre():
        r = read_file(fn_drops_cache, dflt='')
        if r:
            DROPS.update(json.loads(r))
        if '_' in FLG.name:
            app.die('No underbar in name')

        require_tools('kubectl')
        if FLG.range and not '{}' in FLG.name:
            _ = 'Range given but no placeholder "{}" in name - assuming "%s-{}"'
            app.info(_ % FLG.name)
            FLG.name += '-{}'
        set_environ_vars()
        D = FLG.features_dir
        if D:
            FLG.features_dir = os.path.abspath(D)
        app.out_formatter = formatter
        set_token()
        # XL to real size:
        # size_alias_to_real('size')
        return parametrized_workflow()

    def list_features():
        md = []
        if (
            not FLG.features
            and not sys.argv[-1][0] == '-'
            and sys.argv[-2] == '--list_features'
        ):
            FLG.features = [sys.argv[-1]]
        feats = FLG.features or all_feats()
        feats = validate_features(feats)
        match = FLG.match
        for f, t, feat in feature_fns(feats):
            c = read_file(feat)
            if match and not match in c:
                continue
            descr, body = parse_description_doc_str(c)
            b = f'```bash\n{body}\n```\n'
            md.append(f'# {t} ({f})\n{feat}\n{b}\n\n{descr}---- \n')
        console = Console()
        md = Markdown('\n'.join(md))
        console.print(md)

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

    def domain_list(name=None):
        if name is None:
            name = FLG.name.replace('{}', '*')

        def simplify_values(d):
            for k in 'data', 'port', 'priority', 'flags', 'tag', 'weight':
                d.pop(k)
            d['name'] += '.' + d.get('domain')
            return d

        def headers(all):
            # for k in all: if k['type'] == 'A': k['name'] = Text(k['name'], style='red')
            if not all:
                return ['id']
            return sorted([k for k in all[0].keys() if not k == 'domain'])

        def lister():
            ds, r = [d['name'] for d in GET('domains')['domains']], []
            k = lambda i, f: setitem(i, 'domain', f) or i
            g = lambda f: GET(f'domains/{f}/records')['domain_records']
            r.extend(
                [k(i, f) for f in ds for i in g(f) if not i['type'] == 'NS']
            )
            r.sort(key=lambda i: i['name'])
            return r

        return list_resources(
            name, 'domain_records', simplify_values, headers, lister=lister
        )

    @classmethod
    def domain_delete(A):
        p = lambda r: f'domains/{r["domain"]}/records/{r["id"]}'
        return resource_delete(
            'domain_records', A.domain_list, FLG.force, pth=p
        )

    def database_list(name=None):
        if name is None:
            name = FLG.name.replace('{}', '*')

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
                [
                    '$',
                    {
                        'style': 'red',
                        'justify': 'right',
                        'title': f'{t}$ (estimated)',
                    },
                ],
                ['since', {'justify': 'right'}],
                ['tags'],
                ['size'],
                ['con'],
            ]

        return list_resources(name, 'databases', simplify_values, headers)

    @classmethod
    def database_delete(A):
        return resource_delete('databases', A.database_list, FLG.force)

    def loadbalancer_list(name=None):
        if name is None:
            name = FLG.name.replace('{}', '*')

        def simplify_values(d):
            drops = d.get('droplet_ids', ())
            r = {
                k: d.get(k)
                for k in ['ip', 'name', 'status', 'tag', 'id', 'created_at']
            }
            r.update(
                {
                    'algo': d.get('algorithm'),
                    'letsencr': d.get('disable_lets_encrypt_dns_records'),
                    'droplets': ','.join([dropname_by_id(i) for i in drops]),
                    'rules': ','.join(
                        [
                            '{entry_port}->{target_port}'.format(**i)
                            for i in d['forwarding_rules']
                        ]
                    ),
                }
            )
            r['$'] = 100
            r['since'] = times.dt_human(d['created_at'])
            r['region'] = d['region']['slug']
            return r

        def headers(all):
            t = int(sum([d.get('$', 0) for d in all]))
            return [
                ['name', {'style': 'green'}],
                'ip',
                ['since', {'justify': 'right'}],
                'rules',
                'droplets',
                'status',
                'tag',
                'algo',
                'letsencr',
            ]

        return list_resources(name, 'load_balancers', simplify_values, headers)

    @classmethod
    def loadbalancer_delete(A):
        return resource_delete(
            'load_balancers', A.loadbalancer_list, FLG.force
        )

    def droplet_list_no_cache():
        DROPS.clear()
        return Actions.droplet_list(cache=False)

    def droplet_list(name=None, filtered=True, cache=True):
        if not cache and exists(fn_drops_cache):
            os.unlink(fn_drops_cache)
        if name is None:
            name = FLG.name.replace('{}', '*')

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
            for k, t in ['ip', 'public'], ['ip_priv', 'private']:
                try:
                    r[k] = [
                        i['ip_address']
                        for i in d['networks']['v4']
                        if i['type'] == t
                    ][0]
                except:
                    pass
            for l in 'volume_ids', 'tags':
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
                ['ip', {'min_width': 15}],
                ['$', {'style': 'red', 'justify': 'right', 'title': f'{t}$'}],
                ['since', {'justify': 'right'}],
                'tags',
                'size_slug',
                'region',
                'ip_priv',
                'id',
                'volume_ids',
            ]

        r = list_resources(
            name, 'droplets', simplify_values, headers, filtered=filtered
        )
        return r

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
        d['private_networking'] = True
        name = d['name']
        assert_sane_name(name)
        droplet(name)

        feats = validate_features(d.pop('features'))
        d['tags'] = t = list(d['tags'])
        t.extend(feats)
        d['ssh_keys'] = [get_ssh_id()]
        if name in DROPS or name == 'local':
            if not name == 'local':
                app.warn(f'Droplet {name} exists already')
        else:
            DROPS[name] = {'name': name}
            dd('post', d)

        # if FLG.droplet_create_no_init:
        #     app.info('Created. No init', **d)
        #     return 'created'
        # if FLG.droplet_create_ssh_add_config:
        #     do(add_ssh_config, ip=ip, name=name)
        Actions.droplet_init(name=name, features=feats)
        # wait_for_ssh(name=name)
        return Actions.droplet_list(name=name)

    @classmethod
    def droplet_delete(A):
        return resource_delete(
            'droplets', partial(A.droplet_list, cache=False), FLG.force
        )

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
        da = Actions.loadbalancer_list()
        if da['load_balancers']:
            formatter(da)
        a = Actions.billing()
        app.info('month to date usage', amount=a['month_to_date_usage'])

    def droplet_init(name, features):
        # if not 'local' in name: return
        configure_features(name, features)
        app.info('initted', logger=name)


def dropname_by_id(id, fail=False):
    d = [i for i in DROPS.values() if i['id'] == id]
    if not d:
        if fail:
            return '[droplet gone]'
            # app.die(f'droplet {id} not found')
        DROPS.clear()
        Actions.droplet_list()
        return dropname_by_id(id, True)
    return d[0].get('name', 'gone droplet')


def configure_features(name, features, prefix='', local=None):
    threading.current_thread().logger = name
    feats = validate_features(features)
    if not feats:
        app.warn('no init features')
        return
    app.info(f'initing', name=name, feats=feats, logger=name)
    user = FLG.user
    # if user != 'root' and not 'add_sudo_user' in feats:
    #     app.info('Non root user -> adding add_sudo_user feat', user=user)
    #     feats.insert(0, 'add_sudo_user')
    # if not 'functions' in feats:
    #     app.info('Adding common functions to features')
    #     feats.insert(0, 'functions')

    fn_feats = feature_fns(feats)
    for f, t, fn in fn_feats:
        app.info('parsing feature', feat=t, logger=name)
        s = read_file(fn).lstrip()
        _, s = parse_description_doc_str(s)

        parts = find_my_init_parts(name, s)
        for part, nr in zip(parts, range(len(parts))):
            run_init_part(f, name, part, f'{prefix}{nr}', local)


drop = lambda name: local_drop if name == 'local' else DROPS[name]


def run_dependency(ig, name, feat):
    """
    source %(feature:functions)s -> feat = "feature:functions"
    """
    n = feat.split(':', 1)[1]
    full = f'ran: {feat}'
    if drop(name).get(full):
        app.info(f'skipping: {n} (ran already)', logger=name)
        return n
    drop(name)[full] = True
    configure_features(name, [n], prefix='%s-%s' % (ig.get('nr'), n))
    return n


def feature_fns(feats):
    fns = []
    D = FLG.features_dir
    dirs = [d_init_feats()]
    dirs.insert(0, D) if D else 0
    for f in feats:
        if '/' in f:
            assert exists(f)
            fn = f
        else:
            fn = [
                t
                for t in all_feats()
                if f == t.split(':', 1)[1].rsplit('.sh', 1)[0]
            ]
            assert len(fn) == 1
            F = fn
            for d in dirs:
                fn = d + '/' + F[0]
                if exists(fn):
                    break
        if not exists(fn):
            app.die('Not found', feature=f, checked=dirs)
        t = os.path.basename(fn)
        fns.append([f, t, fn])
    return fns


def find_my_init_parts(name, script):
    """script the sum of all scripts - which we split now into parts, run consecutively
    The parts are built from at-hand information like name matching.
    Within the parts we have cond blocks, evalled later.
    """
    if script.startswith('#!'):
        # no shebang
        script = '\n' + script.split('\n', 1)[1]
    I = script.split('\n# part:')
    r = []
    empty_header = False
    for part in I:
        cond, body = part.split('\n', 1)
        if not body.strip():
            if not r:
                empty_header = True
            continue
        if not cond:
            cond = 'name'  # always there
        if pycond.pycond(cond.strip())(state=ItemGetter(name=name)):
            r.append({'body': body})
    if len(r) > 1 and not empty_header:
        head = r.pop(0)
        for p in r:
            p['body'] = head['body'] + p['body']
    return r


def run_init_part(feat, name, part, nr, local):
    marker = '-RES-'
    pre = [
        '#!/bin/bash',
        f'echo "--------------  {name} {feat} part {nr} --------------  "',
    ]
    pre.extend(['ip="%(ip)s"', f'name="{name}"', ''])
    pre = '\n'.join(pre)
    ctx = ItemGetter(name=name, marker=marker, nr=nr)
    body = pre + part['body']
    script = preproc_init_script(body, ctx) % ctx
    d_tmp = tmp_dir[0] + f'/{name}'
    fnt = f'{d_tmp}/{feat}_{nr}.sh'
    DROP = drop(name)
    ip = DROP['ip']
    fntr = f'root@{ip}:/root/' + os.path.basename(fnt)
    fntres = f'{fnt}.res'
    local = name == 'local'
    where = 'locally' if local else 'remotely'
    app.info(f'Running script {nr} {where}', logger=name)
    write_file(fnt, script, chmod=0o755, mkdir=True)
    if not 'functions' in feat:
        os.system(f'echo -e "\x1b[35m";cat "{fnt}"; echo -e "\x1b[0m"')
    # local could have been set, when this is a dep of another one.
    if not local:
        scp = 'scp -q ' + ssh().split(' ', 1)[1]
        cmd = f'{scp} "{fnt}" "{fntr}"'
        if os.system(cmd):
            app.info('waiting for ssh', logger=name)
            wait_for_ssh(ip, name)
            if system(cmd):
                app.die('Init failed', name=name)
        fntr = '/root/' + fntr.split('/root/', 1)[1]
        cmd = f'{ssh()} "root@{ip}" "{fntr}"'
    else:
        cmd = f'"{fnt}"'
        cmd = f'cd "{d_tmp}" && {cmd}'
    cmd += f' | tee >(grep -e {marker} --color=never > "{fntres}")'
    # if not local: cmd += ' &'

    if system(cmd):
        app.die('cmd failed')
    res = {}

    # while not exists(fntres):
    #     print(name, 'wait fntres')
    #     time.sleep(0.5)

    def parse(res_line, name=name, res=res):
        l = res_line.split(' ', 2)
        DROP[l[1]] = l[2]
        res[l[1]] = l[2]

    [parse(l) for l in read_file(f'{fntres}', dflt='').splitlines()]
    if res:
        app.info(f'{name} init result', **res)
    # os.unlink(fnt)
    # os.unlink(fntres)


def preproc_init_script(init, ctx):
    """filter blocks by pycond statements
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
        if line.startswith('# end'):
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
    return '\n'.join(r) + '\n'


class ItemGetter(dict):
    # cond: env.selinux (pycond uses .get, not getitem) -> fwd to that:
    def get(self, k, dflt=None):
        if k in self:
            return super().get(k)
        return self.__getitem__(k, dflt)

    def __getitem__(self, k, dflt=''):
        l = k.rsplit('|', 1)
        r = self.g(l[0])
        if r in (None, '') and len(l) == 2:
            return l[1]
        return r

    def g(self, k):
        if k in self:
            return self.get(k)
        tmout = 120
        if k.startswith('wait:'):
            _, tmout, k = k.split(':', 2)
        l = k.split('.')
        if l[0] == 'flag':
            return getattr(FLG, l[1])
        if l[0] == 'secret':
            return cast(secrets[l[1]])
        if l[0] == 'env':
            return cast(os.environ.get(l[1], ''))
        name = self.get('name')
        if (
            l[0] in DROPS
            or l[0] == 'local'
            or l[0] == 'match:key'
            or l[0] == 'all'
        ):
            drop, k = l[0], l[1]
        elif l[0] == 'matched':
            return self.get('matched')[l[1]]
        else:
            drop = name

        if k.startswith('feature:'):
            return run_dependency(self, name, k)

        def waiter(name=drop, k=k, self=self):
            if name == 'match:key':
                h = [d for d in DROPS.values() if k in d]
                if not h:
                    return
                self['matched'] = h[0]
                return h[0][k]
            if not have_droplet_ips():
                Actions.droplet_list(name=name)
            if name == 'all':
                if any([n for n in nodes() if not DROPS.get(n, {}).get(k)]):
                    return
                return True
            d = local_drop if name == 'local' else DROPS.get(name)
            if not d:
                app.die(
                    f'Droplet {name} expected but not present.',
                    hint='was it created?',
                )
            return d.get(k)

        v = waiter()
        if v:
            return v
        t0 = now()
        r = wait_for(f'{k} of {drop}', waiter, tmout=int(tmout))
        # print('ret', r, 'for', k)
        app.info(f'got {k} of {drop}', dt=now() - t0, logger=name, value=r)
        return r


def nodes():
    return os.environ['nodes'].split(' ')


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
