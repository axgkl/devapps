#!/bin/bash
_='# Kind Installation

## Requirments

Docker installed and running (feature docker)
'

cluster="%(env.cluster_name|kind)s"
nodes="%(env.cluster_nodes|3)s"

fn="$cluster/kind_config.yaml"
mkdir -p "$cluster"

function write_config {
	echo -e '
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
networking:
  apiServerAddress: "%(ip)s"
nodes:
- role: control-plane' >"$fn"
	# extraPortMappings:
	# - containerPort: 80
	#   hostPort: 80
	#   listenAddress: "0.0.0.0" # Optional, defaults to "0.0.0.0"
	#	   protocol: udp # Optional, defaults to tcp' >"$fn"
	for _ in $(seq 1 $nodes); do echo '- role: worker' >>"$fn"; done
}

function inst_kind {
	local fk="/usr/local/bin/kind"
	test -e "$fk" && return 0
	curl -Lo "$fk" "https://kind.sigs.k8s.io/dl/v0.14.0/kind-linux-amd64"
	chmod +x "$fk"
}

write_config
inst_kind
kind create cluster --name "$cluster" --config "$fn"

# part:local: name
transfer_kubeconfig "/root/.kube/config"
