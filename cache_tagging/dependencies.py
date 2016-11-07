import copy
import time
import operator
import functools
import collections
from cache_tagging import interfaces, defer, exceptions, utils

TagStateBean = collections.namedtuple('TagStateBean', ('time', 'status', 'thread_id'))


class CompositeDependency(interfaces.IDependency):
    def __init__(self, *delegates):
        """
        :type delegates: tuple[cache_tagging.interfaces.IDependency]
        """
        self.delegates = list(delegates)

    def evaluate(self, cache, transaction_start_time, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction_start_time: float
        :type version: int or None
        """
        items = []
        for delegate in self.delegates:
            try:
                delegate.evaluate(cache, transaction_start_time, version)
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

    def acquire(self, cache, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.acquire(cache, delay, version)

    def release(self, cache, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """
        for delegate in self.delegates:
            delegate.release(cache, delay, version)

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


class TagsDependency(interfaces.IDependency):
    TAG_TIMEOUT = 24 * 3600
    LOCK_PREFIX = "lock"
    LOCK_TIMEOUT = 5

    class STATUS(object):
        ACQUIRED = 0
        RELEASED = 1

    def __init__(self, *tags):
        """
        :type tags: tuple[str]
        """
        if len(tags) == 1 and isinstance(tags[0], (list, tuple, set, frozenset)):
            tags = tags[0]
        self.tags = set(tags)
        self.tag_versions = {}

    def evaluate(self, cache, transaction_start_time, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction_start_time: float
        :type version: int or None
        """
        deferred = self._get_tag_versions(cache, version)
        deferred += self._get_locked_tags(cache, transaction_start_time, version)
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

        def callback(node, caches):
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

    def acquire(self, cache, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """
        return self._set_tags_status(cache, self.STATUS.ACQUIRED, delay, version)

    def release(self, cache, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """
        self._set_tags_status(cache, self.STATUS.RELEASED, delay, version)

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
            lambda _, caches: {tag: caches[tag_key] for tag, tag_key in tag_keys.items() if tag_key in caches},
            tag_keys.values()
        )
        return deferred

    def _get_locked_tags(self, cache, transaction_start_time, version):
        tag_keys = {tag: self._make_locked_tag_key(tag) for tag in self.tags}

        def callback(_, caches):
            locked_tag_caches = {tag: caches[tag_key] for tag, tag_key in tag_keys.items() if tag_key in caches}
            return set(tag for tag, tag_bean in locked_tag_caches.items()
                       if self._tag_is_locked(tag_bean, transaction_start_time))

        deferred = defer.Deferred(cache.get_many, defer.GetManyDeferredIterator, version)
        deferred.add_callback(callback, tag_keys.values())
        return deferred

    def _make_tag_versions(self, cache, tags, version):
        if not tags:
            return dict()
        new_tag_versions = {tag: utils.generate_tag_version() for tag in tags}
        new_tag_key_versions = {utils.make_tag_key(tag): tag_version for tag, tag_version in new_tag_versions.items()}
        cache.set_many(new_tag_key_versions, self.TAG_TIMEOUT, version)
        return new_tag_versions

    def _set_tags_status(self, cache, status, delay, version):
        """Locks tags for concurrent transactions."""
        data = TagStateBean(time.time() + delay, status, self._get_thread_id())
        cache.set_many(
            {self._make_locked_tag_key(tag): data for tag in self.tags}, self._get_timeout(delay), version
        )

    @staticmethod
    def _get_thread_id():
        return utils.get_thread_id()

    def _make_locked_tag_key(self, tag):
        return '{0}_{1}'.format(self.LOCK_PREFIX, utils.make_tag_key(tag))

    def _get_timeout(self, delay):
        timeout = self.LOCK_TIMEOUT
        timeout += delay
        return timeout

    def _tag_is_locked(self, tag_bean, transaction_start_time):
        if tag_bean.thread_id == self._get_thread_id():
            # Acquired by current thread, ignore it
            return False
        if tag_bean.status == self.STATUS.ACQUIRED:
            # Tag still is acquired
            return True
        if transaction_start_time <= tag_bean.time:
            # We don't create cache in all transactions started earlier
            # than finished the transaction which has invalidated tag.
            return True


class DummyDependency(interfaces.IDependency):

    def evaluate(self, cache, transaction_start_time, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction_start_time: float
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

    def acquire(self, cache, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """

    def release(self, cache, delay, version):
        """
        :type cache: cache_tagging.interfaces.ICache
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
