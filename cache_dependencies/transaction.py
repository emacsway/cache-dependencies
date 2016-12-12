import time
from functools import wraps

from cache_dependencies import dependencies, interfaces, mixins, utils
from cache_dependencies.utils import Undef


class AbstractTransaction(interfaces.ITransaction):
    def __init__(self, lock):
        self._lock = lock

    def get_session_id(self):
        return utils.get_thread_id()

    def evaluate(self, dependency, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        return self._lock.evaluate(dependency, self, version)

    @staticmethod
    def _current_time():
        return time.time()


class Transaction(AbstractTransaction):
    def __init__(self, lock):
        """
        :type lock: cache_dependencies.interfaces.IDependencyLock
        """
        super(Transaction, self).__init__(lock)
        self._dependencies = dict()
        self._start_time = self._current_time()
        self._end_time = None

    def get_start_time(self):
        return self._start_time

    def get_end_time(self):
        if self._end_time is None:
            raise RuntimeError("Transaction is not finished yet!")
        return self._end_time

    def parent(self):
        return None

    def add_dependency(self, dependency, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        assert isinstance(dependency, interfaces.IDependency)
        if version not in self._dependencies:
            self._dependencies[version] = dependencies.CompositeDependency()
        self._dependencies[version].extend(dependency)
        self._lock.acquire(dependency, self, version)

    def finish(self):
        self._end_time = self._current_time()
        for version, dependency in self._dependencies.items():
            self._lock.release(dependency, self, version)


class SavePoint(Transaction):
    def __init__(self, lock, parent):
        """
        :type lock: cache_dependencies.interfaces.IDependencyLock
        :type parent: cache_dependencies.transaction.Transaction or cache_dependencies.transaction.SavePoint
        """
        super(SavePoint, self).__init__(lock)
        assert isinstance(parent, interfaces.ITransaction)
        self._parent = parent

    def get_start_time(self):
        return self.parent().get_start_time()

    def get_end_time(self):
        return self.parent().get_end_time()

    def parent(self):
        return self._parent

    def add_dependency(self, dependency, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        assert isinstance(dependency, interfaces.IDependency)
        super(SavePoint, self).add_dependency(dependency, version)
        self._parent.add_dependency(dependency, version)

    def finish(self):
        pass


class DummyTransaction(AbstractTransaction):

    def get_start_time(self):
        return self._current_time()

    def get_end_time(self):
        return self._current_time()

    def parent(self):
        return None

    def add_dependency(self, dependency, version):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type version: int or None
        """
        assert isinstance(dependency, interfaces.IDependency)

    def finish(self):
        pass


class AbstractTransactionManager(interfaces.ITransactionManager):

    def __call__(self, func=None):
        if func is None:
            return self

        @wraps(func)
        def _decorated(*args, **kw):
            with self:
                rv = func(*args, **kw)
            return rv

        return _decorated

    def __enter__(self):
        self.begin()

    def __exit__(self, *args):
        self.finish()
        return False


class TransactionManager(AbstractTransactionManager):

    def __init__(self, lock):
        """
        :type lock: cache_dependencies.interfaces.IDependencyLock
        """
        self._lock = lock
        self._current = None

    def current(self, node=Undef):
        if node is Undef:
            return self._current or DummyTransaction(self._lock)
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


class ThreadSafeTransactionManagerDecorator(mixins.ThreadSafeDecoratorMixIn, AbstractTransactionManager):

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
