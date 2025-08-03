# Quickstart

## Advanced Logging Features

We added a few processors and console rendering features to the awesome [structlog](https://github.com/hynek/structlog).

Example usage:

```python lp mode=make_file fn=/tmp/myapp.py fmt=mk_console
from threading import Thread
from devapp.app import init_app

# log time deltas in millis, highlight 'main' strings, add unique symbol for threads
app = init_app(log_time_fmt='dt', log_dev_match='main', log_add_thread_name=True)

# by default kw 'json' and 'payload' will be colorized using pygments' json lexer:
main = lambda: app.info('In main', foo='bar', json={'bar': {'foo': True}})

if __name__ == '__main__':
    app.info('Starting main')
    t = Thread(target=main, daemon=True).start()


```

```bash lp fmt=xt_flat session=quickstart
python /tmp/myapp.py
```



## Flags

Via nested classes, devapps allows to define [absl](https://abseil.io/docs/python/quickstart) flags:


```python lp mode=make_file fn=/tmp/mymain.py fmt=mk_console
from devapp.app import app, FLG
from devapp.tools import define_flags

class Flags:
  autoshort = '' # prefix for short flag keys, built with collision avoidance 
  class greeting:
    d = 'Hi'
  # more.., incl. action flags and complex types

define_flags(Flags)

main = lambda: app.debug(f'{FLG.greeting} {FLG.greeted}', greeted=FLG.greeted)


```

```python lp mode=make_file fn=/tmp/myapp.py fmt=mk_console
#!/usr/bin/env python
"""
# Simple Test App
- Spawns a thread
- Logs
- Uses Flags
"""
from devapp.app import init_app
import sys
sys.path.append('.')
from mymain import main # flags found anywhere imported

class AppFlags:
  autoshort = ''
  class greeted:
    '''Who is greeted'''
    s = 'G' # explicit short. See help output below
    d = 'World'


if __name__ == '__main__':
    init_app(flags=AppFlags).info('Starting main')
    main()
```

```bash lp fmt=xt_flat session=quickstart
python /tmp/myapp.py -h
python /tmp/myapp.py -hf log_
python /tmp/myapp.py -hf greet
python /tmp/myapp.py -G=Joe -ll 10 -latn
```



