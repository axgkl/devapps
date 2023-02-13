# Interactive FZF Apps

## Parameters

### App Level

#### Mandatory

#### Optional

- `str:default_menu` [Alphabetically first menu class name]: Which menu to present at app start.
- `str:name` (str): No logical purpose.

### Menu Level

#### Mandatory

- `callable->list:produce`: Must return raw data as list. Typically list of dicts.

## Understanding the Application

Follow `class Streams` within the pipeline module.
Most important is the stream starting with the Menu items producer (the items stream).

## Debugging

- `<appname> -hf | grep d_tmp` shows you where the application log files are written.
- Loglevel via `-ll` / `--log_level`
- In `pipeline.py` ensure the debug mode is set, so that each stream map operator function is wrapped via `wrap` function, and therefore logged.

### Interactive Debugging

`pp items` in breakpoints within functions of the items stream will print the items with entries reduced to just a few.

- Use Fzf.dbgstop when debugging stuff while fzf is on.
- Use wrap function in pipeline builder

### Tips

Sometimes it is useful to set the fzf.cmd to sth like 'sleep 10000' just before the `popen_fzf` - then you still have std out
and in.
