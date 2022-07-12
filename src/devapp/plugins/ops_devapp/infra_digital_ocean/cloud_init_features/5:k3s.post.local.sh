#!/bin/bash
mkdir -p conf
fn="$(pwd)/conf/k3s.yaml"
scp root@$ip:/etc/rancher/k3s/k3s.yaml "$fn"
sed -i "s/127.0.0.1/$ip/g" "$fn"
touch environ
grep -v KUBECONFIG <environ >environ.1
echo 'export KUBECONFIG="'$fn'"' >>environ.1
mv environ.1 environ
type kubectl 2>/dev/null && {
	export KUBECONFIG="$fn"
	kubectl get nodes
}
echo "source environ to activate KUBECONFIG=$fn"
