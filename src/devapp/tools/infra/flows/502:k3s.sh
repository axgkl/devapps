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
  
  	ops infra_digital_ocean droplet_create --features k3s --name k2{} --range master,1,2,3 --size M
  
  - Same with selinux off (faster install), relative time and by thread indication:
  
  	selinux=false ops ido dc -f k3s -n k2{} -r master,1,2,3 -S M -ltf dt -latn
  
  
  
  ## Misc
  
  - https://github.com/DavidZisky/kloud3s/blob/master/digitalocean/cloud_manager/k3s_deployer_cloudmanag.sh
  
  '

source "%(feature:functions.sh)s"

set -a
INSTALL_K3S_VERSION="%($k3s_version|v1.24.2+k3s2)s"
domain="%(!$domain)s"
dns_provider="%(!$dns_provider)s" # aws or digitialociean
email="%(!$email)s"
k3s_debug="true"
k3s_server_location="/var/lib/rancher/k3s"
k8s_cluster_cidr_v4="10.244.54.0/23"
k8s_service_cidr_v4="10.43.0.0/24"
k8s_coredns_srv_ip_v4="10.43.0.10"
k8s_node_cidr_size_v4=27
k8s_max_pods_per_node=32
no_selinux="%($no_selinux)s"
tools="%($tools|net-tools tcpdump tcpflow dnsutils lvm2 parted)s"
ttl="%($ttl|120)s"
set +a

# part: ========================================================== name eq local

echo "Have all internal ips: %(wait:200:all.ip_priv)s" # we start when we have those

function generate_token {
    set_fact k3s_server_token "$(tr -dc A-Za-z0-9 </dev/urandom | head -c 64)"
}

function configure_dns_to_k8s_api {
  local zone="$cluster_name.$domain"

    local dp='infra_aws_cloud'
    test "$dns_provider" == "digitalocean" && dp="infra_digital_ocean"
    export ttl="${ttl:-120}"
    local ips_ext="" ips_int=""
    set -x
    for n in $names; do
      ips_ext="$ips_ext,$(kv "$n" ip)"
      ips_int="$ips_int,$(kv "$n" ip_priv)"
    done
    ops $dp dns_create -n "k3s-api-ext-$zone" -ips "$ips_ext" --dns_create_rm
    ops $dp dns_create -n "k3s-api-int-$zone" -ips "$ips_int" --dns_create_rm
    set +x
    sleep 10000
}



do_ generate_token
do_ configure_dns_to_k8s_api

# part: ========================================================== name contains master
set_fact is_master true


# part: ========================================================== name not eq local
sleep 10000
function double_check_priv_network_present { ip addr show | grep 'inet 10\.' || die "private iface missing"1; }

function install_tools {
    type tcpflow && return # installed
    # shellcheck disable=SC2086
    pkg_inst ${tools}
}

function configure_forwarding {
    local fn=/etc/sysctl.d/99-sysctl.conf
    echo 'net.ipv4.ip_forward=1' >>$fn
    echo 'net.ipv6.conf.all.forwarding=1' >>$fn
    /sbin/sysctl -p
}

install_k3s_() {
    set -x
    function disable_selinux {
        setenforce 0
        export INSTALL_K3S_SKIP_SELINUX_RPM=true
        export INSTALL_K3S_SELINUX_WARN=true
    }
    test -n "$no_selinux" && do_ disable_selinux
    curl -sfL https://get.k3s.io | sh -s - "${INSTALL_K3S_EXEC:-}" \
        --token "%(local.k3s_server_token)s" \
        --kubelet-arg="cloud-provider=external" \
        --kubelet-arg="provider-id=digitalocean://%(id)s" "$@"
    set +x
}

# cond: _____________________________________________________________________ name contains master

function install_k3s {
    local fn="/var/lib/rancher/k3s/server/node-token"
    test -f "$fn" && return 0
    export INSTALL_K3S_EXEC='server'
    mkdir -p /etc/rancher/k3s
    cat << EOF | sed -e 's/^    //g' > /etc/rancher/k3s/config.yaml
    ---
    node-name: $name
    node-ip: %(ip_priv)s
    disable-cloud-controller: true
    disable-network-policy: true
    disable-kube-proxy: true
    disable:
      - traefik
      - servicelb
      - metrics-server
    flannel-backend: none
    data-dir: $k3s_server_location
    cluster-cidr: $k8s_cluster_cidr_v4
    service-cidr: $k8s_service_cidr_v4
    service-node-port-range: 32225-32767
    cluster-dns: $k8s_coredns_srv_ip_v4
    kubelet-arg:
      - "v=5"
      - "feature-gates=TopologyAwareHints=true,EphemeralContainers=true,GracefulNodeShutdown=true"
      - "config=/etc/rancher/k3s/kubelet.yaml"
      - "max-pods=$k8s_max_pods_per_node
      - "make-iptables-util-chains=false"
      - "cloud-provider=external"
      - "node-status-update-frequency=4s"
    #  - "network-plugin=cni"
    kube-apiserver-arg:
      - "v=5"
      - "feature-gates=TopologyAwareHints=true,EphemeralContainers=true,GracefulNodeShutdown=true"
      - "default-not-ready-toleration-seconds=20"
      - "default-unreachable-toleration-seconds=20"
    kube-controller-manager-arg:
      - "v=5"
      - "feature-gates=TopologyAwareHints=true,EphemeralContainers=true,GracefulNodeShutdown=true"
      - "bind-address=0.0.0.0"
      - "allocate-node-cidrs=true"
      - "node-monitor-period=4s"
      - "node-monitor-grace-period=16s"
      - "pod-eviction-timeout=120s"
      - "node-cidr-mask-size=$k8s_node_cidr_size_v4"
    kube-scheduler-arg:
      - "bind-address=0.0.0.0"
      - "feature-gates=TopologyAwareHints=true,EphemeralContainers=true,GracefulNodeShutdown=true"
    #kube-proxy-arg:
    #  - "metrics-bind-address=0.0.0.0"
    tls-san:
      - "{{ k3s_api_int }}.{{ k3s_svc_dns_suffix }}.{{ k3s_dns_zone }}"
      - "{{ k3s_api_ext }}.{{ k3s_svc_dns_suffix }}.{{ k3s_dns_zone }}"
      - "{{ address }}"
    write-kubeconfig-mode: 644
    debug: $k3s_debug
    node-label:
    {% for kn, kv in k3s_labels.items() %}
      - "{{ kn }}={{ kv }}"
    {% endfor %}
    token: {{ hostvars['localhost']['k3s_token'] }}

    # See https://rancher.com/docs/k3s/latest/en/security/hardening_guide/
    #    --protect-kernel-defaults=true \
    #    --secrets-encryption=true \
EOF
    
  

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

# else __________________________________________________________________________________________

function install_k3s {
    test -e "/var/lib/rancher/k3s/agent" && return 0
    echo "%(wait:200:match:key.is_master)s"
    #export K3S_URL="https://%(matched.ip_priv)s:6443"
    export K3S_URL="https://%(matched.ip)s:6443"
    export INSTALL_K3S_EXEC='agent'
    install_k3s_ --node-external-ip="$ip"
}
# end ___________________________________________________________________________________________

do_ double_check_priv_network_present
do_ install_tools
do_ configure_forwarding
do_ install_k3s
set_fact k3s_installed true

# part: ========================================================== name eq local

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
    email: '$email'
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
