# CI/CD Setup

devapps repos may be hosted on internal package servers, then we use [gitlab-runners][glr] to run CI/CD jobs.

!!! note
    gitlab-runners are available for all major OS. `devapps` and derived packages builds are run on Linux only.


1. [Download][gl] the runner for your architecture
2. Configure tokens and repository CI support as explained in the [documentation][gl]

In order for a runner to be able to build devapps we configure this in addition:



## Access to python versions via conda.

With conda in `/data/miniconda3` in this example:

```ini
[gitlab-runner@doglr ~]$ cat /etc/systemd/system/gitlab-runner.service
[Unit]
Description=GitLab Runner
After=syslog.target network.target
ConditionFileIsExecutable=/usr/local/bin/gitlab-runner

[Service]
StartLimitInterval=5
StartLimitBurst=10
Environment=PATH=/data/miniconda3/bin:/data/miniconda3/envs/py38/bin:/root/.local/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/root/bin
ExecStart=/usr/local/bin/gitlab-runner "run" "--working-directory" "/mnt/volume_fra1_01/gitlab-runner" "--config" "/etc/gitlab-runner/config.toml" "--service" "gitlab-runner" "--syslog" "--user" "gitlab-runner"

Restart=always
RestartSec=120

[Install]
WantedBy=multi-user.target


```

## Access to Private Artifactory

```toml
[gitlab-runner@doglr pypoetry]$ pwd
/data/gitlab-runner/.config/pypoetry
[gitlab-runner@doglr pypoetry]$ cat auth.toml
[http-basic]
[http-basic.ax]
username = "klessinger"
password = "xxxxxxxxxxxxxxxxxxxxxx" # use the hashed one on third party machines


[gitlab-runner@doglr pypoetry]$ cat config.toml
[repositories]
[repositories.ax]
url = "https://artifacts.github.com/artifactory/api/pypi/pypi-ax-sources/simple/"

```

## Tmux

Configure the base index to be 1 for literate programming docu builds in `$HOME/.tmux.conf`:

```tmux
[gitlab-runner@doglr ~]$ cat .tmux.conf
set-option -g base-index 1
set-window-option -g pane-base-index 1
```

!!! note
    If no tmux config file is found at an lp step, we automatically do create one, with the content above. 


## git

Setup git - some `doc pre_process` doc building steps do commit the changed pages:

```bash
$ git config --global user.email gitlab-runner@<hostname>
$ git config --global user.name "gitlab-runner"
```


# CI Files

## Adding Development Versions of Other Repos


!!! tip "CI with development versions"
    Should you temporarily need *development versions* of other repos of the devapps family you can do it like so in your
    `.gitlab-ci.yml` file:

    Example: dev. version of lc-doctools required:

    ```yaml
    variables:
      PIP_CACHE_DIR: "${CI_PROJECT_DIR}/.cache/pip"
      # until we have a fixed version we use a development version:
      PYTHONPATH: "${CI_PROJECT_DIR}/build/lc-doctools/src"
      make_autodocs: "true"
      HGUSER: cibuild # for badges


    cache:
      key: "${CI_JOB_NAME}"
      key: lc_devapp_38
      paths:
        - .cache/pip
        - .venv

    stages:
      #- quality
      - doctests

    # TODO: remove this cloning when version is fix:
    .install-deps-template: &install-deps
      before_script:
        - env # print the environ
        - mkdir build
        - git clone "https://gitlab-ci-token:${CI_JOB_TOKEN}@mycompany.com/devapps/lc-doctools.git" "build/lc-doctools"
        - poetry --version
        - poetry debug
        - poetry config virtualenvs.in-project true --local
        - poetry install -vv
      tags:
    (...)

    ```

!!! warning
    There will be a rather prominent warning in your built documentation when you built using non released dependencies!


[glr]: https://docs.gitlab.com/runner/
[gl]: https://docs.gitlab.com/runner/install/

