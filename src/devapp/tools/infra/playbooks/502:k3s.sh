#!/bin/bash
# vim: set sw=4

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
function define_vars_and_functions {
    set -a
    D="%(!$dir_project)s"
    api_base="%(!$infra_api_base)s"
    app_namespaces="%($app_namespaces)s"
    dns_provider="%(!$dns_provider)s" # aws or digitialociean
    domain="%(!$domain)s"
    company="${domain#*.}" # foo.company.com -> company.com (for node labels)
    email="%(!$email)s"
    k3s_debug="true"
    k3s_server_location="/var/lib/rancher/k3s"
    k8s_cluster_cidr_v4="10.244.54.0/23"
    k8s_coredns_srv_ip_v4="10.43.0.10"
    k8s_max_pods_per_node=32
    k8s_node_cidr_size_v4=27
    k8s_service_cidr_v4="10.43.0.0/24"
    #k8s_service_node_port_range="32225-32767"
    k8s_service_node_port_range="30000-32767" # XT has a 32222 one but cilium tests are hardcoded on 31sth
    log_fmt=2                                 # colored term output also for devapp subprocessesut also for devapp subprocesses
    private_registry="%($private_registry)s"  # only one at this time
    region="%(!$region)s"
    network_name="%($network_name)s"
    no_selinux="%($no_selinux)s"
    tools="%($tools|net-tools tcpdump tcpflow dnsutils lvm2 parted)s"
    ttl="%($ttl|120)s"
    v_certmgmr="%($certmgr_version|1.9.1)s"
    v_cilium="%($cilium_version|1.11.8)s"
    v_ext_dns="%($ext_dns_version|0.12.0)s"
    v_hetzner_ccm="%($ccm_version|1.12.1)s"
    v_k3s="%($k3s_version|v1.24.2+k3s2)s"
    zone="$cluster_name.$domain"
    set +a
    mkdir -p "$D/conf" # for stuff we want to keep
    mkdir -p "$D/tmp"  # for stuff we want to keep for debug
}

function dns_ops_plugin {
    # our helpers for dns and certmgr configuration
    case "$dns_provider" in
    "digitalocean") echo "infra_digital_ocean" ;;
    "aws") echo "infra_aws_cloud" ;;
    *) die "DNS Provider $dns_provider not supported" ;;
    esac
}

do_ always define_vars_and_functions

# part: ========================================================== name eq local

function verify_registry_creds {
    ops kubectl add_registry_auth --private_registry="$private_registry" --login_only
}

function generate_token {
    echo "Have all internal ips: %(wait:200:all.ip_priv)s" # we start when we have those
    set_fact k3s_server_token "$(tr -dc A-Za-z0-9 </dev/urandom 2>/dev/null | head -c 64)"
}

function configure_dns_to_k8s_api {
    export ttl="${ttl:-120}"
    local ips_ext="" ips_int=""
    for n in $names; do
        if [[ $n =~ master ]]; then
            ips_ext="$ips_ext:$(kv "$n" ip)"
            ips_int="$ips_int:$(kv "$n" ip_priv)"
        fi
    done
    test -z "$ips_ext" && die "No master node"
    # we have time for that, waiting for ssh access anyway on the remote side:
    # TODO: create multi for digitalocean:
    shcmd ops "$(dns_ops_plugin)" dns_multi_create --name_ip_pairs "k3s-api-ext-$zone::$ips_ext,k3s-api-int-$zone::$ips_int" --rm &
}

do_ verify_registry_creds
do_ always generate_token
do_ configure_dns_to_k8s_api
# part: ========================================================== name contains master
set_fact is_master true

