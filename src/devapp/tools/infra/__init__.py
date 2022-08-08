from devapp.app import app, FLG, system, DieNow
from operator import itemgetter
from devapp.tools import (
    exists,
    read_file,
    json,
    dirname,
    cache,
    write_file,
    to_list,
)


from devapp.tools.flag import build_action_flags
from functools import partial
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from tempfile import NamedTemporaryFile
import os, sys
import threading
import time, requests

# Could be done far smaller.
import sys
import pycond
from devapp import gevent_patched

import json
import os

import time
from devapp.app import FLG, app, do, system
from operator import setitem
from devapp.tools.times import times
from fnmatch import fnmatch
from devapp.tools import confirm, exists, read_file, write_file, dirname, cast

# abort while in any waiting loop (concurrent stuff failed):
DIE = []
secrets = {}
DROPS = {}
NETWORKS = {}
SSH_KEYS = {}
# pseudo droplet running parallel flows locally on the control machine
local_drop = {'name': 'local', 'ip': '127.0.0.1'}
now = lambda: int(time.time())


class fs:
    tmp_dir = [0]
    fn_drops_cache = lambda: f'/tmp/droplets_{prov[0].name}.json'

    def make_temp_dir(prefix):
        dnt = NamedTemporaryFile(prefix=f'{prefix}_').name
        user = FLG.user
        os.makedirs(dnt, exist_ok=True)
        sm = dirname(dnt) + f'/{prefix}.{user}'  # convenience
        os.unlink(sm) if exists(sm) else 0
        os.symlink(dnt, sm, target_is_directory=True)
        fs.tmp_dir[0] = sm


# even with accept-new on cloud infra you run into problems since host keys sometimes change for given ips:
# so: ssh = 'ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null '
_ = '-o StrictHostKeyChecking=accept-new -o UserKnownHostsFile='
ssh = lambda: f'ssh {_}{fs.tmp_dir[0]}/ssh_known_hosts '


def multithreaded(f, range_, kw, after):
    n = kw['name']
    n = n if '{}' in n else (n + '-{}')
    names = [n.replace('{}', str(i)) for i in range_]
    t = []
    names.insert(0, 'local')   # for local tasks
    for n in names:
        k = dict(kw)
        k['name'] = n
        app.info('Background', **k)
        # time.sleep(1)
        _ = threading.Thread
        t.append(
            _(target=in_thread_func_wrap, args=(f,), kwargs=k, daemon=False)
        )
        t[-1].start()
    while any([d for d in t if d.isAlive()]) and not DIE:
        time.sleep(0.5)
    if DIE:
        app.error('Early exit parallel flow')
        sys.exit(1)
    return after()


def in_thread_func_wrap(f, *args, **kw):
    n = kw.get('name') or f.__name__
    threading.current_thread().logger = n
    app.info(f.__name__, logger=n, **kw)
    try:
        return f(*args, **kw)
    except DieNow as ex:
        app.error(ex.args[0], **ex.args[1])
    except Exception as ex:
        app.error(str(ex), exc=ex)
    DIE.append(1)


def require_tools(*tools):
    for t in tools:
        if system(f'type {t}', no_fail=True):
            at = 'https://github.com/alexellis/arkade#catalog-of-clis'
            app.error(
                f'Missing tool: {t}',
                hint=f'Consider installing arkade, which can "arkade get" these tools: {at}',
            )
            sys.exit(1)


class env:
    names = lambda: os.environ['names'].split(' ')

    def set_environ_vars(name=None, range=None):
        """Set common env vars, usable in feature scripts"""
        name = name if not name is None else FLG.name
        range = range if not range is None else FLG.range
        rl, names = 1, [name]
        k = lambda r: name.replace('{}', r)
        if '{}' in name:
            rl = len(range)
            names = [k(r) for r in range]
        E = {}
        E['cluster_name'] = k('').replace('-', '')
        E['rangelen'] = str(rl)
        E['names'] = ' '.join(names)
        E['dir_project'] = os.getcwd()
        os.environ.update(E)
        return E


