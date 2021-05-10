# Resource Definitions

Here the mechanics for defining resources.



!!! hint
    Check existing resources.py files in other devapp repos for further examples.

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
