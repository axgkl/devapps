#!/usr/bin/env python
"""
# Digital Ocean Infrastructure Tool

## Purpose
Low level Operations on the DO Cloud, using their REST API
E.g. when terraform destroy fails, you can delete droplets using this.

## Caution

Most playbooks are tested against a Fedora host filesystem (the default image)

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
https://docs.digitalocean.com/reference/api/api-reference/
"""


from devapp.app import run_app, FLG, app
from devapp.tools.infra import Actions, Flags, Provider, Prov, fmt, rm, Api
from operator import setitem

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))


class Actions(Actions):

    # only at DO:

    database_list = lambda name=None: Prov().list_simple(name, Prov().database)
    database_delete = rm('database')
    domain_list = lambda name=None: Prov().list_simple(name, Prov().domain)
    domain_delete = rm('domain', pth=lambda d: f'domains/{d["name"]}')

    def domain_create(name=None):
        name = name or FLG.name
        Prov().assert_sane_name(name)
        if not name:
            app.die('Provide domain')
        data = {'name': name}
        Api.req('domains', 'post', data=data)
        return Actions.domain_list(name=name)

    def dns_list(name=None):
        return Prov().list_simple(name, Prov().dns, lister=Prov().dns.records)

    class dns_create:
        class ips:
            s = 'ips'
            n = 'Adds A record. Set flag name to intended zone (domain must be present) and give a list of ips'
            d = []

        class ttl:
            s = 'ttl'
            d = 120

        def run(name=None, ips=None, ttl=None):
            """we do it all here"""
            name = FLG.name = name or FLG.name
            Prov().assert_sane_name(name, True)
            ips = ips or FLG.dns_create_ips
            ttl = ttl or FLG.dns_create_ttl
            have = Actions.domain_list(name='*')
            dom_name = 'axlc.net.'
            if 1:
                recs = [i for i in have['data'] if name.endswith(i['name'])]
                if len(recs) != 1:
                    app.die('No matching domain', name=name, have=have['data'])
                dom_name = recs[0]['name']
            for ip in ips:
                d = dict(name=name.split(dom_name)[0][:-1], ttl=ttl, type='A', data=ip)
                _ = Api.post(f'domains/{dom_name}/records', data=d)
            return Actions.dns_list(name=name)

    def dns_delete(name=None):
        name = FLG.name = name or FLG.name
        Prov().assert_sane_name(name, False)
        return Prov().resource_delete(Prov().dns)


class Flags(Flags):
    class do_api_token:
        d = 'cmd:pass show DO/pat'


Flags._pre_init(Flags, Actions)
Flags.region.d = 'fra1'


def fmt_ips(_, d, into):
    for k, t in ['ip', 'public'], ['ip_priv', 'private']:
        try:
            into[k] = [i['ip_address'] for i in d['networks']['v4'] if i['type'] == t][0]
        except Exception:
            pass


def fmt_price(_, d, into):
    into[fmt.key_typ] = fmt.typ(d['vcpus'], int(d['memory'] / 1024), d['disk'])
    into[fmt.key_curncy] = round(float(d['size']['price_monthly']), 1)
    fmt.price_total(_, d, into, d['size']['price_hourly'])


def fmt_drops_in_vpc(_, d, into):
    ds = Prov().DROPS.values()
    d['droplet_ids'] = [i['id'] for i in ds if i.get('vpc_uuid') == d['id']]
    fmt.droplet_id_to_name('droplet_ids', d, into)


def fmt_region(key, d, into):
    v = d[key]
    v = v['slug'] if 'slug' in v else v
    setitem(into, key, v)


fmt_tags = lambda key, d, into: setitem(into, 'tags', ' '.join(d[key]))


