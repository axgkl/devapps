#!/bin/bash
_='# Docker Installation

Fedora only version for now
'

source "%(feature:functions.sh)s"

function docker_inst {
	echo 'Installing docker'
	dnf -y install dnf-plugins-core
	dnf config-manager --add-repo https://download.docker.com/linux/fedora/docker-ce.repo
	waitproc no rpm
	dnf install -y docker-ce docker-ce-cli containerd.io docker-compose-plugin
	systemctl enable --now docker
	sleep 1
	docker info
}
docker info || docker_inst