class wait:
    def for_(why, waiter, tmout=60, dt=3):
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

    def for_ip(name):
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

        return wait.for_(f'droplet {name} ip', waiter, tmout=300, dt=4)

    def for_ssh(ip=None, name=None):
        assert name
        if not ip:
            ip = wait.for_ip(name)
        kw = {'tmout': 60, 'dt': 2}
        wait.for_remote_cmd_output(
            f'droplet {name}@{ip} ssh', 'ls /', ip=ip, **kw
        )
        return ip

    @cache(0)
    def for_remote_cmd_output(why, cmd, ip, user='root', tmout=60, dt=3):
        def waiter():
            return (
                os.popen(f'{ssh()} {user}@{ip} {cmd} 2>/dev/null')
                .read()
                .strip()
            )

        return wait.for_(why, waiter, tmout=tmout, dt=dt)


class fmt:
    # fmt:off
    key_ram           = 'RAM GB'
    key_tags          = 'tags'
    key_created       = 'created'
    key_ip_range      = 'iprange'
    key_curncy        = '€'
    key_curncy_tot    = f'∑{key_curncy}'
    key_disk_size     = 'Disk GB'
    key_size_alias    = ''
    key_price_monthly = f'{key_curncy}/Month'
    key_droplet       = 'droplet'
    key_droplets      = 'droplets'
    key_ssh_pub_key   = 'pub key end'
    key_typ           = '🖥'
    # fmt:on

    volumes = lambda key, d, into: setitem(into, 'volumes', ' '.join(d[key]))

    def typ(cores, mem, disk):
        return f'{cores}/{mem}/{disk}'

    def price_total(key, d, into, price_hourly):
        s = times.iso_to_unix(into[fmt.key_created])
        _ = (now() - s) / 3600 * price_hourly
        into[fmt.key_curncy_tot] = round(_, 1)

    def vol_price(key, d, into):
        s = into[fmt.key_disk_size]
        p = prov[0].vol_price_gig_month * s
        into[fmt.key_curncy] = round(p, 1)
        fmt.price_total(key, d, into, p / 30 / 24)

    def ssh_pub_key(key, d, into):
        into[fmt.key_ssh_pub_key] = '..' + d[key][-20:].strip()

    def droplet_id_to_name(key, d, into):
        ids, r = to_list(d.get(key, '')), []
        for id in ids:

            if id:
                d = [k for k, v in DROPS.items() if v.get('id') == id]
                r.append(id if not d else d[0])

        into[fmt.key_droplets] = ','.join(r)

    def price_monthly(key, d, into):
        into[fmt.key_price_monthly] = int(d.get(key))

    def size_name_and_alias(key, d, into):
        n = into['name'] = d.get(key)
        into[fmt.key_size_alias] = prov[0].size_aliases_rev().get(n, '')

    def to_ram(key, d, into):
        c = getattr(prov[0], 'conv_ram_to_gb', lambda x: x)
        into[fmt.key_ram] = c(int(d.get(key)))

    def to_since(key, d, into):
        v = into[fmt.key_created] = d.get(key)
        into['since'] = times.dt_human(v)

    def setup_table(title, headers, all=None):
        tble = Table(title=title)
        t, crn = [], (fmt.key_curncy, fmt.key_curncy_tot)
        for k in crn:
            if all and all[0].get(k) is not None:
                t.append(int(sum([d.get(k, 0) for d in all])))

        def auto(col, dicts=all):

            if dicts:
                try:
                    float(dicts[0].get(col, ''))
                    if col in crn:
                        T, u = (t[0], 'M') if col == crn[0] else (t[1], 'T')
                        return [
                            col,
                            {
                                'justify': 'right',
                                'style': 'red',
                                'title': f'{T}{fmt.key_curncy}/{u}',
                            },
                        ]
                    return [col, {'justify': 'right'}]
                except:
                    pass
            if col == 'name':
                return [col, {'style': 'green'}]
            return [col]

        headers = [auto(i) if isinstance(i, str) else i for i in headers]
        headers = [[h[0], {} if len(h) == 1 else h[1]] for h in headers]
        [tble.add_column(h[1].pop('title', h[0]), **h[1]) for h in headers]

        def string(s):
            if isinstance(s, list):
                s = ','.join([str(i) for i in s])
            return str(s)

        if all is not None:
            for d in all:
                tble.add_row(*[string(d.get(h[0], '')) for h in headers])
        return tble

    def mdout(md):
        console = Console()
        md = Markdown('\n'.join(md))
        console.print(md)

    def printer(res):
        if not isinstance(res, dict):
            return
        f = res.get('formatter')
        if f:
            console = Console(markup=False, emoji=False)
            console.print(f(res))
            return True


syst = lambda s: os.popen(s).read().strip()


def set_token():
    if not secrets.get('do_token'):
        secrets['do_token'] = syst(FLG.token_cmd)
    if not secrets['do_token']:
        app.die('Token command failed', cmd=FLG.token_cmd)


def die(msg):
    app.die(msg)


class Api:
    @cache(3)
    def get(ep, **kw):
        r = Api.req(ep, 'get', **kw)
        return r

    def req(ep, meth, data=None, plain=False):
        """https://docs.hetzner.cloud/#server-types"""
        data = data if data is not None else {}
        token = secrets['do_token']
        url = f'{prov[0].base_url}/{ep}'
        if app.log_level > 10:
            app.info(f'API: {meth} {ep}')
        else:
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
        return r


from inspect import signature


def actions_spawner_when_parallel(
    parallel={'droplet_create', 'droplet_init', 'volume_create'}
):
    """parallel -> threads are spawned for all names in a range"""
    action = app.selected_action
    app.info(action)
    if action in parallel:
        # utillity for temporary files - at the same place:
        fs.make_temp_dir(action)
        f = getattr(prov[0].Actions, action)
        if isinstance(f, type):
            f = f.run

        sig = signature(f).parameters
        kw = {}
        for k in sig:
            if k[0] == '_':
                continue
            v = getattr(FLG, k, None)
            if v is None:
                v = getattr(FLG, f'{action}_{k}', None)
            if v is None:
                app.die('Missing action parameter', param=k)
            kw[k] = v
        if '{}' in FLG.name:
            range_ = FLG.range
            if not range_:
                app.die('Missing range', name=FLG.name)
            return partial(
                multithreaded, f, range_, kw, after=Actions.droplet_list
            )
        else:
            return partial(f, **kw)


