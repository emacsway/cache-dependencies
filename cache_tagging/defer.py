import copy
import collections
from functools import wraps
from cache_tagging import interfaces, utils


class DeferredNode(interfaces.IDeferred):
    """Defers query execution for aggregation purpose.

    Used mainly to reduce count of cache.get_many().
    """
    def __init__(self, executor, iterator_factory, *args, **kwargs):
        self.execute = executor
        self.args = args
        self.kwargs = kwargs
        self.queue = []
        self.iterator_factory = iterator_factory
        self.aggregation_criterion = utils.to_hashable((executor, iterator_factory, args, kwargs))
        self._parent = None
        self._iterator = None

    def add_callback(self, callback, *args, **kwargs):
        self.queue.append([callback, args, kwargs])
        return self

    def get(self):
        return next(iter(self))

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent):
        """
        :type parent: cache_tagging.interfaces.IDeferred
        """
        if self._parent is None:
            self._parent = parent
        else:
            self._parent.parent = parent  # Recursion

    def __iter__(self):
        if self._iterator is None:
            self._iterator = self.iterator_factory(self)
            self._iterator.state = State()
        return self._iterator

    def __copy__(self):
        c = copy.copy(super(DeferredNode, self))
        c.queue = c.queue[:]
        c._parent = copy.copy(c._parent)
        return c


class Deferred(interfaces.IDeferred):
    deferred_factory = DeferredNode

    def __init__(self, executor, iterator_factory, *args, **kwargs):
        self.node = self.deferred_factory(executor, iterator_factory, *args, **kwargs)

    def add_callback(self, callback, *args, **kwargs):
        return self.node.add_callback(callback, *args, **kwargs)

    def get(self):
        return self.node.get()

    @property
    def parent(self):
        return self.node.parent

    @parent.setter
    def parent(self, parent):
        """
        :type parent: cache_tagging.interfaces.IDeferred
        """
        self.node.parent = parent

    def __iadd__(self, other):
        """
        :type other: cache_tagging.interfaces.IDeferred
        :rtype: cache_tagging.interfaces.IDeferred
        """
        if isinstance(other, Deferred):
            other_node = other.node
        else:
            other_node = other

        if self.node.aggregation_criterion == other_node.aggregation_criterion:
            self.node.queue.extend(other_node.queue)
            if other_node.parent is not None:
                return self.__iadd__(other_node.parent)
        else:
            other_node_copy = copy.copy(other_node)
            other_node_copy.parent = self.node
            self.node = other_node_copy
        return self

    def __iter__(self):
        return self.node.iterator


class State(object):
    _contexts = None
    _current_context = None

    def _attr_exc(f):
        @wraps(f)
        def _deco(*a, **kw):
            try:
                return f(*a, **kw)
            except KeyError:
                raise AttributeError
        return _deco

    def __init__(self):
        self._contexts = dict()
        self._current_context = None

    def switch_context(self, context_key):
        self._current_context = self._contexts.setdefault(context_key, {})

    @_attr_exc
    def __getattr__(self, key):
        return self._current_context[key]

    def __setattr__(self, key, value):
        if hasattr(self.__class__, key):
            return object.__setattr__(self, key, value)
        self._current_context[key] = value

    @_attr_exc
    def __delattr__(self, key):
        del self._current_context[key]

    _attr_exc = staticmethod(_attr_exc)


class AbstractDeferredIterator(collections.Iterator):
    """

    Don't use yield statement, because of:
    "Restriction:  A generator cannot be resumed while it is actively"
    Source: https://www.python.org/dev/peps/pep-0255/

    :type state: cache_tagging.defer.State
    """
    state = None

    def __init__(self, deferred):
        """
        :type deferred: cache_tagging.interfaces.IDeferred
        """
        self._node = deferred
        self._index = 0

    def __iter__(self):
        return self

    def _delegate(self):
        if self._node.parent:
            parent_iterator = iter(self._node.parent)
            parent_iterator.state = self.state
            return next(parent_iterator)
        else:
            raise StopIteration


class GetManyDeferredIterator(AbstractDeferredIterator):

    def __next__(self):
        node = self._node
        queue_len = len(node.queue)
        self.state.switch_context(node.aggregation_criterion)
        if self._index >= len(node.queue):
            return self._delegate()
        self._index += 1
        bulk_caches = self._get_bulk_caches(node)
        callback, args, kwargs = node.queue[queue_len - self._index]
        result = {key: bulk_caches[key] for key in args[0] if key in bulk_caches}
        return callback(node, result)

    next = __next__

    def _get_bulk_caches(self, node):
        if node.aggregation_criterion not in self._bulk_caches_map:
            self._bulk_caches_map[node.aggregation_criterion] = node.execute(
                self._get_all_cache_keys(node.aggregation_criterion), *node.args, **node.kwargs
            ) or {}
        return self._bulk_caches_map[node.aggregation_criterion]

    @property
    def _bulk_caches_map(self):
        if not hasattr(self.state, 'bulk_caches_map'):
            self.state.bulk_caches_map = {}
        return self.state.bulk_caches_map

    def _get_all_cache_keys(self, acceptable_aggregation_criterion):
        keys = set()
        node = self._node
        while node:
            if node.aggregation_criterion == acceptable_aggregation_criterion:
                keys |= self._get_node_cache_keys(node)
            node = node.parent
        return list(keys)

    @staticmethod
    def _get_node_cache_keys(node):
        """
        :type node: cache_tagging.interfaces.IDeferred
        """
        keys = set()
        for callback, args, kwargs in node.queue:
            keys |= set(args[0])
        return keys


class NoneDeferredIterator(AbstractDeferredIterator):

    def __next__(self):
        node = self._node
        queue_len = len(node.queue)
        self.state.switch_context(node.aggregation_criterion)
        if self._index >= len(node.queue):
            if node.parent:
                return next(iter(node.parent))
            else:
                raise StopIteration
        self._index += 1
        callback, args, kwargs = node.queue[queue_len - self._index]
        return callback(node, None)

    next = __next__
