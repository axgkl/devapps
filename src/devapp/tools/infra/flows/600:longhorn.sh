#!/bin/bash

source "%(feature:functions.sh)s"

# cond: name not eq local
function install_longhorn_tools {
    yum --setopt=tsflags=noscripts install -y iscsi-initiator-utils nfs-utils
    systemctl enable --now iscsid
}

systemctl status iscsid >/dev/null || install_longhorn_tools
set_fact have_longhorn_tools true

# else:
echo "have all longhorn tools: %(all.have_longhorn_tools)s"
K version
helm repo add longhorn https://charts.longhorn.io
helm repo update
helm install longhorn longhorn/longhorn \
    --namespace longhorn-system --create-namespace \
    --set service.ui.loadBalancerIP="164.92.191.230" \
    --set service.ui.type="LoadBalancer"
# end
