#!/bin/bash
_='# Useful functions

This is run at the very start and creates /root/functions.sh, which all others source
'
ip="$ip"
dir_project="$dir_project"
name="$name"
cluster_name="$cluster_name"
nodes="$nodes"

function add_result { echo "%(marker)s $1 $2"; }

function h1 {
    echo -e "\x1b[1;38;49m $name \x1b[1;30;41m $*\x1b[0;37m"
}

function do_ {
    h1 "$1"
    eval "$@"
}

function transfer {
    local src="$1"
    local dst="$2"
    mkdir -p "$(dirname "$dst")"
    scp_ "root@$ip:$src" "$dst"
}

function transfer_kubeconfig {
    local fn="$(kubeconf)"
    transfer "$1" "$fn"
    sed -i "s/127.0.0.1/$ip/g" "$fn"
    touch environ
    # adding all fo them, user can comment then:
    echo "export KUBECONFIG=\"$fn\"" >>"$dir_project/environ"
    echo "source $dir_project/environ, to activate KUBECONFIG=$fn"
}

function kubeconf { echo "$dir_project/conf/k8s/$cluster_name/config.yaml"; }

function K {
    export KUBECONFIG="$(kubeconf)"
    kubectl "$@"
}

function HELM {
    export KUBECONFIG="$(kubeconf)"
    helm "$@"
}

function scp_ { scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"; }

function ssh_ { ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"; }

function waitproc {
    # wait until a process is completed or present
    local no=false
    test "$1" == "no" && {
        no=true
        shift
    }
    while true; do
        $no && { pgrep "$1" || return 0; }
        $no || { pgrep "$1" && return 0; }
        sleep 1
        echo "awaiting $1"
    done

}

return 2>/dev/null || mv "$0" "functions.sh"
