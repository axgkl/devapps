#!/usr/bin/env python
"""
# Hetzner Infrastructure Tool

https://www.hetzner.com/cloud/#pricing

## Purpose
Low level Operations on the DO Cloud, using their REST API
E.g. when terraform destroy fails, you can delete droplets using this.

## Caution

Most features are tested against a Fedora host filesystem (the default image)

## Requirements
- API Token

## Examples:

### Listing
- ops ihc
- ops ihc --since 10h
- ops ihc -m "*foo*"

### Creation
- ops ihc dc -n mydroplet                             # create a minimal droplet
- ops ihc dc -n mydroplet -sac -f k3s -s m-2vcpu-16gb # create a droplet with this size, name foo, with k3s feature

### Deletion
- ops ihc dd --since 1h # delete all created within the last hour (-f skips confirm)

## Misc

See Actions at -h
"""


from devapp.app import run_app, FLG, app
from devapp.tools.infra import Actions, Flags, Provider, Api, prov, fmt
from devapp.tools.times import times
from operator import setitem

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))


class Flags(Flags):
    class Actions(Flags.Actions):   # for -h output (then def.ed in this mod)
        pass


class Actions(Actions):
    pass


Flags.token_cmd.d = 'pass show HCloud/token'
Flags.region.d = 'hel1'
Flags.image.d = 'fedora-36'


def monthly(server_type, region, which='monthly'):
    s = server_type
    p = [l for l in s['prices'] if l['location'] == region]
    if not p:
        app.info(
            'Not available in region',
            name=s['name'],
            region=FLG.region,
        )
        return -1
    return round(float(p[0][f'price_{which}']['gross']), 2)


def fmt_region(key, d, into):
    l = d[key]['location'] if key == 'datacenter' else d[key]
    into['region'] = l['name']


fmt_tags = lambda key, d, into: setitem(
    into, 'tags', [f'{k}:{v}' for k, v in d['labels'].items()]
)
fmt_ip_ranges = lambda key, d, into: setitem(
    into, 'iprange', [i['ip_range'] for i in d[key]]
)


def fmt_ips(key, d, into):
    r = into
    try:
        r['ip_priv'] = d['private_net'][0]['ip']
    except:
        pass
    for k, t in (['ip', 'public_net'],):
        try:
            r[k] = d[t]['ipv4']['ip']
        except:
            pass


def fmt_price(key, d, into):
    if key == 'prices':
        into[fmt.key_price_monthly] = monthly(d, FLG.region)   # size list
    else:
        st = d['server_type']
        into[fmt.key_typ] = fmt.typ(st['cores'], int(st['memory']), st['disk'])
        reg = d['datacenter']['location']['name']   # droplet
        into[fmt.key_curncy] = monthly(st, reg)
        fmt.price_total(key, d, into, monthly(st, reg, 'hourly'))


class Prov(Provider):
    name = 'Hetzner'
    base_url = 'https://api.hetzner.cloud/v1'
    vol_price_gig_month = 0.0476   # https://www.hetzner.com/cloud/#pricing
    Actions = Actions

    # fmt:off
    alias_sizes = [
        ['XXS'      , 'cpx11'         ],
        ['XS'       , 'cx31'          ],
        ['S'        , 'ccx12'         ],
        ['M'        , 'ccx32'         ],
        ['L'        , 'ccx52'         ],
        ['XL'       , 'ccx62'         ],
    ]
    # fmt:on

    def rm_junk(api_response):
        try:
            [i['datacenter'].pop('server_types') for i in api_response]
        except:
            pass

    class volume:
        # fmt:off
        endpoint = 'volumes'
        normalize = [
            ['created'  , fmt.to_since           ] ,
            ['location' , fmt_region             ] ,
            ['server'   , fmt.droplet_id_to_name ] ,
            ['size'     , fmt.key_disk_size      ] ,
            ['id'       , fmt.vol_price          ] ,
        ]
        # fmt:on

        def create_data(d):
            r = dict(d)
            r['location'] = r.pop('region')
            t = r.pop('tags')
            return r

    class ssh_keys:
        endpoint = 'ssh_keys'
        normalize = [['public_key', fmt.ssh_pub_key]]

    class image:
        # fmt:off
        endpoint = 'images'
        normalize = [
            ['created'      , fmt.to_since      ] ,
            ['disk_size'    , fmt.key_disk_size ] ,
            ['rapid_deploy' , 'rapid'           ] ,
        ]
        # fmt:on

    class sizes:
        # fmt:off
        endpoint = 'server_types?per_page=100'
        normalize = [
            ['name'        , fmt.size_name_and_alias ] ,
            ['prices'      , fmt_price               ] ,
            ['cores'       , 'CPU'                   ] ,
            ['memory'      , fmt.to_ram              ] ,
            ['disk'        , fmt.key_disk_size       ] ,
            ['description' , 'Descr'                 ] ,
        ]
        # fmt:on

    class droplet:
        # fmt:off
        endpoint = 'servers'

        normalize = [
            ['created'     , fmt.to_since ] ,
            ['datacenter'  , fmt_region   ] ,
            ['volumes'     , fmt.volumes  ] ,
            ['tags'        , fmt_tags     ] ,
            ['id'          , fmt_ips      ] ,
            ['server_type' , fmt_price    ] ,
        ]
        # fmt:on

        def create_data(d):
            r = dict(d)
            r['automount'] = False
            r['location'] = r.pop('region')
            r.pop('private_networking')
            t = r.pop('tags')
            if t:
                r['labels'] = {'feats': ','.join(t)}
            r['server_type'] = r.pop('size')
            return r

    class network:
        # fmt:off
        endpoint = 'networks'
        normalize = [
            ['created'  , fmt.to_since            ] ,
            ['tags'     , fmt_tags                ] ,
            ['servers'  , fmt.droplet_id_to_name  ] ,
            ['subnets'  , fmt_ip_ranges           ] ,
        ]
        # fmt:on

        def create_data(d):
            return d


prov[0] = Prov
Flags.size.n = 'aliases ' + Prov.size_aliases()
main = lambda: run_app(Actions, flags=Flags)

if __name__ == '__main__':
    main()
