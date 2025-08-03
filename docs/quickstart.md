# Quickstart

## Advanced Logging

```python lp mode=make_file fn=/tmp/myapp.py fmt=mk_console
#!/usr/bin/env python
"""
# Simple Test App
- Spawns a thread
- Logs
"""
from threading import Thread
from devapp.app import init_app

app = init_app(log_time_fmt='dt', log_dev_match='main', log_add_thread_name=True)

def main():
    app.info('In main', foo='bar', json={'bar': {'foo': True}})

if __name__ == '__main__':
    app.info('Starting main')
    t = Thread(target=main, daemon=True).start()


```

```bash lp fmt=xt_flat session=quickstart
python /tmp/myapp.py
```

## Flags

```python lp mode=make_file fn=/tmp/mymain.py fmt=mk_console
from devapp.app import app, FLG
from devapp.tools import define_flags

class Flags:
  autoshort = ''
  class greeting:
    d = 'Hi'
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
from devapp.app import init_app, FLG
from devapp.tools import define_flags
import sys
sys.path.append('.')
from mymain import main 

class AppFlags:
  autoshort = ''
  class greeted:
    '''Who is greeted'''
    s = 'G'
    d = 'World'
define_flags(AppFlags)


if __name__ == '__main__':
    init_app().info('Starting main')
    main()
```

```bash lp fmt=xt_flat session=quickstart
python /tmp/myapp.py -hf log
python /tmp/myapp.py -hf greet
python /tmp/myapp.py -G=Joe -ll 10 -latn
```



