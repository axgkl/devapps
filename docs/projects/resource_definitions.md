# Resource Definitions

Here the mechanics for defining resources are given - for developers of new apps.

Those must be defined in `<namespace>/operations/resources.py` files.



!!! hint

    Check existing resources.py files in other devapp repos for further examples.

    ```bash
    # find devapp's resources files:
    l="$(python -c 'import devapp; print(devapp.__file__)')"
    cd "$(dirname $l)/.." # in site-packages now
    find . -print |grep 'operations/resources.py'
    ```


Mechanics in `devapp/tools/resource.py`

## Resource Base Variables

```python
class rsc:
    class hedgedoc:
        foo = 'bar'
```

results, before any exploration in the following starting state:

```
(Pdb) pp rsc

- bin_name        hedgedoc
- disabled        False
- doc
- foo             bar
- host_conf_dir   $PROJECT_ROOT/conf/${host:-$HOSTNAME}/hedgedoc
- installed       False
- module          hedgedoc
- module_dir      /home/gk/repos/ax/devapps/lc-docs/src/hedgedoc
- name            hedgedoc
```

### `bin_name`: Modify bin wrapper name

Modify name of wrapper in bin folder via env: `export <origname>_name=xxx`

Example:

```
hedgedoc_name=xxx ops p list
> devapp/tools/resource.py(707)check_installed_path()
(Pdb) pp rsc

- bin_name        xxx
- host_conf_dir   $PROJECT_ROOT/conf/${host:-$HOSTNAME}/xxx
(...)
```

## Flow

### Determining Installed State

At install or list, we find if the resource is installed, by checking both, path presence and
post_install been run.

#### Path Present

`path` determined by resource type:

- If `pkg` is False, it is `project.root()/bin` - i.e. present
- If fs resource: `fs_dir/rsc.name` (fs_dir sth like `fs` in conda root env)
- S.conda_prefix + '/envs/%s/bin' % (g(rsc, 'conda_env', rsc.name)) otherwise

Presence is given when `path/cmd|exe` is present, if cmd or exe exist - else `path`
present. If a resource defines a `verify_present` function, only the path is returned in
`rsc_path` , which will later, at run time, put in the $PATH by the wrapper.

#### Post Install Been Run

If the rsc defines a `post_inst` function, it will be called and if it's result is truthy,
we consider this pass. Default is True.

=> Provide such a function if the path may be present but resource is still not installed
possibly, even if. Check there if all if there, and only then return True.

This is only important for list.


### Installing: Conda

Install mode is conda, if pkg is not set to False and not fs resource.

Env name is `g(rsc, 'conda_env', rsc.name)`, i.e. settable via `conda_env = "foo"`

We prefer micromamba if available, else we use conda.

What to install into the environ:

```python
p = g(rsc, 'conda_pkg') or g(rsc, 'pkg') or ' '.join(rsc.provides)
```







## Postinstall Functions

Resource with a post_inst step (after conda install the package).

Provide all the install steps, incl. those for all provides within a `post_inst` function, also for all provides.


```python

def my_post_inst(rsc, install=False, verify=False, api=None, **kw):
    """Install steps, also for all provides"""
    d = api.rsc_path(rsc) or ''
    fn_cfg = d + '/../config/elasticsearch.yml'
    cfg = read_file(fn_cfg, dflt='')
    if verify:
        (...) # check done (also check if post_inst function was run)
    if install:
        (...) # run postinstall


def foo(**kw):
    """Just deliver the wrapper params for a provides here, no installation"""
     return {
            'env': {'fooenvparam': 'bar'},
            'cmd': 'foo -bar'
      }

def elasticsearch(**kw):
    """Just deliver the wrapper params here, no installation"""
    return 'elasticsearch -flag1 ..'

class rsc:
    class elasticsearch:
        d = True # disabled, only installed with -irm elastic
        cmd = elasticsearch # name of bin/<wrapper>
        conda_pkg = 'elasticsearch-bin'
        conda_chan = 'anaconda-platform'
        port = 9200
        port_wait_timeout = 20
        post_inst = my_post_inst # postinstall function after conda install
        systemd = 'elasticsearch' # it is a service -> unit can be created
        provides = [foo] # optional other executables

```
