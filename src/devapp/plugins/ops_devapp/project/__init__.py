#!/usr/bin/env python
"""
# Creating A Project With Resources

This plugin is helper for creating a project directory, incl. required local resources.
Your system remains unchanged, except <project_dir> and <conda_prefix>.

It provides an `install` action (implicitely by providing the --init_resource_match or --init_at switch)

Default action is: `list` (show installable resources, -m <match> filters).

At install we will (re-)initialize a "project_dir", at location given with --init_at (default: '.'), incl:

- Installing available resources, like databases and tools within a given directory (conda_prefix)

- Creating resource start wrappers in <project_dir>/bin

- Generating default config when required

- Optionally generating systemd unit files (e.g. via: --init_create_all_units)

- Instances support: export <name>_instances=x before running and you'll get x systemd units created, for startable commands.
    Example: export client_instances=10; ops p -irm client -icau
    (Name of a resource: ops p [-m <match>])

- Any other parametrization: Via environ variables
  Check key environ vars in list output and also doc text.

Privilege escalation is not required for any of these steps.
"""
# Could be done far smaller.
from re import match
from devapp import gevent_patched
import hashlib
import json
import os
import shutil
from copy import deepcopy
from functools import partial

import requests
from devapp.app import FLG, app, run_app, do, system
from devapp import tools
from devapp.tools import (
    exists,
    to_list,
    repl_dollar_var_with_env_val,
    project,
    read_file,
    write_file,
)
import devapp.tools.resource as api
from .devinstall import dev_install


class Flags(api.CommonFlags):
    autoshort = ''

    class force:
        n = 'Assume y on all questions. Required when started w/o a tty'
        d = False

    class force_reinstall:
        n = 'Do not only install resources detected uninstalled but reinstall all'
        d = False

    class init_at:
        n = 'Set up project in given directory. env vars / relative dirs supported. Sets install action implicitly'

    class dev_install:
        n = 'Set the project up in developer mode - incl. make and poetry file machinery'
        d = False

    class init_create_all_units:
        n = 'If set we create unit files for ALL service type resources'
        d = False

    class init_create_unit_files:
        """Valid: Entries in rsc.provides, rsc.cmd or rsc.exe (i.e. the filename of the wrapper in bin dir). Not: rsc.name."""

        n = 'List service unit files you want to have created for systemctl --user.'
        d = []

    class resource_match:
        s = 'm'
        n = 'Provide a match string for actions. Examples: -irm "redis, hub" or -irm \'!mysql, !redis\' (! negates).'
        d = []

    class init_resource_match:
        n = 'Like resource match but implies install action'
        d = []

    class add_post_process_cmd:
        n = 'Add this to all commands which have systemd service units. Intended for output redirection. Not applied when stdout is a tty.\n'
        n += """Example: -appc='2>&1 | rotatelogs -e -n1 "$logfile" 1M' ($logfile defined in wrapper -> use single quotes).\n"""
        n += 'Tip: Use rotatelogs only on powers of 10 - spotted problems with 200M. Use 100M or 1G in that case.'
        d = ''

    class edit_matching_resource_file:
        n = 'Open resource files in $EDITOR, matching given string in their content'
        d = ''

    class delete_all_matching_service_unit_files:
        n = 'This removes all matching unit files calling devapp service wrappers. Say "service" to match all'
        d = ''

    class Actions:
        class list:
            n = 'Show available definition files.'
            d = True

        class list_resources_files:
            n = 'Alias for list action'
            d = False

        class install:
            d = False


S = api.S


def create_project_dirs():
    ds = ['bin', 'data', 'log', 'work', 'conf', 'tmp', 'build']
    D = project.root()
    if not FLG.fs_dir:
        ds.append('fs')
    for d in ds:
        d = D + '/' + d
        if not exists(d):
            app.info('creating', dir=d)
            os.makedirs(d)
        else:
            app.debug('exists already', dir=d)


def git_init():
    D = project.root()
    if not exists(D + '/.git'):
        do(system, 'git init')
    fn = D + '/.gitignore'
    if not exists(fn):
        s = '\n'.join(['data/', 'log/', '*.py[cod]'])
        write_file(fn, s)


import sys


def rscs_dicts(rscs):
    return [api.to_dict(r) for r in rscs]


def rscs_details(rscs):
    return app.info('Resource details', json=rscs_dicts(rscs))


def confirm(d, rscs):
    cu = 'Reconfiguring' if exists(d) else 'Creating'
    L, O = '\x1b[0;38;5;240m', '\x1b[0m'
    matching_units = []

    def n(r, u=matching_units):
        n = r.name
        g = api.g
        if FLG.init_create_all_units:
            matching_units.extend(to_list(str(g(r, 'systemd', None))))
        # if given one by one:
        units = g(FLG, 'init_create_unit_files', [])
        cmds = api.rsc_cmds(r)
        for c in cmds:
            # that check is also in write_resource! don't change only here:
            if any([u for u in units if u == c]):
                matching_units.append(c)

        p = getattr(r, 'provides', '')
        if p:
            n += ' [%s]' % ' '.join(r.provides)
        return L + n + O if getattr(r, 'installed') else n

    rsc = '\n - '.join(n(r) for r in rscs)
    mu = list(set(matching_units))
    units = 'Unit files:           ' + ('-' if not mu else ', '.join(mu)) + '\n'
    r = [
        '',
        cu + ' project directory %s' % d,
        '',
        'Conda resources into: %s' % api.S.conda_prefix,
        'Filesystem rscs into: %s' % api.S.fs_dir,
        units,
        'Resources: \n - %s' % rsc,
        '',
        'Confirm [Y|q|d:details|f:force non interactive install]: ',
    ]
    return '\n'.join(r)


