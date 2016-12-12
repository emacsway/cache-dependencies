import copy
import unittest
from cache_dependencies import defer

try:
    from unittest import mock
except ImportError:
    import mock


class DeferredTestCase(unittest.TestCase):
    def test_parent(self):
        d1 = defer.DeferredNode(None, defer.NoneDeferredIterator)
        d2 = defer.DeferredNode(None, defer.NoneDeferredIterator)
        d1.parent = d2
        d3 = defer.DeferredNode(None, defer.NoneDeferredIterator)
        d2.parent = d3

        d4 = defer.DeferredNode(None, defer.NoneDeferredIterator)
        d5 = defer.DeferredNode(None, defer.NoneDeferredIterator)
        d4.parent = d5

        d1.parent = d4

        d_order = [d1, d2, d3, d4, d5, None]
        for i in range(0, 4):
            self.assertIs(d_order[i].parent, d_order[i + 1],
                          "d{0}.parent is not d{1}".format(i + 1, i + 2))

    def test_iadd(self):
        d0 = defer.Deferred(None, defer.NoneDeferredIterator, 0)
        d0.add_callback(lambda *a, **kw: 0)
        dn0 = d0.node
        d1 = defer.Deferred(None, defer.NoneDeferredIterator, 1)
        d1.add_callback(lambda *a, **kw: 1)
        dn1 = d1.node
        d2 = defer.Deferred(None, defer.NoneDeferredIterator, 2)
        d2.add_callback(lambda *a, **kw: 2)
        dn2 = d2.node
        d3 = defer.Deferred(None, defer.NoneDeferredIterator, 3)
        d3.add_callback(lambda *a, **kw: 3)
        dn3 = d3.node
        d4 = defer.Deferred(None, defer.NoneDeferredIterator, 4)
        d4.add_callback(lambda *a, **kw: 4)
        dn4 = d4.node
        d5 = defer.Deferred(None, defer.NoneDeferredIterator, 5)
        d5.add_callback(lambda *a, **kw: 5)
        dn5 = d5.node
        d31 = defer.Deferred(None, defer.NoneDeferredIterator, 3)
        d31.add_callback(lambda *a, **kw: 31)
        dn31 = d31.node
        d32 = defer.Deferred(None, defer.NoneDeferredIterator, 3)
        d32.add_callback(lambda *a, **kw: 32)
        dn32 = d32.node

        d_ = defer.Deferred(None, defer.NoneDeferredIterator, 3)
        d_ += d32
        d_ += d31
        d_ += d2
        d_ += d1
        d_ += d0

        d = defer.Deferred(None, defer.NoneDeferredIterator, 5)
        d += d5
        d += d4
        d += d3
        d += d_

        node = d.node
        c = 0
        while node:
            self.assertEqual(len(node.queue), 3 if c == 3 else 1)
            if c == 3:
                for i, n in enumerate([dn3, dn32, dn31]):
                    self.assertListEqual(node.queue[i], n.queue[0])
            self.assertTupleEqual(node.args, (c,))
            self.assertNotIn(node, [dn0, dn1, dn2, dn3, dn4, dn5, d31, d32])
            c += 1
            node = node.parent
        self.assertEqual(c, 5 + 1)
        self.assertTupleEqual(tuple(d), (0, 1, 2, 31, 32, 3, 4, 5))


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
        executor1 = mock.Mock(side_effect=lambda keys, versions: cached)
        deferred = defer.Deferred(executor1, defer.GetManyDeferredIterator, None)
        deferred.add_callback(
            lambda node, caches, keys: {'result1_' + k: v for k, v in caches.items()},
            {'tag_1', 'tag_2'}
        )

        executor2 = mock.Mock(side_effect=lambda keys, versions: cached)
        deferred2 = defer.Deferred(executor2, defer.GetManyDeferredIterator, 1)
        deferred2.add_callback(
            lambda node, caches, keys: {'result2_' + k: v for k, v in caches.items()},
            {'tag_3', 'tag_4'}
        )
        deferred += deferred2

        deferred3 = defer.Deferred(executor1, defer.GetManyDeferredIterator, None)
        deferred3.add_callback(
            lambda node, caches, keys: {'result3_' + k: v for k, v in caches.items()},
            {'locked_tag_1', 'locked_tag_2'}
        )
        deferred += deferred3
        result3 = deferred.get()

        self.assertDictEqual(result3, {
            'result3_locked_tag_1': 'locked_tag_1_value',
            'result3_locked_tag_2': 'locked_tag_2_value',
        })

        result2 = deferred.get()
        self.assertDictEqual(result2, {
            'result2_tag_3': 'tag_3_value',
            'result2_tag_4': 'tag_4_value',
        })

        result1 = deferred.get()
        self.assertDictEqual(result1, {
            'result1_tag_1': 'tag_1_value',
            'result1_tag_2': 'tag_2_value',
        })

        executor1.assert_called_once_with({'tag_1', 'tag_2', 'locked_tag_1', 'locked_tag_2'}, None)
        executor2.assert_called_once_with({'tag_3', 'tag_4'}, 1)
