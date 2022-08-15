#!/bin/bash

_='# Install Tools

'

source "%(feature:functions.sh)s"

# part: name not eq local
pkg_inst net-tools tcpdump tcpflow dnsutils lvm2 parted

h1 "configure forwarding"
echo 'net.ipv4.ip_forward=1' >>/etc/sysctl.d/99-sysctl.conf
echo 'net.ipv6.conf.all.forwarding=1' >>etc/sysctl.d/99-sysctl.conf
/sbin/sysctl -p
