import time
from unittest import TestCase
from .helpers import CacheStub


def f():
    return 1


class C:
    def m(n):
        return 2


class CacheStubTest(TestCase):
    """
    Because library historically uses Django cache API, - some tests here are taken from Django.
    """

    CACHE_NAME = 'default'

    def setUp(self):
        self.cache = CacheStub()

    def test_set_get(self):
        self.cache.set('key1', 'value1')
        self.assertEqual(self.cache.get('key1'), 'value1')

    def test_non_existent(self):
        self.assertIsNone(self.cache.get("non_existent_key"))
        self.assertEqual(self.cache.get("non_existent_key", 5), 5)

    def test_expiration(self):
        self.cache.set('key1', 'value', 1)
        self.cache.set('key2', 'value', 1)
        self.cache.set('key3', 'value', 1)

        time.sleep(2)
        self.assertIsNone(self.cache.get("key1"))

        self.cache.add("key2", "new_value")
        self.assertEqual(self.cache.get("key2"), "new_value")
        self.assertFalse(self.cache.has_key("key3"))

    def test_has_key(self):
        self.cache.set("key1", "val1")
        self.assertTrue(self.cache.has_key("key1"))
        self.assertFalse(self.cache.has_key("val1"))

    def test_in(self):
        self.cache.set("key1", "val1")
        self.assertIn("key1", self.cache)
        self.assertNotIn("val1", self.cache)

    def test_add(self):
        self.cache.add("addkey1", "value")
        result = self.cache.add("addkey1", "newvalue")
        self.assertFalse(result)
        self.assertEqual(self.cache.get("addkey1"), "value")

    def test_delete(self):
        self.cache.set("key1", "val1")
        self.cache.set("key2", "val2")
        self.assertEqual(self.cache.get("key1"), "val1")
        self.cache.delete("key1")
        self.assertIsNone(self.cache.get("key1"))
        self.assertEqual(self.cache.get("key2"), "val2")

    def test_incr(self):
        self.cache.set('answer', 41)
        self.assertEqual(self.cache.incr('answer'), 42)
        self.assertEqual(self.cache.get('answer'), 42)
        self.assertEqual(self.cache.incr('answer', 10), 52)
        self.assertEqual(self.cache.get('answer'), 52)
        self.assertEqual(self.cache.incr('answer', -10), 42)
        with self.assertRaises(ValueError):
            self.cache.incr('does_not_exist')

    def test_decr(self):
        self.cache.set('answer', 43)
        self.assertEqual(self.cache.decr('answer'), 42)
        self.assertEqual(self.cache.get('answer'), 42)
        self.assertEqual(self.cache.decr('answer', 10), 32)
        self.assertEqual(self.cache.get('answer'), 32)
        self.assertEqual(self.cache.decr('answer', -10), 42)
        with self.assertRaises(ValueError):
            self.cache.decr('does_not_exist')

    def test_set_many(self):
        self.cache.set_many({"key1": "val1", "key2": "val2"})
        self.assertEqual(self.cache.get("key1"), "val1")
        self.assertEqual(self.cache.get("key2"), "val2")

    def test_set_many_expiration(self):
        self.cache.set_many({"key1": "val1", "key2": "val2"}, 1)
        time.sleep(2)
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_get_many(self):
        self.cache.set('a', 'a_val')
        self.cache.set('b', 'b_val')
        self.cache.set('c', 'c_val')
        self.cache.set('d', 'd_val')
        self.assertDictEqual(self.cache.get_many(['a', 'c', 'd']), {'a': 'a_val', 'c': 'c_val', 'd': 'd_val'})
        self.assertDictEqual(self.cache.get_many(['a', 'b', 'e']), {'a': 'a_val', 'b': 'b_val'})

    def test_delete_many(self):
        self.cache.set("key1", "val1")
        self.cache.set("key2", "val2")
        self.cache.set("key3", "val3")
        self.cache.delete_many(["key1", "key2"])
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))
        self.assertEqual(self.cache.get("key3"), "val3")

    def test_clear(self):
        self.cache.set("key1", "val1")
        self.cache.set("key2", "val2")
        self.cache.clear()
        self.assertIsNone(self.cache.get("key1"))
        self.assertIsNone(self.cache.get("key2"))

    def test_multiple_data_types(self):
        stuff = {
            'string': 'this is a string',
            'int': 42,
            'list': [1, 2, 3, 4],
            'tuple': (1, 2, 3, 4),
            'dict': {'A': 1, 'B': 2},
            'function': f,
            'class': C,
        }
        self.cache.set("stuff", stuff)
        self.assertEqual(self.cache.get("stuff"), stuff)

    def test_cache_versioning_get_set(self):
        # set, using default version = 1
        self.cache.set('answer1', 42)
        self.assertEqual(self.cache.get('answer1'), 42)
        self.assertEqual(self.cache.get('answer1', version=1), 42)
        self.assertIsNone(self.cache.get('answer1', version=2))

    def test_cache_versioning_add(self):
        self.cache.add('answer1', 42, version=2)
        self.assertIsNone(self.cache.get('answer1', version=1))
        self.assertEqual(self.cache.get('answer1', version=2), 42)

        self.cache.add('answer1', 37, version=2)
        self.assertIsNone(self.cache.get('answer1', version=1))
        self.assertEqual(self.cache.get('answer1', version=2), 42)

        self.cache.add('answer1', 37, version=1)
        self.assertEqual(self.cache.get('answer1', version=1), 37)
        self.assertEqual(self.cache.get('answer1', version=2), 42)

    def test_cache_versioning_has_key(self):
        self.cache.set('answer1', 42)

        # has_key
        self.assertTrue(self.cache.has_key('answer1'))
        self.assertTrue(self.cache.has_key('answer1', version=1))
        self.assertFalse(self.cache.has_key('answer1', version=2))

    def test_cache_versioning_delete(self):
        self.cache.set('answer1', 37, version=1)
        self.cache.set('answer1', 42, version=2)
        self.cache.delete('answer1')
        self.assertIsNone(self.cache.get('answer1', version=1))
        self.assertEqual(self.cache.get('answer1', version=2), 42)

        self.cache.set('answer2', 37, version=1)
        self.cache.set('answer2', 42, version=2)
        self.cache.delete('answer2', version=2)
        self.assertEqual(self.cache.get('answer2', version=1), 37)
        self.assertIsNone(self.cache.get('answer2', version=2))

    def test_cache_versioning_incr_decr(self):
        self.cache.set('answer1', 37, version=1)
        self.cache.set('answer1', 42, version=2)
        self.cache.incr('answer1')
        self.assertEqual(self.cache.get('answer1', version=1), 38)
        self.assertEqual(self.cache.get('answer1', version=2), 42)
        self.cache.decr('answer1')
        self.assertEqual(self.cache.get('answer1', version=1), 37)
        self.assertEqual(self.cache.get('answer1', version=2), 42)

        self.cache.set('answer2', 37, version=1)
        self.cache.set('answer2', 42, version=2)
        self.cache.incr('answer2', version=2)
        self.assertEqual(self.cache.get('answer2', version=1), 37)
        self.assertEqual(self.cache.get('answer2', version=2), 43)
        self.cache.decr('answer2', version=2)
        self.assertEqual(self.cache.get('answer2', version=1), 37)
        self.assertEqual(self.cache.get('answer2', version=2), 42)

    def test_cache_versioning_get_set_many(self):
        self.cache.set_many({'ford1': 37, 'arthur1': 42})
        self.assertDictEqual(self.cache.get_many(['ford1', 'arthur1']), {'ford1': 37, 'arthur1': 42})
        self.assertDictEqual(self.cache.get_many(['ford1', 'arthur1'], version=1), {'ford1': 37, 'arthur1': 42})
        self.assertDictEqual(self.cache.get_many(['ford1', 'arthur1'], version=2), {})

        self.cache.set_many({'ford2': 37, 'arthur2': 42}, version=2)
        self.assertDictEqual(self.cache.get_many(['ford2', 'arthur2']), {})
        self.assertDictEqual(self.cache.get_many(['ford2', 'arthur2'], version=1), {})
        self.assertDictEqual(self.cache.get_many(['ford2', 'arthur2'], version=2), {'ford2': 37, 'arthur2': 42})

    def test_incr_version(self):
        self.cache.set('answer', 42, version=2)
        self.assertIsNone(self.cache.get('answer'))
        self.assertIsNone(self.cache.get('answer', version=1))
        self.assertEqual(self.cache.get('answer', version=2), 42)
        self.assertIsNone(self.cache.get('answer', version=3))

        self.assertEqual(self.cache.incr_version('answer', version=2), 3)
        self.assertIsNone(self.cache.get('answer'))
        self.assertIsNone(self.cache.get('answer', version=1))
        self.assertIsNone(self.cache.get('answer', version=2))
        self.assertEqual(self.cache.get('answer', version=3), 42)

        with self.assertRaises(ValueError):
            self.cache.incr_version('does_not_exist')

    def test_decr_version(self):
        self.cache.set('answer', 42, version=2)
        self.assertIsNone(self.cache.get('answer'))
        self.assertIsNone(self.cache.get('answer', version=1))
        self.assertEqual(self.cache.get('answer', version=2), 42)

        self.assertEqual(self.cache.decr_version('answer', version=2), 1)
        self.assertEqual(self.cache.get('answer'), 42)
        self.assertEqual(self.cache.get('answer', version=1), 42)
        self.assertIsNone(self.cache.get('answer', version=2))

        with self.assertRaises(ValueError):
            self.cache.decr_version('does_not_exist', version=2)
