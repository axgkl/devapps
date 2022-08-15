#!/usr/bin/env python
"""
# AWS Infra Mgmt

Currently only route53

## Examples

Wiith "dev-xyz.mydomain.com" present at AWS:

dns_create -n myhost.k3s.dev-xyz.mydomain.com -ips=1.2.3.4,1.1.1.1
dns_delete -n myhost.k3s.dev-xyz.mydomain.com
"""

import os
from devapp.app import run_app, FLG, app
from devapp.tools.infra import Actions, Flags, Provider, Api, Prov, fmt, rm
import time
import hmac, hashlib, requests, base64
from operator import setitem

# Droplet list results are cached in tmp/droplets.json. We will read from here if recent.'
# droplet_list_cache_max_age = int(os.environ.get('droplet_list_cache_max_age', 3))


# only route53 action supported, remove all others:
rma = lambda key, f: delattr(Actions, key) if callable(f) else 0
[rma(d, getattr(Actions, d)) for d in dir(Actions) if not d[0] == '_']


def dotted(name, create=True):
    name = name or FLG.name
    if not name.endswith('.'):
        name += '.'
    FLG.name = name
    Prov().assert_sane_name(name, create)
    return name


class Actions(Actions):
    def dns_list(name=None):
        return Prov().list_simple(name, Prov().dns, lister=get_zones)

    def domain_list(name=None):
        return Prov().list_simple(name, Prov().domain, lister=get_domains)

    list = dns_list

    class dns_create:
        class ips:
            s = 'ips'
            n = 'Adds A record. Set flag name to intended zone (domain must be present) and give a list of ips'
            d = []

        class ttl:
            s = 'ttl'
            d = 120

        class rm:
            s = 'rm'
            n = 'delete any existing zone before creation'
            d = False

        def run(name=None, ips=None, ttl=None):
            """we do it all here"""
            name = dotted(name)
            # we allow (and filter) empty start or end comma, simplifies bash scripts a lot in loops:
            ips = [i for i in ips or FLG.dns_create_ips if i]
            ttl = ttl or FLG.dns_create_ttl
            rm = FLG.dns_create_rm
            have = Actions.dns_list(name='*')['data']
            id = [i for i in have if name.endswith(i['domain'])]
            if id:
                if rm:
                    r = [i for i in have if i['name'] == name]
                    if r:
                        Actions.dns_delete(name=name, force=True)
                id = id[0]['zoneid']
            else:
                have = Actions.domain_list(name='*')
                id = [i for i in have['data'] if name.endswith(i['name'])]
                if len(id) != 1:
                    app.die('No matching domain', name=name, have=have['data'])
                id = id[0]['id']
            dns_modify('CREATE', ips=ips, name=name, ttl=ttl, zoneid=id)
            return Actions.dns_list(name=name)

    def dns_delete(name=None, force=None):
        name = dotted(name, False)
        return Prov().resource_delete(Prov().dns, force=force)


def dns_modify(action, ips, name, ttl, zoneid, **_):
    app.info(f'DNS {action}', **dict(locals()))
    assert action in {'CREATE', 'DELETE'}
    if not ips:
        app.die('No ips', **dict(locals()))
    rr = ''.join([TARR.format(ip=ip) for ip in ips])
    d = dict(name=name, rr=rr, ttl=ttl, base_doc=AA.base_doc, action=action)
    xml = xmlhead + '\n' + TAR.format(**d).replace('\n', '')
    path = f'hostedzone/{zoneid}/rrset'
    r = AA.send_request(path, xml, 'post')
    return r


class Flags(Flags):
    class aws_key:
        n = 'key or command to get it'
        d = ''

    class aws_secret:
        n = 'secret or command to get it'
        d = 'cmd: pass show AWS/pw'


Flags._pre_init(Flags, Actions)


_ = 'We will create default network, if not present yet'
# Flags.Actions.droplet_create.private_network.n += _


