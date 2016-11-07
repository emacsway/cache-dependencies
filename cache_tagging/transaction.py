import time
from functools import wraps

from cache_tagging import dependencies, interfaces, mixins
from cache_tagging.utils import Undef


class AbstractTransaction(interfaces.ITransaction):
    def __init__(self, lock):
        self._lock = lock
        self.start_time = self._current_time()

    def evaluate(self, tags, version):
        return self._lock.evaluate(tags, self.start_time, version)

    @staticmethod
    def _current_time():
        return time.time()


class Transaction(AbstractTransaction):
    def __init__(self, lock):
        super(Transaction, self).__init__(lock)
        self._dependencies = dict()

    def parent(self):
        return None

    def add_dependency(self, dependency, version):
        assert isinstance(dependency, interfaces.IDependency)
        if version not in self._dependencies:
            self._dependencies[version] = dependencies.CompositeDependency()
        self._dependencies[version].extend(dependency)
        self._lock.acquire(dependency, version)

    def finish(self):
        for version, dependency in self._dependencies.items():
            self._lock.release(dependency, version)


class SavePoint(Transaction):
    def __init__(self, lock, parent):
        super(SavePoint, self).__init__(lock)
        assert parent is not None
        assert isinstance(parent, (SavePoint, Transaction))
        self._parent = parent
        self.start_time = parent.start_time

    def parent(self):
        return self._parent

    def add_dependency(self, dependency, version):
        assert isinstance(dependency, interfaces.IDependency)
        super(SavePoint, self).add_dependency(dependency, version)
        self._parent.add_dependency(dependency, version)

    def finish(self):
        pass


class DummyTransaction(AbstractTransaction):
    def parent(self):
        return None

    def add_dependency(self, dependency, version):
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
        :type lock: cache_tagging.interfaces.IDependencyLock
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
