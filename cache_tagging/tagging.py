# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import time
import random
import hashlib
import operator
import itertools

from cache_tagging.exceptions import TagLocked, InvalidTag
from cache_tagging.utils import get_thread_id, warn, make_tag_key

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)

# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange

TAG_TIMEOUT = 24 * 3600
MAX_TAG_KEY = 18446744073709551616     # 2 << 63


class CacheTagging(object):
    """Tags support for Django cache."""

    def __init__(self, cache, relation_manager, transaction):
        """Constructor of cache instance."""
        self.cache = cache
        self.ignore_descendants = False
        self.transaction = transaction
        self.relation_manager = relation_manager

    def get_or_set_callback(self, key, callback, tags=[], timeout=None,
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

        value, tag_versions = self._unpack_data(data)
        try:
            self._validate_tag_versions(tag_versions.items())
        except InvalidTag:
            return default

        self.finish(key, tag_versions.keys(), version=version)
        return value

    @staticmethod
    def _pack_data(value, tag_versions):
        return {
            '__value': value,
            '__tag_versions': tag_versions,
        }

    @classmethod
    def _unpack_data(cls, data):
        if cls._is_packed_data(data):
            return data['__value'], data['__tag_versions']
        else:
            return data, {}

    @staticmethod
    def _is_packed_data(data):
        return isinstance(data, dict) and '__tag_versions' in data and '__value' in data

    def _validate_tag_versions(self, tag_versions, version=None):
        if tag_versions:
            actual_tag_versions = self._get_tag_versions(set(map(operator.itemgetter(0), tag_versions)), version)
            invalid_tag_versions = set((tag, tag_version) for tag, tag_version in tag_versions
                                       if actual_tag_versions.get(tag) != tag_version)
            if invalid_tag_versions:
                raise InvalidTag(invalid_tag_versions)

    def _get_tag_versions(self, tags, version=None):
        tag_keys = {tag: make_tag_key(tag) for tag in tags}
        caches = self.cache.get_many(list(tag_keys.values()), version) or {}
        return {tag: caches[tag_key] for tag, tag_key in tag_keys.items() if tag_key in caches}

    def get_many(self, keys, version=None, abort=False):
        if not abort and not self.ignore_descendants:
            current_cache_node = self.relation_manager.current()
            for key in keys:
                self.begin(key)
                self.relation_manager.current(current_cache_node)

        caches = self.cache.get_many(keys, version)

        values, all_tag_versions = dict(), dict()
        for key, data in caches.items():
            values[key], all_tag_versions[key] = self._unpack_data(data)

        try:
            self._validate_tag_versions(set(itertools.chain(*[tuple(i.items()) for i in all_tag_versions.values() if i])))
        except InvalidTag as e:
            for key, tag_versions in all_tag_versions:
                if not self._is_valid_tag_versions(tag_versions, e.args[0]):
                    values.pop(key, None)

        for key in values:  # Looping trought filtered result
            self.finish(key, all_tag_versions[key], version=version)
        return values

    @staticmethod
    def _is_valid_tag_versions(tag_versions, invalid_tag_versions):
        for invalid_tag, invalid_tag_version in invalid_tag_versions:
            if tag_versions.get(invalid_tag) == invalid_tag_version:
                return False
        return True

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

        try:
            tag_versions = self._make_tag_versions(tags, version)
        except TagLocked:
            self.finish(key, tags, version=version)
            return

        self.finish(key, tags, version=version)
        return self.cache.set(key, self._pack_data(value, tag_versions), timeout, version)

    def _make_tag_versions(self, tags, version=None):
        tag_versions = {}
        if tags:
            tag_versions = self.transaction.current().get_tag_versions(tags, version)
            new_tag_versions = {tag: generate_tag_version() for tag in tags if tag_versions.get(tag) is None}
            if new_tag_versions:
                tag_versions.update(new_tag_versions)
                new_tag_key_versions = {make_tag_key(tag): tag_version for tag, tag_version in new_tag_versions.items()}
                self.cache.set_many(new_tag_key_versions, TAG_TIMEOUT, version)
        return tag_versions

    def invalidate_tags(self, *tags, **kwargs):
        """Invalidate specified tags"""
        if len(tags):
            version = kwargs.get('version', None)
            self.transaction.current().add_tags(tags, version=version)
            tag_keys = list(map(make_tag_key, tags))
            self.cache.delete_many(tag_keys, version=version)

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


def generate_tag_version():
    """ Generates a new unique identifier for tag version."""
    hash = hashlib.md5("{0}{1}{2}".format(
        randrange(0, MAX_TAG_KEY), get_thread_id(), time.time()
    ).encode('utf8')).hexdigest()
    return hash
