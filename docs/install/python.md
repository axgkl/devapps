# Installing Python 

Python is *the* base requirement for any devapp. 

This base package requires minimum Python 3.7 but derived apps may require higher versions.


!!! summary "Python Environment"

    We highly recommend to not use the Python of your host system but install within a dedicated
    environment.

    To install Python versions, there are many options, incl. <a
    href="https://docs.conda.io/projects/conda/en/latest/user-guide/install/linux.html"><code>miniconda</code></a>,
    <a href="https://github.com/pyenv/pyenv"><code>pyenv</code></a> or packages of your
    distribution.</summary>.


Subsequently we explain the two ways of installing and activating a specific Python version, which
do not require root permissions and are contained within directories.


## Conda

Conda or its lighther variant [Miniconda](https://docs.conda.io/projects/conda/en/latest/) is a
binary package dependency management and deployment system.

It allows to install not only Python in any version under one base environment but also other
resources, e.g. redis, nodejs or other databases, w/o "spamming" your filesystem outside of the base
directory.   This can be done conflict free, within prefixes
([environments](https://docs.conda.io/projects/conda/en/latest/user-guide/tasks/manage-environments.html)).

> Conda is comparable to the homebrew packaging system but not dependent on a fixed directory within
> `/usr/local`. A [localized][cl] homebrew is very similar to Conda (but restricted to OSX only,
> i.e. no option for us).

[cl]: https://medium.com/macoclock/a-clean-approach-to-installing-homebrew-d17c797fb045

Installation is simple and described [here](https://conda.io/projects/conda/en/latest/user-guide/install/index.html).

On Linux:

```bash
curl 'https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh' -O install.sh
chmod +x install.sh
./install.sh -b # installs non interactively into $HOME/miniconda3

# makes the conda command available (consider an alias within e.g. your .bashrc):
source miniconda3/etc/profile.d/conda.sh 

# we can now install any python version within the base environment like so:
conda  create -n py38  python=3.8
# and activate, not leaving your current shell process:
conda activate py38

```

!!! success "Activation not required to run"
    Like with homebrew, any installed binary can be executed without previous
    activation of its environment.

    Example: `$HOME/miniconda3/envs/myredis/bin/redis-server` will work.


## Pyenv

If you "only" require Python, then `pyenv` is a more lightweight way than conda.

```bash
# install pyenv
git clone https://github.com/pyenv/pyenv ~/.pyenv

# setup pyenv (you should also put these three lines in .bashrc or similar)
export PATH="${HOME}/.pyenv/bin:${PATH}"
export PYENV_ROOT="${HOME}/.pyenv"
eval "$(pyenv init -)"

# install Python 3.8
pyenv install 3.8

# make it available globally
pyenv global system 3.8
```

