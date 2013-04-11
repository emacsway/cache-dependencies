from __future__ import absolute_import, unicode_literals
# -*- coding: utf-8 -*-
import os
import hashlib
import random
import time

from threading import local

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


__version__ = '0.7.6.2'

# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange

TAG_TIMEOUT = 24 * 3600
MAX_TAG_KEY = 18446744073709551616     # 2 << 63


class CacheTagging(object):
    """Tags support for Django cache."""

    def __init__(self, cache):
        """Constructor of cache instance."""
        self.cache = cache
        self.ignore_descendants = False
        self.ctx = local()

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
        if not hasattr(tags, '__iter__'):  # Called as native API
            if timeout is not None and version is None:
                version = timeout
            timeout = tags
            return self.cache.set(name, value, timeout, version)

        tags = set(tags)
        # pull tags from descendants (cached fragments)
        try:
            tags.update(self.get_ancestors()[name][version])
        except KeyError:
            pass

        tag_versions = {}
        if len(tags):
            tag_caches = self.cache.get_many(
                list(map(tag_prepare_name, tags))
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
                self.cache.set_many(tag_new_dict, TAG_TIMEOUT, version)

        data = {
            'tag_versions': tag_versions,
            'value': value,
        }

        self.finish(name, tags, version=version)
        return self.cache.set(name, data, timeout, version)

    def invalidate_tags(self, *tags, **kwargs):
        """Invalidate specified tags"""
        if len(tags):
            version = kwargs.get('version', None)
            tags_prepared = list(map(tag_prepare_name, set(tags)))
            self.add_to_transaction_scope(tags_prepared, version=version)
            self.cache.delete_many(tags_prepared, version=version)

    def get_ancestors(self):
        """Get transaction scopes. Using threading.local()"""
        if not hasattr(self.ctx, 'ancestors'):
            self.ctx.ancestors = {}
        return self.ctx.ancestors

    def add_to_ancestors(self, tags, version=None):
        """add tags to ancestor"""
        for cachename, versions in self.get_ancestors().items():
            versions.setdefault(version, set()).update(tags)

    def begin(self, name):
        """Start cache creating."""
        self.get_ancestors()[name] = {}

    def abort(self, name):
        """Clean tags for given cache name."""
        self.get_ancestors().pop(name, {})

    def finish(self, name, tags, version=None):
        """Start cache creating."""
        self.get_ancestors().pop(name, {})
        self.add_to_ancestors(tags, version=version)

    def transaction_begin(self):
        """Handles database transaction begin."""
        self.get_transaction_scopes().append({})
        return self

    def transaction_finish(self):
        """Handles database transaction commit or rollback.

        In any case (commit or rollback) we need to invalidate tags,
        because caches can be generated for
        current database session (for rollback case) or
        another database session (for commit case).
        So, method is named "transaction_finish" (not "transaction_commit"
        or "transaction_rollback")."""
        scope = self.get_transaction_scopes().pop()
        if len(scope):
            for version, tags in scope.items():
                self.cache.delete_many(list(tags), version=version)
        return self

    def transaction_finish_all(self):
        """Handles all database's transaction commit or rollback."""
        while len(self.get_transaction_scopes()):
            self.transaction_finish()
        return self

    def get_transaction_scopes(self):
        """Get transaction scopes."""
        if not hasattr(self.ctx, 'transaction_scopes'):
            self.ctx.transaction_scopes = []
        return self.ctx.transaction_scopes

    def add_to_transaction_scope(self, tags, version=None):
        """Adds cache names to current scope."""
        scopes = self.get_transaction_scopes()
        if len(scopes):
            scopes[-1].setdefault(version, set()).update(tags)

    def __getattr__(self, name):
        """Proxy for all native methods."""
        return getattr(self.cache, name)


def tag_prepare_name(name):
    """Adds prefixed namespace for tag name"""
    version = str(__version__).replace('.', '')
    name = hashlib.md5(str(name).encode('utf-8')).hexdigest()
    return 'tag_{0}_{1}'.format(version, name)


def tag_generate_version():
    """ Generates a new unique identifier for tag version."""
    pid = os.getpid()
    tid = _thread.get_ident()
    hash = hashlib.md5("{0}{1}{2}{3}".format(
        randrange(0, MAX_TAG_KEY),
        pid,
        tid,
        time.time()
    )).hexdigest()
    return hash
