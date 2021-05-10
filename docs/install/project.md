# Creating Products and Projects Using Devapps

Build tool is [poetry](https://python-poetry.org/) 

## Scaffolding

We offer a product scaffolding set of templates, installing the basic layout
of a devapps project:

1. Install [`copier`](https://copier.readthedocs.io/en/stable/).
2. Clone  https://github.com/pawamoy/copier-poetry.git to get the templates.
3. Run `copier copier-poetry <your new product (or project)>` 
4. Adapt the files to your liking


!!! note Copier
    In contrast to other scaffolding tools like cookiecutter copier does allow
    updates, when the templates update.


## Makefile

The makefile allows various dev related actions. For most actions it calls
`duties.py`, which uses [poetry](https://python-poetry.org/) to run actions.

`make setup` installs a virtual environment, based on your `pyproject.toml`.


## Products involving Node-RED

Instead of raw `devapps` configure [`lc-python`](http://pages.github.com/lc-python/) as main dependency within your
pyproject.toml. It comes additionally with python and javascript modules and
tools for handling Nodejs / Node-RED.

## Developping on Many Repos Concurrently

A devapps project or product repo may directly or indirectly depend on other repos of the devapps
familiy. 


- [`lc-doctools`](http://pages.github.com/lc-doctools/): (Auto-)documentation building tools
- [`devapps`](http://pages.github.com/devapps/): This repo
- [`lc-python`](http://pages.github.com/lc-python/): For Python reference implementation of Node-RED based data pipeline building.

Plus, on a project, your product devapps base repo.

In order to develop on many of them we recommend using PYTHONPATH like shown
for the lc-diameter product:

```console
$ alias lcd
alias lcd='r="$HOME/repos"; export PYTHONPATH="$r/devapps/src:$r/lc-doctools/src:$r/lc-python/src"; cd "$r/lc-diameter"; poetry shell'
```


Now we can develop on any of the involved repos while also working on lc-diameter.

Once all tests are running we create new package versions and
bump the version number in `pyproject.toml`.