# part: ========================================================== name not eq local
function double_check_priv_network_present {
    ip addr show | grep 'inet 10\.' || die "private iface missing"1
}
function install_tools {
    info 'checking presence of tools and package mgr type'
    type tcpflow 2>/dev/null && return "$SKIP_PRESENT"
    # shellcheck disable=SC2086
    pkg_inst ${tools}
}
function networking_sysctls {
    local _='most for cilium
    See https://github.com/cilium/cilium/pull/20072
    See https://github.com/cilium/cilium/issues/10645#issuecomment-701419363
    See https://github.com/cilium/cilium/issues/20125#issuecomment-1155684032
    '
    local fn=/etc/sysctl.d/99-sysctl.conf
    #local fn=/etc/sysctl.d/99-zzz-override_cilium.conf
    grep 'martians' <$fn && return "$SKIP_PRESENT"
    deindent <<'    EOF' >"$fn"
    net.ipv4.ip_forward=1
    net.ipv6.conf.all.forwarding=1
    net.ipv4.conf.*.log_martians=1
    net.ipv4.conf.all.log_martians=1
    net.ipv4.conf.all.log_martians=1
    net.ipv4.conf.*.rp_filter=0
    net.ipv4.conf.all.rp_filter=0
    net.ipv4.conf.default.rp_filter=0
    EOF
    systemctl restart systemd-sysctl # globs only understood by systemd not sysctl -p
}
function write_kubelet_config {
    mkdir -p /etc/rancher/k3s
    deindent <<'    EOF' >/etc/rancher/k3s/kubelet.yaml
    ---
    apiVersion: kubelet.config.k8s.io/v1beta1
    kind: KubeletConfiguration
    shutdownGracePeriod: 80s
    shutdownGracePeriodCriticalPods: 40s
    EOF
}

function run_k3s_installer {
    function disable_selinux {
        setenforce 0
        export INSTALL_K3S_SKIP_SELINUX_RPM=true
        export INSTALL_K3S_SELINUX_WARN=true
    }
    test -n "$no_selinux" && do_ disable_selinux
    export INSTALL_K3S_VERSION="$v_k3s"
    curl -sfL https://get.k3s.io | sh -s - "${INSTALL_K3S_EXEC:-}"
}

function install_k3s {
    local fn="/etc/rancher/k3s/config.yaml"
    test -f "$fn" && return "$SKIP_PRESENT"
    do_ write_kubelet_config
    do_ write_k3s_config
    do_ run_k3s_installer
}

# cond: _____________________________________________________________________ name contains master
export INSTALL_K3S_EXEC='server'

function write_k3s_config {
    deindent <<EOF >/etc/rancher/k3s/config.yaml
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
    service-node-port-range: $k8s_service_node_port_range
    cluster-dns: $k8s_coredns_srv_ip_v4
    kubelet-arg:
      - "v=5"
      - "feature-gates=TopologyAwareHints=true,EphemeralContainers=true,GracefulNodeShutdown=true"
      - "config=/etc/rancher/k3s/kubelet.yaml"
      - "max-pods=$k8s_max_pods_per_node"
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
      - "k3s-api-ext-$zone"
      - "k3s-api-int-$zone"
      - "%(ip_priv)s"
    write-kubeconfig-mode: 644
    debug: $k3s_debug
    node-label:
      - "$company/type=master"
      - "$company/layer=control"
    token: %(local.k3s_server_token)s

    # See https://rancher.com/docs/k3s/latest/en/security/hardening_guide/
    #    --protect-kernel-defaults=true \
    #    --secrets-encryption=true \

EOF
}

# else __________________________________________________________________________________________
export INSTALL_K3S_EXEC='agent'

function write_k3s_config {
    echo "%(wait:200:match:key.is_master)s"
    #export K3S_URL="https://%(matched.ip_priv)s:6443"
    export K3S_URL="https://%(matched.ip_priv)s:6443"

    deindent <<EOF >/etc/rancher/k3s/config.yaml
    ---
    node-name: $name
    node-ip: %(ip_priv)s
    kubelet-arg:
      - "v=5"
      - "feature-gates=TopologyAwareHints=true,EphemeralContainers=true,GracefulNodeShutdown=true"
      - "config=/etc/rancher/k3s/kubelet.yaml"
      - "max-pods=$k8s_max_pods_per_node"
      - "make-iptables-util-chains=false"
      - "cloud-provider=external"
      - "node-status-update-frequency=4s"
      #- "network-plugin=cni"
    debug: $k3s_debug
    node-label:
      - "$company/type=worker"
      - "$company/layer=work"
    token: %(local.k3s_server_token)s
    server: https://k3s-api-int-$zone:6443
EOF
}

# end ___________________________________________________________________________________________

do_ double_check_priv_network_present
do_ install_tools
do_ networking_sysctls
do_ install_k3s
set_fact k3s_installed true

# part: ========================================================== name eq local

echo "%(wait:200:all.k3s_installed)s"

