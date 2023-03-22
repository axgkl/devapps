from devapp.tools import read_file, write_file, os, sys, json, exists
import time
from devapp.app import app, FLG
import threading
from devapp.tools.infra import (
    Api,
    DIE,
    DROPS,
    Playbooks,
    Prov,
    attr,
    configure_playbooks,
    env,
    fmt,
    fs,
    list_simple,
    paral,
    rm,
    ssh,
    vol_sizes,
    wait,
)
from devapp.tools.flag import build_action_flags, set_action_func_param_values
from devapp.tools.times import times


def droplet(name):
    return Actions.droplet_list(name=name)


class Flags:
    _cli_action = None
    autoshort = ''

    class match:
        n = 'Further Filter, applied to any value for name-matching droplets, e.g. region. Embedded within *<value>*'
        d = ''

    class since:
        n = 'A global filter applied to any list operation. E.g. "1h" filters out all droplets created longer ago than one hour'
        d = ''

    class tags:
        n = 'Set tags when creating or use as filter for list / delete'
        d = []

    class ssh_keys:
        n = 'Must be present on Infra Provider. Can be ssh key id or name (slower then, add. API call, to find id). If not set we add all present ones.'
        d = []

    class playbooks_dir:
        s = 'fdir'
        n = 'Custom feature catalog directory, in addition to built in one'

    class force:
        n = 'No questions asked, e.g. when deleting'
        d = False

    class range:
        n = 'Placeholder "{}" in name will be replaced with these.'
        d = []

    # class domain: d = ''
    class kube_config:
        n = 'Filename of kubeconfig to use (for Actions where relevant)'
        d = os.environ.get('KUBECONFIG', '')

    def _pre_init(Flags, Actions):
        build_action_flags(Flags, Actions)
        # adjust short names, we want droplet to get 'd'
        # A = Flags.Actions
        # for F in 'domain', 'database', 'dns':
        #     for d in 'list', 'create', 'delete':
        #         c = attr(A, f'{F}_{d}', 0)
        #         if c:
        #             c.s = F[:2] + d[0]


