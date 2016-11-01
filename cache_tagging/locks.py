import time
import operator
import threading
import collections
from functools import reduce
from cache_tagging.exceptions import TagLocked
from cache_tagging.interfaces import ITagsLock
from cache_tagging.utils import get_thread_id, make_tag_key


TagBean = collections.namedtuple('TagBean', ('time', 'status', 'thread_id'))


class TagsLock(ITagsLock):

    def __init__(self, thread_safe_cache_accessor, delay=None):
        self._cache = thread_safe_cache_accessor
        self._delay = delay  # For master/slave

    def get_tag_versions(self, tags, transaction_start_time, version=None):
        deferred = Deferred(self._cache().get_many, version)
        self._get_tag_versions(tags, deferred)
        return deferred.pop()

    def _get_tag_versions(self, tags, deferred):
        tag_keys = {tag: make_tag_key(tag) for tag in tags}
        deferred.append(
            tag_keys.values(),
            lambda _, caches: {tag: caches[tag_key] for tag, tag_key in tag_keys.items() if tag_key in caches}
        )
        return deferred

    @staticmethod
    def make(isolation_level, thread_safe_cache_accessor, delay):
        if isolation_level == 'READ UNCOMMITED':
            return ReadUncommittedTagsLock(thread_safe_cache_accessor, delay)
        elif isolation_level == 'READ COMMITED':
            return ReadCommittedTagsLock(thread_safe_cache_accessor, delay)
        elif isolation_level == 'REPEATABLE READS':
            return RepeatableReadsTagsLock(thread_safe_cache_accessor, delay)
        elif isolation_level == 'SERIALIZABLE':
            return SerializableTagsLock(thread_safe_cache_accessor, delay)


class ReadUncommittedTagsLock(TagsLock):
    """
    Tag Lock for Read Ucnommited and higher transaction isolation level.
    """
    def acquire_tags(self, tags, version=None):
        pass

    def release_tags(self, tags, version=None):
        if self._delay:
            threading.Timer(self._delay, self._release_tags_delayed, [tags, version]).start()

    def _release_tags_delayed(self, tags, version=None):
        self._cache().delete_many(list(map(make_tag_key, tags)), version=version)


class ReadCommittedTagsLock(ReadUncommittedTagsLock):
    def release_tags(self, tags, version=None):
        self._release_tags_delayed(tags, version)
        super(ReadCommittedTagsLock, self).release_tags(tags, version)


class RepeatableReadsTagsLock(TagsLock):
    """
    Tag Lock for Repeatable Reads and higher transaction isolation level.
    """
    LOCK_PREFIX = "lock"
    LOCK_TIMEOUT = 5

    class STATUS(object):
        ASQUIRED = 0
        RELEASED = 1

    def acquire_tags(self, tags, version=None):
        return self._set_tags_status(tags, self.STATUS.ASQUIRED, version)

    def release_tags(self, tags, version=None):
        return self._set_tags_status(tags, self.STATUS.RELEASED, version)

    def _set_tags_status(self, tags, status, version=None):
        """Locks tags for concurrent transactions."""
        data = TagBean(time.time(), status, get_thread_id())
        self._cache().set_many(
            {self._make_locked_tag_key(tag): data for tag in tags}, self._get_timeout(), version
        )

    def _make_locked_tag_key(self, tag):
        return '{0}_{1}'.format(self.LOCK_PREFIX, make_tag_key(tag))

    def _get_timeout(self):
        timeout = self.LOCK_TIMEOUT
        if self._delay:
            timeout += self._delay
        return timeout

    def get_tag_versions(self, tags, transaction_start_time, version=None):
        """Returns tags dict if all tags is not locked.

        Raises TagLocked, if current transaction has been started earlier
        than any tag has been invalidated by concurent process.
        Actual for SERIALIZABLE and REPEATABLE READ transaction levels.
        """
        deferred = Deferred(self._cache().get_many, version)
        self._get_tag_versions(tags, deferred)
        self._get_locked_tags(tags, transaction_start_time, deferred)
        locked_tags = deferred.pop()
        if locked_tags:
            raise TagLocked(locked_tags)
        return deferred.pop()

    def _get_locked_tags(self, tags, transaction_start_time, deferred):
        tag_keys = {tag: self._make_locked_tag_key(tag) for tag in tags}

        def callback(_, caches):
            locked_tag_caches = {tag: caches[tag_key] for tag, tag_key in tag_keys.items() if tag_key in caches}
            return set(tag for tag, tag_bean in locked_tag_caches.items()
                       if self._tag_is_locked(tag_bean, transaction_start_time))

        deferred.append(tag_keys.values(), callback)
        return deferred

    def _tag_is_locked(self, tag_bean, transaction_start_time):
        if tag_bean.thread_id == get_thread_id():
            # Acquired by current thread, ignore it
            return False
        if tag_bean.status == self.STATUS.ASQUIRED:
            # Tag still is asquired
            return True
        if transaction_start_time <= (tag_bean.time + self._delay):
            # We don't create cache in all transactions started earlier than finished the transaction which has invalidated tag.
            return True


class SerializableTagsLock(RepeatableReadsTagsLock):
    pass


class Deferred(object):

    def __init__(self, executor, *args, **kwargs):
        self._execute = executor
        self._args = args
        self._kwargs = kwargs
        self._queue = []
        self._iterator = None

    def append(self, keys, callback):
        self._queue.append([keys, callback])

    def pop(self):
        if self._iterator is None:
            self._iterator = iter(self)
        return next(self._iterator)

    def __iter__(self):
        keys = reduce(operator.or_, map(set, map(operator.itemgetter(0), self._queue)))
        result = self._execute(list(keys), *self._args, **self._kwargs) or {}
        for i in reversed(self._queue):
            yield i[1](self, {key: result[key] for key in i[0] if key in result})
