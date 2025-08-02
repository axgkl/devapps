# The `ops project` Tool

After installation of `devapps` you have the `ops project` command available[^1]. The tool allows to install and
maintain projects and resources.

[^1]: Technically `project` is implemented as a [plugin](../../dev/plugins) of the `ops` tool.

## Project

To use the tool, first activate your environment via `poetry shell` or `. .venv/bin/activte' in case of a development installation (virtual environ activation in case of a uv / pip(x) based install).

Let's now create a (new) directory for the project:

```bash lp session='project', fmt='xt_flat'
rm -rf $HOME/myproject # lp: silent
mkdir $HOME/myproject && cd $HOME/myproject && ls -lta
```

## Resources

`devapps` (and derived packages) contain resource defining python modules named `resources.py`.

### Resources of `devapps`

Here are the resources defined in `devapps`. They are required for running the tests but also provide some tools:

```bash lp session=project
['ops project list']
```

!!! note "More Tools"

    `devapps` based applications usually define more, e.g. databases, more tools or log targets.

!!! hint "Batteries Included - but Replaceable"

    DevApps' resource management is only meant as a convenience machinery to quickly get up projects or dev setups up
    and running. In production you'll have more distributed setups anyway, installed e.g. via Ansible and/or Container
    Orchestrators.

    Means:
    You do not need to have those resources managed as shown below - we install "normal" versions, packaged as Conda
    packages and use standard config options (see previous chapter why).

## Project Init

Via the `--init_at` flag you set up a new project, within the given directory, plus its resources:

```bash lp session=project timeout=100
['ops project --init_at . --port_offset 2000 --force', 'tree -L 2']
```

As you can see, we created start files in the `bin` subdirectory of the project directory, pointing to where the actual binaries
had been installed. We did set a global `port_offset`, which affects any port of listening resources started.

!!! hint "Controlling Resources Installation"

    There are few options regarding which resources are to be installed, where.
    See the output of the `-h` regarding this:

    ```bash lp session=project
    ops p -h
    ```

!!! note "More CLI flags"

    More control flags are only accessible via `--helpfull <match>` (`-hf`):
    Try `ops p -hf log_level`, `ops p -hf port` (...)

??? example "Project initialization flags"

    In the example above, a `--port_offset=2000` flag was given, determining the start parameters written into the redis wrapper:

    ```bash lp session=project fmt=mk_console expect=false
    [{'cmd': 'bin/redis-server', 'timeout': 0.5}, 'send-keys: C-c']
    ```

!!! success "Idempotency"

    If you need to re-parametrize the project (e.g. set different port offsets) then run `ops project --init_at` again
    and have new start wrappers created.

## Unit Files

We do not try to manage the live cycle of services but leave that to systemd (available on all Linux major distributions).

The `--init_create_unit_files=<name of daemon resource>` will create a unit file after installing the resource itself:

!!! example "Creating a resource incl. unit file"

    ```bash xlp session=project
    ops project --init_at=. --init_create_unit_files=redis-server --force
    ```

    You control the service using `systemctl --user`:

    ```bash xlp session=project
    [
    {'cmd': 'systemctl --user --no-pager start  redis-server-myproject'},
    {'cmd': 'systemctl --user --no-pager status redis-server-myproject', 'assert': '(running)'},
    {'cmd': 'systemctl --user --no-pager stop   redis-server-myproject'}
    ]


    ```

!!! hint

    In order to install unit files for *ALL* service type resources, you can  supply `--init_create_all_units`, alternatively.



