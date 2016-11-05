import threading
from cache_tagging import interfaces


class TagsLock(interfaces.ITagsLock):

    def __init__(self, thread_safe_cache_accessor, delay=0):
        self._cache = thread_safe_cache_accessor
        self._delay = delay  # For master/slave

    def evaluate(self, dependency, transaction_start_time, version):
        dependency.evaluate(self._cache(), transaction_start_time, version)

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
    """Tag Lock for Read Uncommitted transaction isolation level."""
    def acquire(self, dependency, version):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """

    def release(self, dependency, version):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """
        if self._delay:
            return self._release_tags_delayed(dependency, version)

    def _release_tags_delayed(self, dependency, version):
        return threading.Timer(self._delay, self._release_tags_target, [dependency, version]).start()

    def _release_tags_target(self, dependency, version):
        dependency.invalidate(self._cache(), version)


class ReadCommittedTagsLock(ReadUncommittedTagsLock):
    """Tag Lock for Read Committed transaction isolation level."""
    def release(self, dependency, version):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """
        self._release_tags_target(dependency, version)
        super(ReadCommittedTagsLock, self).release(dependency, version)


class RepeatableReadsTagsLock(TagsLock):
    """Tag Lock for Repeatable Reads transaction isolation level."""
    def acquire(self, dependency, version):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """
        dependency.acquire(self._cache(), self._delay, version)

    def release(self, dependency, version):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type version: int or None
        """
        dependency.release(self._cache(), self._delay, version)


class SerializableTagsLock(RepeatableReadsTagsLock):
    """Tag Lock for Serializable transaction isolation level."""
