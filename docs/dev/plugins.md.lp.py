{'133c631951b107fa36d9975a96a6f4d7': [{'cmd': '/bin/rm -rf '
                                              '"src/devapp/plugins/myapp_devapp"',
                                       'res': '$ /bin/rm -rf '
                                              '"src/devapp/plugins/myapp_devapp"\n'}],
 '263423491cbed582e160b55ffa41471a': [{'cmd': 'myapp sh -h',
                                       'res': '$ myapp sh -h \n'
                                              'No plugins found. Create '
                                              'plugins/myapp_<namespace>/ '
                                              'folder(s), containing '
                                              'importable python modules.'},
                                      {'cmd': 'myapp sh -gn Joe',
                                       'res': '$ myapp sh -gn '
                                              'Joe                                    \n'
                                              'No plugins found. Create '
                                              'plugins/myapp_<namespace>/ '
                                              'folder(s), containing '
                                              'importable python modules.'}],
 '36e37536a8fc4ce9266a91a1e070aaf8': {'formatted': '\n'
                                                   '\n'
                                                   '\n'
                                                   '\n'
                                                   '```python\n'
                                                   '\n'
                                                   '[tool.poetry.scripts]\n'
                                                   'myapp = '
                                                   '"devapp.plugin_tools:main"\n'
                                                   '\n'
                                                   '```',
                                      'res': '\n'
                                             '\n'
                                             '\n'
                                             '\n'
                                             '```python\n'
                                             '\n'
                                             '[tool.poetry.scripts]\n'
                                             'myapp = '
                                             '"devapp.plugin_tools:main"\n'
                                             '\n'
                                             '```'},
 '6586b291bca5a7fff9acee1922b5d625': [{'cmd': {'cmd': 'mkdir -p '
                                                      '"src/devapp/plugins/myapp_devapp"'},
                                       'res': '$ mkdir -p '
                                              '"src/devapp/plugins/myapp_devapp"'}],
 'd852e832941bd0e14fb6aa4e50808adf': {'cmd': '$ cat '
                                             'src/devapp/plugins/myapp_devapp/say_hello.py',
                                      'res': '"""\n'
                                             'Saying Hello\n'
                                             '"""\n'
                                             '\n'
                                             '\n'
                                             'from functools import partial\n'
                                             '\n'
                                             'from devapp.app import run_app, '
                                             'do, app\n'
                                             'from devapp.tools import FLG\n'
                                             '\n'
                                             '\n'
                                             'class Flags:\n'
                                             "    'Simple Hello World'\n"
                                             '\n'
                                             "    autoshort = 'g'  # all short "
                                             'forms for our flags prefixed '
                                             'with this\n'
                                             '\n'
                                             '    class name:\n'
                                             "        n = 'Who shall be "
                                             "greeted'\n"
                                             "        d = 'User'\n"
                                             '\n'
                                             '\n'
                                             '# '
                                             '--------------------------------------------------------------------------- '
                                             'app\n'
                                             'def greet(name):\n'
                                             "    print('Hey, %s!' % name)\n"
                                             "    app.info('greeted', "
                                             'name=name)\n'
                                             '\n'
                                             '\n'
                                             'def run():\n'
                                             '    do(greet, name=FLG.name)\n'
                                             '\n'
                                             '\n'
                                             'main = partial(run_app, run, '
                                             'flags=Flags)'},
 'db4dd02bc8bd78fa6374981ba71c7de2': [{'cmd': {'cmd': 'poetry install',
                                               'timeout': 10},
                                       'res': '$ poetry '
                                              'install                                      \n'
                                              '\x1b[34mInstalling dependencies '
                                              'from lock file\x1b[39m  \n'
                                              '\n'
                                              '\x1b[1mPackage '
                                              'operations\x1b[0m\x1b[39m\x1b[49m: '
                                              '\x1b[34m0\x1b[39m installs, '
                                              '\x1b[34m1\x1b[39m update, '
                                              '\x1b[34m0\x1b[39m '
                                              'removals                            \n'
                                              '\n'
                                              '  '
                                              '\x1b[1m\x1b[32m•\x1b[0m\x1b[39m\x1b[49m '
                                              'Updating '
                                              '\x1b[36mdocutools\x1b[39m '
                                              '(\x1b[1m2022.1.21 '
                                              '/home/gk/repos/docutools/src\x1b[0m\x1b[39m\x1b[49m '
                                              '-> '
                                              '\x1b[32m2022.1.21\x1b[39m)    \n'
                                              '\n'
                                              '\x1b[1mInstalling\x1b[0m\x1b[39m\x1b[49m '
                                              'the current project: '
                                              '\x1b[36mdevapps\x1b[39m '
                                              '(\x1b[32m2022.1.18\x1b[39m)'},
                                      {'cmd': 'mytool -h',
                                       'res': '$ mytool -h   \n'
                                              '-bash: mytool: command not '
                                              'found'}],
 'e467f9672c9675bb381b9b43cd945da5': {'formatted': '\n\n', 'res': '\n\n'}}