import collections
from functools import wraps
from cache_tagging.utils import to_hashable


class Deferred(object):  # Queue?
    """Defers query execution for aggregation purpose.

    Used mainly to reduce count of cache.get_many().
    """
    def __init__(self, executor, iterator_factory, *args, **kwargs):
        self.execute = executor
        self.args = args
        self.kwargs = kwargs
        self.queue = []
        self._parent = None
        self.iterator = iterator_factory(self)
        # Should state to be delegated to Deferred() instance (self),
        # to have ability use generators instead of iterators? It'll harder to test.
        self.iterator.state = State()
        self.aggregation_criterion = to_hashable((executor, iterator_factory, args, kwargs))

    def add_callback(self, callback, *args, **kwargs):  # put? apply?
        self.queue.append([callback, args, kwargs])
        return self

    def get(self):  # recv?
        try:
            return next(self.iterator)
        except StopIteration:
            return self.parent.get()

    @property
    def parent(self):
        return self._parent

    @parent.setter
    def parent(self, parent):
        """
        :type parent: cache_tagging.defer.Deferred
        """
        self._parent = parent
        self.iterator.state = parent.iterator.state

    def __add__(self, other):
        result = self.__class__(self.execute, *self.args, **self.kwargs)
        result += self
        result += other
        return result

    def __iadd__(self, other):
        """
        :type other: cache_tagging.defer.Deferred
        :rtype: cache_tagging.defer.Deferred
        """
        if self.aggregation_criterion == other.aggregation_criterion:
            self.queue.extend(other.queue)
            return self
        else:
            other.parent = self
            return other

    def __iter__(self):
        return self.iterator


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


class GetManyDeferredIterator(collections.Iterator):
    """
    :type state: cache_tagging.defer.State
    """
    state = None

    def __init__(self, deferred):
        """
        :type deferred: cache_tagging.defer.Deferred
        """
        self._deferred = deferred
        self._iterator = None

    def __iter__(self):
        return self

    def __next__(self):
        if self._iterator is None:
            self._iterator = self._make_iterator()
        return next(self._iterator)

    next = __next__

    def _make_iterator(self):
        node = self._deferred
        self.state.switch_context(node.aggregation_criterion)
        for result in self._iter_node(node):
            yield result
        if node.parent:
            for result in node.parent:
                yield result

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
        node = self._deferred
        while node:
            if node.aggregation_criterion == acceptable_aggregation_criterion:
                keys |= self._get_node_cache_keys(node)
            node = node.parent
        return list(keys)

    @staticmethod
    def _get_node_cache_keys(node):
        """
        :type node: cache_tagging.defer.Deferred
        """
        keys = set()
        for callback, args, kwargs in node.queue:
            keys |= set(args[0])
        return keys

    def _iter_node(self, node):
        """
        :type node: cache_tagging.defer.Deferred
        """
        bulk_caches = self._get_bulk_caches(node)
        for callback, args, kwargs in reversed(node.queue):
            result = {key: bulk_caches[key] for key in args[0] if key in bulk_caches}
            yield callback(node, result)
