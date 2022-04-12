from __future__ import absolute_import, unicode_literals
import sys
import hashlib
from threading import local

import django.core.cache
from django.conf import settings
from django.core import signals as core_signals
from django.core.cache import DEFAULT_CACHE_ALIAS
from django.db.models import signals as model_signals
from functools import partial as curry

from cache_dependencies.tagging import CacheTagging
from cache_dependencies.relations import RelationManager, ThreadSafeRelationManagerDecorator
from cache_dependencies.locks import DependencyLock
from cache_dependencies.transaction import TransactionManager, ThreadSafeTransactionManagerDecorator
from cache_dependencies.nocache import NoCache

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)

nocache = NoCache(
    hashlib.md5(
        'nocache_{0}'.format(settings.SECRET_KEY).encode('utf8')
    ).hexdigest()
)


class CacheCollection(object):
    """Collections of caches.

    Cache Middlewares and decorators obtains the cache instances
    by get_cache() function in Django < 1.7.
    For correct transaction handling we should to return
    the same instance by cache alias.
    """
    def __init__(self):
        self.ctx = local()

    def __call__(self, backend=None, *args, **kwargs):
        """Returns instance of CacheTagging class."""
        backend = backend or DEFAULT_CACHE_ALIAS
        key = (backend, args, frozenset(kwargs.items()))

        if key not in self._caches:
            options = getattr(settings, 'CACHE_TAGGING', {}).get(backend, {})
            delay = options.get('DELAY', 0) or 0
            isolation_level = options.get('ISOLATION_LEVEL', 'READ COMMITTED')
            django_backend = options.get('BACKEND', backend)
            if hasattr(django.core.cache, 'caches'):
                cache = django.core.cache.caches[django_backend]
            else:
                cache = django.core.cache.get_cache(django_backend, *args, **kwargs)

            def thread_safe_cache_accessor():
                return self(backend, *args, **kwargs).cache
            tags_lock = DependencyLock.make(isolation_level, thread_safe_cache_accessor, delay)
            transaction = ThreadSafeTransactionManagerDecorator(TransactionManager(tags_lock))
            relation_manager = ThreadSafeRelationManagerDecorator(RelationManager())
            self._caches[key] = CacheTagging(
                cache, relation_manager, transaction
            )
        return self._caches[key]

    def __getitem__(self, alias):
        return self(alias)

    def all(self):
        return self._caches.values()

    @property
    def _caches(self):
        if not hasattr(self.ctx, 'caches'):
            self.ctx.caches = {}
        return self.ctx.caches

caches = get_cache = CacheCollection()


class DefaultCacheProxy(object):
    """
    Proxy access to the default Cache object's attributes.

    This allows the legacy `cache` object to be thread-safe using the new
    ``caches`` API.
    """
    def __getattr__(self, name):
        return getattr(caches[DEFAULT_CACHE_ALIAS], name)

    def __setattr__(self, name, value):
        return setattr(caches[DEFAULT_CACHE_ALIAS], name, value)

    def __delattr__(self, name):
        return delattr(caches[DEFAULT_CACHE_ALIAS], name)

    def __contains__(self, key):
        return key in caches[DEFAULT_CACHE_ALIAS]

    def __eq__(self, other):
        return caches[DEFAULT_CACHE_ALIAS] == other

    def __ne__(self, other):
        return caches[DEFAULT_CACHE_ALIAS] != other

cache = DefaultCacheProxy()


def _clear_cached(tags_func, cache_alias='default', *args, **kwargs):
    """
    Model's save and delete callback
    """
    obj = kwargs['instance']
    try:
        tags = tags_func(*args, **kwargs)
    except TypeError:
        tags = tags_func(obj)
    if not isinstance(tags, (list, tuple, set, frozenset)):
        tags = (tags, )
    if isinstance(cache_alias, string_types):
        cache = caches[cache_alias]
    else:
        cache = cache_alias
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
            apply_cache = len(data) > 2 and data[2] or 'default'
            model_signals.post_save.connect(
                curry(_clear_cached, tags_func, apply_cache),
                sender=Model, weak=False
            )
            model_signals.pre_delete.connect(
                curry(_clear_cached, tags_func, apply_cache),
                sender=Model, weak=False
            )

registry = CacheRegistry()


def autodiscover():
    """
    Auto-discover INSTALLED_APPS cachecontrol.py modules
    and fail silently when not present.
    """
    import importlib
    from django.conf import settings
    for app in settings.INSTALLED_APPS:
        try:
            __import__(app)
            importlib.import_module("caches", sys.modules[app].__path__)
        except (ImportError, ModuleNotFoundError):
            continue
        __import__("{0}.caches".format(app))


def close_caches(**kwargs):
    for cache in caches.all():
        cache.close()

core_signals.request_finished.connect(close_caches)
