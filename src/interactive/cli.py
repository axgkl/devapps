#!/usr/bin/env python
"""
# Interactive stateful menues, using fzf

## Usage

Create an App Class with subclasses for it's various listable items

Those must have at least a produce method, returning lists of items.

### Preview

Default is to json hilight the selected items



"""

from interactive import preview_cmd_flag, execute_args_sep
import sys
import os

"""
# DEV
No unnecessary imports if we are ALSO called by fzf for previews
(just one script to be defined)

## Interactive Debugging

- Use Fzf.dbgstop when debugging stuff while fzf is on.
- Use wrap function in pipeline builder


"""


def is_execute(a):
    return a[1].startswith(execute_args_sep)


#  is_preview = lambda a: a[1].startswith(preview_args_sep)


def main():
    argv = sys.argv
    if len(argv) == 1 or not len(argv[1]):
        print('call me with an argument, e.g. a json file, directory, or app')
        sys.exit(1)

    if argv[1] == preview_cmd_flag:
        from interactive import preview_process

        return preview_process.main(argv)

    # restarting ourselves with fzf actions triggerable by us:
    fn_fifo = os.environ.get('STDIN_FIFO')
    if not fn_fifo:
        d = os.path.dirname(__file__)
        i = ' '.join(["'%s'" % a for a in argv])
        sys.exit(os.system(f'{d}/with_stdin_fifo.py {i}'))

    from absl import app

    from interactive.app import load_app, start, fn_app_ctrl_fifo

    fn_app_ctrl_fifo[0] = fn_fifo

    for s, f in ('-hf', '--helpfull'), ('-h', '--help'):
        if s in argv:
            argv[argv.index(s)] = f
    if os.path.isdir(argv[1]):
        argv.insert(1, 'files')
    if os.path.isfile(argv[1]):
        argv.insert(1, 'file')

    modname = argv[1]
    mod = load_app(modname)
    print(app.run(start(mod)))


# is_debug_fzf = lambda a: a[1] == 'fzf-debug'


# def main():
#     _ = 'FZF_DEFAULT_OPTS'
#     if _ in os.environ:
#         del os.environ[_]
#     argv = sys.argv
#     # os.system('notify-send "%s"' % argv)
#
#     if len(argv) == 1:
#         hint = 'try give me e.g. a json file or a directory'
#         from .app import get_app
#
#         return get_app().die('Require data to display', hint=hint)
#     K = False
#     if argv[1] == 'mf':
#         # debug: mock fzf: with this as first arg we do not start fzf but send a preview hit only:
#         from interactive import fzf_ctrl
#
#         fzf_ctrl.FZF = 'fui fzf-debug'
#         argv.pop(1)
#
#     if is_preview(argv):
#         from interactive import preview
#
#         f = preview.preview.main
#     elif is_execute(argv):
#         K = True
#         from interactive import preview
#
#         f = preview.execute.main
#
#     elif is_debug_fzf(argv):
#         from interactive import fzf_debug
#
#         f = fzf_debug.run
#
#     else:
#         from interactive import app
#
#         f = app.run
#     r = f(argv)
#
#     if isinstance(r, str):
#         # if r == 'cancelled': sys.exit(130)
#         print(r)
#     if K and 0:
#         os.system('notify-send "killing %s - %s"' % (os.getppid(), r))
#         os.kill(os.getppid(), 15)
#
#
if __name__ == '__main__':
    main()
#     main()
#
#     # class create_droplet(doctl_api_menu):
#     #     size = 's-1vcpu-1gb'
#     #     region = 'fra1'
#     #     image = 'Arch-Linux-x86_64-cloudimg-20210415.20050.qcow2'
#     #     ssh_keys = 'gk'
#     #     name = 'droplet'
#
#     # doctl compute droplet create --image ubuntu-20-04-x64 --size s-1vcpu-1gb --region nyc1 example.com
#     # doctl compute droplet create --image ubuntu-20-04-x64 --size s-1vcpu-1gb --region nyc1 example.com
