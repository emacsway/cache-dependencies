# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from cache_dependencies import interfaces, dependencies, utils
from cache_dependencies.cache import CacheWrapper


class CacheTagging(object):  # Backward compatibility

    def __init__(self, cache, relation_manager, transaction):
        """Constructor of cache instance."""
        self.cache = CacheWrapper(cache, relation_manager, transaction)

    def get_or_set_callback(self, key, callback, tags=(), timeout=None,
                            version=None, args=None, kwargs=None):
        """Returns cache value if exists

        Otherwise calls cache_funcs, sets cache value to it and returns it.
        """
        value = self.get(key, version=version)
        if value is None:
            args = args or ()
            kwargs = kwargs or {}
            value = callback(*args, **kwargs)
            self.set(key, value, tags, timeout, version)
        return value

    def set(self, key, value, tags=(), timeout=None, version=None):
        """Sets cache value and tags."""
        if not isinstance(tags, (list, tuple, set, frozenset, interfaces.IDependency)):  # Called as native API
            if version is None and timeout is not None:
                version = timeout
            tags, timeout = dependencies.DummyDependency(), tags

        if isinstance(tags, interfaces.IDependency):
            dependency = tags
        elif tags:
            dependency = dependencies.TagsDependency(tags)
        else:
            dependency = dependencies.DummyDependency()
        self.cache.set(key, value, dependency, timeout, version)

    def invalidate_tags(self, *tags, **kwargs):
        """Invalidate specified tags"""
        if len(tags) == 1 and isinstance(tags[0], interfaces.IDependency):
            dependency = tags[0]
        elif len(tags) == 1 and isinstance(tags[0], (list, tuple, set, frozenset)):
            dependency = dependencies.TagsDependency(tags[0])
        elif tags:
            dependency = dependencies.TagsDependency(tags)
        else:
            dependency = dependencies.DummyDependency()
        version = kwargs.get('version', None)
        self.cache.invalidate_dependency(dependency, version)

    def transaction_begin(self):
        utils.warn('cache.transaction_begin()', 'cache.transaction.begin()')
        self.transaction.begin()
        return self

    def transaction_finish(self):
        utils.warn('cache.transaction_finish()', 'cache.transaction.finish()')
        self.transaction.finish()
        return self

    def transaction_finish_all(self):
        utils.warn('cache.transaction_finish_all()', 'cache.transaction.flush()')
        self.transaction.flush()
        return self

    def __getattr__(self, name):
        """Proxy for all native methods."""
        return getattr(self.cache, name)
