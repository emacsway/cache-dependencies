import time
import threading
import collections
from cache_tagging.exceptions import TagLocked
from cache_tagging.utils import get_thread_id


TagBean = collections.namedtuple('TagBean', ('time', 'status', 'thread_id'))


class TagsLock(object):

    def acquire_tags(self, tags, version=None):
        raise NotImplementedError

    def release_tags(self, tags, version=None):
        raise NotImplementedError

    def get_tags(self, tags, transaction_start_time, version=None):
        raise NotImplementedError

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

    def __init__(self, thread_safe_cache_accessor, delay=None):
        self._cache = thread_safe_cache_accessor
        self._delay = delay  # For master/slave

    def acquire_tags(self, tags, version=None):
        pass

    def release_tags(self, tags, version=None):
        if self._delay:
            threading.Timer(self._delay, self._release_tags_delayed, [tags, version]).start()

    def _release_tags_delayed(self, tags, version=None):
        self._cache().delete_many(list(tags), version=version)

    def get_tags(self, tags, transaction_start_time, version=None):
        return self._cache().get_many(tags, version) or {}


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

    def __init__(self, thread_safe_cache_accessor, delay=None):
        self._cache = thread_safe_cache_accessor
        self._delay = delay  # For master/slave

    def acquire_tags(self, tags, version=None):
        return self._set_tags_status(tags, self.STATUS.ASQUIRED, version)

    def release_tags(self, tags, version=None):
        return self._set_tags_status(tags, self.STATUS.RELEASED, version)

    def _set_tags_status(self, tags, status, version=None):
        """Locks tags for concurrent transactions."""
        data = TagBean(time.time(), status, get_thread_id())
        self._cache().set_many(
            {self._get_locked_tag_name(tag): data for tag in tags}, self._get_timeout(), version
        )

    def _get_locked_tag_name(self, tag):
        return '{0}_{1}'.format(self.LOCK_PREFIX, tag)

    def _get_timeout(self):
        timeout = self.LOCK_TIMEOUT
        if self._delay:
            timeout += self._delay
        return timeout

    def get_tags(self, tags, transaction_start_time, version=None):
        """Returns tags dict if all tags is not locked.

        Raises TagLocked, if current transaction has been started earlier
        than any tag has been invalidated by concurent process.
        Actual for SERIALIZABLE and REPEATABLE READ transaction levels.
        """
        tags = set(tags)
        cache_names = tags | set(map(self._get_locked_tag_name, tags))
        caches = self._cache().get_many(list(cache_names), version) or {}
        tag_caches = {k: v for k, v in caches.items() if k in tags}
        locked_tag_caches = {k: v for k, v in caches.items() if k not in tags}

        if locked_tag_caches:
            for tag_bean in locked_tag_caches.values():
                if self._tag_is_locked(tag_bean, transaction_start_time):
                        raise TagLocked
        return tag_caches

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
