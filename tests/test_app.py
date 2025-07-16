#!/usr/bin/env python
"""# Tests for the app module"""

is_auto_doc_file = True
import pytest
import os
import json
import sys
from devapp import app as app_module
from devapp.app import app, run_app
import devapp.tools

define_flags = devapp.tools.define_flags
FLG = devapp.tools.FLG

# from lcdoc.py_test.auto_docs import gen_mod_doc

# for CFL - this needs the docs_dir, which it picks from a project config
# (*not* a devapps project, but mkdocs config)
import lcdoc.call_flows.call_flow_logging as cfl

# from lcdoc.auto_docs import mod_doc


def test_run_app_show_flags(we_are_in_app_process=False):
    """
    Tests basic app and flags
    """
    # we'll run the test app in a subprocess - there can only be one app:
    if we_are_in_app_process:
        fn_md, plot = cfl.init_mod_doc(__file__)

        @cfl.document(trace=(app_module, devapp.tools), dest=fn_md)
        def test_start_app():
            """A test function which starts an app"""

            # the "classic" abseil way to define a flag:
            from absl import flags

            flags.DEFINE_string('my_string_flag', 'str_flg_dflt', 'A test flag')

            class TestFlags:
                class test_cli_flag_boolean:
                    """Just a test flag - This is the secondary description"""

                    n = 'This is the main CLI flag description'
                    d = False  # the default. Type dictates flag parser

            # activate the flags in a dedicated step, not at import:
            define_flags(TestFlags)

            def my_app():
                app.info('A message', will_go_to='stderr')
                # we just return the values of all flags defined.
                return {'foo': 'bar', 'flags': FLG.flag_values_dict()}

            # An app is started like this, causing:
            # - the logging system to get initalized
            # - the flags being parsed
            # - the return value pretty printed on stdout
            return run_app(my_app)

        test_start_app()

    # in order to test the subprocess in foreground:  ./test_app.py 1
    me = __file__
    cmd = me + ' test_run_app_show_flags'
    res = os.popen(cmd).read()
    print('response:-')
    print(res)
    print('----------')
    res = json.loads(res)
    # check the output of the process:
    assert res['foo'] == 'bar'
    assert res['flags']['test_cli_flag_boolean'] == False
    assert res['flags']['my_string_flag'] == 'str_flg_dflt'


# gen_mod_doc(globals())


if __name__ == '__main__':
    # test funcs call the __file__ with the testfunc as first arg:
    test_func = sys.argv.pop(1)
    if test_func == '1':
        test_func = 'test_run_app_show_flags'
    globals()[test_func](we_are_in_app_process=True)

    # with pytest.raises(SystemExit):
    #     dev.main(['-h'])
    # captured = capsys.readouterr()
    # assert 'devapp' in captured.out
    # we run a process which is passed to this function again:
