# 130sec vs 90 sec without gevent. Because os.system blocks for feats in gevent

from devapp import gevent_patched as _
from devapp.app import FLG, app, do, system
from devapp.app import app, FLG, system, DieNow
from devapp.tools import json, dirname, cache
from devapp.tools import os, sys, write_file, to_list
from devapp.tools import confirm, exists, read_file, dirname, cast
from devapp.tools.flag import build_action_flags
from devapp.tools.times import times
from fnmatch import fnmatch
from functools import partial
from operator import setitem
from rich.console import Console
from rich.markdown import Markdown
from rich.table import Table
from tempfile import NamedTemporaryFile
import pycond
import requests
import threading
import time

# abort while in any waiting loop (concurrent stuff failed):
DIE = []
DROPS = {}
NETWORKS = {}
SSH_KEYS = {}
# pseudo droplet running parallel flows locally on the master machine
local_drop = {'name': 'local', 'ip': '127.0.0.1'}
now = lambda: int(time.time())

attr = lambda o, k, d=None: getattr(o, k, d)


def rm(rsc, *a, skip_non_exists=False, **kw):
    def f(rsc=rsc, skip=skip_non_exists, a=a, kw=kw):
        r = attr(Prov(), rsc, None)
        if not r and skip:
            return
        if not r:
            app.die(f'Have no {rsc}')
        return resource_delete(r, *a, **kw)

    return f


class fs:
    tmp_dir = [0]
    fn_drops_cache = lambda: f'/tmp/droplets_{Prov().name}.json'

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
        E['dir_project'] = os.environ.get('dir_project', os.getcwd())
        E['fn_cache'] = fs.fn_drops_cache()
        E['infra_api_base'] = attr(Prov(), 'base_url', '')
        app.info('Environ vars', **E)
        os.environ.update(E)
        return E


class wait:
    def for_(why, waiter, tmout=60, dt=3):
        t0 = now()
        tries = int(tmout / dt)
        i = 0
        l = attr(threading.current_thread(), 'logger', app.name)
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
        wait.for_remote_cmd_output(f'droplet {name}@{ip} ssh', 'ls /', ip=ip, **kw)
        return ip

    @cache(0)
    def for_remote_cmd_output(why, cmd, ip, user='root', tmout=60, dt=3):
        def waiter():
            return os.popen(f'{ssh()} {user}@{ip} {cmd} 2>/dev/null').read().strip()

        return wait.for_(why, waiter, tmout=tmout, dt=dt)


def conc(l, sep=','):
    return sep.join([str(i) for i in l])


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
    key_typ           = 'hw'
    flag_deleted       = 'deleted' # just a marker
    # fmt:on

    volumes = lambda key, d, into: setitem(into, 'volumes', conc(d[key], ' '))

    def typ(cores, mem, disk):
        return f'{cores}/{mem}/{disk}'

    def price_total(key, d, into, price_hourly):
        s = times.iso_to_unix(into[fmt.key_created])
        _ = (now() - s) / 3600 * price_hourly
        into[fmt.key_curncy_tot] = round(_, 1)

    def vol_price(key, d, into):
        s = into[fmt.key_disk_size]
        p = Prov().vol_price_gig_month * s
        into[fmt.key_curncy] = round(p, 1)
        fmt.price_total(key, d, into, p / 30 / 24)

    def ssh_pub_key(key, d, into):
        into[fmt.key_ssh_pub_key] = '..' + d[key][-20:].strip()

    def droplet_id_to_name(key, d, into):
        ids, r = to_list(d.get(key, '')), []
        for id in ids:

            if id:
                d = [k for k, v in DROPS.items() if v.get('id') == id]
                r.append(str(id) if not d else d[0])

        into[fmt.key_droplets] = ','.join(r)

    def price_monthly(key, d, into):
        into[fmt.key_price_monthly] = int(d.get(key))

    def size_name_and_alias(key, d, into):
        n = into['name'] = d.get(key)
        into[fmt.key_size_alias] = Prov().size_aliases_rev().get(n, '')

    def to_ram(key, d, into):
        c = attr(Prov(), 'conv_ram_to_gb', lambda x: x)
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

        if headers[0][0] == 'name' and all:
            mw = max([len(i['name']) for i in all])
            headers[0][1]['min_width'] = mw
        [tble.add_column(h[1].pop('title', h[0]), **h[1]) for h in headers]

        def string(s):
            if isinstance(s, list):
                s = ' '.join(sorted([str(i) for i in s]))
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


