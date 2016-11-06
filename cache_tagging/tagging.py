# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from cache_tagging import interfaces, dependencies, exceptions
from cache_tagging.utils import warn

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)

TAG_TIMEOUT = 24 * 3600


class CacheTagging(object):
    """Tags support for Django cache."""

    def __init__(self, cache, relation_manager, transaction):
        """Constructor of cache instance."""
        self.cache = cache
        self.ignore_descendants = False
        self.transaction = transaction
        self.relation_manager = relation_manager

    def get_or_set_callback(self, key, callback, tags=(), timeout=None,
                            version=None, args=None, kwargs=None):
        """Returns cache value if exists

        Otherwise calls cache_funcs, sets cache value to it and returns it.
        """
        value = self.get(key, version=version)
        if value is None:
            args = args or []
            kwargs = kwargs or {}
            value = callback(*args, **kwargs)
            self.set(key, value, tags, timeout, version)
        return value

    def get(self, key, default=None, version=None, abort=False):
        """Gets cache value.

        If one of cache tags is expired, returns default.
        """
        if not abort and not self.ignore_descendants:
            self.begin(key)
        data = self.cache.get(key, None, version)
        if data is None:
            return default

        value, dependency = self._unpack_data(data)

        deferred = dependency.validate(self.cache, version)
        validation_status = deferred.get()
        if not validation_status:
            return default

        self.finish(key, dependency, version=version)
        return value

    @staticmethod
    def _pack_data(value, tag_versions):
        return {
            '__value': value,
            '__dependency': tag_versions,
        }

    @classmethod
    def _unpack_data(cls, data):
        if cls._is_packed_data(data):
            return data['__value'], data['__dependency']
        else:
            return data, dependencies.DummyDependency()

    @staticmethod
    def _is_packed_data(data):
        return isinstance(data, dict) and '__dependency' in data and '__value' in data

    def get_many(self, keys, version=None, abort=False):
        if not abort and not self.ignore_descendants:
            current_cache_node = self.relation_manager.current()
            for key in keys:
                self.begin(key)
                self.relation_manager.current(current_cache_node)

        caches = self.cache.get_many(keys, version)

        cache_values, cache_dependencies = dict(), dict()
        for key, data in caches.items():
            cache_values[key], cache_dependencies[key] = self._unpack_data(data)

        dependencies_reversed = {v: k for k, v in cache_dependencies.items()}
        composite_dependency = dependencies.CompositeDependency(*cache_dependencies.values())
        deferred = composite_dependency.validate(self.cache, version)
        composite_validation_status = deferred.get()
        if not composite_validation_status:
            for dependency_validation_status in composite_validation_status:
                if not dependency_validation_status:
                    cache_values.pop(dependencies_reversed[dependency_validation_status.dependency], None)

        for key in cache_values:  # Looping through filtered result
            self.finish(key, cache_dependencies[key], version=version)
        return cache_values

    def set(self, key, value, tags=(), timeout=None, version=None):
        """Sets cache value and tags."""
        if not isinstance(tags, (list, tuple, set, frozenset, interfaces.IDependency)):  # Called as native API
            if timeout is not None and version is None:
                version = timeout
            timeout = tags
            self.finish(key, dependencies.DummyDependency(), version=version)
            return self.cache.set(key, value, timeout, version)

        if isinstance(tags, interfaces.IDependency):
            dependency = tags
        elif tags:
            dependency = dependencies.TagsDependency(tags)
        else:
            dependency = dependencies.DummyDependency()

        combined_dependency_with_descendants = dependencies.CompositeDependency()
        combined_dependency_with_descendants.extend(dependency)
        combined_dependency_with_descendants.extend(self.relation_manager.get(key).get_dependency(version))

        try:
            self.transaction.current().evaluate(combined_dependency_with_descendants, version)
        except exceptions.DependencyLocked:
            self.finish(key, dependency, version=version)
            return

        self.finish(key, dependency, version=version)
        return self.cache.set(key, self._pack_data(value, combined_dependency_with_descendants), timeout, version)

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
        self.transaction.current().add_dependency(dependency, version=version)
        dependency.invalidate(self.cache, version)

    def begin(self, key):
        """Start cache creating."""
        self.relation_manager.current(key)

    def abort(self, key):
        """Clean tags for given cache key."""
        self.relation_manager.pop(key)

    def finish(self, key, dependency, version=None):
        """Start cache creating."""
        self.relation_manager.pop(key).add_dependency(dependency, version)

    def close(self):
        self.transaction.flush()
        self.relation_manager.clear()
        # self.cache.close()

    def transaction_begin(self):
        warn('cache.transaction_begin()', 'cache.transaction.begin()')
        self.transaction.begin()
        return self

    def transaction_finish(self):
        warn('cache.transaction_finish()', 'cache.transaction.finish()')
        self.transaction.finish()
        return self

    def transaction_finish_all(self):
        warn('cache.transaction_finish_all()', 'cache.transaction.flush()')
        self.transaction.flush()
        return self

    def __getattr__(self, name):
        """Proxy for all native methods."""
        return getattr(self.cache, name)
