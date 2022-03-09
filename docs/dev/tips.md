# Developer Tips

Assorted Tips for Developing on DevApps packages.

## Documentation

Can be dynamic, with assertions. See [docutools][d] for more. 

[d]: https://axiros.github.io/docutools/features/lp/parameters/


## CI/CD

### `Failed to connect to bus: No such file or directory`

We are using the systemd **user** service to manage processes. This means there is a systemd process
that runs as unprivileged user. The systemd user service is not used as commonly as the normal
systemd process manager. For example Red Hat disabled the systemd user service in RHEL 7 (and
thereby all distros that come from RHEL, like CentOS, Oracle Linux 7, Amazon Linux 2). However,
RedHat has assured that running the systemd user service is supported as long as the service is
re-enabled.

This is how to start the `systemd --user service` for user with $UID=_UID_ (the current user):

As root create this unit file:

____________________________________________________________________________________________________

```
# cat /etc/systemd/system/user@_UID_.service

[Unit]
Description=User Manager for UID %i
After=systemd-user-sessions.service
# These are present in the RHEL8 version of this file except that the unit is Requires, not Wants.
# It's listed as Wants here so that if this file is used in a RHEL7 settings, it will not fail.
# If a user upgrades from RHEL7 to RHEL8, this unit file will continue to work:

After=user-runtime-dir@%i.service
Wants=user-runtime-dir@%i.service

[Service]
LimitNOFILE=infinity
LimitNPROC=infinity
User=%i
PAMName=systemd-user
Type=notify
# PermissionsStartOnly is deprecated and will be removed in future versions of systemd
# This is required for all systemd versions prior to version 231
PermissionsStartOnly=true
ExecStartPre=/bin/loginctl enable-linger %i
ExecStart=-/lib/systemd/systemd --user
Slice=user-%i.slice
KillMode=mixed
Delegate=yes
TasksMax=infinity
Restart=always
RestartSec=15

[Install]
WantedBy=default.target

```

____________________________________________________________________________________________________

Then enable and start the unit.

```
Run `ps -fww $(pgrep -f "systemd --user")` to verify success, then try re-init the project.
'''

[Here](https://help.tableau.com/current/server-linux/en-us/systemd_user_service_error.htm) is more information.


In order to debug failing jobs you'll want to run them in foreground, logged in as **another user**, then `su - gitlab-runner`. When you get this error at `systemctl --user status`:

- loginctl enable-linger gitlab-runner  # starts dbus
- export XDG_RUNTIME_DIR=/run/user/$UID # in .bashrc of gitlab-runner


### Get exactly environ of runner

- do `- poetry run env | tee | grep PATH > env` in the before-script section of .gitlab-ci.yml
- then `set -a && source ./env && set +a` in your debug session, after `poetry shell`.



### Start gitlab-runner within nspawned Container

This has isolation advantages and also you can instantly restart the whole machine, stopping every system service
started at failed jobs.


Example: `systemd-nspawn -D debian_filesystem -b` (filesystem e.g. from `docker pull debian`, then `docker export <containerId> | tar -xf .`)

To run a whole CI/CD cycle, including docs:

1. `apt-get install make gcc wget curl mercurial locales lsof # for docutools`
1. install gitlab runner, give it a specific tag, which you configure in your `.gitlab-ci.yml`
1. install $HOME/miniconda3
1. Add `.config/pypoetry/auth.toml` and `config.toml` for artifactory
1. Configure base-index 1 for tmux (for literate programming docu)

Now you can have commits in repos with the tag built by firing up the container:

```bash
1.~$ alias gitlab
alias gitlab='sudo systemd-nspawn -D debian_filesystem -b -M gitlab'
```

Stop the whole machine any time with ctrl-[[[



#### Manual Start of Runner

Then you can manually run CI/CD jobs:

1. Login as gitlab-runner user
1. In home dir say: `gitlab-runner --debug run` 
1. Push a commit - watch it build
1. Then stop and check if started as service, i.e. at nspawn container boot.

!!! note "Trouble Shooting"

    - To be able to login add console and pty/0 into etc/securetty 
    - If you change the runner user away from gitlab-runner, the unit file has the be adapted
      manually (not done by install routine)
    - `Ctrl-]]]` powers the container off (immediate hard shutdown)




