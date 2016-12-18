import unittest
from cache_dependencies import interfaces, dependencies, relations

try:
    from unittest import mock
except ImportError:
    import mock


class AbstractCacheNodeTestCase(unittest.TestCase):

    def run(self, result=None):
        if self.__class__.__name__.startswith('Abstract'):
            return
        super(AbstractCacheNodeTestCase, self).run(result)

    @staticmethod
    def _make_dependency():
        instance = mock.Mock(spec=interfaces.IDependency)
        instance.extend = mock.Mock(return_value=True)
        return instance


class CacheNodeTestCase(AbstractCacheNodeTestCase):
    def setUp(self):
        self.cache_key = 'key1'
        self.parent = mock.Mock(interfaces.ICacheNode)
        self.cache_node = relations.CacheNode(self.cache_key, self.parent)

    def test_parent(self):
        self.assertIs(self.cache_node.parent(), self.parent)

    def test_key(self):
        self.assertEqual(self.cache_node.key(), self.cache_key)

    def test_add_get_dependency(self):
        dependency1 = self._make_dependency()
        dependency1.id = 1
        dependency2 = self._make_dependency()
        dependency2.id = 2
        dependency3 = self._make_dependency()
        dependency3.id = 3
        self.cache_node.add_dependency(dependency1, None)
        self.parent.add_dependency.assert_called_once_with(dependency1, None)
        self.parent.reset_mock()

        self.cache_node.add_dependency(dependency2, None)
        self.parent.add_dependency.assert_called_once_with(dependency2, None)
        self.parent.reset_mock()
        dependency1.extend.assert_called_once_with(dependency2)
        dependency1.reset_mock()

        self.cache_node.add_dependency(dependency3, 1)
        self.parent.add_dependency.assert_called_once_with(dependency3, 1)
        self.parent.reset_mock()
        dependency1.extend.assert_not_called()

        dependency_none = self.cache_node.get_dependency(None)
        self.assertEqual(len(dependency_none.delegates), 1)
        self.assertEqual(dependency_none.delegates[0].id, 1)

        dependency_1 = self.cache_node.get_dependency(1)
        self.assertEqual(len(dependency_1.delegates), 1)
        self.assertEqual(dependency_1.delegates[0].id, 3)

    def test_get_dependency_none(self):
        self.assertIsInstance(self.cache_node.get_dependency(), dependencies.DummyDependency)

    def test_bool(self):
        self.assertTrue(self.cache_node)


class DummyCacheNodeTestCase(AbstractCacheNodeTestCase):
    def setUp(self):
        self.cache_node = relations.DummyCacheNode()

    def test_parent(self):
        self.assertIsInstance(self.cache_node.parent(), relations.DummyCacheNode)

    def test_add_dependency(self):
        self.cache_node.add_dependency(self._make_dependency())

    def test_get_dependency(self):
        self.assertIsInstance(self.cache_node.get_dependency(), dependencies.DummyDependency)

    def test_bool(self):
        self.assertFalse(self.cache_node)


class RelationManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.relation_manager = relations.RelationManager()

    def test_get(self):
        node_key1 = self.relation_manager.get('key1')
        self.assertIsInstance(node_key1, relations.CacheNode)
        self.assertEqual(node_key1.key(), 'key1')
        self.assertIsInstance(node_key1.parent(), relations.DummyCacheNode)

        node_key1_2 = self.relation_manager.get('key1')
        self.assertIs(node_key1, node_key1_2)

        node_key2 = self.relation_manager.get('key2')
        self.assertEqual(node_key2.key(), 'key2')
        self.assertIsNot(node_key2, node_key1)
        self.assertIsInstance(node_key2.parent(), relations.DummyCacheNode)

    def test_get_sets_parent(self):
        self.relation_manager.current('key1')
        node_key1 = self.relation_manager.get('key1')
        self.assertIsInstance(node_key1.parent(), relations.DummyCacheNode)

        node_key2 = self.relation_manager.get('key2')
        self.assertEqual(node_key2.key(), 'key2')
        self.assertIsNot(node_key2, node_key1)
        self.assertIs(node_key2.parent(), node_key1)

    def test_current_none(self):
        self.assertIsInstance(self.relation_manager.current(), relations.DummyCacheNode)

    def test_current_by_key(self):
        self.relation_manager.current('key1')
        node_key1 = self.relation_manager.current()
        self.assertEqual(node_key1.key(), 'key1')
        self.assertIsInstance(node_key1.parent(), relations.DummyCacheNode)

    def test_current_by_node(self):
        init_node_key1 = self.relation_manager.get('key1')
        self.relation_manager.current(init_node_key1)
        node_key1 = self.relation_manager.current()
        self.assertIs(node_key1, init_node_key1)

    def test_pop_none(self):
        self.assertIsInstance(self.relation_manager.pop('key1'), relations.DummyCacheNode)

    def test_pop_current(self):
        self.relation_manager.current('key1')
        init_node_key1 = self.relation_manager.get('key1')
        self.relation_manager.current('key2')
        init_node_key2 = self.relation_manager.get('key2')

        node_key2 = self.relation_manager.pop('key2')
        self.assertIs(node_key2, init_node_key2)
        self.assertIs(self.relation_manager.current(), init_node_key1)

    def test_pop_not_current(self):
        self.relation_manager.current('key1')
        init_node_key1 = self.relation_manager.get('key1')
        self.relation_manager.current('key2')
        init_node_key2 = self.relation_manager.get('key2')

        node_key1 = self.relation_manager.pop('key1')
        self.assertIs(node_key1, init_node_key1)
        self.assertIs(self.relation_manager.current(), init_node_key2)

    def test_clear(self):
        self.relation_manager.current('key1')
        init_node_key1 = self.relation_manager.get('key1')
        self.assertIsInstance(self.relation_manager.current(), relations.CacheNode)

        self.relation_manager.clear()
        self.assertIsInstance(self.relation_manager.current(), relations.DummyCacheNode)
        node_key1 = self.relation_manager.pop('key1')
        self.assertIsNot(node_key1, init_node_key1)
