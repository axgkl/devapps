# Plugins

Here is how you create or extend tools with plugins, callable like `<toolname> <pluginname> [plugin flags]`.

!!! note "Git Analogy"

    In this terminology, "git" would be the name of the tool, "checkout" would be the name of the plugin.

## Defining a **New** Tool

Using uv, in your `pyproject.toml` add the name of the tool within the `scripts` section like so:

```python lp hide_cmd=True mode=python
from devapp.tools import read_file, write_file

fn, sect = 'pyproject.toml', '[project.scripts]'
app = '\nmyapp = "devapp.tools.plugin:main"'
s = read_file(fn)
if not app in s:
    s = s.replace(sect, sect + app)
    write_file(fn, s)
print(sect + app)
```

This makes the tool available, with no plugins yet:

```bash lp fmt=xt_flat
uv run myapp -h || true
```

We are ready to create plugins:

Plugins must reside within `<package>/plugins/<tool_name>_<package_name>/` subdirectory of packages of the current repo.

The package name at the end is to allow "higher order repos" to supply plugins with same name but changed behaviour.

For the demo we pick the `devapp` package within this repo, `devapps`:

```bash lp fmt=xt_flat asserts="myapp_devapp"
mkdir -p "src/devapp/plugins/myapp_devapp" && ls "src/devapp/plugins" && pwd
```

Then we create a demo plugin:

```python lp fn=src/devapp/plugins/myapp_devapp/say_hello.py mode=make_file
"""
Saying Hello
"""

from functools import partial

from devapp.app import run_app, do, app
from devapp.tools import FLG


class Flags:
    'Simple Hello World'

    autoshort = 'g'  # all short forms for our flags prefixed with this

    class name:
        n = 'Who shall be greeted'
        d = 'User'


# --------------------------------------------------------------------------- app
def greet(name):
    print('Hey, %s!' % name)


def run():
    do(greet, name=FLG.name)


main = partial(run_app, run, flags=Flags)
```

The plugin is now available:

```bash lp fmt=xt_flat asserts="Hey, Joe"
['myapp -h', 'myapp sh -lf 2 -gn Joe']
```

- Further plugins for our `myapp` tool are now simply added into this directory

## Extending a Given Tool

Higher order repos (dependend/derived on devapp) can add their own plugins for `myapp`, following
the directory convention given above.

Means: A package "foo" depending on devapp may add a

    /src(of_foo package)/bar/plugins/myapp_bar/bettergreeter.py

so that the `myapp` tool has a better/more specialized greeter plugin.

Derived package foo may also _change_ the behaviour of the "say_hello" plugin of "myapp" by
providing this module as well.

Here is how you "patch" a given module, e.g. the `project` plugin of the `ops` tool, from a devapps
derived package (here `lc-python`):

```python
~/repos/lc-python/sr/o/p/ops_operators master !3 ?1 ❯ pwd
/home/gk/repos/lc-python/src/operators/plugins/ops_operators
~/repos/lc-python/sr/o/p/ops_operators master !3 ?1 ❯ cat project.py
from devapp.plugins.ops_devapp.project import *


class Flags(Flags):
    'defined here, so that ops project -h works correctly'

# (overwrite your stuff here)

main = lambda: run_app(run, flags=Flags)
```

.

```python lp silent=True mode=python
# cleaning up:
from devapp.tools import read_file, write_file
fn = 'pyproject.toml'
app = '\nmyapp = "devapp.plugin_tools:main"'
write_file(fn, read_file(fn).replace(app, ''))
```

```bash lp  silent=True
/bin/rm -rf "src/devapp/plugins/myapp_devapp"
```
