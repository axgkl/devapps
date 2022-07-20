#!/bin/bash
_='# Adds a sudo user

NOPASSWD is set.

This will be run automatically if --user is not "root"

## Requirements

Filesystem must have sudo installed.
'
user="%(flag.user)s"
adduser $user
cp -a /root/.ssh /home/$user/
chown -R $user /home/$user/.ssh
echo "$user     ALL=(ALL)       NOPASSWD: ALL" >>/etc/sudoers
