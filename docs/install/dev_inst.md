# Development Install

In order to *develop* applications or projects derived on `devapps` (or on `devapps` itself):

1. clone this or the derived application's repository
1. configure artifactory credentials (for packages referred to in your `pyproject.toml` file) as explained before
1. `pip install poetry` if you not yet have the build system (does not need to match your target python version)
1. run `poetry install`

It takes around a minute for poetry to resolve all dependencies.  
After this you can enter the virtual environment via poetry shell with all required packages and commands available:



```bash lp new_session='devapp_inst'
[
 {'cmd': 'poetry shell', 'expect': False, 'timeout': 2},
 'ops -h',
]
```


## Co-Developing Dependent Packages

If you want to develop not only on the poetry installed package but also on others than using a PYTHONPATH based trick
is convenient:

Clone the other repositories under development as well and export `$PYTHONPATH` like so:

```console
$ (lc-python-Z3KKTfGL-py3.7) 2.lc-python$ type ldp
ldp is aliased to `export PYTHONPATH="/home/joe/repos/devapps/src:/home/joe/repos/lc-doctools/src"; cd /home/joe/repos/lc-python; poetry shell'

```

The devapps dependent `lc-python` environment will now use e.g. `devapps` from the checkout and not from the configured package.

!!! hint "Scripts from cloned repos"
    The PYTHONPATH trick works also when those other packages ship with scripts, e.g.
    the `doc` script from `lc-doctools`, or `ops` from `devapps`.   
    You do need to have at least one version with such a script in your `pyproject.yml`,
    so that the script is installed and found in your `$PATH` within the virtual environment.