def verify_systemctl_availability():
    if 'linux' not in sys.platform.lower():
        app.die('System platform must be Linux for unit files')
    if os.system('type systemctl'):
        app.die('Systemd must be present for unit files')


def start_editor(finder=api.find_resources_files_in_sys_path):
    m = finder().items()
    for mn, fn in m:
        print()
        app.info(fn, module=mn)
        s = read_file(fn)
        if FLG.edit_matching_resource_file in s:
            do(system, '$EDITOR "%s"' % fn)
    return mn


def delete_all_matching_service_unit_files(match):
    d = os.environ.get('HOME') + '/.config/systemd/user'
    for fn in os.listdir(d):
        if match not in fn:
            app.info('Skipping not matching unit', fn=fn)
        fn = d + '/' + fn
        if not os.path.isfile(fn):
            continue
        s = read_file(fn)
        if api.unit_match in s:
            app.warn('Unlinking unit file', fn=fn)
        app.info('Skipping unit without match string', match=api.unit_match)


class disabled:
    rscs = ()


def get_matching_resources():
    m = FLG.init_resource_match
    m.extend(FLG.resource_match)
    negates = []
    for u in list(m):
        if u.startswith('!'):
            m.remove(u)
            negates.append(u[1:])
    r = api.find_resource_defs()
    rscs = S.rscs_defined
    api.add_install_state(rscs)

    # matches = lambda r: any([_ in str(api.to_dict(r)) for _ in m])
    def matches(rsc, m=m):
        r = api.to_dict(rsc)
        for _ in m:
            if (
                str(r.get('systemd')) == _
                or str(r.get('cmd')).startswith(_)
                or str(r.get('name')).startswith(_)
            ):
                return True

    rscs = [r for r in rscs if not m or matches(r, m)]
    if negates:
        n = negates
        rscs = [r for r in rscs if not any([_ in str(api.to_dict(r)) for _ in n])]
    disabled.rscs = d = [
        r for r in rscs if r.disabled is True and not matches(r) and not r.installed
    ]
    if d:
        app.info('Disabled (only via -irm)', resources=[i.name for i in d])
    [rscs.remove(r) for r in list(rscs) if r in d]
    return rscs


def run():
    if FLG.install or FLG.init_resource_match or FLG.init_at:
        # backwards compat
        FLG.init_at = FLG.init_at or '.'
        FLG.list = False
        FLG.install = True

    if FLG.list_resources_files or FLG.list:
        rscs = get_matching_resources()
        app.info('Listing Defined Resources')
        app.info('details', json=rscs_dicts(rscs))
        return [r for r in rscs]

    m = FLG.delete_all_matching_service_unit_files
    if m:
        return do(delete_all_matching_service_unit_files, match=m)

    if FLG.edit_matching_resource_file:
        return start_editor()

    # the project directory:
    d = FLG.init_at
    if not d:
        return app.error('No project dir given')

    d = repl_dollar_var_with_env_val(d)
    d = os.path.abspath(d)
    d = d[:-1] if d.endswith('/') else d
    if not exists(d):
        app.die('Not exists', dir=d)
    do(os.chdir, d)
    d = FLG.init_at = os.path.abspath('.')
    project.set_project_dir(dir=d)

    rscs = get_matching_resources()
    project.set_project_dir(dir=d)
    if FLG.init_create_unit_files:
        do(verify_systemctl_availability)

    if not (sys.stdin.isatty() and sys.stdout.isatty()) and not FLG.force:
        app.die('Require --force when run without a tty')

    if FLG.force:
        app.warn('Installing resources', resources=rscs)
    else:
        while True:
            y = input(confirm(d, rscs))
            if y.lower() in ('n', 'q'):
                app.die('Unconfirmed, stopping installation')
            if y.lower() == 'd':
                rscs_details(rscs)
                continue
            if y.lower() == 'f':
                FLG.force = True
            print()
            break

    do(create_project_dirs)
    do(os.chdir, d)
    if FLG.dev_install:
        do(dev_install)

    for r in rscs:
        do(api.Install.resource, r, ll=10)

    do(git_init)
    if FLG.init_create_unit_files:
        app.info('All project file created.')
        app.info('Enabling systemd user service units.')
        if not os.system('systemctl --user --no-pager status | head -n0'):
            app.info('systemd --user available, calling daemon-reload')
            if not os.system('systemctl --user daemon-reload'):
                return app.info('Done init.')

        app.warn('systemd --user service seems not running', hint=T_SDU_SVD)
        # automatic installs must get an error when this happens:
        app.die('Failing the project init command, please fix systemd --user')


# https://serverfault.com/a/1026914 - this is really relevant,
# since RH and drives deployers crazy on first command!
T_SDU_SVD = """
We are using the systemd **user** service to manage processes. This means there is a systemd process that runs as unprivileged user. 
The systemd user service is not used as commonly as the normal systemd process manager.
For example Red Hat disabled the systemd user service in RHEL 7 (and thereby all distros that come from RHEL, like CentOS, Oracle Linux 7, Amazon Linux 2).
However, RedHat has assured that running the systemd user service is supported as long as the service is re-enabled.

This is how to start the `systemd --user service` for user with $UID=_UID_ (the current user):

As root create this unit file:

____________________________________________________________________________________________________

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

____________________________________________________________________________________________________

Then enable and start the unit.

Run `ps -fww $(pgrep -f "systemd --user")` to verify success, then try re-init the project.
"""

T_SDU_SVD = T_SDU_SVD.replace('_UID_', str(os.getuid()))


def main():
    return run_app(run, flags=Flags)


if __name__ == '__main__':
    main()
