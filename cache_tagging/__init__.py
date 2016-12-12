import os
import sys
import warnings
from cache_dependencies import __version__, __version_info__

warnings.warn("cache_tagging is deprecated. Use cache_dependencies instead", PendingDeprecationWarning, stacklevel=2)
__path__.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.realpath(sys.modules[__name__].__file__))),
    'cache_dependencies'
))
