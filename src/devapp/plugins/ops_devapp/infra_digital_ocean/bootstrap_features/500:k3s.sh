#!/bin/bash

_='# Deploy a single server k3s.

- Server config for kubectl is put to ./conf/ks.yaml
- Locally we add the KUBECONFIG variable pointing to server config into a file "./environ"

## Conventions:

Server must have "server" within its name.

## Env Parameters

- selinux[=true]: When false, install without SELINUX context (install much faster)

## Examples

- 4 Node server cluster:

	ops infra_digital_ocean droplet_create --features k3s --name k2{} --range server,1,2,3 --size M

- Same with selinux off (faster install), relative time and by thread indication:

	selinux=false ops ido dc -f k3s -n k2{} -r server,1,2,3 -S M -ltf dt -latn

'

# cond: not env.selinux
setenforce 0
export INSTALL_K3S_SKIP_SELINUX_RPM=true
export INSTALL_K3S_SELINUX_WARN=true
# end cond

function inst_k3s {
	curl -sfL https://get.k3s.io | sh -
}

# cond: name contains server
function do_server {
	local fn="/var/lib/rancher/k3s/server/node-token"
	export INSTALL_K3S_EXEC='server'
	# we try install again when failed - which sometimes happens
	# right after boostrap, when rpm is still busy boostrapping:
	test -f "$fn" || (
		waitproc no rpm
		inst_k3s || exit 1
	)
	add_result k3s_server_token "$(cat "$fn")"
}
do_server

# else:
function do_worker {
	export K3S_TOKEN="%(wait:500:match:key.k3s_server_token)s"
	export K3S_URL="https://%(matched.ip)s:6443"
	export INSTALL_K3S_EXEC='agent'
	test -e "/var/lib/rancher/k3s/agent" || inst_k3s
}
do_worker
# end cond

# part:local: name contains server
transfer_kubeconfig "/etc/rancher/k3s/k3s.yaml"
