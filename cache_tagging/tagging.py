# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
from cache_tagging import interfaces
from cache_tagging.dependencies import CompositeDependency, DummyDependency, TagsDependency
from cache_tagging.exceptions import TagsLocked
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
        providing_dependency, invalid_tags = deferred.get()
        if invalid_tags:
            return default

        tag_versions = getattr(dependency, 'tags', set())
        self.finish(key, tag_versions, version=version)
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
            return data, DummyDependency()

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

        values, dependencies = dict(), dict()
        for key, data in caches.items():
            values[key], dependencies[key] = self._unpack_data(data)

        dependencies_reversed = {v: k for k, v in dependencies.items()}
        composite_dependency = CompositeDependency(*dependencies.values())
        deferred = composite_dependency.validate(self.cache, version)
        providing_dependency, invalid_dependencies = deferred.get()
        for providing_dependency, invalid_tags in invalid_dependencies:
            if invalid_tags:
                values.pop(dependencies_reversed[providing_dependency], None)

        for key in values:  # Looping through filtered result
            self.finish(key, getattr(dependencies[key], 'tags', set()), version=version)
        return values

    def set(self, key, value, tags=(), timeout=None, version=None):
        """Sets cache value and tags."""
        if not isinstance(tags, (list, tuple, set, frozenset)):  # Called as native API
            if timeout is not None and version is None:
                version = timeout
            timeout = tags
            self.finish(key, (), version=version)
            return self.cache.set(key, value, timeout, version)

        tags = set(tags)
        # pull tags from descendants (cached fragments)
        tags.update(self.relation_manager.get(key).get_tags(version))

        if tags:
            dependency = TagsDependency(tags)
        else:
            dependency = DummyDependency()

        try:
            self.transaction.current().evaluate(dependency, version)
        except TagsLocked:
            self.finish(key, tags, version=version)
            return

        self.finish(key, tags, version=version)
        return self.cache.set(key, self._pack_data(value, dependency), timeout, version)

    def invalidate_tags(self, *tags, **kwargs):
        """Invalidate specified tags"""
        dependency = None
        if len(tags) == 1 and isinstance(tags[0], interfaces.IDependency):
            dependency = tags[0]
        elif len(tags) == 1 and isinstance(tags[0], (list, tuple, set, frozenset)):
            dependency = TagsDependency(tags[0])
        elif tags:
            dependency = TagsDependency(tags)
        else:
            dependency = DummyDependency()

        version = kwargs.get('version', None)
        self.transaction.current().add_tags(getattr(dependency, 'tags', set()), version=version)
        dependency.invalidate(self.cache, version)

    def begin(self, key):
        """Start cache creating."""
        self.relation_manager.current(key)

    def abort(self, key):
        """Clean tags for given cache key."""
        self.relation_manager.pop(key)

    def finish(self, key, tags, version=None):
        """Start cache creating."""
        self.relation_manager.pop(key).add_tags(tags, version)

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
