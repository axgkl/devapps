
def binenv_env():
    def r(k, e=os.environ):
        k = f'binenv_{k}dir'
        r = 'export ' + k.upper() + '="'
        return r + e.get(k, e['HOME'] + '/.local/bin') + '"'

    return ''.join([r(k) for k in ['link', 'bin']])


def verify_binenv(path, rsc, **kw):
    breakpoint()   # FIXME BREAKPOINT
    cmd = f'{binenv_env()} type binenv 1>/dev/null 2>/dev/null'
    return not os.system(cmd)


def binenv(rsc, **kw):
    breakpoint()   # FIXME BREAKPOINT
    if rsc.installed:
        return

    from devapp.tools import download_file
    import platform

    archi = platform.machine().replace('x86_', 'amd').lower()
    url_binenv = f'https://github.com/devops-works/binenv/releases/download/v0.19.8/binenv_{platform.uname()[0]}_{archi}'
    fn = os.environ['HOME'] + '/binenv'
    os.unlink(fn) if exists(fn) else 0
    download_file(url_binenv, fn)
    os.chmod(fn, 0o755)
    breakpoint()   # FIXME BREAKPOINT
    os.system(f'{binenv_env()} {fn} update')
    os.system(f'{binenv_env()} {fn} install')


