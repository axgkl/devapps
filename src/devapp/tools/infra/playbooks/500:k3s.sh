#!/bin/bash

_='# Deploy a single server k3s.

- Server config for kubectl is put to ./conf/ks.yaml
- Locally we add the KUBECONFIG variable pointing to server config into a file "./environ"

## Conventions:

Server must have "master" within its name.

## Env Parameters

- selinux[=true]: When false, install without SELINUX context (install much faster)

## Examples

- 4 Node server cluster:

	ops infra_digital_ocean droplet_create --playbooks k3s --name k2{} --range master,1,2,3 --size M

- Same with selinux off (faster install), relative time and by thread indication:

	selinux=false ops ido dc -f k3s -n k2{} -r master,1,2,3 -S M -ltf dt -latn



## Misc

- https://github.com/DavidZisky/kloud3s/blob/master/digitalocean/cloud_manager/k3s_deployer_cloudmanag.sh

'

source "%(feature:functions.sh)s"

# part: name eq local
function generate_token {
    set_fact k3s_server_token "$(tr -dc A-Za-z0-9 </dev/urandom | head -c 64)"
}
do_ generate_token

# part: name contains master

set_fact is_master true

# part: name not eq local

# cond: env.selinux eq false
function disable_selinux {
    setenforce 0
    export INSTALL_K3S_SKIP_SELINUX_RPM=true
    export INSTALL_K3S_SELINUX_WARN=true
}
do_ disable_selinux
# end

install_k3s_() {
    h1 "Installing K3s $INSTALL_K3S_EXEC"
    waitproc no rpm
    set -x
    curl -sfL https://get.k3s.io | sh -s - "${INSTALL_K3S_EXEC:-}" \
        --token "%(local.k3s_server_token)s" \
        --kubelet-arg="cloud-provider=external" \
        --kubelet-arg="provider-id=digitalocean://%(id)s" "$@"
    set +x
}

# cond: name contains master
function install_k3s {
    local fn="/var/lib/rancher/k3s/server/node-token"
    test -f "$fn" && return 0
    export INSTALL_K3S_EXEC='server'
    install_k3s_ \
        --write-kubeconfig-mode 644 \
        --disable-cloud-controller \
        --no-deploy servicelb \
        --node-taint CriticalAddonsOnly=true:NoExecute
    #--disable traefik \
    #		--node-external-ip="$ip" \
    #		--node-taint CriticalAddonsOnly=true:NoExecute \
    #--disable local-storage || exit 1
}

# else:

function install_k3s {
    test -e "/var/lib/rancher/k3s/agent" && return 0
    echo "%(wait:200:match:key.is_master)s"
    #export K3S_URL="https://%(matched.ip_priv)s:6443"
    export K3S_URL="https://%(matched.ip)s:6443"
    export INSTALL_K3S_EXEC='agent'
    install_k3s_ --node-external-ip="$ip"
}
# end
# rpm often not ready:
do_ install_k3s || do_ install_k3s || exit 1
set_fact k3s_installed true

# part: name eq local

echo "%(wait:200:all.k3s_installed)s"

function get_kubeconfig {
    echo "%(match:key.is_master)s"
    ip="%(matched.ip)s"
    transfer_kubeconfig "/etc/rancher/k3s/k3s.yaml"
}

function install_ccm {
    ccm_version="v0.1.36"
    K -n kube-system create secret generic digitalocean --from-literal=access-token="%(secret.do_token)s"
    K apply -f "https://raw.githubusercontent.com/digitalocean/digitalocean-cloud-controller-manager/master/releases/$ccm_version.yml"
}

function install_ext_dns {
    function inst_ext_dns {
        HELM -n kube-system install external-dns \
            --set provider=digitalocean \
            --set digitalocean.apiToken="%(secret.do_token)s" \
            --set policy=sync \
            bitnami/external-dns
    }
    inst_ext_dns || {
        HELM repo add bitnami https://charts.bitnami.com/bitnami
        inst_ext_dns || exit 1
    }
}

function install_cert_mgr {
    K -n kube-system create secret generic digitalocean-dns --from-literal=access-token="%(secret.do_token)s"
    HELM -n kube-system install cert-manager bitnami/cert-manager --set installCRDs=true
    sleep 4
}

function install_dns_issuer {
    echo -e '
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-dns
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: %(flag.email)s
    # Name of a secret used to store the ACME account private key
    privateKeySecretRef:
      name: letsencrypt-dns
    solvers:
    - dns01:
        digitalocean:
          tokenSecretRef:
            name: digitalocean-dns
            key: access-token
' >dns_issuer.yaml

    until (K -n kube-system apply -f dns_issuer.yaml); do
        echo 'cert manager not ready yet. '
        sleep 4
    done
}
do_ get_kubeconfig
#do_ install_ccm
#do_ install_ext_dns
#do_ install_cert_mgr
#do_ install_dns_issuer
