# Gitlab Runner (in User Mode)

With docu tools

Note:

Call `/opt/devapps/home_devapps/gitlab_runner/build/bin/gitlabrunner.gitlab register` only once
afer install (otherwise you'll have tons of runners, if done in ExecStartPre)

Unlock in devapps for other projects

Change tags away from production



## Troubleshooting

plantuml fails with gconf error

Solution: apt-get install libgconf-2-4. Seems to be a host conda  jre dependency


Runner does work when started in foreground but not in systemd

Solution: Move .bash_logout away (https://gitlab.com/gitlab-org/gitlab-runner/issues/3849)



