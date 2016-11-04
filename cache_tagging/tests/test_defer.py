import unittest
from cache_tagging import defer

try:
    from unittest import mock
except ImportError:
    import mock


class DeferredTestCase(unittest.TestCase):
    # TODO:
    pass


class GetManyDeferredIteratorTestCase(unittest.TestCase):

    def test_get_many(self):
        cached = {
            'tag_1': 'tag_1_value',
            'tag_2': 'tag_2_value',
            'tag_3': 'tag_3_value',
            'tag_4': 'tag_4_value',
            'locked_tag_1': 'locked_tag_1_value',
            'locked_tag_2': 'locked_tag_2_value',
            'locked_tag_3': 'locked_tag_3_value',
            'locked_tag_4': 'locked_tag_4_value',
        }
        executor = mock.Mock(side_effect=lambda keys, versions: cached)
        deferred = defer.Deferred(executor, defer.GetManyDeferredIterator, None)
        deferred.add_callback(
            lambda _, caches: {'result1_' + k: v for k, v in caches.items()},
            set(('tag_1', 'tag_2',))
        )
        deferred2 = defer.Deferred(executor, defer.GetManyDeferredIterator, None)
        deferred2.add_callback(
            lambda _, caches: {'result2_' + k: v for k, v in caches.items()},
            set(('locked_tag_1', 'locked_tag_2',))
        )
        deferred += deferred2
        result2 = deferred.get()
        self.assertDictEqual(result2, {
            'result2_locked_tag_1': 'locked_tag_1_value',
            'result2_locked_tag_2': 'locked_tag_2_value',
        })
        result1 = deferred.get()
        self.assertDictEqual(result1, {
            'result1_tag_1': 'tag_1_value',
            'result1_tag_2': 'tag_2_value',
        })
        self.assertEqual(executor.call_count, 1)
        self.assertSetEqual(set(executor.call_args[0][0]),
                            set(('tag_1', 'tag_2', 'locked_tag_1', 'locked_tag_2',)))
        self.assertIsNone(executor.call_args[0][1])
        self.assertDictEqual(executor.call_args[1], dict())
