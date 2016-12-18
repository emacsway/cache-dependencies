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


class InitCacheNodeTestCase(AbstractCacheNodeTestCase):
    def setUp(self):
        self.cache_key = 'key1'
        self.cache_node = relations.CacheNode(self.cache_key)

    def test_parent(self):
        self.assertIsInstance(self.cache_node.parent(), relations.DummyCacheNode)

    def test_get_dependency(self):
        self.assertIsInstance(self.cache_node.get_dependency(), dependencies.DummyDependency)


class NestedCacheNodeTestCase(AbstractCacheNodeTestCase):
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


class DummyCacheNodeTestCase(AbstractCacheNodeTestCase):
    def setUp(self):
        self.cache_node = relations.DummyCacheNode()

    def test_parent(self):
        self.assertIsInstance(self.cache_node.parent(), relations.DummyCacheNode)

    def test_add_dependency(self):
        self.cache_node.add_dependency(self._make_dependency())

    def test_get_dependency(self):
        self.assertIsInstance(self.cache_node.get_dependency(), dependencies.DummyDependency)
