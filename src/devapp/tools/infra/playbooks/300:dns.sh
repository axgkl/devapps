#!/bin/bash

_='# Register DNS

  For internal and external ips of cluster

  ## Required Environ Vars

  - $domain
  - $dns_provider: E.g. "digitalocean"
  - $dns_provider_token_cmd: E.g. "pass show DO/token"

  and also one private network ip configured on each host.
'

source "%(feature:functions.sh)s"

# part: name eq local

echo "%(wait:200:all.ip_priv)s"
export domain_name="$cluster_name.$domain"
export ttl="${ttl:-120}"
export log_fmt=3
function do_dns {
    local n="$1" ipi ipe
    ipi="$(kv "$1" ip_priv)"
    ipe="$(kv "$1" ip)"
    ops dns add_a_record --host_name="$n-int" --ips="$ipi"
    ops dns add_a_record --host_name="$n-ext" --ips="$ipe"
}

ops dns delete_domain || true
ops dns add_domain
for n in $(echo $names); do do_dns "$n"; done
