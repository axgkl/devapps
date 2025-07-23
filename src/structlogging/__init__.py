# The package was probably designed to:
#
# Be part of a larger ecosystem
# Allow other packages to extend structlogging.*
# Enable modular installation of components
#
# 💡 Modern Alternative:
# Python 3.3+ has implicit namespace packages - just don't include __init__.py files in namespace directories and it works automatically! Much cleaner. 🚀
# This was essentially the "old way" of doing what modern Python now does automatically.
# -> Removed all this:
# try:
#     __import__('pkg_resources').declare_namespace(__name__)
#
# except ImportError:
#     from pkgutil import extend_path
#
#     __path__ = extend_path(__path__, __name__)
#
#
# """
# This is ususally imported only when logging is configured.
# Our features depend on structlog which is not a dependency.
# """
# try:
#     pass
# except ImportError as ex:
#     ex.args += (
#         'Hint: You have to add structlog to your packages.=> pip install structlog',
#     )
#     raise
#

# -- Setup for a stdlib logging free, getattr free use:
