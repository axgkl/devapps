"""
Strategy to be robust:
    unshare -m
    then mount overlay

    any change: begin from start
    state is kept in environ's 'DA_LAYERS' variable

"""

import os
from json import dumps, loads

from devapp import FLG, app, flag, run_app

env = os.environ.get
is_dir = os.path.isdir
exists = os.path.exists

flag.string('bases', env('DA_DIR', ''), 'Base dirs')
flag.boolean('create', False, 'Create Layer')
flag.boolean('remove', False, 'Remove Layer')


flag.string(
    'layer',
    '',
    (
        'Directory or match in $DA_DIR/layers or absolute dir.',
        'This will be on top, catching read write ops.',
    ),
)

flag.string(
    'overlay',
    env('DA_DIR', ''),
    'Created overlay directory - this is the resulting dir',
)


def show():
    return loads(env('DA_LAYERS') or '{}')


def write_state(state):
    start_pid = state['start_pid']
    fn = app.workdir + 'state.%s' % start_pid
    if exists(fn):
        app.log.dbg('State already written', fn=fn)
    else:
        with open(app.workdir + 'state.%s' % start_pid, 'w') as fd:
            fd.write(dumps(state))
        app.log.dbg('State written', **state)


def create():
    """Create Layers"""
    have = show()
    if have:
        write_state(have)
    fail = os.system('unshare -m ')
    # TODO: Now continue...


def remove():
    """Remove Layers"""
    # TODO: Implement layer removal logic
    have = show()
    if not have:
        app.log.info('No layers to remove')
        return
    # Add implementation here
    app.log.info('Layer removal not yet implemented')
    return have


def main():
    """Called from max d package"""
    if FLG.create and FLG.remove:
        app.die('Cannot do both')
    if not FLG.create and not FLG.remove:
        return show()
    return (create if FLG.create else remove)()


layer = lambda: run_app(main)