function get_kubeconfig {
    # copy it over from a master, ssh-ing to it's ip:
    echo "%(match:key.is_master)s"
    transfer_kubeconfig "/etc/rancher/k3s/k3s.yaml" "k3s-api-ext-$zone" "%(matched.ip)s"
}
function rm_master_node_label {
    local l R="node-role.kubernetes.io/master"
    l="$(K get nodes --show-labels)"
    grep "$R" <<<"$l" || return "$SKIP_PRESENT"
    # https://github.com/kubernetes/kubernetes/issues/65618 In later version of k8s there is a better mechanics to allow services on master
    for n in $names; do
        if [[ $n =~ master ]]; then K label node "$n" "$R-"; fi
    done
}
function install_digital_ocean_ccm {
    ccm_version="v0.1.36"
    K -n kube-system create secret generic digitalocean --from-literal=access-token="%(secret.hcloud_api_token)s"
    K -n kube-system create secret generic digitalocean --from-literal=access-token="%(secret.hcloud_api_token)s"
    K apply -f "https://raw.githubusercontent.com/digitalocean/digitalocean-cloud-controller-manager/master/releases/$ccm_version.yml"
}
function install_hetzner_ccm {
    K -n kube-system get pods | grep hcloud-cloud-controller-manager && return "$SKIP_PRESENT"
    shcmd ops infra_hetzner_cloud kube_add_ccm \
        --kube_config="$(kubeconf)" \
        --network_name="$network_name" \
        --cidr="$k8s_cluster_cidr_v4" \
        --version="$v_hetzner_ccm"
}

function install_cilium {
    _='
	  cilium status (cilium tool installed)
	  kubectl -n kube-system attach  cilium-47jzs # see monitor OR 
	  kubectl -n kube-system exec  cilium-47jzs -ti /bin/sh
	  '
    K -n kube-system get pods | grep cilium && return "$SKIP_PRESENT"
    helm repo add cilium https://helm.cilium.io 2>/dev/null
    local fn="$D/conf/cilium_values.yaml"
    local replicas=0
    for n in $names; do
        if [[ $n =~ master ]]; then replicas=$((replicas + 1)); fi
    done
    test $replicas == "1" || replicas=2 # max, when > 1 set hard to 2
    info "Cilium replicas set to $replicas"

    deindent <<EOF >"$fn"
    ---
    name: cilium-k3s
    cluster:
      name: k3s-cluster
      id: 1

    agent: true
    rollOutCiliumPods: true

    operator:
      enabled: true
      rollOutPods: true
      replicas: ${replicas?}

    debug:
      enabled: $k3s_debug
    k8sServiceHost: k3s-api-int-$zone
    k8sServicePort: 6443

    # Bandwith Manager
    # https://cilium.io/blog/2020/11/10/cilium-19#bwmanager
    # https://docs.cilium.io/en/stable/operations/performance/tuning/#bandwidth-manager
    bandwidthManager: true

    # Tunnelling mode
    tunnel: "geneve"
    autoDirectNodeRoutes: false

    # BPF stuff
    bpf:
      masquerade: true
      hostRouting: false
      tproxy: true
      lbBypassFIBLookup: false
    ipMasqAgent:
      enabled: true

    # Kube-Proxy replacement
    kubeProxyReplacement: "strict"
    kubeProxyReplacementHealthzBindAddr: "[::]:10256"
    localRedirectPolicy: false
    ipv4NativeRoutingCIDR: "10.0.0.0/8"
    l2NeighDiscovery:
      enabled: false
      refreshPeriod: "30s"

    l7Proxy: false

    policyEnforcementMode: "never"

    hostServices:
      enabled: true
      protocols: tcp,udp

    installIptablesRules: false
    installNoConntrackIptablesRules: false

    ipam:
      mode: "kubernetes"

    # Load-balancing - DSR requires native routing
    # https://docs.cilium.io/en/stable/gettingstarted/kubeproxy-free/#xdp-acceleration
    loadBalancer:
      standalone: false
      algorithm: maglev
      mode: snat
      acceleration: disabled
      dsrDispatch: opt
      serviceTopology: true

    nodePort:
      enabled: true
      range: "${k8s_service_node_port_range//-/,}"
      bindProtection: true
      autoProtectPortRange: true
      enableHealthCheck: true

    cleanState: true
    nodeinit:
      enabled: $k3s_debug
    enableK8sTerminatingEndpoint: true

    # Hubble/Observability
    hubble:
      enabled: $k3s_debug
      metrics:
        enabled:
          - dns:query;ignoreAAAA
          - drop
          - tcp
          - flow
          - icmp
          - http
      relay:
        enabled: $k3s_debug
        rollOutPods: true
      ui:
        enabled: $k3s_debug
        standalone:
          enabled: false
        rollOutPods: true
        podLabels:
          lb-app: hubble-ui

    ipv4:
      enabled: true
    ipv6:
      enabled: false

    enableIPv4Masquerade: true
    enableIPv6Masquerade: false
EOF
    helm install cilium cilium/cilium --version "${v_cilium?}" --namespace kube-system --values "$fn"
    local c
    info 'Waiting for cilium to be up...'
    sleep 4
    for ((i = 1; i < 20; i++)); do
        sleep 1
        c="$(K -n kube-system get pods | grep cilium)"
        test -z "$c" && continue
        grep -v Running <<<"$c" || break
    done
    test "$i" == "20" && die "cilium did not come up"
    info 'cilium is ready'
}

