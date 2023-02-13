#!/usr/bin/env python
# vim:sw=4
"""
# K8s Ops
"""
import time

t0 = time.time()
import os
from devapp.app import run_app, FLG, app
from devapp.tools.infra import Provider, Api, Prov, fmt, rm, env
from devapp.tools.infra.actions import conv2classmethods
import time
from devapp.tools.flag import build_action_flags, set_action_func_param_values
import hmac, hashlib, requests, base64
from operator import setitem
from devapp.tools import cache, write_file, exists, read_file


class Flags:
    class kube_namespace:
        s = 'kns'
        n = 'Namespace to act upon'
        d = 'all'

    class kube_config:
        s = 'kc'
        n = 'Location of kubeconfig'
        d = env.get('KUBECONFIG', env.get('HOME') + '/.kube/config')


fn_err = '/tmp/kc.err'
err_file = lambda: read_file(fn_err, dflt='')

import json


def api_log():
    """logs the k8s api requests"""
    lines = err_file().splitlines()
    r = {}
    if lines[-1].startswith('error:'):
        r['err'] = lines.pop().split('error: ', 1)[-1]

    while lines:
        l = lines.pop(0)
        verb, body = l.split('] ', 1)[1].split(' ', 1)
        if not r.get('method'):
            if verb.lower() in {'get', 'post', 'put', 'delete'}:
                r['method'] = verb.lower()
                r['url'], r['status'], _ = body.split(' ', 2)
                r['dt'] = (
                    ' '.join(body.rsplit(' ', -2)[-2:])
                    .replace(' milliseconds', 'ms')
                    .replace(' seconds', 's')
                )
        if verb == 'Response':
            l = body.split('Body: ')
            if len(l) > 1:
                r['json'] = json.loads(l[1])
    app.debug(r.get('err') or r.get('url').split('/api', 1)[1], **r)


def kubectl(*args, exec=None, on_err='die', get_cmd=False, with_ns=True):
    if len(args) > 1:
        args = ' '.join([f'"{a}"' for a in args])
    else:
        args = args[0]
    ns = FLG.kube_namespace
    if with_ns and not ' -n ' in args and not ' --namespace' in args:
        ns = f' -n {ns}' if ns != 'all' else ' -A'
        args += ns
    kc = FLG.kube_config
    if not exists(kc):
        app.die('Kubeconfig not present', location=kc)
    cmd = f'kubectl {args} --kubeconfig={kc}'
    if exec:
        cmd += f' -- {exec}'
    try:
        if app.log_level < 20:
            cmd += ' -v10'
        app.info(args)
        if get_cmd:
            return cmd
        _ = os.popen(f'{cmd} 2>{fn_err}; echo ":$?"').read().strip()
        if app.log_level < 20:
            api_log()
        res, st = _.rsplit(':', 1)
        if on_err == 'die' and st != '0':
            app.die(err_file().rsplit('\n', 1)[-1])
        return res
    finally:
        os.unlink(fn_err) if exists(fn_err) else 0


