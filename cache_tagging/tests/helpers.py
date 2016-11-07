import time
import pickle
from cache_tagging.cache import AbstractCache


class CacheStub(AbstractCache):

    def __init__(self):
        self._cache = {}
        self._expire_info = {}
        self.default_timeout = 300

    def add(self, key, value, timeout=None, version=None):
        key = self.make_key(key, version=version)
        self.validate_key(key)
        if self._has_expired(key):
            self._cache[key] = self.pack(value)
            self._expire_info[key] = self.get_expiration(timeout)
            return True
        return False

    def get(self, key, default=None, version=None):
        key = self.make_key(key, version=version)
        self.validate_key(key)
        if not self._has_expired(key):
            pickled = self._cache.get(key)
            if pickled is not None:
                return self.unpack(pickled, default)
        return default

    def set(self, key, value, timeout=None, version=None):
        key = self.make_key(key, version=version)
        self.validate_key(key)
        self._cache[key] = self.pack(value)
        self._expire_info[key] = self.get_expiration(timeout)

    def delete(self, key, version=None):
        key = self.make_key(key, version=version)
        self.validate_key(key)
        self._cache.pop(key, None)
        self._expire_info.pop(key, None)

    def clear(self):
        self._cache.clear()
        self._expire_info.clear()

    def get_expiration(self, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        return time.time() + timeout

    def _has_expired(self, key):
        exp = self._expire_info.get(key, -1)
        if exp is None or exp > time.time():
            return False
        return True

    @staticmethod
    def pack(value):
        return pickle.dumps(value, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def unpack(pickled, default=None):
        try:
            return pickle.loads(pickled)
        except pickle.PickleError:
            return default
