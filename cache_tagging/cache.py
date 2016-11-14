# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import warnings
from cache_tagging import interfaces, exceptions, dependencies

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


class CacheWrapper(object):  # Adapter
    """Supports for Django dependency."""

    def __init__(self, cache, relation_manager, transaction):
        """Constructor of cache instance.

        :type cache: cache_tagging.interfaces.ICache
        :type relation_manager: cache_tagging.interfaces.IRelationManager
        :type transaction: cache_tagging.interfaces.ITransactionManager
        """
        self.cache = cache
        self.ignore_descendants = False
        self.transaction = transaction
        self.relation_manager = relation_manager

    def get_or_set_callback(self, key, callback, dependency, timeout=None,
                            version=None, args=None, kwargs=None):
        """Returns cache value if exists

        Otherwise calls cache_funcs, sets cache value to it and returns it.

        :type key: str
        :type callback: collections.Callable
        :type dependency: cache_tagging.interfaces.IDependency
        :type timeout: int or None
        :type version: int or None
        :type args: tuple
        :type kwargs: dict
        """
        value = self.get(key, version=version)
        if value is None:
            args = args or []
            kwargs = kwargs or {}
            value = callback(*args, **kwargs)
            self.set(key, value, dependency, timeout, version)
        return value

    def get(self, key, default=None, version=None, abort=False):
        """Gets cache value.

        If one of cache dependencies is expired, returns default.

        :type key: str
        :type default: object
        :type version: int or None
        :type abort: bool
        """
        if not abort and not self.ignore_descendants:
            self.begin(key)
        data = self.cache.get(key, None, version)
        if data is None:
            return default

        value, dependency = self._unpack_data(data)

        deferred = dependency.validate(self.cache, version)
        try:
            deferred.get()
        except exceptions.DependencyInvalid:
            return default

        self.finish(key, dependency, version=version)
        return value

    def get_many(self, keys, version=None, abort=False):
        """
        :type keys: collections.Iterable[str]
        :type version: int or None
        :type abort: bool
        """
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
        try:
            deferred.get()
        except exceptions.DependencyInvalid as composite_error:
            for dependency_error in composite_error:
                cache_values.pop(dependencies_reversed[dependency_error.dependency], None)

        for key in cache_values:  # Looping through filtered result
            self.finish(key, cache_dependencies[key], version=version)
        return cache_values

    def set(self, key, value, dependency=None, timeout=None, version=None):
        """Sets cache value and dependency.

        :type key: str
        :type value: object
        :type dependency: cache_tagging.interfaces.IDependency or None
        :type timeout: int or None
        :type version: int or None
        """
        if dependency is None:
            dependency = dependencies.DummyDependency()
        combined_dependency_with_descendants = dependencies.CompositeDependency()
        combined_dependency_with_descendants.extend(dependency)
        combined_dependency_with_descendants.extend(self.relation_manager.get(key).get_dependency(version))

        try:
            self.transaction.current().evaluate(combined_dependency_with_descendants, version)
            # if tags will be invalidated again during this time by concurrent transaction - no problem, we just
            # save cache with invalid tags, and no one can read this cache.
        except exceptions.DependencyLocked:
            pass
        else:
            return self.cache.set(key, self._pack_data(value, combined_dependency_with_descendants), timeout, version)
        finally:
            self.finish(key, dependency, version=version)


    def invalidate_dependency(self, dependency, version=None):
        """Invalidate dependency.

        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """
        self.transaction.current().add_dependency(dependency, version=version)
        dependency.invalidate(self.cache, version)

    def begin(self, key):
        """Start cache creating.

        :type key: str
        """
        self.relation_manager.current(key)

    def abort(self, key):
        """Clean dependencies for given cache key.

        :type key: str
        """
        self.relation_manager.pop(key)

    def finish(self, key, dependency, version=None):
        """Start cache creating.

        :type key: str
        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """
        self.relation_manager.pop(key).add_dependency(dependency, version)

    def close(self):
        self.transaction.flush()
        self.relation_manager.clear()
        # self.cache.close()  # should be closed directly or by signal, for example, request_finished in Django.

    @staticmethod
    def _pack_data(value, dependency):
        return {
            '__value': value,
            '__dependency': dependency,
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

    def __getattr__(self, name):
        """Delegate for all native methods."""
        return getattr(self.cache, name)


def default_key_func(key, key_prefix, version):
    """
    Default function to generate keys.

    Constructs the key used by all other methods. By default it prepends
    the `key_prefix'. KEY_FUNCTION can be used to specify an alternate
    function with custom key making behavior.
    """
    return '%s:%s:%s' % (key_prefix, version, key)


class AbstractCache(interfaces.ICache):
    """Historically used Django API interface.

    You can make adapter for any cache system.
    """

    # Memcached does not accept keys longer than this.
    MEMCACHE_MAX_KEY_LENGTH = 250

    key_prefix = ''
    version = 1
    key_func = staticmethod(default_key_func)

    def make_key(self, key, version=None):
        """Constructs the key used by all other methods. By default it
        uses the key_func to generate a key (which, by default,
        prepends the `key_prefix' and 'version'). An different key
        function can be provided at the time of cache construction;
        alternatively, you can subclass the cache backend to provide
        custom key making behavior.
        """
        if version is None:
            version = self.version

        new_key = self.key_func(key, self.key_prefix, version)
        return new_key

    def get_many(self, keys, version=None):
        """
        Fetch a bunch of keys from the cache. For certain backends (memcached,
        pgsql) this can be *much* faster when fetching multiple values.

        Returns a dict mapping each key in keys to its value. If the given
        key is missing, it will be missing from the response dict.
        """
        d = {}
        for k in keys:
            val = self.get(k, version=version)
            if val is not None:
                d[k] = val
        return d

    def has_key(self, key, version=None):
        """
        Returns True if the key is in the cache and has not expired.
        """
        return self.get(key, version=version) is not None

    def incr(self, key, delta=1, version=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        value = self.get(key, version=version)
        if value is None:
            raise ValueError("Key '%s' not found" % key)
        new_value = value + delta
        self.set(key, new_value, version=version)
        return new_value

    def decr(self, key, delta=1, version=None):
        """
        Subtract delta from value in the cache. If the key does not exist,
        raise a ValueError exception.
        """
        return self.incr(key, -delta, version=version)

    def __contains__(self, key):
        """
        Returns True if the key is in the cache and has not expired.
        """
        # This is a separate method, rather than just a copy of has_key(),
        # so that it always has the same functionality as has_key(), even
        # if a subclass overrides it.
        return self.has_key(key)

    def set_many(self, data, timeout=None, version=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs.  For certain backends (memcached), this is much more efficient
        than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        for key, value in data.items():
            self.set(key, value, timeout=timeout, version=version)

    def delete_many(self, keys, version=None):
        """
        Set a bunch of values in the cache at once.  For certain backends
        (memcached), this is much more efficient than calling delete() multiple
        times.
        """
        for key in keys:
            self.delete(key, version=version)

    def validate_key(self, key):
        """
        Warn about keys that would not be portable to the memcached
        backend. This encourages (but does not force) writing backend-portable
        cache code.

        """
        if len(key) > self.MEMCACHE_MAX_KEY_LENGTH:
            warnings.warn(
                'Cache key will cause errors if used with memcached: ' +
                '{0} (longer than {1})'.format(key, self.MEMCACHE_MAX_KEY_LENGTH)
            )
        for char in key:
            if ord(char) < 33 or ord(char) == 127:
                warnings.warn(
                    'Cache key contains characters that will cause ' +
                    'errors if used with memcached: {0:!r}'.format(key)
                )

    def incr_version(self, key, delta=1, version=None):
        """Adds delta to the cache version for the supplied key. Returns the
        new version.
        """
        if version is None:
            version = self.version

        value = self.get(key, version=version)
        if value is None:
            raise ValueError("Key '%s' not found" % key)

        self.set(key, value, version=version + delta)
        self.delete(key, version=version)
        return version + delta

    def decr_version(self, key, delta=1, version=None):
        """Substracts delta from the cache version for the supplied key.
        Returns the new version.
        """
        return self.incr_version(key, -delta, version)

    def close(self, **kwargs):
        """Close the cache connection"""
        pass
