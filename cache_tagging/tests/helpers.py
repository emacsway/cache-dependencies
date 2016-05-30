import time
import pickle
from cache_tagging.interfaces import BaseCache

_caches = {}
_expire_info = {}


class CacheStub(BaseCache):

    def __init__(self, name):
        self._cache = _caches.setdefault(name, {})
        self._expire_info = _expire_info.setdefault(name, {})
        self.default_timeout = 300

    def set(self, key, value, timeout=None, version=None):
        key = self.make_key(key, version=version)
        self.validate_key(key)
        self._cache[key] = self.pack(value)
        self._expire_info[key] = self.get_expiration(timeout)

    def get_expiration(self, timeout=None):
        if timeout is None:
            timeout = self.default_timeout
        return time.time() + timeout

    @staticmethod
    def pack(value):
        return pickle.dumps(value, pickle.HIGHEST_PROTOCOL)

    @staticmethod
    def unpack(pickled):
        return pickle.loads(pickled)
