from cache_tagging.interfaces import ICacheNode, IRelationManager
from cache_tagging.mixins import ThreadSafeDecoratorMixIn
from cache_tagging.utils import Undef

try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


class CacheNode(ICacheNode):

    def __init__(self, name, parent=None):
        self._name = name
        self._parent = parent
        self._tags = dict()

    def parent(self):
        return self._parent

    def name(self):
        return self._name

    def add_tags(self, tags, version=None):
        if version not in self._tags:
            self._tags[version] = set()
        self._tags[version] |= set(tags)
        if self._parent is not None:
            self._parent.add_tags(tags, version)

    def get_tags(self, version=None):
        try:
            return self._tags[version]
        except KeyError:
            return set()


class NoneCacheNode(ICacheNode):
    """Using pattern Special Case"""
    def __init__(self):
        pass

    def parent(self):
        return None

    def name(self):
        return 'NoneCache'

    def add_tags(self, tags, version=None):
        pass

    def get_tags(self, version=None):
        return set()


class RelationManager(IRelationManager):

    def __init__(self):
        self._current = None
        self._data = dict()  # recursive cache is not possible, so, using dict instead of stack.

    def get(self, name):
        if name not in self._data:
            self._data[name] = CacheNode(name, self._current)
        return self._data[name]

    def pop(self, name):
        try:
            node = self._data.pop(name)
        except KeyError:
            node = NoneCacheNode()

        if self.current() is node:
            self.current(node.parent())
        return node

    def current(self, name_or_node=Undef):
        if name_or_node is Undef:
            return self._current or NoneCacheNode()
        if isinstance(name_or_node, string_types):
            node = self.get(name_or_node)
        else:
            node = name_or_node
        self._current = node

    def clear(self):
        self._data = dict()


class ThreadSafeRelationManagerDecorator(ThreadSafeDecoratorMixIn, IRelationManager):

    def get(self, name):
        self._validate_thread_sharing()
        return self._delegate.get(name)

    def pop(self, name):
        self._validate_thread_sharing()
        return self._delegate.pop(name)

    def current(self, name_or_node=Undef):
        self._validate_thread_sharing()
        return self._delegate.current(name_or_node)

    def clear(self):
        self._validate_thread_sharing()
        return self._delegate.clear()
