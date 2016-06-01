import time
from functools import wraps

from cache_tagging.interfaces import ITransaction, ITransactionManager
from cache_tagging.mixins import ThreadSafeDecoratorMixIn
from cache_tagging.utils import Undef


class BaseTransaction(ITransaction):
    def __init__(self, lock):
        self._lock = lock
        self.start_time = self._curret_time()

    def get_tag_versions(self, tags, version=None):
        return self._lock.get_tag_versions(tags, self.start_time, version)

    @staticmethod
    def _curret_time():
        return time.time()


class Transaction(BaseTransaction):
    def __init__(self, lock):
        super(Transaction, self).__init__(lock)
        self._tags = dict()

    def parent(self):
        return None

    def add_tags(self, tags, version=None):
        if version not in self._tags:
            self._tags[version] = set()
        self._tags[version] |= set(tags)
        self._lock.acquire_tags(tags, version)

    def finish(self):
        for version, tags in self._tags.items():
            self._lock.release_tags(tags, version)


class SavePoint(Transaction):
    def __init__(self, lock, parent):
        super(SavePoint, self).__init__(lock)
        assert parent is not None
        assert isinstance(parent, (SavePoint, Transaction))
        self._parent = parent
        self.start_time = parent.start_time

    def parent(self):
        return self._parent

    def add_tags(self, tags, version=None):
        super(SavePoint, self).add_tags(tags, version)
        self._parent.add_tags(tags, version)

    def finish(self):
        pass


class NoneTransaction(BaseTransaction):
    def parent(self):
        return None

    def add_tags(self, tags, version=None):
        pass

    def finish(self):
        pass


class BaseTransactionManager(ITransactionManager):

    def __call__(self, f=None):
        if f is None:
            return self

        @wraps(f)
        def _decorated(*args, **kw):
            with self:
                rv = f(*args, **kw)
            return rv

        return _decorated

    def __enter__(self):
        self.begin()

    def __exit__(self, *args):
        self.finish()
        return False


class TransactionManager(BaseTransactionManager):

    def __init__(self, lock):
        """
        :type lock: cache_tagging.interfaces.ITagsLock
        """
        self._lock = lock
        self._current = None

    def current(self, node=Undef):
        if node is Undef:
            return self._current or NoneTransaction(self._lock)
        self._current = node

    def begin(self):
        if self._current is None:
            self.current(Transaction(self._lock))
        else:
            self.current(SavePoint(self._lock, self.current()))
        return self.current()

    def finish(self):
        self.current().finish()
        self.current(self.current().parent())

    def flush(self):
        while self._current:
            self.finish()


class ThreadSafeTransactionManagerDecorator(ThreadSafeDecoratorMixIn, BaseTransactionManager):

    def current(self, node=Undef):
        self._validate_thread_sharing()
        return self._delegate.current(node)

    def begin(self):
        self._validate_thread_sharing()
        return self._delegate.begin()

    def finish(self):
        self._validate_thread_sharing()
        return self._delegate.finish()

    def flush(self):
        return self._delegate.flush()
