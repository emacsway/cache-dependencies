from cache_dependencies.utils import Undef


class IDependency(object):

    def evaluate(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        raise NotImplementedError

    def validate(self, cache, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        :rtype: cache_dependencies.interfaces.IDeferred
        """
        raise NotImplementedError

    def invalidate(self, cache, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        """
        raise NotImplementedError

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        raise NotImplementedError

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """
        raise NotImplementedError

    def extend(self, other):
        """
        :type other: cache_dependencies.interfaces.IDependency
        :rtype: bool
        """
        raise NotImplementedError

    def __copy__(self):
        """
        :rtype: cache_dependencies.interfaces.IDependency
        """
        raise NotImplementedError


class IDeferred(object):  # Queue?
    """
    :type queue: list[collections.Callable, tuple, dict]
    :type aggregation_criterion: tuple
    """
    queue = None
    aggregation_criterion = None

    def add_callback(self, callback, *args, **kwargs):  # put? apply?
        """
        :type callback: collections.Callable
        :rtype: cache_dependencies.interfaces.IDeferred
        """
        raise NotImplementedError

    def get(self):  # recv?
        raise NotImplementedError

    @property
    def parent(self):
        raise NotImplementedError

    @parent.setter
    def parent(self, parent):
        raise NotImplementedError

    @parent.deleter
    def parent(self):
        raise NotImplementedError

    def __iter__(self):
        raise NotImplementedError


class ICacheNode(object):

    def parent(self):
        """
        :rtype: cache_dependencies.interfaces.ICacheNode
        """
        raise NotImplementedError

    def key(self):
        """
        :rtype: str
        """
        raise NotImplementedError

    def add_dependency(self, dependency, version=None):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        raise NotImplementedError

    def get_dependency(self, version=None):
        """
        :type version: int or None
        :rtype dependency: cache_dependencies.interfaces.IDependency
        """
        raise NotImplementedError

    def __bool__(self):
        """
        :rtype: bool
        """

    def __nonzero__(self):
        return self.__bool__()


class IRelationManager(object):

    def get(self, key):
        """
        :type key: str
        :rtype: cache_dependencies.interfaces.ICacheNode
        """
        raise NotImplementedError

    def current(self, key_or_node=Undef):
        """
        :type key_or_node: str or cache_dependencies.interfaces.ICacheNode
        :rtype: cache_dependencies.interfaces.ICacheNode
        """
        raise NotImplementedError

    def pop(self, key):
        """
        :type key: str
        :rtype: cache_dependencies.interfaces.ICacheNode
        """
        raise NotImplementedError

    def clear(self):
        raise NotImplementedError


class IDependencyLock(object):

    def acquire(self, dependency, transaction, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        raise NotImplementedError

    def release(self, dependency, transaction, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        raise NotImplementedError

    def evaluate(self, dependency, transaction, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        raise NotImplementedError

    @staticmethod
    def make(isolation_level, thread_safe_cache_accessor, delay):
        """
        :type isolation_level: str
        :type thread_safe_cache_accessor: () -> cache_dependencies.interfaces.ICache
        :type delay: int
        :rtype: cache_dependencies.interfaces.IDependencyLock
        """
        raise NotImplementedError
    

class ITransaction(object):

    def get_session_id(self):
        """
        :rtype:
        """
        raise NotImplementedError

    def get_start_time(self):
        """
        :rtype: float
        """
        raise NotImplementedError

    def get_end_time(self):
        """
        :rtype: float
        """
        raise NotImplementedError

    def parent(self):
        """
        :rtype: cache_dependencies.interfaces.ITransaction
        """
        raise NotImplementedError

    def add_dependency(self, dependency, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        raise NotImplementedError

    def evaluate(self, dependency, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        raise NotImplementedError

    def finish(self):
        raise NotImplementedError

    def __bool__(self):
        """
        :rtype: bool
        """

    def __nonzero__(self):
        return self.__bool__()


class ITransactionManager(object):

    def __call__(self, func=None):
        raise NotImplementedError

    def __enter__(self):
        raise NotImplementedError

    def __exit__(self, *args):
        raise NotImplementedError

    def current(self, node=Undef):
        """
        :type node: cache_dependencies.interfaces.ITransaction
        :rtype: cache_dependencies.interfaces.ITransaction
        """
        raise NotImplementedError

    def begin(self):
        """Handles database transaction begin."""
        raise NotImplementedError

    def finish(self):
        """Handles database transaction commit or rollback.

        In any case (commit or rollback) we need to invalidate tags,
        because caches can be generated for
        current database session (for rollback case) or
        another database session (for commit case).
        So, method is named "finish" (not "commit"
        or "rollback").
        """
        raise NotImplementedError

    def flush(self):
        """Finishes all active transactions."""
        raise NotImplementedError


class ICache(object):
    """Historically used Django API interface."""
    def add(self, key, value, timeout=None, version=None):
        """
        Set a value in the cache if the key does not already exist. If
        timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.

        Returns True if the value was stored, False otherwise.
        """
        raise NotImplementedError

    def get(self, key, default=None, version=None):
        """
        Fetch a given key from the cache. If the key does not exist, return
        default, which itself defaults to None.
        """
        raise NotImplementedError

    def set(self, key, value, timeout=None, version=None):
        """
        Set a value in the cache. If timeout is given, that timeout will be
        used for the key; otherwise the default cache timeout will be used.
        """
        raise NotImplementedError

    def delete(self, key, version=None):
        """
        Delete a key from the cache, failing silently.
        """
        raise NotImplementedError

    def get_many(self, keys, version=None):
        """
        Fetch a bunch of keys from the cache. For certain backends (memcached,
        pgsql) this can be *much* faster when fetching multiple values.

        Returns a dict mapping each key in keys to its value. If the given
        key is missing, it will be missing from the response dict.
        """
        raise NotImplementedError

    def has_key(self, key, version=None):
        """
        Returns True if the key is in the cache and has not expired.
        """
        raise NotImplementedError

    def incr(self, key, delta=1, version=None):
        """
        Add delta to value in the cache. If the key does not exist, raise a
        ValueError exception.
        """
        raise NotImplementedError

    def decr(self, key, delta=1, version=None):
        """
        Subtract delta from value in the cache. If the key does not exist,
        raise a ValueError exception.
        """
        raise NotImplementedError

    def __contains__(self, key):
        """
        Returns True if the key is in the cache and has not expired.
        """
        # This is a separate method, rather than just a copy of has_key(),
        # so that it always has the same functionality as has_key(), even
        # if a subclass overrides it.
        raise NotImplementedError

    def set_many(self, data, timeout=None, version=None):
        """
        Set a bunch of values in the cache at once from a dict of key/value
        pairs.  For certain backends (memcached), this is much more efficient
        than calling set() multiple times.

        If timeout is given, that timeout will be used for the key; otherwise
        the default cache timeout will be used.
        """
        raise NotImplementedError

    def delete_many(self, keys, version=None):
        """
        Set a bunch of values in the cache at once.  For certain backends
        (memcached), this is much more efficient than calling delete() multiple
        times.
        """
        raise NotImplementedError

    def clear(self):
        """Remove *all* values from the cache at once."""
        raise NotImplementedError

    def incr_version(self, key, delta=1, version=None):
        """Adds delta to the cache version for the supplied key. Returns the
        new version.
        """
        raise NotImplementedError

    def decr_version(self, key, delta=1, version=None):
        """Substracts delta from the cache version for the supplied key.
        Returns the new version.
        """
        raise NotImplementedError

    def close(self, **kwargs):
        """Close the cache connection"""
        raise NotImplementedError
