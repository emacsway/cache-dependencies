# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import os
import hashlib
import random
import socket
import threading
import time
import warnings
from functools import wraps

try:
    import _thread
except ImportError:
    import thread as _thread  # Python < 3.*

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


__version__ = '0.7.7.0'

# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange

TAG_TIMEOUT = 24 * 3600
TAG_LOCKING_TIMEOUT = 5
MAX_TAG_KEY = 18446744073709551616     # 2 << 63


def warn(old, new, stacklevel=3):
    warnings.warn(
        "{0} is deprecated. Use {1} instead".format(old, new),
        PendingDeprecationWarning,
        stacklevel=stacklevel
    )


class CacheTagging(object):
    """Tags support for Django cache."""

    def __init__(self, cache, tags_manager, transaction):
        """Constructor of cache instance."""
        self.cache = cache
        self.ignore_descendants = False
        self.transaction = transaction
        self.tags_manager = tags_manager

    def get_or_set_callback(self, name, callback, tags=[], timeout=None,
                            version=None, args=None, kwargs=None):
        """Returns cache value if exists

        Otherwise calls cache_funcs, sets cache value to it and returns it.
        """
        value = self.get(name, version=version)
        if value is None:
            args = args or []
            kwargs = kwargs or {}
            value = callback(*args, **kwargs)
            self.set(name, value, tags, timeout, version)
        return value

    def get(self, name, default=None, version=None, abort=False):
        """Gets cache value.

        If one of cache tags is expired, returns default.
        """
        if not abort and not self.ignore_descendants:
            self.begin(name)
        data = self.cache.get(name, None, version)
        if data is None:
            return default

        if not isinstance(data, dict) or 'tag_versions' not in data\
                or 'value' not in data:
            return data  # Returns native API

        # Just idea, and, maybe, not good idea.
        # Cache can be many times rewrited on highload with
        # high overlap of transactions.
        # if self.transaction.scopes:
        #     transaction_start_time = self.transaction.scopes[0]['time']
        #     if self.transaction.delay:
        #         transaction_start_time -= self.transaction.delay
        #     if transaction_start_time <= data['time'] and data['thread_id'] != get_thread_id():
        #         return default

        if len(data['tag_versions']):
            tag_caches = self.cache.get_many(
                list(map(tag_prepare_name, list(data['tag_versions'].keys()))),
                version
            )
            for tag, tag_version in data['tag_versions'].items():
                tag_prepared = tag_prepare_name(tag)
                if tag_prepared not in tag_caches\
                        or tag_caches[tag_prepared] != tag_version:
                    return default

        self.finish(name, data['tag_versions'].keys(), version=version)
        return data['value']

    def set(self, name, value, tags=(), timeout=None, version=None):
        """Sets cache value and tags."""
        if not isinstance(tags, (list, tuple, set, frozenset)):  # Called as native API
            if timeout is not None and version is None:
                version = timeout
            timeout = tags
            return self.cache.set(name, value, timeout, version)

        tags = set(tags)
        # pull tags from descendants (cached fragments)
        tags.update(self.tags_manager.get(name).values(version))

        tag_versions = {}
        if len(tags):
            tag_cache_names = list(map(tag_prepare_name, tags))
            # tag_caches = self.cache.get_many(tag_cache_names, version) or {}
            try:
                tag_caches = self.transaction.get_tags(tag_cache_names, version)
            except TagLocked:
                self.finish(name, tags, version=version)
                return

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
                self.cache.set_many(tag_new_dict, TAG_TIMEOUT, version)

        data = {
            'tag_versions': tag_versions,
            'value': value,
            # 'time': time.time(),
            # 'thread_id': get_thread_id(),
        }

        self.finish(name, tags, version=version)
        return self.cache.set(name, data, timeout, version)

    def invalidate_tags(self, *tags, **kwargs):
        """Invalidate specified tags"""
        if len(tags):
            version = kwargs.get('version', None)
            tags_prepared = list(map(tag_prepare_name, set(tags)))
            self.transaction.add_tags(tags_prepared, version=version)
            self.cache.delete_many(tags_prepared, version=version)

    def begin(self, name):
        """Start cache creating."""
        self.tags_manager.current(name)

    def abort(self, name):
        """Clean tags for given cache name."""
        self.tags_manager.pop(name)

    def finish(self, name, tags, version=None):
        """Start cache creating."""
        self.tags_manager.pop(name).add(tags, version)

    def close(self):
        self.transaction.flush()
        self.tags_manager.clear()
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

    def get_transaction_scopes(self):
        warn('cache.get_transaction_scope()', 'cache.transaction.scopes')
        return self.transaction.scopes

    def add_to_transaction_scope(self, tags, version=None):
        warn('cache.add_to_transaction_scope()', 'cache.transaction.add_tags()')
        self.transaction.add_tags(tags, version)

    def __getattr__(self, name):
        """Proxy for all native methods."""
        return getattr(self.cache, name)


def get_thread_id():
    """Returs id for current thread."""
    return '{0}.{1}.{2}'.format(
        socket.gethostname(), os.getpid(), _thread.get_ident()
    )


def tag_prepare_name(name):
    """Adds prefixed namespace for tag name"""
    version = str(__version__).replace('.', '')
    name = hashlib.md5(str(name).encode('utf-8')).hexdigest()
    return 'tag_{0}_{1}'.format(version, name)


