import os
import sys
import warnings
from django_cache_dependencies import (
    CacheCollection, DefaultCacheProxy, caches, get_cache, cache, _clear_cached, CacheRegistry,
    registry, autodiscover, close_caches, DEFAULT_CACHE_ALIAS
)

warnings.warn("cache_tagging.django_cache_tagging is deprecated. Use django_cache_dependencies instead", PendingDeprecationWarning, stacklevel=2)
__path__.insert(0, os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.realpath(sys.modules[__name__].__file__)))),
    'django_cache_dependencies'
))