def die(msg):
    app.die(msg)


class Api:
    """Typical infra api, works for hetzner and do, not aws. One token"""

    secrets = {}

    def set_secrets():
        for key in to_list(Prov().secrets):
            if not Api.secrets.get(key):
                v = cmd = attr(FLG, key)
                if v.startswith('cmd:'):
                    v = syst(v.split(':', 1)[1].strip())
            if not v:
                app.die('Have no secret', key=key, given=cmd)
            Api.secrets[key] = v

    @cache(3)
    def get(ep, **kw):
        r = Api.req(ep, 'get', **kw)
        return r

    def post(ep, data):
        return Api.req(ep, 'post', data)

    def delete(ep, data):
        return Api.req(ep, 'delete', data)

    def req(ep, meth, data=None, plain=False):
        """https://docs.hetzner.cloud/#server-types"""
        data = data if data is not None else {}
        P = Prov()
        token = Api.secrets[P.secrets]
        url = f'{P.base_url}/{ep}'
        if app.log_level > 10:
            app.info(f'API: {meth} {ep}')
        else:
            app.debug(f'API: {meth} {ep}', **data)
        meth = attr(requests, meth)
        h = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }
        r = meth(url, data=json.dumps(data), headers=h) if data else meth(url, headers=h)
        if not r.status_code < 300:
            die(r.text)
        if plain:
            return r
        t = r.text or '{}'
        r = json.loads(t)
        return r


from inspect import signature


