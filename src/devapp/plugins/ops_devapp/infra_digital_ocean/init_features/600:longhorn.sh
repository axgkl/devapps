#!/bin/bash

source "%(feature:functions.sh)s"

# part:
function install_longhorn_tools {
	yum --setopt=tsflags=noscripts install -y iscsi-initiator-utils nfs-utils
	systemctl enable --now iscsid
}

systemctl status iscsid >/dev/null || install_longhorn_tools

add_result have_longhorn_tools true

# part:local: name contains control
echo "have all longhorn tools: %(all.have_longhorn_tools)s"
K version
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn \
	--namespace longhorn-system --create-namespace \
	--set service.ui.loadBalancerIP="$ip" \
	--set service.ui.type="LoadBalancer"
