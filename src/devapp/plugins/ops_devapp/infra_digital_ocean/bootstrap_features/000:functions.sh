#!/bin/bash
_='# Useful functions

This is run at the very start and creates /root/functions.sh, which all others source
'

ip="%(ip)s" # causes wait for droplet ip
name="%(name)s"

function add_result { echo "%(marker)s $1 $2"; }

function transfer {
	local src="$1"
	local dst="$2"
	mkdir -p "$(dirname "$dst")"
	scp_ "root@$ip:$src" "$dst"
}

function transfer_kubeconfig {
	local fn="$(pwd)/conf/k8s/%(name)s/config.yaml"
	transfer "$1" "$fn"
	sed -i "s/127.0.0.1/$ip/g" "$fn"
	touch environ
	# adding all fo them, user can comment then:
	echo "export KUBECONFIG=\"$fn\"" >>environ
	echo "source environ to activate KUBECONFIG=$fn"
}

function scp_ { scp -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"; }

function ssh_ { ssh -o StrictHostKeyChecking=no -o UserKnownHostsFile=/dev/null "$@"; }

function waitproc {
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

return 2>/dev/null
mv "$0" functions.sh
