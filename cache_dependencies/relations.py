from cache_dependencies import dependencies, interfaces, mixins
from cache_dependencies.utils import Undef

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


class CacheNode(interfaces.ICacheNode):
    def __init__(self, key, parent):
        """
        :type key: str
        :type parent: cache_dependencies.interfaces.ICacheNode
        """
        self._key = key
        self._parent = parent
        self._dependencies = dict()

    def parent(self):
        return self._parent

    def key(self):
        return self._key

    def add_dependency(self, dependency, version=None):
        assert isinstance(dependency, interfaces.IDependency)
        if version not in self._dependencies:
            self._dependencies[version] = dependencies.CompositeDependency()
        self._dependencies[version].extend(dependency)
        self.parent().add_dependency(dependency, version)

    def get_dependency(self, version=None):
        try:
            return self._dependencies[version]
        except KeyError:
            return dependencies.DummyDependency()

    def __bool__(self):
        return True


class DummyCacheNode(interfaces.ICacheNode):
    """Using pattern Special Case"""
    def __init__(self):
        pass

    def parent(self):
        return self

    def key(self):
        return 'DummyCache'

    def add_dependency(self, dependency, version=None):
        pass

    def get_dependency(self, version=None):
        return dependencies.DummyDependency()

    def __bool__(self):
        return False


class RelationManager(interfaces.IRelationManager):
    def __init__(self):
        self._current = DummyCacheNode()
        self._data = dict()  # recursive cache is not possible, so, using dict instead of stack.

    def get(self, key):
        if key not in self._data:
            self._data[key] = CacheNode(key, self._current)
        return self._data[key]

    def current(self, key_or_node=Undef):
        if key_or_node is Undef:
            return self._current
        if isinstance(key_or_node, string_types):
            node = self.get(key_or_node)
        else:
            node = key_or_node
        self._current = node

    def pop(self, key):
        try:
            node = self._data.pop(key)
        except KeyError:
            node = DummyCacheNode()

        if self.current() is node:
            self.current(node.parent())
        return node

    def clear(self):
        self._current = DummyCacheNode()
        self._data = dict()


class ThreadSafeRelationManagerDecorator(mixins.ThreadSafeDecoratorMixIn, interfaces.IRelationManager):
    def get(self, key):
        self._validate_thread_sharing()
        return self._delegate.get(key)

    def current(self, key_or_node=Undef):
        self._validate_thread_sharing()
        return self._delegate.current(key_or_node)

    def pop(self, key):
        self._validate_thread_sharing()
        return self._delegate.pop(key)

    def clear(self):
        self._validate_thread_sharing()
        return self._delegate.clear()
