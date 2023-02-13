#!/bin/bash
# vim: set sw=4

_='# Hypermoden Kube Setup
  
  - GatewayAPI
  
  ## Conventions:
  
  Server must have seen 502:k3s
  
  ## Env Parameters
  
  - None: None at this time
  
  ## Examples
  
  
  ## Misc
  
  
  '

source "%(feature:functions.sh)s"
function define_vars_and_functions {
    set -a
    D="%(!$dir_project)s"
    api_base="%(!$infra_api_base)s"
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

# part: ========================================================== name eq local

function check_kube_con {
    K get nodes
}

do_ check_kube_con
