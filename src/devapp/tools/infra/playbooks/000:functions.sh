#!/bin/bash
_='# Useful functions

  This is run at the very start and creates /root/functions.sh, which all others source
'
cluster_name="%(env.cluster_name)s"
dir_project="%(env.dir_project)s"
names="%(env.names)s"
function_filter="%(env.function_filter)s"

SKIP_PRESENT=20

function set_fact { echo -e "%(marker)s \x1b[48;5;56m$1\x1b[0m $2"; }
function deindent {
    (
        IFS='' # drop only once (i.e. the first) 4 spaces:
        while read -r line; do echo "${line/    /}"; done
    )
}
function die {
    echo -e "\x1b[48;5;124mERROR $name: $*\x1b[0m"
    set_fact ERR "$*"
    exit 1
}

function have { type $1 1>/dev/null 2>/dev/null; }
function h1 {
    echo -e "\x1b[1;38;49m $name \x1b[1;30;41m $*\x1b[0;37m"
}
function info {
    echo -e "INFO: $name $*"
}

function do_ {
    local filter="$function_filter"
    test "$1" == "always" && {
        filter=
        shift
    }

    local func="$1"
    test -z "$filter" || {
        if [[ $func != *$filter* ]]; then
            h1 "$func skipped (filtered)"
            return 0
        fi
    }
    h1 "$func"
    eval "$@"
    local res=$?
    test $res == $SKIP_PRESENT && {
        h1 "$func skipped (present already)"
        return 0
    }
    test $res != 0 && die "$1 failed"
    return $res
}
function shcmd {
    info "$@"
    eval "$@"
}

function transfer {
    local src="$1"
    local dst="$2"
    local ip="$3"
    mkdir -p "$(dirname "$dst")"
    scp_ "root@$ip:$src" "$dst"
}

function transfer_kubeconfig {
    local fn api_host ip
    api_host="${2?}"
    ip="${3?}"
    fn="$(kubeconf)"
    transfer "$1" "$fn" "$ip"
    sed -i "s/127.0.0.1/${api_host}/g" "$fn"
    chmod 600 "$fn" # helm says group readable is unsecure
    touch environ
    # adding all fo them, user can comment then:
    echo "export KUBECONFIG=\"$fn\"" >>"$dir_project/environ"
    echo "source $dir_project/environ, to activate KUBECONFIG=$fn"
    # takes a while (ssl)
    for i in 1 2 3 4 5; do
        K get nodes --request-timeout=2 --show-labels | grep kubernetes.io && return
        sleep 1
    done
    die "local kubectl failed"
}

# query the drops cache by node and key:
function kv { cat "$fn_cache" | jq -r '."'$1'"."'$2'"'; }

function kubeconf { echo "$dir_project/conf/k8s/$cluster_name/config.yaml"; }

function K {
    export KUBECONFIG="$(kubeconf)"
    kubectl "$@"
}

function HELM {
    export KUBECONFIG="$(kubeconf)"
    helm "$@"
}

function pkg_inst {
    local i
    type apt 2>/dev/null && i=apt || i=dnf
    info "package system is $i"
    $i install -y "$@"
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
