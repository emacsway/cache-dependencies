import sys

from django.conf import settings
from django.core.cache import DEFAULT_CACHE_ALIAS
from django.core.cache import get_cache as django_get_cache
from django.db.models import signals
from django.utils.encoding import force_unicode
from django.utils.functional import curry

from .. import CacheTagging


def get_cache(*args, **kwargs):
    """Returns instance of CacheTagging class."""
    cache = django_get_cache(*args, **kwargs)
    return CacheTagging(cache)

cache = get_cache(DEFAULT_CACHE_ALIAS)


def _clear_cached(tags_func, cache=None, *args, **kwargs):
    """
    Model's save and delete callback
    """
    obj = kwargs['instance']
    tags = tags_func(obj)
    if not hasattr(tags, '__iter__'):
        tags = (tags, )
    if cache is None:
        cache = globals()['cache']
    cache.invalidate_tags(*tags)


class CacheRegistry(object):
    """
    Stores all registered caches
    """
    def __init__(self):
        """Constructor, initial registry."""
        self._registry = []

    def register(self, model_tags):
        """Registers handlers."""
        self._registry.append(model_tags)

        for data in model_tags:
            Model = data[0]
            tags_func = data[1]
            apply_cache = len(data) > 2 and data[2] or cache
            signals.post_save.connect(
                curry(_clear_cached, tags_func, apply_cache),
                sender=Model, weak=False
            )
            signals.pre_delete.connect(
                curry(_clear_cached, tags_func, apply_cache),
                sender=Model, weak=False
            )

registry = CacheRegistry()


def autodiscover():
    """
    Auto-discover INSTALLED_APPS cachecontrol.py modules
    and fail silently when not present.
    """
    import imp
    from django.conf import settings
    for app in settings.INSTALLED_APPS:
        try:
            __import__(app)
            imp.find_module("caches", sys.modules[app].__path__)
        except ImportError, AttributeError:
            continue
        __import__("{0}.caches".format(app))
