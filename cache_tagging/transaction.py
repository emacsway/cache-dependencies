import time
from functools import wraps
from cache_tagging.utils import Undef


class ITransaction(object):
    def parent(self):
        raise NotImplementedError

    def add_tags(self, tags, version=None):
        raise NotImplementedError

    def get_tag_versions(self, tags, version=None):
        raise NotImplementedError

    def finish(self):
        raise NotImplementedError

    @staticmethod
    def _curret_time():
        return time.time()


class Transaction(ITransaction):
    def __init__(self, lock):
        self._lock = lock
        self._tags = dict()
        self.start_time = self._curret_time()

    def parent(self):
        return None

    def add_tags(self, tags, version=None):
        if version not in self._tags:
            self._tags[version] = set()
        self._tags[version] |= set(tags)
        self._lock.acquire_tags(tags, version)

    def get_tag_versions(self, tags, version=None):
        return self._lock.get_tag_versions(tags, self.start_time, version)

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


class NoneTransaction(ITransaction):

    def parent(self):
        return None

    def add_tags(self, tags, version=None):
        pass

    def get_tag_versions(self, tags, version=None):
        return dict()

    def finish(self):
        pass


class TransactionManager(object):

    def __init__(self, lock):
        """
        :type lock: TagLock
        """
        self._lock = lock
        self._current = None

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

    def current(self, node=Undef):
        if node is Undef:
            return self._current or NoneTransaction()
        self._current = node

    def begin(self):
        """Handles database transaction begin."""
        if self._current is None:
            self.current(Transaction(self._lock))
        else:
            self.current(SavePoint(self._lock, self.current()))
        return self.current()

    def finish(self):
        """Handles database transaction commit or rollback.

        In any case (commit or rollback) we need to invalidate tags,
        because caches can be generated for
        current database session (for rollback case) or
        another database session (for commit case).
        So, method is named "finish" (not "commit"
        or "rollback").
        """
        self.current().finish()
        self.current(self.current().parent())

    def flush(self):
        """Finishes all active transactions."""
        while self._current:
            self.finish()
