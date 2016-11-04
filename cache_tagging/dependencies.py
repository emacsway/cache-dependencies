import time
import collections
from cache_tagging import interfaces, defer, exceptions, utils

TagBean = collections.namedtuple('TagBean', ('time', 'status', 'thread_id'))


class TagsDependency(interfaces.IDependency):
    LOCK_PREFIX = "lock"
    LOCK_TIMEOUT = 5

    class STATUS(object):
        ASQUIRED = 0
        RELEASED = 1

    def __init__(self, *tags):
        """
        :type tags: tuple[str]
        """
        if len(tags) == 1 and isinstance(tags[0], (list, tuple, set, frozenset)):
            tags = tags[0]
        self.tags = set(tags)

    def evaluate(self, cache, transaction_start_time, version=None):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type transaction_start_time: float
        :type version: int or None
        """
        deferred = self._get_tag_versions(cache, version)
        deferred += self._get_locked_tags(cache, transaction_start_time, version)
        locked_tags = deferred.get()
        if locked_tags:
            raise exceptions.TagsInvalid(locked_tags)
        return deferred.get()

    def validate(self, cache, data, version=None):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type data: dict
        :type version: int or None
        """

    def invalidate(self, cache, version=None):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type version: int or None
        """
        tag_keys = list(map(utils.make_tag_key, self.tags))
        cache.delete_many(tag_keys, version=version)

    def acquire(self, cache, delay=0, version=None):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """
        return self._set_tags_status(cache, self.STATUS.ASQUIRED, delay, version)

    def release(self, cache, delay=0, version=None):
        """
        :type cache: cache_tagging.interfaces.ICache
        :type delay: int
        :type version: int or None
        """
        self._set_tags_status(cache, self.STATUS.RELEASED, delay, version)

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

    def _set_tags_status(self, cache, status, delay, version):
        """Locks tags for concurrent transactions."""
        data = TagBean(time.time(), status, self._get_thread_id())
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

    def _tag_is_locked(self, tag_bean, transaction_start_time, delay):
        if tag_bean.thread_id == self._get_thread_id():
            # Acquired by current thread, ignore it
            return False
        if tag_bean.status == self.STATUS.ASQUIRED:
            # Tag still is asquired
            return True
        if transaction_start_time <= (tag_bean.time + delay):
            # We don't create cache in all transactions started earlier than finished the transaction which has invalidated tag.
            return True
