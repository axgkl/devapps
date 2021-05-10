"""
This is only to allow pip install -e of this repo where poetry add is no option
(e.g. when developping on repos which require it but also it depends on them (doctools))
"""


# Always prefer setuptools over distutils
from setuptools import setup, find_packages

# those allow minimal usage:
req = [
    'absl-py',
    'decorator',
    'jsondiff',
    'Pygments',
    'PyJWT',
    'structlog',
    'ujson',
    'humanize',
    'inflection',
    'lz4',
    'Rx',
    'tabulate',
    'requests',
    'PyYAML',
]
PKG = find_packages('.')
setup(
    name='devapps',
    version='1000.01.01',
    description='devapps end to end',
    packages=PKG,
    # for async rx we assume rx is installed:
    install_requires=[req],
    include_package_data=True,
    license='BSD',
    # See https://pypi.python.org/pypi?%3Aaction=list_classifiers
    zip_safe=False,
)