class paral:
    def actions_spawner_when_parallel(
        parallel={'droplet_create', 'droplet_init', 'volume_create'}
    ):
        """parallel -> threads are spawned for all names in a range"""
        action = app.selected_action
        app.info(action)
        if action in parallel:
            # utillity for temporary files - at the same place:
            fs.make_temp_dir(action)
            f = attr(Prov().Actions, action)
            if isinstance(f, type):
                f = f.run

            sig = signature(f).parameters
            kw = {}
            for k in sig:
                if k[0] == '_':
                    continue
                v = attr(FLG, k, None)
                if v is None:
                    v = attr(FLG, f'{action}_{k}', None)
                if v is None:
                    app.die('Missing action parameter', param=k)
                kw[k] = v
            return partial(
                paral.multithreaded, f, FLG.range, kw, after=Actions.droplet_list
            )

    def multithreaded(f, range_, kw, after):
        n = kw['name']
        if range_:
            n = n if '{}' in n else (n + '-{}')
            names = [n.replace('{}', str(i)) for i in range_]
        else:
            names = [n]
        t = []
        names.insert(0, 'local')   # for local tasks
        for n in names:
            k = dict(kw)
            k['name'] = n
            app.info('Background', **k)
            # time.sleep(1)
            _ = threading.Thread
            t.append(
                _(target=paral.in_thread_func_wrap, args=(f,), kwargs=k, daemon=False)
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


class Features:
    def init():
        here = os.path.abspath(os.path.dirname(__file__))
        return here + '/flows'

    def all():
        h = []
        D = attr(FLG, 'features_dir', '')
        for d in [D, Features.init()]:
            if not d or not exists(d):
                continue
            l = [
                f
                for f in os.listdir(d)
                if not '.local' in f and ':' in f and f.endswith('.sh') and not f in h
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
                    app.die('Feature not exact', matches=fn, known=all_features)
                r.append(fn[0])
        r = sorted(r)
        r = [i.rsplit('.sh', 1)[0] for i in r]
        r.extend(cust)
        return r

    def parse_description_doc_str(c, doc_begin="\n_='# "):
        if not doc_begin in c[:100]:
            return 'No description', c
        _, c = c.split(doc_begin, 1)
        r, c = c.split('\n', 1)
        while c[0] in {' ', '\n'}:
            _, c = c.split('\n', 1)
            r += '\n' + _[2:]
        c, r = c.lstrip(), r.rstrip()
        c = c[1:] if c[0] == "'" else c
        r = r[:-1] if r[-1] == "'" else r
        return '# ' + r, c

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
                fn = [t for t in Features.all() if f == t.rsplit('.sh', 1)[0]]
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
        n = 'When creating networks or droplets with own networks. Given range will be configured as subnet within a 10/8 network.'
        s = 'ipr'
        d = '10.140.10.0/24'

    # class domain: d = ''
    class kube_config:
        n = 'Filename of kubeconfig to use (for Actions where relevant)'

    def _pre_init(Flags, Actions):
        build_action_flags(Flags, Actions)
        # adjust short names, we want droplet to get 'd'
        A = Flags.Actions
        for F in 'domain', 'database', 'dns':
            for d in 'list', 'create', 'delete':
                c = attr(A, f'{F}_{d}', 0)
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
    Prov().rm_junk(all_)
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
        r = {}
        if isinstance(n, tuple):
            np, n = n
            np(d, r)

        for k, f in n:
            v = d.get(k)
            if callable(f):
                f(k, d, into=r)
            else:
                r[f] = v
        d.update(r)
        return d

    return _


def list_simple(name, cls, headers=None, **kw):
    ep = attr(cls, 'endpoint', cls.__name__)
    h = attr(cls, 'headers', headers)
    np = attr(Prov(), 'normalize_pre')
    np = np if np is None else partial(np, cls=cls, headers=h)
    n = (np, attr(cls, 'normalize', []))
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
    P = Prov()
    name = name
    match = FLG.match
    since = FLG.since
    tags = FLG.tags
    # for list user expects this. All others will set it:
    if name is None:
        name = FLG.name.replace('{}', '*')

    def matches(d, name=name, match=match, since=since, tags=tags):
        # creating? nr is on aws domains
        # if not d.get('id') and not d.get('nr'): return True
        # print('-' * 100)
        # print(name, d)
        # print('-' * 100)
        #
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

    class nil:
        endpoint = None

    if attr(P, 'droplet', nil).endpoint == endpoint:
        if have_droplet_ips():
            rsc, total = 'droplets', DROPS.values()
        else:
            rsc, total = get_all(endpoint, normalizer, lister)
            [DROPS.setdefault(d['name'], {}).update(d) for d in total]
            write_file(fs.fn_drops_cache(), json.dumps(DROPS), mkdir=True)
    else:
        rsc, total = get_all(endpoint, normalizer, lister)

    if attr(P, 'network', nil).endpoint == endpoint:
        P.NETWORKS.clear()
        P.NETWORKS.update({k['name']: k for k in total})
    elif attr(P, 'ssh_keys', nil).endpoint == endpoint:
        P.SSH_KEYS.clear()
        P.SSH_KEYS.update({k['name']: k for k in total})
    # if name != 'local' and attr(P, 'droplet', nil).endpoint == endpoint: breakpoint()   # FIXME BREAKPOINT
    if callable(filtered):
        all = filtered(total)
    else:
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


def resource_delete(typ, lister=None, force=None, pth=None):
    if lister is None:
        n = attr(typ, '__name__', typ.__class__.__name__)
        lister = attr(Prov().Actions, f'{n}_list')
    force = FLG.force if force is None else force
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
    else:
        app.info('yes, --force is set')
    for dr in ds:
        app.warn('deleting', **dr)
        pre = attr(typ, 'prepare_delete')
        k = pre(dr) if pre else 0
        if k == fmt.flag_deleted:
            continue
        id = dr.get('id')   # domains have none
        path = f'{typ.endpoint}/{id}' if pth is None else pth(dr)
        _ = threading.Thread
        _(target=paral.in_thread_func_wrap, args=(Api.req, path, 'delete')).start()
    return d


import string

name_allwd = set(string.ascii_letters + string.digits + '-.')


have_droplet_ips = lambda: DROPS and not any(
    [d for d in DROPS.values() if not (d.get('ip') and d.get('ip_priv'))]
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
        # require_tools('kubectl')
        if FLG.range and not '{}' in FLG.name:
            _ = 'Range given but no placeholder "{}" in name - assuming "%s-{}"'
            app.info(_ % FLG.name)
            FLG.name += '-{}'
        E = env.set_environ_vars()

        D = FLG.features_dir
        if D:
            FLG.features_dir = os.path.abspath(D)
        app.out_formatter = fmt.printer
        Api.set_secrets()
        # XL to real size:
        # size_alias_to_real('size')

        if attr(FLG, 'droplet_create'):
            pn = FLG.droplet_create_private_network
            Actions.droplet_create._pre(env=E, priv_net=pn)
        if hasattr(FLG, 'droplet_list'):
            # saving us the .run calls:
            Actions.droplet_list = Actions.droplet_list()
        a = paral.actions_spawner_when_parallel()
        return a

    def cluster_delete():
        if not FLG.name:
            app.die('require name prefix')
        if not '*' in FLG.name:
            FLG.name += '*'
        p = Prov(0)
        for k in 'droplet', 'volume', 'placement_group', 'network', 'load_balancer':
            f = rm(k, skip_non_exists=True)
            f()

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
        return list_simple(name, Prov().load_balancer, headers=headers)

    load_balancer_delete = rm('load_balancer')

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
        return list_simple(name, Prov().volume, headers=headers)

    def volume_create(
        name,
        size,
        tags=None,
        region=None,
        _attach_to=None,
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
        region = region or FLG.region
        tags = tags or FLG.tags
        size = _sizes.get(size, size)
        size = int(size)
        if size < 5 or size > 1000000:
            app.die('Invalid size', size=size)
        d = dict(locals())
        d.pop('_sizes')
        Prov().assert_sane_name(d['name'], True)
        d['tags'] = t = list(d['tags'])
        data = Prov().volume.create_data(d)
        Api.req(Prov().volume.endpoint, 'post', data=data)
        return Actions.volume_list(name=name)

    volume_delete = rm('volume')

    def network_list(name=None):
        headers = [
            'name',
            fmt.key_droplets,
            'iprange',
            'since',
            'tags',
            'id',
        ]
        ns = list_simple(name, Prov().network, headers=headers)
        return ns

    class network_create:
        def run(name=None, ip_range=None):
            name = FLG.name if name is None else name
            Prov().assert_sane_name(name, True)
            d = {
                'ip_range': FLG.ip_range if ip_range is None else ip_range,
                'name': name,
            }
            data = Prov().network.create_data(d)
            Api.req(Prov().network.endpoint, 'post', data=data)
            r = Actions.network_list(name=name)

            # while not Prov().NETWORKS.get(name):
            #     breakpoint()   # FIXME BREAKPOINT
            #     r = Actions.network_list(name=name)
            #     time.sleep(0.3)

            return r

    network_delete = rm('network')

    class droplet_list_no_cache:
        s = 'dl'

        def run(*a, **kw):
            DROPS.clear()
            kw['cache'] = False
            return Actions.droplet_list(*a, **kw)

    class droplet_list:
        s = 'd'

        @classmethod
        def run(cls, name=None, filtered=True, cache=True):
            if not cache and exists(fs.fn_drops_cache()):
                app.info('unlinking droplets cache', fn=fs.fn_drops_cache())
                os.unlink(fs.fn_drops_cache())

            def headers(all):

                return [
                    ['name', {'style': 'green'}],
                    ['ip', {'min_width': 15}],
                    fmt.key_typ,
                    fmt.key_curncy,
                    fmt.key_curncy_tot,
                    ['since', {'justify': 'right'}],
                    'tags',
                    'region',
                    'ip_priv',
                    'id',
                    'volumes',
                ]

            return list_simple(name, Prov().droplet, headers=headers, filtered=filtered)

        __call__ = run

    def ssh_key_list(name=None):
        h = ['name', 'fingerprint', 'id', 'since', fmt.key_ssh_pub_key]
        s = list_simple(name, Prov().ssh_keys, headers=h, lister='ssh_keys')
        return s

    def ssh():
        cmd, a = '', list(sys.argv)
        if '--' in a:
            p = a.index('--')
            cmd = ' '.join([f'{i}' for i in a[p + 1 :]])
            a = a[:p]
        # convenience: he ssh <name> or he ssh <nr in list>
        if FLG.name == Flags.name.d:
            FLG.name = a[-1]
        # we allow he ssh 2- -> goes up from the end:
        i = None
        if FLG.name[-1] == '-' and FLG.name[:-1].isdigit():
            i = -int(FLG.name[:-1]) - 1
        if FLG.name.isdigit():
            i = int(FLG.name) - 1
        if i is not None:
            ips = [Actions.droplet_list(name='*')['data'][i]['ip']]
        else:
            ips = [i['ip'] for i in Actions.droplet_list(name=FLG.name)['data']]
            if not ips:
                app.die('no name match')
        fs.make_temp_dir('ssh')
        [os.system(ssh() + f'root@{ip} {cmd}') for ip in ips]

    class droplet_create:
        class private_network:
            n = 'Name of private network to attach to. iprange flag determines subnet size.'
            t = ['default', 'own']
            d = 'default'

        class volume:
            n = 'Gigabytes of volume to create and attach to droplet(s)'
            d = 0

        def _pre(env, priv_net):
            """Main Thread here still.
            default network is always 10.0.0.1/8"""
            DROPS.clear()
            Actions.droplet_list.run(cache=False)

            id = FLG.ssh_keys
            if not id.isdigit():
                Actions.ssh_key_list(name='*')
                sn = FLG.ssh_keys
                id = [
                    int(i['id'])
                    for i in Prov().SSH_KEYS.values()
                    if not sn or i['name'] == sn
                ]
                if not id:
                    app.die('No ssh key')
            else:
                id = [int(id)]
            app.info('Setting ssh key ids', ids=id)
            FLG.ssh_keys = id

            Actions.network_list()
            netw_have = Prov().NETWORKS
            # we cannot delete existing networks here, want to run the create cmd many times, not creating existing servers:
            # means: Say own when you want a new one and give the cluster a unique name.
            # only then ip range is respected.
            if priv_net == 'own':
                ndn = env['cluster_name']
            else:
                ndn = Prov().network.default()   # on DO sth like "fra1-default"
            FLG.droplet_create_private_network = ndn
            # networkd is default
            if not ndn in netw_have:
                app.info('Creating network', name=ndn, range=FLG.ip_range)
                Actions.network_create.run(ndn, ip_range=FLG.ip_range)
                while not ndn in Prov().NETWORKS:
                    app.info(f'waiting for network: {ndn}')
                    Actions.network_list()
                    time.sleep(0.5)

            f = attr(Prov().droplet, 'prepare_create')
            if f:
                f(env)

        def run(
            name,
            image,
            region,
            size,
            tags,
            ssh_keys,
            private_network,
            volume,
            features,
        ):
            d = dict(locals())
            d['size'] = Prov().unalias_size(d['size'])
            name = d['name']
            Prov().assert_sane_name(name, True)
            droplet(name)   # assure up to date status
            # if not name == 'local': breakpoint()   # FIXME BREAKPOINT
            feats = Features.validate(d.pop('features'))
            d['tags'] = t = list(d['tags'])
            t.extend(feats)

            if name in DROPS or name == 'local':
                if not name == 'local':
                    app.warn(f'Droplet {name} exists already')
            else:
                D = Prov().droplet
                DROPS[name] = {'name': name}
                data = D.create_data(d)

                if volume:
                    V = Prov().Actions.volume_create(
                        name=name,
                        size=volume,
                    )
                    data['volumes'] = [V['data'][0]['id']]

                r = Api.req(D.endpoint, 'post', data=data)

            Actions.droplet_init(name=name, features=feats)
            # wait_for_ssh(name=name)

            # if not name == 'local':
            #     # withint init this will not show it, takes around 4,5 seconds until
            #     # in get result
            #     WOULD KILL WAITING for DROPS facts results elsewhere:
            #     return Actions.droplet_list_no_cache.run(name=name)

    class droplet_delete:
        """
        Deletes all matching droplets. --name must be given, "*" accepted.'
        Example: Delete all created within the last hour: "dd --since 1h -n '*'"
        """

        l = lambda *a, **kw: Prov().Actions.droplet_list_no_cache.run(*a, **kw)
        run = rm('droplet', lister=l)

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

        s = lambda l: reversed(sorted(l, key=lambda x: x[fmt.key_price_monthly]))
        return list_simple(name, Prov().sizes, headers=h, sorter=s)

    #
    # l = Prov().droplet.get_sizes(aliases=Prov().size_aliases_rev())
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
        return list_simple(name, Prov().image, headers=h)

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
        app.warn('no init features', logger=name)
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
        parts = find_my_feat_flow_parts(name, s)
        for part, nr in zip(parts, range(len(parts))):
            run_flow_part(f, name, part, f'{prefix}{nr}', local)


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


def normalize_script_start(s):
    # may start with shebang, may start with # part: .. - or not
    if s.startswith('#!'):
        # no shebang
        s = '\n' + s.split('\n', 1)[1]
    s = s.lstrip()
    if not s.startswith('# part:'):
        s = '# part: name\n' + s
    s = '\n' + s
    return s


def find_my_feat_flow_parts(name, script):
    """script the sum of all scripts - which we split now into parts, run consecutively
    The parts are built from at-hand information like name matching.
    Within the parts we have cond blocks, evalled later.
    """
    script = normalize_script_start(script)
    I = script.split('\n# part:')
    r = []
    empty_header = False
    for part in I:
        if not part.strip():
            continue
        cond, body = part.split('\n', 1)
        if not body.strip():
            if not r:
                empty_header = True
            continue
        cond = parse_cond(cond)
        if cond(state=ItemGetter(name=name)):
            r.append({'body': body})
    if len(r) > 1 and not empty_header:
        head = r.pop(0)
        for p in r:
            p['body'] = head['body'] + p['body']
    return r


def run_flow_part(feat, name, part, nr, local):
    # feat like 001:add_sudo_user
    # if not name == 'local': time.sleep(10000)
    assert len(feat.split(':')) == 2, f'Exected nr:feat, got {feat}'
    # if not name == 'local': time.sleep(1000000)
    marker = 'NEW FACT:'
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
    # if feat == '000:functions':
    #     fnt = 'functions.sh'
    # else:
    fnt = f'{feat}_{nr}.sh'
    fnt = f'{d_tmp}/{fnt}'
    DROP = drop(name)
    ip = DROP['ip']
    fntr = f'root@{ip}:/root/' + os.path.basename(fnt)
    fntres = f'{fnt}.res'
    local = name == 'local'
    where = 'locally' if local else 'remotely'
    app.info(f'Running script {nr} {where}', logger=name)
    write_file(fnt, script, chmod=0o755, mkdir=True)

    # print the rendered script content (if its not the tools (functions)):
    # if not 'functions' in feat:
    #     os.system(f'echo -e "\x1b[35m";cat "{fnt}"; echo -e "\x1b[0m"')
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
    # strip all ansi colors:
    cmd += f' | tee >(grep -e "{marker}" --color=never | sed -e \'s/\\x1B\\[[0-9;]*[JKmsu]//g\' > "{fntres}")'
    # if not local: cmd += ' &'
    # if name == 'local': breakpoint()   # FIXME BREAKPOINT
    if system(cmd):
        app.die('cmd failed')
    facts = {}

    # while not exists(fntres):
    #     print(name, 'wait fntres')
    #     time.sleep(0.5)

    def parse(res_line, name=name, facts=facts, marker=marker, drop=DROP):
        l = res_line.split(marker, 1)[1].strip().split(' ', 1)
        drop[l[0]] = l[1]
        facts[l[0]] = l[1]

    [parse(l) for l in read_file(f'{fntres}', dflt='').splitlines()]
    if facts:
        app.info(f'{name}: new facts', **facts)
    if 'ERR' in facts:
        app.die(facts['ERR'])
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
        pyc = pycond.pycond(clean_cond(line.split(':', 1)[1]))(state=ctx)
    return '\n'.join(r) + '\n'


def parse_cond(cond):
    cond = 'name' if not cond else cond
    cond = clean_cond(cond)
    try:
        return pycond.pycond(cond)
    except Exception as ex:
        app.die('cannot parse condition', cond=cond, exc=ex)


def clean_cond(s):
    # "==== name eq master ===" -> "name eq master"
    s = s.strip()
    if len(s) > 3 and s[0] == s[1] == s[2]:
        c = s[0]
        while s.startswith(c):
            s = s[1:]
        while s.endswith(c):
            s = s[:-1]
    return s.strip()


class ItemGetter(dict):
    # cond: env.selinux (pycond uses .get, not getitem) -> fwd to that:
    def get(self, k, dflt=None):
        if k in self:
            return super().get(k)
        return self.__getitem__(k, dflt)

    def __getitem__(self, k, dflt='', req=False):
        if k[0] == '!':
            req = True
            k = k[1:]
        k = k.replace('$', 'env.')
        l = k.rsplit('|', 1)
        r = self.g(l[0])
        if r in (None, '') and len(l) == 2:
            return l[1]
        if not r and req:
            app.die(f'Required: {k}')
        return r

    def g(self, k):
        if k in self:
            return self.get(k)
        tmout = 120
        if k.startswith('wait:'):
            _, tmout, k = k.split(':', 2)
        l = k.split('.')
        if l[0] == 'flag':
            return attr(FLG, l[1])
        if l[0] == 'secret':
            return cast(Api.secrets[l[1]])
        if l[0] == 'env':
            return cast(os.environ.get(l[1], ''))
        name = self.get('name')
        if l[0] in DROPS or l[0] == 'local' or l[0] == 'match:key' or l[0] == 'all':
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
                if any([n for n in env.names() if not DROPS.get(n, {}).get(k)]):
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


def assert_sane_name(name, create=False):
    s = name_allwd
    if not create:
        s = s.union(set('{}*?'))
    ok = not any([c for c in name if not c in s])
    if not ok or not name:
        app.die(
            'Require "name" with chars only from a-z, A-Z, 0-9, . and -',
            name=name,
        )


class kubectl:
    def add_namespace(self, ns):
        self(f'create namespace "{ns}"', on_err='report')

    def add_secret(self, name, ns, kv, on_exists='rm'):
        app.info('adding secret', name=name, keys=[i for i in kv])
        vals = ' '.join([f'--from-literal="{k}={v}"' for k, v in kv.items()])
        if self(f'--namespace {ns} create secret generic {name} {vals}', on_err='report'):
            assert on_exists == 'rm'
            app.warning('have to first remove existing secret', name=name)
            self(f'--namespace {ns} delete secret {name}')
            self(f'--namespace {ns} create secret generic {name} {vals}')

    def apply(self, fn, body=None):
        if not '://' in fn:
            if not fn[0] == '/':
                fn = os.environ['dir_project'] + '/' + fn
            if body:
                write_file(fn, body, mkdir=True)
        self(f'apply -f "{fn}"')

    def __call__(self, *args, on_err='die'):
        fn = FLG.kube_config
        if not exists(fn):
            app.die('No kubeconfig file', fn=fn)
        k = ' '.join([f'"{i}"' for i in args]) if len(args) > 1 else args[0]
        err = os.system(f'export KUBECONFIG="{fn}" && kubectl {k}')
        if err:
            if on_err == 'die':
                app.die('kubectl command failed', args=args)
            elif on_err == 'report':
                return err
            app.die(f'on_err handler not defined for failing kubectl', args=args)


class Provider:
    """Provider specific."""

    assert_sane_name = assert_sane_name
    size_aliases = lambda: ', '.join([f'{i}:{k}' for i, k in Prov().alias_sizes])
    unalias_size = lambda s: dict(Prov().alias_sizes).get(s, s)
    size_aliases_rev = lambda: {k: v for v, k in dict(Prov().alias_sizes).items()}
    list_resources = list_resources
    list_simple = list_simple
    resource_delete = resource_delete
    DROPS = DROPS
    NETWORKS = NETWORKS
    SSH_KEYS = SSH_KEYS
    kubectl = kubectl()   # obj only for call method, was a function before


prov = [0]   # set by the specific one, a derivation of Provider


def Prov(init=None):
    if init:
        prov[0] = init
    return prov[0]


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
#     wf = g(Workflows, name)
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
# wf = g(Workflows, action, 0)
# if not wf:
#     return
# attrs = lambda c: [i for i in dir(c) if i[0] not in ['_', 'd', 'n'] and i != 'run']
# kw = {}
# for a in attrs(wf):
#     v = g(FLG, action + '_' + a, None)
#     if v is not None:
#         kw[a] = v
# return partial(wf.run, **kw)