class Actions:
    class _cli:
        """required by build_action_flags (shortcuts, defaults, names)"""

        droplet_list = 'd'
        droplet_list_no_cache = 'dl'
        filtered = 'filt'

        def name(action=None, **kw):
            if 'create' in action:
                return 'n', '[required]', 'name of new instance'
            return 'n', '', '* accepted'

        nodes = 'no'

        ip_range = (
            'ipr',
            '10.140.10.0/24',
            'When creating networks or droplets with own networks. Given range will be configured as subnet within a 10/8 network.',
        )
        playbooks = (
            'pb',
            [],
            'Have:\n%s.\nFilename accepted. Numbers only allowed.' % Playbooks.show(),
        )
        private_network = (
            'pn',
            ('default', ['default', 'own']),
            'Name of private network to attach to. iprange flag determines subnet size.',
        )

        def size(action=None, **_):
            if action != 'volume_create':
                p = Prov().size_aliases()
            else:
                p = Prov().vol_size_aliases() + ' GB'
            return 'S', 'XXS', p

        ssh_enter = 'ssh'
        type = 'typ', '', 'type of resource'
        user = (
            'u',
            os.environ['USER'],
            'Username to create additionally to root at create (with sudo perms)',
        )

    def _pre(A):
        r = read_file(fs.fn_drops_cache(), dflt='')
        if r:
            DROPS.update(json.loads(r))
        if app.selected_action:
            fs.make_temp_dir(app.selected_action)
            app.info('Selected action: ' + app.selected_action)
        # require_tools('kubectl')
        if FLG.range and not '{}' in FLG.name:
            _ = 'Range given but no placeholder "{}" in name - assuming "%s-{}"'
            app.info(_ % FLG.name)
            FLG.name += '-{}'
        E = env.set_base_environ_vars()

        D = FLG.playbooks_dir
        if D:
            FLG.playbooks_dir = os.path.abspath(D)
        app.out_formatter = fmt.printer
        Api.set_secrets()
        return set_action_func_param_values(A, app, FLG)

    def cluster_delete(A, name='*'):
        if not '*' in name:
            name += '*'
        for k in 'droplet', 'volume', 'placement_group', 'network', 'load_balancer':
            f = rm(k, name, skip_non_exists=True)
            f()

    def playbooks_list(A, playbooks):
        """Query feature descriptions (given with -f or all).
        --list_playbooks -m <match>
        --list_playbooks k3s (ident to --feature=k3s)
        """

        md = []

        plays = playbooks or Playbooks.all()
        plays = Playbooks.validate(plays)
        match = FLG.match
        for f, t, feat in sorted(Playbooks.fns(plays)):
            c = read_file(feat)
            if match and not match in c:
                continue
            descr, body = Playbooks.parse_description_doc_str(c)
            b = f'```bash\n{body}\n```\n'
            md.append(f'# {t} ({f})\n{feat}\n{b}\n\n{descr}---- \n')
        fmt.mdout(md)

    def billing(A):
        return Api.get('customers/my/balance')

    def billing_pdf(A, uuid):
        """download invoice as pdf. billing_list action gives the uuid"""
        r = Api.get(f'customers/my/invoices/{uuid}/pdf', plain=True)
        fn = 'digital_ocean_invoice.pdf'
        write_file(fn, r.content, mode='wb')
        return f'created {fn}'

    def billing_list(A):
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

    def load_balancer_list(A, name='*'):

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

    def load_balancer_delete(A, name='*'):
        rm('load_balancer', name)()

    def volume_list(A, name='*'):
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
        A,
        name,
        tags,
        region,
        size='XXS',
        _attach_to=None,
    ):
        if name == 'local':
            return
        tags = tags or FLG.tags
        size = vol_sizes.get(size, size)
        size = int(size)
        if size < 5 or size > 1000000:
            app.die('Invalid size', size=size)
        d = dict(locals())
        d.pop('A')
        Prov().assert_sane_name(d['name'], True)
        d['tags'] = t = list(d['tags'])
        data = Prov().volume.create_data(d)
        Api.req(Prov().volume.endpoint, 'post', data=data)
        return A.volume_list(name=name)

    # volume_delete = rm('volume')
    def volume_delete(A, name='*'):
        rm('volume', name)()

    def network_list(A, name='*'):
        headers = [
            'name',
            fmt.key_droplets,
            'iprange',
            'since',
            'tags',
            'net',
            'id',
        ]
        ns = list_simple(name, Prov().network, headers=headers)
        return ns

    def network_create(A, name, ip_range, tags=[]):
        d = dict(locals())
        Prov().assert_sane_name(name, True)
        data = Prov().network.create_data(d)
        Api.req(Prov().network.endpoint, 'post', data=data)
        return A.network_list(name=name)

    # network_delete = rm('network')
    def network_delete(A, name='*'):
        rm('network', name)()

    def droplet_list_no_cache(A, name='*'):
        DROPS.clear()
        return A.droplet_list(name, cache=False)

    def droplet_list(A, name='*', filtered=True, cache=True):
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

    def ssh_key_list(A, name='*'):
        h = ['name', 'fingerprint', 'id', 'since', fmt.key_ssh_pub_key]
        s = list_simple(name, Prov().ssh_keys, headers=h, lister='ssh_keys')
        return s

    def ssh_enter(A, name=''):
        cmd, a = '', list(sys.argv)
        if '--' in a:
            p = a.index('--')
            cmd = ' '.join([f'{i}' for i in a[p + 1:]])
            a = a[:p]
        # convenience: he ssh <name> or he ssh <nr in list>
        if not name:
            name = a[-1]
        # we allow he ssh 2- -> goes up from the end:
        i = None
        if name[-1] == '-' and name[:-1].isdigit():
            i = -int(name[:-1]) - 1
        if name.isdigit():
            i = int(name) - 1
        if i is not None:
            ips = [A.droplet_list(name='*')['data'][i]['ip']]
        else:
            ips = [i['ip'] for i in A.droplet_list(name=name)['data']]
            if not ips:
                app.die('no name match')
        [os.system(ssh() + f'root@{ip} {cmd}') for ip in ips]

    def ssh_key_ids(A, ssh_keys):
        if not ssh_keys:
            ssh_keys = [i['id'] for i in A.ssh_key_list()['data']]
        if any([i for i in ssh_keys if not isinstance(int(i), int)]):
            A.ssh_key_list(name='*')
            sn = ssh_keys
            ssh_keys = [
                int(i['id'])
                for i in Prov().SSH_KEYS.values()
                if not sn or i['name'] == sn
            ]
            if not ssh_keys:
                app.die('No ssh key')
        else:
            ssh_keys = [int(i) for i in ssh_keys]
        return ssh_keys

    def droplet_create(
        A,
        name,
        region,
        image,
        ssh_keys,
        tags,
        user,
        private_network,
        ip_range,
        playbooks,
        size='XXS',
        _multi=False,
        **kw,
    ):
        """Creates server instances. private_network name and ssh keys must be present"""
        if not _multi:
            A.droplet_list(name='*', cache=not _multi)
            private_network = get_network(A, private_network, ip_range)

        plays = Playbooks.validate(playbooks)
        if plays and name == 'local':
            return A.droplet_init(name=name, playbooks=plays)

        P = Prov()
        ssh_keys = A.ssh_key_ids(ssh_keys)
        size = P.unalias_size(size)
        P.assert_sane_name(name, True)
        if not name in DROPS:
            d = dict(locals())
            D = P.droplet
            DROPS[name] = {'name': name}
            data = D.create_data(d)
            if not name == 'local':
                r = Api.req(D.endpoint, 'post', data=data)
        else:
            app.warn(f'Droplet {name} exists already')

        if user:
            DROPS[name]['user'] = user
        if plays:
            A.droplet_init(name=name, playbooks=plays)
        if _multi:
            return
        return A.droplet_list()

    def cluster_create(
        A,
        name,
        region,
        image,
        ssh_keys,
        tags,
        private_network,
        ip_range,
        playbooks,
        function_filter,
        user,
        nodes=['master'],
    ):
        os.environ['cluster_name'] = name
        os.environ['function_filter'] = function_filter
        ssh_keys = A.ssh_key_ids(ssh_keys)
        private_network = get_network(A, private_network, ip_range)
        os.environ['network_name'] = private_network
        kw = dict(locals())
        [kw.pop(i) for i in ['A']]
        DROPS.clear()
        A.droplet_list(name='*', cache=True)
        P = Prov()
        P.assert_sane_name(name, True)
        [P.assert_sane_name(i, True) for i in nodes]
        threads = []
        names = [f'{name}-{n}' for n in nodes]
        # names.insert(0, 'local')  # for local tasks
        # plays = Features.validate(playbooks)
        os.environ['names'] = ' '.join(names)
        names.insert(0, 'local')
        f = A.droplet_create
        for n in names:
            k = dict(kw)
            k['name'] = n
            k['_multi'] = True
            app.info('Background', **k)
            _ = threading.Thread
            __ = paral.in_thread_func_wrap
            threads.append(_(target=__, args=(f,), kwargs=k, daemon=False))
            threads[-1].start()

        while any([d for d in threads if d.isAlive()]) and not DIE:
            time.sleep(0.5)
        # A.droplet_init(name='local', playbooks=plays)

    def droplet_delete(A, name='*', force=False):
        """
        Deletes all matching droplets. --name must be given, "*" accepted.'
        Example: Delete all created within the last hour: "dd --since 1h -n '*'"
        """
        A.droplet_list_no_cache(name)   # update
        rm('droplet', name)()

    def sizes_list(A, name='*'):
        h = [
            [fmt.key_size_alias, {'justify': 'center'}],
            'name',
            [fmt.key_price_monthly, {'justify': 'right', 'style': 'red'}],
            ['CPU', {'justify': 'right'}],
            [fmt.key_ram, {'justify': 'right'}],
            [fmt.key_disk_size, {'justify': 'right'}],
            ['Descr', {'style': 'cyan'}],
        ]

        def s(l):
            return reversed(sorted(l, key=lambda x: x[fmt.key_price_monthly]))

        return list_simple(name, Prov().sizes, headers=h, sorter=s)

    def images_list(A, name='*'):
        h = ['name', 'description', fmt.key_disk_size, 'since', 'id', 'rapid']
        return list_simple(name, Prov().image, headers=h)

    def list(
        A,
    ):
        dr = A.droplet_list()
        fmt.printer(dr)
        # da = Actions.database_list()
        # if da['data']:
        #     fmt.printer(da)
        da = A.load_balancer_list()
        if da['data']:
            fmt.printer(da)
        return
        a = A.billing()
        app.info('month to date usage', amount=a['month_to_date_usage'])

    def droplet_init(A, name, playbooks):
        # if not 'local' in name: return
        configure_playbooks(name, playbooks)
        app.info('initted', logger=name)


def get_network(A, name, ip_range):
    A.network_list()
    netw_have = Prov().NETWORKS

    # we cannot delete existing networks here, want to run the create cmd many times, not creating existing servers:
    # means: Say own when you want a new one and give the cluster a unique name.
    # only then ip range is respected.
    if name == 'own':
        name = env['cluster_name']
    else:
        name = Prov().network.default()  # on DO sth like "fra1-default"

    if not name in netw_have:
        A.network_create(name, ip_range)
        # def for_(why, waiter, tmout=60, dt=3):

        def f():
            return A.network_list() and name in Prov().NETWORKS

        wait.for_(f'network {name}', f, 40, 1)
        # while not name in Prov().NETWORKS:
        #     app.info(f'waiting for network: {name}', ip_range=ip_range)
        #     A.network_list()
        #     time.sleep(0.5)
        # app.info(f'Have network {name}')
    return name


# adding @classmethod to everybody. At least my lsp can still resolve methods
def conv2classmethods(Actions):
    for k in dir(Actions):
        if not k[0] == '_' or k in {'_pre', '_post'}:
            f = getattr(Actions, k)
            if callable(f):
                setattr(Actions, k, classmethod(f))
                setattr(Actions, k, classmethod(f))
