import copy
import operator
import functools
from cache_dependencies import interfaces, defer, exceptions, utils


class CompositeDependency(interfaces.IDependency):
    def __init__(self, *delegates):
        """
        :type delegates: tuple[cache_dependencies.interfaces.IDependency]
        """
        self.delegates = list(delegates)

    def evaluate(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
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
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        :rtype: cache_dependencies.interfaces.IDeferred
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
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.invalidate(cache, version)

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.acquire(cache, transaction, version)

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.release(cache, transaction, delay, version)

    def extend(self, other):
        """
        :type other: cache_dependencies.interfaces.IDependency
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


class AbstractTagState(object):
    """
    :type session_id: str
    :type time: float
    """
    time = None

    def __init__(self, transaction):
        """
        :type transaction: cache_dependencies.interfaces.ITransaction
        """
        self.session_id = transaction.get_session_id()

    @staticmethod
    def make_key(tag):
        raise NotImplementedError

    def is_locked(self, transaction):
        """
        :type transaction: cache_dependencies.interfaces.ITransaction
        """
        raise NotImplementedError


class AcquiredTagState(AbstractTagState):

    def __init__(self, transaction):
        """
        :type transaction: cache_dependencies.interfaces.ITransaction
        """
        super(AcquiredTagState, self).__init__(transaction)
        self.time = transaction.get_start_time()

    @staticmethod
    def make_key(tag):
        return 'acquired_{0}'.format(utils.make_tag_key(tag))

    def is_locked(self, transaction):
        """
        :type transaction: cache_dependencies.interfaces.ITransaction
        """
        return transaction.get_session_id() != self.session_id  # Acquired by current thread, ignore it


class ReleasedTagState(AbstractTagState):

    def __init__(self, transaction, delay):
        """
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type delay: int
        """
        super(ReleasedTagState, self).__init__(transaction)
        self.time = transaction.get_end_time()
        self.delay = delay

    @staticmethod
    def make_key(tag):
        return 'released_{0}'.format(utils.make_tag_key(tag))

    def is_locked(self, transaction):
        """
        :type transaction: cache_dependencies.interfaces.ITransaction
        """
        if transaction.get_session_id() == self.session_id:
            # Released by current thread, ignore it
            return False
        elif transaction.get_start_time() <= (self.time + self.delay):
            # We don't create cache in all transactions started earlier
            # than finished the transaction which has invalidated tag.
            return True
        return False

    def is_released(self, acquired_tag_state):
        """
        Tag has not been already repeatedly acquired by concurrent transaction,
        or already acquired and released by concurrent transactions and then
        again released by current transaction.

        :type acquired_tag_state: cache_dependencies.dependencies.AcquiredTagState
        :rtype: bool
        """
        return self.session_id == acquired_tag_state.session_id and self.time > acquired_tag_state.time


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
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
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
        created_tag_versions = self._make_tag_versions(cache, nonexistent_tags, version)
        tag_versions.update(created_tag_versions)
        self.tag_versions = tag_versions

    def validate(self, cache, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        :rtype: cache_dependencies.interfaces.IDeferred
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
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        """
        tag_keys = list(map(utils.make_tag_key, self.tags))
        cache.delete_many(tag_keys, version=version)

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """
        state = AcquiredTagState(transaction)
        cache.set_many(
            {AcquiredTagState.make_key(tag): state for tag in self.tags}, self.TAG_STATE_TIMEOUT, version
        )

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """
        state = ReleasedTagState(transaction, delay)
        cache.set_many(
            {ReleasedTagState.make_key(tag): state for tag in self.tags},
            self.TAG_STATE_TIMEOUT + max(delay, 1),  # Must have ttl greater than ttl of AcquiredTagState
            version
        )

    def extend(self, other):
        """
        :type other: cache_dependencies.interfaces.IDependency
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
        deferred = defer.Deferred(cache.get_many, defer.GetManyDeferredIterator, version)
        bulk_keys = set(acquired_tag_keys.keys()) | set(released_tag_keys.keys())
        deferred.add_callback(self._get_locked_tags_callback, bulk_keys, transaction,
                              acquired_tag_keys, released_tag_keys)
        return deferred

    def _get_locked_tags_callback(self, node, caches, keys, transaction, acquired_tag_keys, released_tag_keys):
        acquired_tag_states = {acquired_tag_keys[tag_key]: state for tag_key, state in caches.items()
                               if tag_key in acquired_tag_keys}
        released_tag_states = {released_tag_keys[tag_key]: state for tag_key, state in caches.items()
                               if tag_key in released_tag_keys}
        locked_tags = set()
        for tag in self.tags:
            state = acquired_tag_states.get(tag)
            released_state = released_tag_states.get(tag)
            if released_state is not None:
                if state is None or released_state.is_released(state):
                    state = released_state
            if state is not None and state.is_locked(transaction):
                locked_tags.add(tag)
        return locked_tags

    def _make_tag_versions(self, cache, tags, version):
        if not tags:
            return dict()
        new_tag_versions = {tag: utils.generate_tag_version() for tag in tags}
        new_tag_key_versions = {utils.make_tag_key(tag): tag_version for tag, tag_version in new_tag_versions.items()}
        cache.set_many(new_tag_key_versions, self.TAG_TIMEOUT, version)
        return new_tag_versions


class DummyDependency(interfaces.IDependency):

    def evaluate(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """

    def validate(self, cache, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        :rtype: cache_dependencies.interfaces.IDeferred
        """
        deferred = defer.Deferred(None, defer.NoneDeferredIterator)
        deferred.add_callback(lambda *a, **kw: None)
        return deferred

    def invalidate(self, cache, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type version: int or None
        """

    def acquire(self, cache, transaction, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type version: int or None
        """

    def release(self, cache, transaction, delay, version):
        """
        :type cache: cache_dependencies.interfaces.ICache
        :type transaction: cache_dependencies.interfaces.ITransaction
        :type delay: int
        :type version: int or None
        """

    def extend(self, other):
        """
        :type other: cache_dependencies.interfaces.IDependency
        :rtype: bool
        """
        if isinstance(other, DummyDependency):
            return True
        return False

    def __copy__(self):
        return copy.copy(super(DummyDependency, self))
