import copy
import collections
from functools import wraps
from cache_dependencies import interfaces, utils


class DeferredNode(interfaces.IDeferred):
    """Defers query execution for aggregation purpose.

    Used mainly to reduce count of cache.get_many().
    """
    def __init__(self, executor, iterator_factory, *args, **kwargs):
        assert issubclass(iterator_factory, AbstractDeferredIterator)
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
        # We should get result in ordered way.
        # Getting result by named key is a bad idea, because of, in this case,
        # caller should to know not only result type (Deferred),
        # but also named key of result.
        # Too high coupling.
        # But in ordered way (i.e. in current case) caller should always get
        # the deferred result to handle whole queue in correct order.
        # Be careful with exceptions!
        # You should raise exception only when all deferred results in callback already is obtained!
        return next(iter(self))

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent):
        """
        :type parent: cache_dependencies.interfaces.IDeferred
        """
        if getattr(self, '_parent', None) is None or parent is None:
            self._parent = parent
        else:
            self._parent.parent = parent  # Recursion

    @parent.deleter
    def parent(self):
        self._parent = None

    def __iter__(self):
        if self._iterator is None:
            self._iterator = self.iterator_factory(self)
        return self._iterator

    def __copy__(self):
        c = copy.copy(super(DeferredNode, self))
        c.queue = c.queue[:]
        c._parent = copy.copy(c._parent)  # excess?
        return c


class Deferred(interfaces.IDeferred):
    deferred_factory = DeferredNode

    def _to_node(f):
        @wraps(f)
        def _deco(self, other):
            if isinstance(other, Deferred):
                other_node = other.node
            elif isinstance(other, interfaces.IDeferred):
                other_node = other
            else:
                raise TypeError("\"other\" should to have type derived from interfaces.IDeferred")
            return f(self, other_node)
        return _deco

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
    @_to_node
    def parent(self, parent):
        """
        :type parent: cache_dependencies.interfaces.IDeferred
        """
        self.node.parent = parent

    @parent.deleter
    def parent(self):
        del self.node.parent

    @_to_node
    def __iadd__(self, other):
        """
        :type other: cache_dependencies.interfaces.IDeferred
        :rtype: cache_dependencies.interfaces.IDeferred
        """
        other = copy.copy(other)
        if other.parent is not None:
            self.__iadd__(other.parent)
            del other.parent

        if self.node.aggregation_criterion == other.aggregation_criterion:
            self.node.queue.extend(other.queue)
        else:
            other.parent, self.node = self.node, other

        return self

    def __iter__(self):
        return iter(self.node)

    _to_node = staticmethod(_to_node)


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

    :type state: cache_dependencies.defer.State
    """
    state = None

    def __init__(self, node):
        """
        :type node: cache_dependencies.interfaces.IDeferred
        """
        self._node = node
        self._index = 0
        self._state = None

    def __iter__(self):
        return self

    def _delegate(self):
        if self._node.parent:
            delegate = iter(self._node.parent)
            delegate.state = self.state
            return next(delegate)
        else:
            raise StopIteration

    @property
    def state(self):
        if self._state is None:
            self._state = State()
        return self._state

    @state.setter
    def state(self, state):
        self._state = state

    def next(self):
        return self.__next__()

    def __next__(self):
        raise NotImplementedError


class GetManyDeferredIterator(AbstractDeferredIterator):

    def __next__(self):
        node = self._node
        queue_len = len(node.queue)
        self.state.switch_context(node.aggregation_criterion)
        if self._index >= len(node.queue):
            return self._delegate()
        self._index += 1
        aggregated_caches = self._get_aggregated_caches(node)
        callback, args, kwargs = node.queue[queue_len - self._index]
        item_caches = {key: aggregated_caches[key] for key in args[0] if key in aggregated_caches}
        return callback(node, item_caches, *args, **kwargs)

    def _get_aggregated_caches(self, node):
        if node.aggregation_criterion not in self._aggregated_caches_mapping:
            self._aggregated_caches_mapping[node.aggregation_criterion] = node.execute(
                self._get_aggregated_cache_keys(node.aggregation_criterion), *node.args, **node.kwargs
            ) or {}
        return self._aggregated_caches_mapping[node.aggregation_criterion]

    @property
    def _aggregated_caches_mapping(self):
        if not hasattr(self.state, 'aggregated_caches_mapping'):
            self.state.aggregated_caches_mapping = {}
        return self.state.aggregated_caches_mapping

    def _get_aggregated_cache_keys(self, acceptable_aggregation_criterion):
        keys = set()
        node = self._node
        while node:
            if node.aggregation_criterion == acceptable_aggregation_criterion:
                keys |= self._get_node_cache_keys(node)
            node = node.parent
        return keys

    @staticmethod
    def _get_node_cache_keys(node):
        """
        :type node: cache_dependencies.interfaces.IDeferred
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
            return self._delegate()
        self._index += 1
        callback, args, kwargs = node.queue[queue_len - self._index]
        return callback(node, None, *args, **kwargs)
