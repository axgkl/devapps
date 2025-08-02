# The CLI Flag System

`devapps` uses [absl flags](https://abseil.io/docs/python/guides/flags) to get configured via the CLI or
environ.

Application modules and packages define the flags they require or support within their source code themselves.

Dependent on which of these modules are **imported** at a certain time after startup (before the call to `app.run`),
then these are the flags presented to the user when he calls `-h|--help|--helpful|-hf`. 

Set flag values are then globals throughout the application.

This makes a lot of sense when a package has a lot of varying use cases, with certain modules sometimes needed or not.

!!! note

    It is allowed to do `FLG.foo=bar` after startup - but considered bad practice.

## Flag Definitions via Nested Class Trees

In devapps, while fully supporting the standard absl mechanics (`flags.DEFINE_string`) we also allow to defined them in
class name spaces:

These are e.g. the flags of the `project` module:

```python
from devapp.app import FLG, app, run_app, do, system

class Flags:
    # short codes built dynamically (conflict resolved) for all flags:
    autoshort = '' # You could give a short code prefix here

    # flag name:
    class force:
        # CLI help string:
        n = 'Assume y on all questions. Required when started w/o a tty'
        d = False # default

    class init_at:
        n = 'Set up project in given directory. env vars / relative dirs supported.'
        d = ''

    class init_create_unit_files:
        n = 'List service unit files you want to have created for systemctl --user'
        d = []

    class init_resource_match:
        n = 'Install only matching resources. Example: -irm "redis, hub"'
        d = []

    class list_resources_files:
        n = 'Show available definition files.'
        d = False

    class edit_matching_resource_file:
        n = 'Open resource files in $EDITOR, matching given string in their content'
        d = ''

    (...)

def run():
    if FLG.init_at:
        # structlog call:
        app.info('Re-initializing project', location=FLG.init_at)
        (...)

# if flags argument to run_app is given it will implicitly call devapp.tools.define_flags:
main = lambda: run_app(run, flags=Flags)
```

!!! hint "Full Control"

    module import does *not* cause flags already to be defined, the parent class is just a namespace
    without any magic.

    Instead there is special call `devapp.tools.define_flags(my_flags_class)`, which calls
    `absl.define_<type>` for any of the inner classes.   

    Handing the flags via the flags argument into `run_app` will issue that call.


A call to help then lists the flags on the CLI:

???+ note "`-h`: Module Help"
    
    This lists the supported flags for the module whose main method is called:

    ```bash lp fmt=xt_flat
    ops project -h
    ```


???+ note "`-hf`: All Flags"

    `-hf <match>` gives help for ALL flags imported, here with a match:

    ```bash lp fmt=xt_flat
    ops project -hf log | grep -A 100 'All supported'
    ```

## Flag Types

```python lp fn=/tmp/flagtest.py mode=make_file chmod=755 xxx
#!/usr/bin/env python
from devapp.app import app, run_app, FLG

class Flags:
    autoshort = '' # enabling short forms, prefixed with '', i.e. not prefixed

    class my_bool:
        d = False

    class my_float:
        d = 1.1

    class my_int:
        d = 1

    class my_multi_str:
        t = 'multi_string'  # can supply more than once, any value

    class my_list:
        s = 'x'   # non auto short form
        t = list  # comma sepped values into a list 
        d =  'foo, bar'

    class my_opt:
        t = ['foo', 'bar']  # can pick exactly one within the list (enum)
        d =  'foo'

    class my_opt_multi:
        t = ('a', 'b', 'c') # now we can select more than one within the tuple (multi_enum)
        d =  'a'

    class my_str:
        d = 'foo' # most easy way

    class my_str_detailed:
        '''Detailed help'''
        n = '''Options (multiline help)
        - opt1: foo
        - opt2: bar
        '''
        s = False # disable short
        d = 'opt1'

    class my_condition:
        # will be parsed into an axiros/pycond filter, incl. the condition (list).
        t = 'pycond'
        d = 'fn not contains frozen and fn not contains /rx/'


# Print out all FLG vals.
# Normal (global) app access e.g. like : if FLG.my_int > 42:
flg = lambda: [(k, getattr(FLG, k)) for k in FLG if k.startswith('my_')]
run = lambda: app.info('Flag values (CLI over defaults):', json=flg())

if __name__ == '__main__':
    # supplying the flags keyword implicitly calls devapp.tools.define_flags on them:
    run_app(run, flags=Flags)

```

With this

```bash lp fmt=xt_flat xxx
/tmp/flagtest.py -h # lp: asserts=my_condition
/tmp/flagtest.py -mo baz || true # lp: asserts='should be one of'
/tmp/flagtest.py -ms a -mb -mf 42.1 -mi 42 -mms a -mms b -mo bar -mom b -mom c -x a,b -ms b -lf plain # lp: asserts=my_int
```

!!! hint

    Note `my_str` defined twice in the example - last wins (except when defined `multi_string`) -> you can preparametrize apps in wrappers
    and still overwrite flags when calling the wrapper.

    E.g. in the wrapper you have -ll 20 while in the call you say -ll 10 to have debug logging for a certain run.  


## Environ Flags

Adding `--environ_flags` causes the app to check the process environ first(!), for any flag value.

???+ example "Setting project directory and log level via environ"

    ```bash lp expect=false new_session=flags fmt=xt_flat
    ['export init_at="$HOME/foo"; export log_level=30', {'cmd': 'ops project -ia /tmp --environ_flags', 'timeout': 1}, 'send-keys: C-c']
    ```

!!! danger "Environ over CLI"

    Please note again that the environ value does overwrite the CLI value, when `environ_flags` is
    explicitly set. On the cli, you'd have to use the `unset` command first.


## Flagsets

You can store full sets of flags in files and refer to them via the absl standard `--flagfile=....` flag.


# Using Flags in `pytest`

When the started process is pytest, then the `environ_flags` flag is set to true. Means you can export non default flag
values before starting pytest like so:

```console
export my_flag=myval && pytest -xs test/test_my_test.py
```


## Action Flags

Example:

```python lp fn=/tmp/action_flagtest.py mode=make_file chmod=755 xxx
#!/usr/bin/env python
from devapp.app import app, run_app, FLG


class Flags:
    autoshort=''

    class force:
        d = False

    class Actions:
        class install:
            d = False

            class verbose:
                s = 'iv' # no auto for nested flags
                d = False

        class run:
            d = True # default


class ActionNS:
    def _pre():
        print('pre')

    def _post():
        print('post')

    def run():
        print('running', FLG.force)

    def install():
        print('installing', FLG.force, FLG.install_verbose)

if __name__ == '__main__':
    run_app(ActionNS, flags=Flags)

```

Test it:

```bash lp fmt=xt_flat xxx
/tmp/action_flagtest.py -h
/tmp/action_flagtest.py # lp: asserts="running False"
/tmp/action_flagtest.py -f # lp: asserts="running True"
/tmp/action_flagtest.py -iv || true # lp: asserts="Unknown command line flag 'iv'"
/tmp/action_flagtest.py install -iv # lp: asserts="installing False True"
/tmp/action_flagtest.py install -f -iv # lp: asserts="installing True True"
/tmp/action_flagtest.py install --install_verbose # lp: asserts="installing False True"
/tmp/action_flagtest.py run --install_verbose=True || true # lp: asserts="Unknown command line flag 'install_verbose'"
```

Mind the concatenation of action and flag name for the nested property verbose within `def install()`
action.




