# This is a namespace package

import warnings
warnings.filterwarnings('ignore', 'Module yola was already imported.*',
                        UserWarning)

try:
    import pkg_resources
    pkg_resources.declare_namespace(__name__)
except ImportError:  # pragma: no cover
    import pkgutil
    __path__ = pkgutil.extend_path(__path__, __name__)