function install_cert_mgr {
    K -n cert-manager get pods | grep cainjector && return "$SKIP_PRESENT"
    shcmd ops "$(dns_ops_plugin)" kube_add_cert_manager \
        --kube_config="$(kubeconf)" \
        --version="${v_certmgmr?}" \
        --email="$email" \
        --zone="$domain"
}

function install_ext_dns {
    K -n external-dns get pods | grep external-dns && return "$SKIP_PRESENT"
    shcmd ops "$(dns_ops_plugin)" kube_add_ext_dns \
        --kube_config="$(kubeconf)" \
        --version="$v_ext_dns" \
        --zone="$domain" \
        --gw_api=true
}

function install_app_namespaces {
    ops kubectl add_registry_auth --kube_config="$(kubeconf)" --private_registry="$private_registry" --namespaces="$app_namespaces"
}
function install_contour_gw_api {
    local i
    if [[ $api_base =~ hetzner ]]; then i="hetzner"; fi
    if [[ $api_base =~ digitalocean ]]; then i="digitalocean"; fi
    test -z "$i" && die "Can not determine infra name from $api_base"
    shcmd ops kubectl --kube_config="$(kubeconf)" add_contour_gw_api --region="$region" --infra_name="$i"
}
function test_kube {
    local pn
    pn="$(K -n kube-system get pods | grep local-path | cut -f 1 -d ' ')"
    test -z "$pn" && die "No pod: local-path-provisioner)"
    shcmd K -n kube-system exec -ti "$pn" -- cat /etc/resolv.conf
    shcmd K -n kube-system exec -ti "$pn" -- ping -c 1 google.com
}

do_ get_kubeconfig
do_ rm_master_node_label
if [[ $api_base =~ hetzner ]]; then do_ install_hetzner_ccm; fi
if [[ $api_base =~ digitalocean ]]; then do_ install_digital_ocean_ccm; fi
do_ install_cilium
do_ install_cert_mgr
do_ install_ext_dns
if [[ -n "$app_namespaces" ]]; then do_ install_app_namespaces; fi
do_ install_contour_gw_api
do_ test_kube
#do_ install_ext_dns
#do_ install_dns_issuer

# begin-archive
# function install_ext_dns {
#     function inst_ext_dns {
#         HELM -n kube-system install external-dns \
#             --set provider=digitalocean \
#             --set digitalocean.apiToken="(secret.do_token)s" \
#             --set policy=sync \
#             bitnami/external-dns
#     }
#     inst_ext_dns || {
#         HELM repo add bitnami https://charts.bitnami.com/bitnami
#         inst_ext_dns || exit 1
#     }
# }
#
# function install_dns_issuer {
#     echo -e '
#   apiVersion: cert-manager.io/v1
#   kind: ClusterIssuer
#   metadata:
#     name: letsencrypt-dns
#   spec:
#   acme:
#     server: https://acme-v02.api.letsencrypt.org/directory
#     email: '$email'
#     # Name of a secret used to store the ACME account private key
#     privateKeySecretRef:
#       name: letsencrypt-dns
#     solvers:
#     - dns01:
#         digitalocean:
#           tokenSecretRef:
#             name: digitalocean-dns
#             key: access-token
# ' >dns_issuer.yaml
#
#     until (K -n kube-system apply -f dns_issuer.yaml); do
#         echo 'cert manager not ready yet. '
#         sleep 4
#     done
# }