def tag_generate_version():
    """ Generates a new unique identifier for tag version."""
    hash = hashlib.md5("{0}{1}{2}".format(
        randrange(0, MAX_TAG_KEY), get_thread_id(), time.time()
    ).encode('utf8')).hexdigest()
    return hash


class TagsManager(object):

    class Tags(object):

        def __init__(self, name, parent=None):
            self._name = name
            self._parent = parent
            self._tags = dict()

        def parent(self):
            return self._parent

        def name(self):
            return self._name

        def add(self, tags, version=None):
            if version not in self._tags:
                self._tags[version] = set()
            self._tags[version] |= set(tags)
            if self._parent is not None:
                self._parent.add(tags, version)

        def values(self, version=None):
            try:
                return self._tags[version]
            except KeyError:
                return set()

    class NoneTags(Tags):
        """Using pattern Special Case"""
        def __init__(self):
            pass

        def parent(self):
            return None

        def name(self):
            return 'NoneTags'

        def add(self, tags, version=None):
            pass

        def values(self, version=None):
            return set()

    class Undef(object):
        pass

    def __init__(self):
        self._current = None
        self._data = dict()  # recursive cache is not possible, so, using dict instead of stack.

    def get(self, name):
        if name not in self._data:
            self._data[name] = self.Tags(name, self._current)
        return self._data[name]

    def pop(self, name):
        try:
            node = self._data.pop(name)
        except KeyError:
            node = self.NoneTags()

        if self.current() is node:
            self.current(node.parent())
        return node

    def current(self, name_or_node=Undef):
        if name_or_node is self.Undef:
            return self._current or self.NoneTags()
        if isinstance(name_or_node, string_types):
            node = self.get(name_or_node)
        else:
            node = name_or_node
        self._current = node

    def clear(self):
        self._data = dict()


class TagLocked(Exception):
    pass


# TODO: Replace Type Code with Subclasses
class Transaction(object):

    LOCK_PREFIX = "lock"
    STATUS_INVALIDATION = 0
    STATUS_COMMIT = 1

    def __init__(self, thread_safe_cache_accessor, delay=None, nonrepeatable_reads=False):
        """Constructor of Transaction instance."""
        self.cache = thread_safe_cache_accessor
        self.delay = delay
        self.nonrepeatable_reads = nonrepeatable_reads
        self.scopes = []

    def __call__(self, f=None):
        if f is None:
            return self

        @wraps(f)
        def _decorated(*args, **kw):
            with self:
                rv = f(*args, **kw)
            return rv

        return _decorated

    def __enter__(self):
        self.begin()

    def __exit__(self, *args):
        self.finish()
        return False

    def get_locked_tag_name(self, tag):
        return '{0}_{1}'.format(self.LOCK_PREFIX, tag)

    def lock_tags(self, tags, status, version=None):
        """Locks tags for concurrent transactions."""
        if self.nonrepeatable_reads:
            timeout = TAG_LOCKING_TIMEOUT
            if self.delay:
                timeout += self.delay
            data = (time.time(), status, get_thread_id())
            self.cache().set_many(
                {self.get_locked_tag_name(tag): data for tag in tags},
                timeout, version
            )

    def get_tags(self, tags, version=None):
        """Returns tags dict if all tags is not locked.

        Raises TagLocked, if current transaction has been started earlier
        than any tag has been invalidated by concurent process.
        Actual for SERIALIZABLE and REPEATABLE READ transaction levels.
        """
        cache_names = list(tags)
        if self.nonrepeatable_reads and self.scopes:
            top_scope = self.scopes[0]
            top_scope_tags = top_scope['tags'].get(version, set())
            cache_names += list(map(self.get_locked_tag_name, top_scope_tags))

        caches = self.cache().get_many(cache_names, version) or {}
        tag_caches = {k: v for k, v in caches.items() if k in tags}
        locked_tag_caches = {k: v for k, v in caches.items() if k not in tags}

        if locked_tag_caches:
            transaction_start_time = top_scope['time']
            if self.delay:
                transaction_start_time -= self.delay
            current_tread_id = get_thread_id()
            for tag_time, tag_status, tag_thread_id in locked_tag_caches.values():
                if (current_tread_id != tag_thread_id and
                    (transaction_start_time <= tag_time or
                     tag_status == self.STATUS_INVALIDATION)):
                    raise TagLocked
        return tag_caches

    def begin(self):
        """Handles database transaction begin."""
        self.scopes.append({'time': time.time(), 'tags': {}})
        return self

    def _finish_delayed(self, scope):
        """Just helper for async. Actual for DB replication (slave delay)."""
        for version, tags in scope['tags'].items():
            self.cache().delete_many(list(tags), version=version)
            self.lock_tags(tags, self.STATUS_COMMIT, version)

    def finish(self):
        """Handles database transaction commit or rollback.

        In any case (commit or rollback) we need to invalidate tags,
        because caches can be generated for
        current database session (for rollback case) or
        another database session (for commit case).
        So, method is named "finish" (not "commit"
        or "rollback").
        """
        scope = self.scopes.pop()
        self._finish_delayed(scope)
        if self.delay and not self.nonrepeatable_reads:
            threading.Timer(self.delay, self._finish_delayed, [scope]).start()
        return self

    def flush(self):
        """Finishes all active transactions."""
        while len(self.scopes):
            self.finish()
        return self

    def add_tags(self, tags, version=None):
        """Adds cache names to current scope."""
        for scope in self.scopes:
            scope['tags'].setdefault(version, set()).update(tags)
        self.lock_tags(tags, self.STATUS_INVALIDATION, version)
