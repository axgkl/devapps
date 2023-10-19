from devapp.app import app, run_app


def main():
    app.info('adsfasfa', bar=23, foo='adsfasfas', payload={'fooJ': 'asdf', 'i': 23})


if __name__ == '__main__':
    run_app(main)
