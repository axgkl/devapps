#!/bin/bash
_='# Adds a sudo user

NOPASSWD is set.


## Requirements

Filesystem must have sudo installed.
'

user="%(flag.user)s"
function add_user {
	adduser $user
	cp -a /root/.ssh /home/$user/
	chown -R $user /home/$user/.ssh
	echo "$user     ALL=(ALL)       NOPASSWD: ALL" >>/etc/sudoers
}

test -d "/home/$user" || add_user
