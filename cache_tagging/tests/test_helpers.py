from unittest import TestCase
from .helpers import CacheStub


class CacheStubTest(TestCase):

    CACHE_NAME = 'default'

    def setUp(self):
        self.cache = CacheStub(self.CACHE_NAME)

    def test_set(self):
        self.cache.set('key1', 'value1')
        self.assertIn(self.cache.make_key('key1'), self.cache._cache)
        self.assertEqual(self.cache._cache[self.cache.make_key('key1')], self.cache.pack('value1'))
        self.assertIn(self.cache.make_key('key1'), self.cache._expire_info)

        self.cache.set('key1', 'value12', version=2)
        self.assertIn(self.cache.make_key('key1', version=2), self.cache._cache)
        self.assertEqual(self.cache._cache[self.cache.make_key('key1', version=2)], self.cache.pack('value12'))
        self.assertIn(self.cache.make_key('key1', version=2), self.cache._expire_info)
