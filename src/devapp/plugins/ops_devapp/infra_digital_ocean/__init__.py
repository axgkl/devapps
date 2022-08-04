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


class Flags(Flags):
    class Actions(Flags.Actions):   # for -h output (then def.ed in this mod)
        class database_list:
            s = 'dal'

        class database_delete:
            s = 'dad'


class Actions(Actions):
    # only at DO:
    def database_list(name=None):
        return prov[0].list_simple(name, prov[0].database)

    @classmethod
    def database_delete(A):
        return prov[0].resource_delete(
            prov[0].database, A.database_list, FLG.force
        )


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


fmt_region = lambda key, d, into: setitem(into, key, d[key]['slug'])
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

    def rm_junk(api_response):
        try:
            [i['region'].pop('sizes') for i in api_response]
        except:
            pass

    class volume:
        # fmt:off
        endpoint = 'volumes'
        normalize = [
            ['created_at'      , fmt.to_since           ] ,
            ['filesystem_type' , 'format'               ] ,
            ['droplet_ids'     , fmt.droplet_id_to_name ] ,
            ['size_gigabytes'  , fmt.key_disk_size      ] ,
            ['region'          , fmt_region             ] ,
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
            ['created_at'     , fmt.to_since      ] ,
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
            ['created_at' , fmt.to_since ] ,
            ['region'     , fmt_region   ] ,
            ['volume_ids' , fmt.volumes  ] ,
            ['tags'       , fmt_tags     ] ,
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

        normalize = [
            ['created_at', fmt.to_since           ] ,
            ['description','tags'                 ] ,
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
            ['created_at'     , fmt.to_since      ] ,
            ['tags'           , fmt_tags          ] ,
            ['num_nodes'      , 'nodes'           ] ,
        ]
        # fmt:on
        # prices not derivable. expensive (2 * price of droplet)
        headers = [
            'name',
            'region',
            'since',
            'tags',
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