class Actions:
    class _cli:
        pods = 'pods'
        exec = 'e'
        login_only = 'lo', '', 'Only try login, no transfer of secrets to cluster'
        nodes = 'no'
        namespaces = 'n', '', 'Space OR comma seperated'
        name_spaces = 'ns'
        pod = 'p', '', 'matching pod. must match unique'

    def _pre(A):
        env.set_base_environ_vars()
        return set_action_func_param_values(Actions, app, FLG)

    # fmt:off
    pods       = lambda A, match = '', s = 'pl'  : get('pods'      , match)
    nodes      = lambda A, match = '', s = 'nl'  : get('nodes'     , match)
    name_spaces = lambda A, match = '', s = 'nsl' : get('namespaces', match)
    # fmt: on

    def add_registry_auth(
        A,
        private_registry='$private_registry',
        private_registry_user='$private_registry_user',
        private_registry_password='$private_registry_password',
        fn_local_auth='auto',  # location of docker auth file
        namespaces=[],
        login_only=False,
    ):
        """Copies local registry auth entries as 'dockerconfig' secrets to the cluster.
        Remember: Use password HASH and not your company password here, if possible on your registry.
        A local auth.json file with your password will be created locally, if not existent
        => DELETE this file afterwards, if on untrusted hosts.
        """
        if private_registry.startswith('$'):
            private_registry = ''
        if private_registry_user.startswith('$'):
            private_registry_user = ''
        if private_registry_password.startswith('$'):
            private_registry_password = ''
        # allow 'foo bar' (easier than in scripts)
        if len(namespaces) == 1 and ' ' in namespaces[0]:
            namespaces = namespaces[0].split()
        if not login_only:
            [P.kubectl.add_namespace(ns) for ns in namespaces]
        if not private_registry:
            return 'no private registry to configure'
        pm = ''
        for k in 'podman', 'docker':
            pm = os.popen(f'which {k}').read().strip()
            if pm:
                break
        if not pm:
            app.die('require local docker or podman')
        cmd = f'{pm} login {private_registry}'
        if private_registry_user:
            cmd += f' -u {private_registry_user}'
        app.info(cmd)
        if private_registry_password:
            cmd += f' -p {private_registry_password}'

        if os.system(cmd):
            app.die('No successful login', reg=private_registry)
        if login_only:
            return
        if not namespaces:
            app.die('No namespaces to configure registry access for')
        fn = fn_local_auth
        if not exists(fn):
            fn = env.get('REGISTRY_AUTH_FILE')
            if not fn:
                fn = env.get('XDG_RUNTIME_DIR') + '/containers/auth.json'
                if not exists(fn):
                    app.info('Not present', fn=fn)
                    fn = env.get('HOME') + '/.docker/config.json'
        if not exists(fn):
            _ = 'try login. E.g.: docker/podman login artificatory.mycompany.com'
            app.die('No auth file', fn=fn, hint=_)
        for ns in namespaces:
            _ = 'private-registry-secret'
            cmd = f'create secret generic {_} --from-file=".dockerconfigjson={fn}" --type=kubernetes.io/dockerconfigjson -n {ns}'
            app.info(cmd)
            P.kubectl(cmd)

    def exec(A, pod_match, cmd='/bin/bash'):
        pods = [i for i in kubectl('get pods').splitlines() if pod_match in i]
        pods = [i.split()[:2] for i in pods]
        ns, pod = sorted([(len(i[1].split('-')), i) for i in pods])[0][1]
        kcmd = kubectl(f'exec -n {ns} -ti {pod}', exec=cmd, get_cmd=True)
        app.info(f'Using pod {pod}', matched=[i[1] for i in pods])
        app.info(kcmd)
        os.system(kcmd)

    def api(A, match=''):
        r = kubectl(f'api-resources', with_ns=False)
        return [l for l in r.splitlines() if match in l]

    def add_contour_gw_api(self, infra_name, region='$region'):
        if not infra_name or not region or region.startswith('$'):
            app.die('Require infra_name and regions for annotations')
        fn = 'conf/contour_quickstart.yaml'

        if not exists(fn):
            from devapp.tools.http import download

            url = 'https://projectcontour.io/quickstart/contour.yaml'
            s = download(url, fn)
        P.kubectl.apply(fn)
        s = T_CONT_GW.format(**dict(locals()))
        P.kubectl.apply('conf/gateway.yaml', s)


conv2classmethods(Actions)
P = Provider()
P.name = 'kube'
Prov(P)


def get(what, match='', **kw):
    r = kubectl(f'get {what}')
    return [l for l in r.splitlines() if match in l]


build_action_flags(Flags, Actions)

main = lambda: run_app(Actions, flags=Flags)
TREG = """

apiVersion: v1
kind: Secret
metadata:
    name: private-registry-secret
    namespace: "{{ item }}"
data:
    .dockerconfigjson: >-
      {{ registry_creds|to_json|b64encode }}
type: kubernetes.io/dockerconfigjson
"""

T_CONT_GW = """
---
kind: ContourDeployment
apiVersion: projectcontour.io/v1alpha1
metadata:
  namespace: projectcontour
  name: {infra_name}-gw-class-config
spec:
  envoy:
    workloadType: DaemonSet
    networkPublishing:
      type: LoadBalancerService
      serviceAnnotations:
        load-balancer.{infra_name}.cloud/location: {region}
        load-balancer.{infra_name}.cloud/protocol: tcp
        load-balancer.{infra_name}.cloud/use-private-ip: "true"
        load-balancer.{infra_name}.cloud/uses-proxyprotocol: "false"
  runtimeSettings:
    envoy:
      listener:
        useProxyProtocol: false
---
kind: GatewayClass
apiVersion: gateway.networking.k8s.io/v1alpha2
metadata:
  name: {infra_name}-gw-class
spec:
  controllerName: projectcontour.io/gateway-controller
  parametersRef:
    kind: ContourDeployment
    group: projectcontour.io
    name: {infra_name}-gw-class-config
    namespace: projectcontour
"""

if __name__ == '__main__':
    main()
