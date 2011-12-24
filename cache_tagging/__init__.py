# -*- coding: utf-8 -*-
import os
import hashlib
import random
import time
import thread

from threading import local

from django.conf import settings
from django.core.cache import DEFAULT_CACHE_ALIAS
from django.core.cache import get_cache as django_get_cache
from django.db.models import signals
from django.utils.functional import curry

__version__ = 0.7

_thread_locals = local()

TAG_TIMEOUT = getattr(settings, 'CACHE_TAG_TIMEOUT', 24 * 3600)

# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange

MAX_TAG_KEY = 18446744073709551616L     # 2 << 63


class CacheTagging(object):
    """Tags support for Django cache."""

    def __init__(self, cache):
        """Constructor of cache instance."""
        self.cache = cache

    def get_or_set_callback(self, name, callback, tags=[], timeout=None,
                            version=None, args=None, kwargs=None):
        """
        Returns cache value if exists
        Otherwise calls cache_funcs, sets cache value to it and returns it.
        """
        value = self.get(name, version=version)
        if value is None:
            args = args or []
            kwargs = kwargs or {}
            value = callback(*args, **kwargs)
            self.set(name, value, tags, timeout, version)
        return value

    def set(self, name, value, tags=(), timeout=None, version=None):
        """Sets cache value and tags."""
        if not hasattr(tags, '__iter__'):  # Called native API
            if timeout is not None:
                version = timeout
            timeout = tags
            return self.cache.set(name, value, timeout, version)
        tag_versions = {}
        if len(tags):
            tags = set(tags)
            tag_caches = self.cache.get_many(
                map(tag_prepare_name, tags)
            )
            tag_new_dict = {}
            for tag in tags:
                tag_prepared = tag_prepare_name(tag)
                if tag_prepared not in tag_caches\
                        or tag_caches[tag_prepared] is None:
                    tag_version = tag_generate_version()
                    tag_new_dict[tag_prepared] = tag_version
                else:
                    tag_version = tag_caches[tag_prepared]
                tag_versions[tag] = tag_version
            if len(tag_new_dict):
                self.cache.set_many(tag_new_dict, TAG_TIMEOUT)

        data = {
            'tag_versions': tag_versions,
            'value': value,
        }
        return self.cache.set(name, data, timeout, version)

    def get(self, name, default=None, version=None):
        """Gets cache value.

        If one of cache tags is expired, returns default.
        """
        data = self.cache.get(name, None, version)
        if data is None:
            return default

        if 'tag_versions' not in data or 'value' not in data:
            return data  # Returns native API

        if len(data['tag_versions']):
            tag_caches = self.cache.get_many(
                map(tag_prepare_name, data['tag_versions'].keys())
            )
            for tag, tag_version in data['tag_versions'].iteritems():
                tag_prepared = tag_prepare_name(tag)
                if tag_prepared not in tag_caches\
                        or tag_caches[tag_prepared] != tag_version:
                    return default
        return data['value']

    def invalidate_tags(self, *tags):
        """Invalidate specified tags"""
        if len(tags):
            tags = set(tags)
            tags_prepared = map(tag_prepare_name, tags)
            self._add_to_scope(*tags_prepared)
            self.cache.delete_many(tags_prepared)

    def transaction_begin(self):
        """Handles database transaction begin."""
        self._get_scopes().append([])
        return self

    def transaction_finish(self):
        """Handles database transaction commit or rollback.

        In any case (commit or rollback) we need to invalidate tags,
        because caches can be generated for
        current database session (for rollback case) or
        another database session (for commit case).
        So, method is named "transaction_finish" (not "transaction_commit"
        or "transaction_rollback")."""
        scope = self._get_scopes().pop()
        if len(scope):
            self.cache.delete_many(scope)
        return self

    def transaction_finish_all(self):
        """Handles all database's transaction commit or rollback."""
        while len(self._get_scopes()):
            self.transaction_finish()
        return self

    def _get_scopes(self):
        """Get transaction scopes."""
        if not hasattr(_thread_locals, 'cache_transaction_scopes'):
            _thread_locals.cache_transaction_scopes = {}
        cls_id = id(self)
        if cls_id not in _thread_locals.cache_transaction_scopes:
            _thread_locals.cache_transaction_scopes[cls_id] = []
        return _thread_locals.cache_transaction_scopes[cls_id]

    def _add_to_scope(self, *args):
        """Adds cache names to current scope."""
        scopes = self._get_scopes()
        if len(scopes):
            scope = scopes[-1]
            for v in args:
                scope.append(v)

    def __getattr__(self, name):
        """Proxy for all native methods."""
        return getattr(self.cache, name)


def tag_prepare_name(name):
    """Adds prefixed namespace for tag name"""
    version = str(__version__).replace('.', '')
    name = hashlib.md5(unicode(name).encode('utf-8')).hexdigest()
    return u'tag_{0}_{1}'.format(version, name)


def tag_generate_version():
    """ Generates a new unique identifier for tag version."""
    pid = os.getpid()
    tid = thread.get_ident()
    hash = hashlib.md5("{0}{1}{2}{3}{4}".format(
        randrange(0, MAX_TAG_KEY),
        pid,
        tid,
        time.time(),
        settings.SECRET_KEY
    )).hexdigest()
    return hash


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
            signals.post_save.connect(curry(_clear_cached,
                                            tags_func,
                                            apply_cache),
                                      sender=Model,
                                      weak=False)
            signals.pre_delete.connect(curry(_clear_cached,
                                             tags_func,
                                             apply_cache),
                                       sender=Model,
                                       weak=False)

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
            imp.find_module("caches",
                            __import__(app, {}, {},
                                       [app.split(".")[-1]]).__path__)
        except ImportError:
            # there is no app admin.py, skip it
            continue
        __import__("%s.caches" % app)