class DProv(Provider):
    name = 'DigitalOcean'
    base_url = 'https://api.digitalocean.com/v2'
    Actions = Actions
    secrets = 'do_api_token'
    conv_ram_to_gb = lambda x: int(x / 1024)
    # https://docs.digitalocean.com/products/volumes/details/pricing/
    vol_price_gig_month = 0.1

    # fmt:off
    alias_sizes = [
        ['XXS'      , 's-1vcpu-1gb'   ],
        ['XS'       , 's-1vcpu-2gb'   ],
        ['S'        , 's-2vcpu-4gb'   ],
        ['M'        , 's-8vcpu-16gb'  ],
        ['L'        , 'c2-16vcpu-32gb'],
        ['XL'       , 'c2-32vcpu-64gb'],
    ]
    # fmt:on

    def normalize_pre(d, r, cls, headers):
        if 'created_at' in d:
            fmt.to_since('created_at', d, r)
        if 'region' in d:
            fmt_region('region', d, r)
        if 'tags' in d:
            fmt_tags('tags', d, r)
        for k in 'droplet_ids', 'droplet_id':
            if k in d:
                fmt.droplet_id_to_name(k, d, r)

    def rm_junk(api_response):
        try:
            [i['region'].pop('sizes') for i in api_response]
        except Exception:
            pass

    class droplet:
        endpoint = 'droplets'
        # fmt:off
        normalize = [ 
            ['volume_ids' , fmt.volumes  ] ,
            ['networks'   , fmt_ips      ] ,
            ['size'       , fmt_price    ] ,
        ]
        # fmt:on

        def create_data(d):
            return dict(d)

    class image:
        # fmt:off
        endpoint = 'images'
        normalize = [
            ['slug'           , 'name'            ] ,
            ['size_gigabytes' , fmt.key_disk_size ] ,
            ['rapid_deploy'   , 'rapid'           ] ,
        ]
        # fmt:on

    class load_balancer:
        # fmt:off
        endpoint = 'load_balancers'
        # fmt:on

    class network:
        # fmt:off
        endpoint = 'vpcs'
        default = lambda: 'default-' + FLG.region
        normalize = [
            ['description',fmt.key_tags           ] ,
            ['ip_range' , fmt.key_ip_range        ] ,
            ['id'       , fmt_drops_in_vpc        ] ,
        ]
        # fmt:on
        def create_data(d):
            breakpoint()   # FIXME BREAKPOINT
            return d

    class ssh_keys:
        endpoint = 'account/keys'
        normalize = [['public_key', fmt.ssh_pub_key]]

    class sizes:
        # fmt:off
        endpoint = 'sizes?per_page=100'
        normalize = [
            ['slug'          , fmt.size_name_and_alias ] ,
            ['price_monthly' , fmt.price_monthly       ] ,
            ['vcpus'         , 'CPU'                   ] ,
            ['memory'        , fmt.to_ram              ] ,
            ['disk'          , fmt.key_disk_size       ] ,
            ['description'   , 'Descr'                 ] ,
        ]
        # fmt:on

        def create_data(d):
            d['private_networking'] = True
            return d

    class volume:
        # fmt:off
        endpoint = 'volumes'
        normalize = [
            ['filesystem_type' , 'format'               ] ,
            ['size_gigabytes'  , fmt.key_disk_size      ] ,
            ['id'              , fmt.vol_price          ] ,
        ]
        # fmt:on

    class database:
        # fmt:off
        endpoint = 'databases'
        normalize = [
            ['num_nodes'      , 'nodes'           ] ,
        ]
        # fmt:on
        # prices not derivable. expensive (2 * price of droplet)
        headers = [
            'name',
            'since',
            'size',
            'nodes',
            'engine',
            'id',
        ]

    class domain:
        endpoint = 'domains'
        headers = ['name', 'id', 'ttl', 'zone_file']

    class dns:
        headers = ['name', 'ips', 'ttl', 'id']

        def prepare_delete(d):
            for id in d['ids']:
                Api.delete(f'domains/{d["domain"]}/records/{id}', {})
            return fmt.flag_deleted

        def records():
            ds = [d['name'] for d in Prov().Actions.domain_list(name='*')['data']]
            ds.append('axlc.net')

            def n(rs, d):
                by_host = {}
                for r in rs:
                    if not r['type'] == 'A':
                        continue
                    r['domain'] = d
                    by_host.setdefault(r['name'], []).append(r)

                def combine_ips(h):
                    # we loose ttl per ip, taking the first one:
                    d = dict(h[0])
                    d['ips'] = [i['data'] for i in h]
                    d['ids'] = [i['id'] for i in h]
                    d['name'] = d['name'] + '.' + d['domain']
                    return d

                return [combine_ips(h) for h in by_host.values()]

            r = []
            [
                r.extend(n(Api.get(f'domains/{d}/records')['domain_records'], d))
                for d in ds
            ]
            return r


Prov(init=DProv)
Flags.size.n = 'aliases ' + DProv.size_aliases()
main = lambda: run_app(Actions, flags=Flags)

if __name__ == '__main__':
    main()
