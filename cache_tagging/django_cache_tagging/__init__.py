from __future__ import absolute_import, unicode_literals
import sys
import hashlib
from threading import local

from django.conf import settings
from django.core import signals as core_signals
from django.core.cache import DEFAULT_CACHE_ALIAS
from django.db.models import signals as model_signals
from django.utils.functional import curry
try:
    from django.core.cache import get_cache as django_get_cache
    django_caches = None
except ImportError:
    from django.core.cache import caches as django_caches
    django_get_cache = None

from cache_tagging.tagging import CacheTagging
from cache_tagging.relations import RelationManager, ThreadSafeRelationManagerDecorator
from cache_tagging.locks import TagsLock
from cache_tagging.transaction import TransactionManager, ThreadSafeTransactionManagerDecorator
from cache_tagging.nocache import NoCache

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
            isolation_level = options.get('ISOLATION_LEVEL', 'READ COMMITED')
            django_backend = options.get('BACKEND', backend)
            if django_caches:
                django_cache = django_caches[django_backend]
            else:
                django_cache = django_get_cache(django_backend, *args, **kwargs)

            def thread_safe_cache_accessor():
                return self(backend, *args, **kwargs)
            tags_lock = TagsLock.make(isolation_level, thread_safe_cache_accessor, delay)
            transaction = ThreadSafeTransactionManagerDecorator(TransactionManager(tags_lock))
            relation_manager = ThreadSafeRelationManagerDecorator(RelationManager())
            self._caches[key] = CacheTagging(
                django_cache, relation_manager, transaction
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
    import imp
    from django.conf import settings
    for app in settings.INSTALLED_APPS:
        try:
            __import__(app)
            imp.find_module("caches", sys.modules[app].__path__)
        except (ImportError, AttributeError):
            continue
        __import__("{0}.caches".format(app))


def close_caches(**kwargs):
    for cache in caches.all():
        cache.close()

core_signals.request_finished.connect(close_caches)
