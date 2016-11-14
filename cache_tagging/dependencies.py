import copy
import time
import operator
import functools
import collections
from cache_tagging import interfaces, defer, exceptions, utils


class CompositeDependency(interfaces.IDependency):
    def __init__(self, *delegates):
        """
        :type delegates: tuple[cache_tagging.interfaces.IDependency]
        """
        self.delegates = list(delegates)

    def evaluate(self, cache, transaction, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type version: int or None
        """
        items = []
        for delegate in self.delegates:
            try:
                delegate.evaluate(cache, transaction, version)
            except exceptions.DependencyLocked as e:
                items.append(e)
        if items:
            raise exceptions.CompositeDependencyLocked(self, items)

    def validate(self, cache, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        :rtype: cache_tagging.interfaces.IDeferred
        """
        try:
            deferred = functools.reduce(
                operator.iadd,
                [delegate.validate(cache, version) for delegate in self.delegates]
            )
        except TypeError:  # self.delegates is empty
            deferred = defer.Deferred(None, defer.NoneDeferredIterator)

        deferred += defer.Deferred(None, defer.NoneDeferredIterator)

        def callback(node, caches):
            errors = []
            for _ in range(0, len(self.delegates)):
                try:
                    node.get()
                except exceptions.DependencyInvalid as e:
                    errors.append(e)
            if errors:
                raise exceptions.CompositeDependencyInvalid(self, errors)

        deferred.add_callback(callback)
        return deferred

    def invalidate(self, cache, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.invalidate(cache, version)

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.acquire(cache, transaction, version)

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.release(cache, transaction, delay, version)

    def extend(self, other):
        """
        :type other: cache_tagging.interfaces.IDependency
        :rtype: bool
        """
        assert isinstance(other, interfaces.IDependency)
        if isinstance(other, CompositeDependency):
            for other_delegate in other.delegates:
                self.extend(other_delegate)
            return True
        else:
            for delegate in self.delegates:
                if delegate.extend(other):  # Chain of responsibility
                    break
            else:
                self.delegates.append(copy.copy(other))
        return True

    def __copy__(self):
        c = copy.copy(super(CompositeDependency, self))
        c.delegates = c.delegates[:]
        return c


class AbstractTagState(collections.namedtuple('TagStateBean', ('transaction_id', 'time'))):
    @staticmethod
    def make_key(tag):
        raise NotImplementedError

    def is_locked(self, transaction):
        """
        :type transaction: cache_tagging.interfaces.ITransaction
        """
        raise NotImplementedError

    def __repr__(self):
        return '{0}({1})'.format(
            self.__class__.__name__,
            ', '.join(
                '{0}={1!r}'.format(name, getattr(self, name)) for name in self._fields
            )
        )

class AcquiredTagState(AbstractTagState):
    __slots__ = ()

    @staticmethod
    def make_key(tag):
        return 'acquired_{0}'.format(utils.make_tag_key(tag))

    def is_locked(self, transaction):
        """
        :type transaction: cache_tagging.interfaces.ITransaction
        """
        return transaction.get_id() != self.transaction_id  # Acquired by current thread, ignore it


class ReleasedTagState(AbstractTagState):
    __slots__ = ()

    @staticmethod
    def make_key(tag):
        return 'released_{0}'.format(utils.make_tag_key(tag))

    def is_locked(self, transaction):
        """
        :type transaction: cache_tagging.interfaces.ITransaction
        """
        if transaction.get_id() == self.transaction_id:
            # Released by current thread, ignore it
            return False
        elif transaction.get_start_time() <= self.time:
            # We don't create cache in all transactions started earlier
            # than finished the transaction which has invalidated tag.
            return True
        return False


class TagsDependency(interfaces.IDependency):
    TAG_TIMEOUT = 24 * 3600
    TAG_STATE_TIMEOUT = 5

    def __init__(self, *tags):
        """
        :type tags: tuple[str]
        """
        if len(tags) == 1 and isinstance(tags[0], (list, tuple, set, frozenset)):
            tags = tags[0]
        self.tags = set(tags)
        self.tag_versions = {}

    def evaluate(self, cache, transaction, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type version: int or None
        """
        deferred = self._get_tag_versions(cache, version)
        deferred += self._get_locked_tags(cache, transaction, version)
        locked_tags = deferred.get()
        tag_versions = deferred.get()
        # All deferred operations in this method should be completed
        # before exception will be raised.
        if locked_tags:
            raise exceptions.TagsLocked(self, locked_tags)
        nonexistent_tags = self.tags - set(tag_versions.keys())
        new_tag_versions = self._make_tag_versions(cache, nonexistent_tags, version)
        tag_versions.update(new_tag_versions)
        self.tag_versions = tag_versions

    def validate(self, cache, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        :rtype: cache_tagging.interfaces.IDeferred
        """
        deferred = self._get_tag_versions(cache, version)

        def callback(node, caches, keys):
            actual_tag_versions = node.get()
            invalid_tags = set(
                tag for tag, tag_version in self.tag_versions.items()
                if actual_tag_versions.get(tag) != tag_version
            )
            if invalid_tags:
                raise exceptions.TagsInvalid(self, invalid_tags)

        deferred.add_callback(callback, set())
        return deferred

    def invalidate(self, cache, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        """
        tag_keys = list(map(utils.make_tag_key, self.tags))
        cache.delete_many(tag_keys, version=version)

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type version: int or None
        """
        data = AcquiredTagState(transaction.get_id(), time.time())
        cache.set_many(
            {AcquiredTagState.make_key(tag): data for tag in self.tags}, self._get_tag_state_timeout(), version
        )

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """
        data = ReleasedTagState(transaction.get_id(), time.time() + delay)
        cache.set_many(
            {ReleasedTagState.make_key(tag): data for tag in self.tags},
            self._get_tag_state_timeout(max(delay, 1)),  # Must have ttl greater than ttl of AcquiredTagState
            version
        )

    def extend(self, other):
        """
        :type other: cache_tagging.interfaces.IDependency
        :rtype: bool
        """
        if isinstance(other, TagsDependency):
            self.tags |= other.tags
            self.tag_versions.update(other.tag_versions)
            return True
        return False

    def __copy__(self):
        c = copy.copy(super(TagsDependency, self))
        c.tags = c.tags.copy()
        c.tag_versions = c.tag_versions.copy()
        return c

    def _get_tag_versions(self, cache, version):
        tag_keys = {tag: utils.make_tag_key(tag) for tag in self.tags}
        deferred = defer.Deferred(cache.get_many, defer.GetManyDeferredIterator, version)
        deferred.add_callback(
            lambda _, caches, keys: {tag: caches[tag_key] for tag, tag_key in tag_keys.items() if tag_key in caches},
            tag_keys.values()
        )
        return deferred

    def _get_locked_tags(self, cache, transaction, version):
        acquired_tag_keys = {AcquiredTagState.make_key(tag): tag for tag in self.tags}
        released_tag_keys = {ReleasedTagState.make_key(tag): tag for tag in self.tags}

        def callback(node, caches, keys):
            acquired_tag_states = {acquired_tag_keys[tag_key]: state for tag_key, state in caches.items()
                                   if tag_key in acquired_tag_keys}
            released_tag_states = {released_tag_keys[tag_key]: state for tag_key, state in caches.items()
                                   if tag_key in released_tag_keys}
            locked_tags = set()
            for tag in self.tags:
                state = acquired_tag_states.get(tag)
                released_state = released_tag_states.get(tag)
                if released_state is not None and (state is None or state.time < released_state.time):
                    state = released_state
                if state is not None and state.is_locked(transaction):
                    locked_tags.add(tag)
            return locked_tags

        deferred = defer.Deferred(cache.get_many, defer.GetManyDeferredIterator, version)
        bulk_keys = set(acquired_tag_keys.keys()) | set(released_tag_keys.keys())
        deferred.add_callback(callback, bulk_keys)
        return deferred

    def _make_tag_versions(self, cache, tags, version):
        if not tags:
            return dict()
        new_tag_versions = {tag: utils.generate_tag_version() for tag in tags}
        new_tag_key_versions = {utils.make_tag_key(tag): tag_version for tag, tag_version in new_tag_versions.items()}
        cache.set_many(new_tag_key_versions, self.TAG_TIMEOUT, version)
        return new_tag_versions

    def _get_tag_state_timeout(self, delay=0):
        timeout = self.TAG_STATE_TIMEOUT
        timeout += delay
        return timeout


class DummyDependency(interfaces.IDependency):

    def evaluate(self, cache, transaction, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type version: int or None
        """

    def validate(self, cache, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        :rtype: cache_tagging.interfaces.IDeferred
        """
        deferred = defer.Deferred(None, defer.NoneDeferredIterator)
        deferred.add_callback(lambda *a, **kw: None)
        return deferred

    def invalidate(self, cache, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        """

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type version: int or None
        """

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction: cache_tagging.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """

    def extend(self, other):
        """
        :type other: cache_tagging.interfaces.IDependency
        :rtype: bool
        """
        if isinstance(other, DummyDependency):
            return True
        return False

    def __copy__(self):
        return copy.copy(super(DummyDependency, self))
