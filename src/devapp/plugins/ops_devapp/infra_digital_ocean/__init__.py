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
https://docs.digitalocean.com/reference/api/api-reference/
"""


from devapp.app import run_app, FLG
from devapp.tools.infra import Actions, Flags, Provider, Api, prov, fmt
from devapp.tools.times import times
from operator import setitem

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))


class Actions(Actions):
    # only at DO:
    def database_list(name=None):
        return prov[0].list_simple(name, prov[0].database)

    @classmethod
    def database_delete(A):
        return prov[0].resource_delete(
            prov[0].database, A.database_list, FLG.force
        )


Flags._pre_init(Flags, Actions)
Flags.token_cmd.d = 'pass show DO/pat'
Flags.region.d = 'fra1'


def fmt_ips(_, d, into):
    for k, t in ['ip', 'public'], ['ip_priv', 'private']:
        try:
            into[k] = [
                i['ip_address'] for i in d['networks']['v4'] if i['type'] == t
            ][0]
        except:
            pass


def fmt_price(_, d, into):
    into[fmt.key_typ] = fmt.typ(d['vcpus'], int(d['memory'] / 1024), d['disk'])
    into[fmt.key_curncy] = round(float(d['size']['price_monthly']), 1)
    fmt.price_total(_, d, into, d['size']['price_hourly'])


def fmt_drops_in_vpc(_, d, into):
    ds = Prov.DROPS.values()
    d['droplet_ids'] = [i['id'] for i in ds if i.get('vpc_uuid') == d['id']]
    fmt.droplet_id_to_name('droplet_ids', d, into)


def fmt_region(key, d, into):
    v = d[key]
    v = v['slug'] if 'slug' in v else v
    setitem(into, key, v)


fmt_tags = lambda key, d, into: setitem(into, 'tags', ' '.join(d[key]))


class Prov(Provider):
    name = 'DigitalOcean'
    base_url = 'https://api.digitalocean.com/v2'
    Actions = Actions
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

    def normalize_post(d, r, cls, headers):
        if 'created_at' in d:
            fmt.to_since('created_at', d, r)
        if 'region' in d:
            fmt_region('', d, r)
        if 'tags' in d:
            fmt_tags('tags', d, r)
        for k in 'droplet_ids', 'droplet_id':
            if k in d:
                fmt.droplet_id_to_name(k, d, r)
        return r

    def rm_junk(api_response):
        try:
            [i['region'].pop('sizes') for i in api_response]
        except:
            pass

    class load_balancer:
        # fmt:off
        endpoint = 'load_balancers'
        # fmt:on

    class volume:
        # fmt:off
        endpoint = 'volumes'
        normalize = [
            ['filesystem_type' , 'format'               ] ,
            ['size_gigabytes'  , fmt.key_disk_size      ] ,
            ['id'              , fmt.vol_price          ] ,
        ]
        # fmt:on

    class ssh_keys:
        endpoint = 'account/keys'
        normalize = [['public_key', fmt.ssh_pub_key]]

    class image:
        # fmt:off
        endpoint = 'images'
        normalize = [
            ['slug'           , 'name'            ] ,
            ['size_gigabytes' , fmt.key_disk_size ] ,
            ['rapid_deploy'   , 'rapid'           ] ,
        ]
        # fmt:on

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
            d['private_networking'] = True
            return d

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


prov[0] = Prov
Flags.size.n = 'aliases ' + Prov.size_aliases()
main = lambda: run_app(Actions, flags=Flags)

if __name__ == '__main__':
    main()