class AWSProv(Provider):
    name = 'AWS'
    Actions = Actions
    secrets = 'aws_key', 'aws_secret'

    def normalize_pre(d, r, cls, headers):
        return

    def rm_junk(api_response):
        return

    class domain:
        endpoint = 'hostedzone'
        normalize = []
        headers = ['name', 'id', 'comment']

    class dns:
        # fmt:off
        endpoint = 'hostedzone'
        normalize = []
        # fmt:on
        headers = ['name', 'ips', 'ttl']

        def prepare_delete(d):
            dns_modify(action='DELETE', **d)
            return fmt.flag_deleted


Prov(init=AWSProv)
main = lambda: run_app(Actions, flags=Flags)


class AA:
    """The Funny AWS API"""

    base = 'https://route53.amazonaws.com/2012-02-29'
    base_doc = 'https://route53.amazonaws.com/doc/2012-02-29'   # for posts

    def sign(s):
        _ = Api.secrets['aws_secret'].encode('utf-8')
        new_hmac = hmac.new(_, digestmod=hashlib.sha256)
        new_hmac.update(s.encode('utf-8'))
        return base64.b64encode(new_hmac.digest()).decode('utf-8')

    def get_request_headers():
        date_header = time.asctime(time.gmtime())
        sk = AA.sign(date_header)
        id = Api.secrets['aws_key']
        auth_header = (
            f'AWS3-HTTPS AWSAccessKeyId={id},Algorithm=HmacSHA256,Signature={sk}'
        )
        return {
            'X-Amzn-Authorization': auth_header,
            'x-amz-date': date_header,
            'Host': 'route53.amazonaws.com',
        }

    def send_request(path, data, method):
        headers = AA.get_request_headers()
        ep = f'{AA.base}/{path}'
        r = getattr(requests, method)(ep, data, headers=headers)
        if app.log_level < 20:
            app.debug('repsonse', xml=r.text)
        if not r.status_code < 300:
            app.die('API Error', txt=r.text)
        return r.text


def xval(s, tag, d=''):
    # sry - but when I was young, allowing this was a main selling point of XML:
    t = f'<{tag}>'
    return d if not t in s else s.split(t, 1)[1].split(f'</{tag}>', 1)[0]


def get_zones(max_items=1000, get_records=True):
    r = AA.send_request('hostedzone', {'maxitems': 1000}, 'get')
    assert 'ListHostedZonesResponse' in r
    All = []
    for hz in r.split('<HostedZone>')[1:]:
        id = xval(hz, 'Id')[1:].replace('hostedzone/', '')
        dom_name = xval(hz, 'Name')
        if not get_records:
            comment = xval(hz, 'Comment')
            All.append({'id': id, 'name': dom_name, 'comment': comment})
            continue
        d = {'identifier': None, 'maxitems': 1000, 'name': None, 'type': None}
        r = AA.send_request(f'hostedzone/{id}/rrset', d, 'get')
        assert 'ListResourceRecordSetsResponse' in r

        def d(s, id=id):
            r = {
                'domain': dom_name,
                'name': xval(s, 'Name'),
                'type': xval(s, 'Type'),
                'ttl': int(xval(s, 'TTL', 0)),
                'zoneid': id,
            }
            if not r['type'] == 'A':
                return

            r['ips'] = [xval(k, 'Value') for k in s.split('<ResourceRecord>')[1:]]
            return r

        all = [d(s) for s in r.split('<ResourceRecordSet>')[1:]]
        all = sorted([k for k in all if k], key=lambda d: d['name'])
        All.extend(all)
    return All


def get_domains():
    return get_zones(max_items=100, get_records=False)


xmlhead = "<?xml version='1.0' encoding='UTF-8'?>"
# template a record:
TAR = """
<ChangeResourceRecordSetsRequest xmlns="{base_doc}/"><ChangeBatch>
<Changes><Change><Action>{action}
</Action><ResourceRecordSet><Name>{name}
</Name><Type>A
</Type><TTL>{ttl}
</TTL><ResourceRecords>{rr}</ResourceRecords>
</ResourceRecordSet>
</Change>
</Changes>
</ChangeBatch>
</ChangeResourceRecordSetsRequest>"""
TARR = '<ResourceRecord><Value>{ip}</Value></ResourceRecord>'


if __name__ == '__main__':
    main()