class Features:
    def init():
        here = os.path.abspath(os.path.dirname(__file__))
        return here + '/flows'

    def all():
        h = []
        D = getattr(FLG, 'features_dir', '')
        for d in [D, Features.init()]:
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

    def validate(feats):
        """featuers may have short forms - here we set the full ones"""
        r, cust = [], []
        all_features = Features.all()
        for f in feats:
            if exists(f):
                cust.append(os.path.abspath(f))
            else:
                fn = [t for t in all_features if f in t]
                if len(fn) == 0:
                    app.die('Feature not found', given=f, known=all_features)
                if len(fn) != 1:
                    app.die(
                        'Feature not exact', matches=fn, known=all_features
                    )
                r.append(fn[0])
        r = sorted(r)
        r = [i.split(':', 1)[1].rsplit('.sh', 1)[0] for i in r]
        r.extend(cust)
        return r

    def parse_description_doc_str(c):
        try:
            c, b = c.split("'", 1)[1].split("\n'", 1)
            c = ('\n' + c).replace('\n#', '\n##')
        except:
            c, b = 'No description', c
        return c, b

    def fns(feats):
        fns = []
        D = FLG.features_dir
        dirs = [Features.init()]
        dirs.insert(0, D) if D else 0
        for f in feats:
            if '/' in f:
                assert exists(f)
                fn = f
            else:
                fn = [
                    t
                    for t in Features.all()
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

    def show():
        fs = Features.all()
        r = [i.rsplit('.sh', 1)[0].split(':', 1) for i in fs]
        return '- ' + '\n- '.join([i[1] for i in r])


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
        d = 'pass show my_token'

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
        n = 'aliases'
        d = 'XXS'

    class region:
        d = 'fra1'

    class tags:
        n = 'Set tags when creating or use as filter for list / delete'
        d = []

    class ssh_keys:
        n = 'Must be present on Infra Provider. Can be ssh key id or name (slower then, add. API call, to find id). If not set we add all present ones.'
        d = ''

    class user:
        n = 'Username to create additionally to root at create (with sudo perms)'
        d = os.environ['USER']

    class features:
        n = 'Configure features via SSH (as root).'
        n += 'Have:\n%s.\nFilename accepted.' % Features.show()
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

    class ip_range:
        n = 'when creating networks or droplets with own networks'
        s = 'ipr'
        d = '10.0.0.0/16'

    def _pre_init(Flags, Actions):
        build_action_flags(Flags, Actions)
        # adjust short names, we want droplet to get 'd'
        A = Flags.Actions
        for F in 'domain', 'database':
            for d in 'list', 'create', 'delete':
                c = getattr(A, f'{F}_{d}', 0)
                if c:
                    c.s = F[:2] + d[0]
        A.list.d = True


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


def get_all(typ, normalizer, lister, logged={}):
    rsc = typ.split('?', 1)[0]
    if isinstance(lister, str):
        rsc = lister
        lister = None
    all_ = Api.get(typ)[rsc] if lister is None else lister()
    prov[0].rm_junk(all_)
    l = len(all_)
    if not logged.get(l):
        if app.log_level < 20:
            app.debug(f'all {typ}', json=all_)
        else:
            app.info(f'{l} {typ}', hint='--log_level=10 to see all data')
        logged[l] = True

    n = make_normalizer(normalizer)
    return rsc, [n(d) for d in all_]


def make_normalizer(n):
    if callable(n):
        return n

    def _(d, n=n):
        r, np = {}, None
        if isinstance(n, tuple):
            n, np = n
        for k, f in n:
            v = d.get(k)
            if callable(f):
                f(k, d, into=r)
            else:
                r[f] = v
        if np:
            np(d, r)
        d.update(r)
        return d

    return _


g = lambda o, k, d=None: getattr(o, k, d)


def list_simple(name, cls, headers=None, **kw):
    ep = g(cls, 'endpoint', cls.__name__)
    h = g(cls, 'headers', headers)
    np = g(prov[0], 'normalize_post')
    np = np if np is None else partial(np, cls=cls, headers=h)
    n = (g(cls, 'normalize', []), np)
    return list_resources(name, ep, n, h, **kw)


def list_resources(
    name,
    endpoint,
    normalizer,
    headers,
    filtered=True,
    lister=None,
    sorter=None,
):
    """droplet, domain, load_balancer, database"""
    name = name
    match = FLG.match
    since = FLG.since
    tags = FLG.tags
    # for list user expects this. All others will set it:
    if name is None:
        name = FLG.name.replace('{}', '*')

    def matches(d, name=name, match=match, since=since, tags=tags):
        # creating?
        if not d.get('id'):
            return True
        if name == 'local':
            return

        if FLG.range:
            if not d['name'] in os.environ['names']:
                return
        else:
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
        if times.utcnow() - times.iso_to_unix(d[fmt.key_created]) < dt:
            return True

    if endpoint == prov[0].droplet.endpoint:
        if have_droplet_ips():
            rsc, total = 'droplets', DROPS.values()
        else:
            rsc, total = get_all(endpoint, normalizer, lister)
            [DROPS.setdefault(d['name'], {}).update(d) for d in total]
            write_file(fs.fn_drops_cache(), json.dumps(DROPS), mkdir=True)
    else:
        rsc, total = get_all(endpoint, normalizer, lister)

    if endpoint == prov[0].network.endpoint:
        prov[0].NETWORKS.clear()
        prov[0].NETWORKS.update({k['name']: k for k in total})
    elif endpoint == prov[0].ssh_keys.endpoint:
        prov[0].SSH_KEYS.clear()
        prov[0].SSH_KEYS.update({k['name']: k for k in total})
    all = [d for d in total if matches(d)] if filtered else total
    if sorter:
        all = [i for i in sorter(all)]

    def formatter(res, headers=headers, matching=len(all), total=len(total)):
        all = res['data']
        typ = res['endpoint'].split('?', 1)[0]
        if callable(headers):
            headers = headers(all)
        taglist = ','.join(tags)
        T = typ.capitalize()
        return fmt.setup_table(
            f'{matching}/{total} {T} (name={name}, matching={match}, since={since}, tags={taglist})',
            headers,
            all=all,
        )

    return {'data': all, 'formatter': formatter, 'endpoint': endpoint}


def resource_delete(typ, lister, force, pth=None):
    name = FLG.name
    if not name:
        app.die('Supply a name', hint='--name="*" to delete all is accepted')
    d = lister(name=name)
    fmt.printer(d)
    ds = d['data']
    rsc = typ.__name__
    if not ds:
        app.error(f'No {rsc} matching', name=name)
        return
    app.info(f'Delete %s {rsc}?' % len(ds))
    if not force:
        confirm(f'Proceed to delete %s {rsc}?' % len(ds))
    for dr in ds:
        app.warn('deleting', **dr)
        id = dr['id']
        path = f'{typ.endpoint}/{id}' if pth is None else pth(dr)
        _ = threading.Thread
        _(target=in_thread_func_wrap, args=(Api.req, path, 'delete')).start()
    return d


import string

name_allwd = set(string.ascii_letters + string.digits + '-.')


def assert_sane_name(name, create=False):
    s = name_allwd
    if not create:
        s = s.union(set('{}*?'))
    ok = not any([c for c in name if not c in s])
    if not ok:
        app.die(
            'Require "name" with chars only from a-z, A-Z, 0-9, . and -',
            name=name,
        )


have_droplet_ips = lambda: DROPS and not any(
    [d for d in DROPS.values() if not d.get('ip')]
)


def run_this(cmd):
    a = ' '.join(list(sys.argv[:2]))
    a += ' ' + cmd
    if do(system, a, log_level='info', no_fail=True):
        DIE.append(True)


from functools import partial
import threading


droplet = lambda name: Actions.droplet_list(name=name)


class Actions:
    def _pre():
        r = read_file(fs.fn_drops_cache(), dflt='')
        if r:
            DROPS.update(json.loads(r))
        require_tools('kubectl')
        if FLG.range and not '{}' in FLG.name:
            _ = 'Range given but no placeholder "{}" in name - assuming "%s-{}"'
            app.info(_ % FLG.name)
            FLG.name += '-{}'
        E = env.set_environ_vars()

        D = FLG.features_dir
        if D:
            FLG.features_dir = os.path.abspath(D)
        app.out_formatter = fmt.printer
        set_token()
        # XL to real size:
        # size_alias_to_real('size')

        if FLG.droplet_create:
            pn = FLG.droplet_create_private_network
            Actions.prepare_droplet_create(env=E, priv_net=pn)
        a = actions_spawner_when_parallel()
        return a

    def list_features():
        """Query feature descriptions (given with -f or all).
        --list_features -m <match>
        --list_features k3s (ident to --feature=k3s)
        """

        md = []
        if (
            not FLG.features
            and not sys.argv[-1][0] == '-'
            and sys.argv[-2] == '--list_features'
        ):
            FLG.features = [sys.argv[-1]]
        feats = FLG.features or Features.all()
        feats = Features.validate(feats)
        match = FLG.match
        for f, t, feat in Features.fns(feats):
            c = read_file(feat)
            if match and not match in c:
                continue
            descr, body = Features.parse_description_doc_str(c)
            b = f'```bash\n{body}\n```\n'
            md.append(f'# {t} ({f})\n{feat}\n{b}\n\n{descr}---- \n')
        fmt.mdout(md)

    def billing():
        return Api.get('customers/my/balance')

    class billing_pdf:
        n = 'download invoice as pdf'

        class uuid:
            n = 'run billing_list to see uuid'

        def run():
            uid = FLG.billing_pdf_uuid
            r = Api.get(f'customers/my/invoices/{uid}/pdf', plain=True)
            fn = 'digital_ocean_invoice.pdf'
            write_file(fn, r.content, mode='wb')
            return f'created {fn}'

    def billing_list():
        r = Api.get('customers/my/billing_history?per_page=100')
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
            return fmt.setup_table('Billing history', head, all=h)

        r['formatter'] = formatter
        return r

    def domain_list(name=None):
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
            ds, r = [d['name'] for d in Api.get('domains')['domains']], []
            k = lambda i, f: setitem(i, 'domain', f) or i
            g = lambda f: Api.get(f'domains/{f}/records')['domain_records']
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

    def load_balancer_list(name=None):

        headers = [
            'name',
            'id',
            'since',
            fmt.key_droplets,
            'region',
            'ip',
            'size',
            # 'droplet',
            # fmt.key_disk_size,
            # 'format',
        ]
        return list_simple(name, prov[0].load_balancer, headers=headers)

    @classmethod
    def load_balancer_delete(A):
        return resource_delete(
            'load_balancers', A.load_balancer_list, FLG.force
        )

    def volume_list(name=None):

        headers = [
            'name',
            'id',
            fmt.key_curncy,
            fmt.key_curncy_tot,
            'region',
            'since',
            fmt.key_droplets,
            fmt.key_disk_size,
            'format',
        ]
        return list_simple(name, prov[0].volume, headers=headers)

    def volume_create(
        name,
        region,
        size,
        tags,
        _sizes={
            'XXS': 10,
            'XS': 50,
            'S': 100,
            'M': 500,
            'L': 1000,
            'XL': 10000,
        },
    ):
        if name == 'local':
            return
        size = _sizes.get(size, size)
        size = int(size)
        if size < 5 or size > 1000000:
            app.die('Invalid size', size=size)
        d = dict(locals())
        d.pop('_sizes')
        assert_sane_name(d['name'], True)
        d['tags'] = t = list(d['tags'])
        data = prov[0].volume.create_data(d)
        Api.req(prov[0].volume.endpoint, 'post', data=data)
        return Actions.volume_list(name=name)

    @classmethod
    def volume_delete(A):
        return resource_delete(prov[0].volume, A.volume_list, FLG.force)

    def network_list(name=None):
        headers = [
            'name',
            fmt.key_droplets,
            'iprange',
            'since',
            'tags',
            'id',
        ]
        ns = list_simple(name, prov[0].network, headers=headers)
        return ns

    class network_create:
        def run(name=None, ip_range=None):
            name = FLG.name if name is None else name
            assert_sane_name(name, True)
            d = {
                'ip_range': FLG.ip_range if ip_range is None else ip_range,
                'name': name,
            }
            data = prov[0].network.create_data(d)
            Api.req(prov[0].network.endpoint, 'post', data=data)
            r = Actions.network_list(name=name)

            # while not prov[0].NETWORKS.get(name):
            #     breakpoint()   # FIXME BREAKPOINT
            #     r = Actions.network_list(name=name)
            #     time.sleep(0.3)

            return r

    @classmethod
    def network_delete(A):
        return resource_delete(prov[0].network, A.network_list, FLG.force)

    def droplet_list_no_cache():
        DROPS.clear()
        return Actions.droplet_list(cache=False)

    def droplet_list(name=None, filtered=True, cache=True):
        if not cache and exists(fs.fn_drops_cache()):
            app.info('unlinking droplets cache', fn=fs.fn_drops_cache())
            os.unlink(fs.fn_drops_cache())

        def headers(all):

            return [
                ['name', {'style': 'green'}],
                ['ip', {'min_width': 15}],
                fmt.key_curncy,
                fmt.key_curncy_tot,
                ['since', {'justify': 'right'}],
                'tags',
                fmt.key_typ,
                'region',
                'ip_priv',
                'id',
                'volumes',
            ]

        return list_simple(
            name, prov[0].droplet, headers=headers, filtered=filtered
        )

    def ssh_key_list(name=None):
        h = ['name', 'fingerprint', 'id', 'since', fmt.key_ssh_pub_key]
        s = list_simple(name, prov[0].ssh_keys, headers=h, lister='ssh_keys')
        return s

    def prepare_droplet_create(env, priv_net):
        """Main Thread here still.
        default network is always 10.0.0.1/8"""

        id = FLG.ssh_keys
        if not id.isdigit():
            Actions.ssh_key_list(name='*')
            sn = FLG.ssh_keys
            id = [
                int(i['id'])
                for i in prov[0].SSH_KEYS.values()
                if not sn or i['name'] == sn
            ]
            if not id:
                app.die('No ssh key')
        else:
            id = [int(id)]
        app.info('Setting ssh key ids', ids=id)
        FLG.ssh_keys = id

        Actions.network_list()
        ns = prov[0].NETWORKS
        dn = prov[0].network.default()
        nn, nr = FLG.ip_range = dn, '10.0.0.0/8'
        if priv_net == 'own':
            nn, nr = env['cluster_name'], FLG.ip_range
        if not nn in ns:
            app.info('Creating network', name=nn, range=nr)
            Actions.network_create.run(nn, ip_range=nr)

    class droplet_create:
        class private_network:
            n = 'Name of private network to attach to.'
            t = ['default', 'own']
            d = 'default'

        def run(
            name,
            image,
            region,
            size,
            tags,
            ssh_keys,
            private_network,
            features,
        ):
            d = dict(locals())
            d['size'] = prov[0].unalias_size(d['size'])
            name = d['name']
            assert_sane_name(name, True)
            droplet(name)   # assure up to date status
            D = prov[0].droplet
            feats = Features.validate(d.pop('features'))
            d['tags'] = t = list(d['tags'])
            t.extend(feats)

            if name in DROPS or name == 'local':
                if not name == 'local':
                    app.warn(f'Droplet {name} exists already')
            else:
                DROPS[name] = {'name': name}
                data = D.create_data(d)
                Api.req(D.endpoint, 'post', data=data)

            Actions.droplet_init(name=name, features=feats)
            # wait_for_ssh(name=name)
            return Actions.droplet_list(name=name)

    @classmethod
    def droplet_delete(A):
        """
        Deletes all matching droplets. --name must be given, "*" accepted.'
        Example: Delete all created within the last hour: "dd --since 1h -n '*'"
        """

        ep = prov[0].droplet.endpoint
        return resource_delete(
            prov[0].droplet, partial(A.droplet_list, cache=False), FLG.force
        )

    def sizes_list(name=None):
        h = [
            [fmt.key_size_alias, {'justify': 'center'}],
            'name',
            [fmt.key_price_monthly, {'justify': 'right', 'style': 'red'}],
            ['CPU', {'justify': 'right'}],
            [fmt.key_ram, {'justify': 'right'}],
            [fmt.key_disk_size, {'justify': 'right'}],
            ['Descr', {'style': 'cyan'}],
        ]

        s = lambda l: reversed(
            sorted(l, key=lambda x: x[fmt.key_price_monthly])
        )
        return list_simple(name, prov[0].sizes, headers=h, sorter=s)

    #
    # l = prov[0].droplet.get_sizes(aliases=prov[0].size_aliases_rev())
    # l = reversed(sorted(l, key=lambda x: x[2]))
    #
    # def formatter(res):
    #     tble = fmt.setup_table(
    #         'Droplet Sizes',
    #         [
    #             ['', {'justify': 'center'}],
    #             ['name', {'style': 'green'}],
    #             ['$/Month', {'justify': 'right', 'style': 'red'}],
    #             ['CPU', {'justify': 'right'}],
    #             ['RAM GB', {'justify': 'right'}],
    #             ['Disk GB', {'justify': 'right'}],
    #             ['Descr', {'style': 'cyan'}],
    #         ],
    #     )
    #     for d in res['sizes']:
    #         tble.add_row(*[str(i) for i in d])
    #     return tble
    #
    # return {'sizes': l, 'formatter': formatter}

    def images_list(name=None):
        h = ['name', 'description', fmt.key_disk_size, 'since', 'id', 'rapid']
        return list_simple(name, prov[0].image, headers=h)

    def list():
        dr = Actions.droplet_list()
        fmt.printer(dr)
        # da = Actions.database_list()
        # if da['data']:
        #     fmt.printer(da)
        da = Actions.load_balancer_list()
        if da['data']:
            fmt.printer(da)
        return
        a = Actions.billing()
        app.info('month to date usage', amount=a['month_to_date_usage'])

    def droplet_init(name, features):
        # if not 'local' in name: return
        configure_features(name, features)
        app.info('initted', logger=name)


# def dropname_by_id(id, fail=False):
#     d = [i for i in DROPS.values() if i['id'] == id]
#     if not d:
#         if fail:
#             return '[droplet gone]'
#             # app.die(f'droplet {id} not found')
#         DROPS.clear()
#         Actions.droplet_list()
#         return dropname_by_id(id, True)
#     return d[0].get('name', 'gone droplet')


def configure_features(name, features, prefix='', local=None):
    feats = Features.validate(features)
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

    fn_feats = Features.fns(feats)
    for f, t, fn in fn_feats:
        app.info('parsing feature', feat=t, logger=name)
        s = read_file(fn).lstrip()
        _, s = Features.parse_description_doc_str(s)

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
    d_tmp = fs.tmp_dir[0] + f'/{name}'
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
            wait.for_ssh(ip, name)
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
                if any(
                    [n for n in env.names() if not DROPS.get(n, {}).get(k)]
                ):
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
        r = wait.for_(f'{k} of {drop}', waiter, tmout=int(tmout))
        # print('ret', r, 'for', k)
        app.info(f'got {k} of {drop}', dt=now() - t0, logger=name, value=r)
        return r


class Provider:
    """Provider specific."""

    size_aliases = lambda: ', '.join(
        [f'{i}:{k}' for i, k in prov[0].alias_sizes]
    )
    unalias_size = lambda s: dict(prov[0].alias_sizes).get(s, s)
    size_aliases_rev = lambda: {
        k: v for v, k in dict(prov[0].alias_sizes).items()
    }
    list_resources = list_resources
    list_simple = list_simple
    resource_delete = resource_delete
    DROPS = DROPS
    NETWORKS = NETWORKS
    SSH_KEYS = SSH_KEYS


prov = [0]   # set by the specific one, a derivation of Provider


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
