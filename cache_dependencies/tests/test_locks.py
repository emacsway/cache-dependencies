import time
import unittest
from cache_tagging import interfaces, locks, utils
from cache_tagging.tests import helpers

try:
    from unittest import mock
except ImportError:
    import mock


class AbstractDependencyLockTestCase(unittest.TestCase):
    """Abstract class.

    See http://stackoverflow.com/questions/1323455/python-unit-test-with-base-and-sub-class
    and self.run()
    """

    delay = 0
    lock_factory = None

    def setUp(self):
        self.transaction = mock.Mock(interfaces.ITransaction)
        self.transaction.get_start_time.return_value = time.time() - 2
        self.cache = helpers.CacheStub()
        self.lock = self.lock_factory(lambda: self.cache, self.delay)
        self.dependency = self._make_dependency()
        self.tag_versions = {
            'tag1': utils.generate_tag_version(),
            'tag2': utils.generate_tag_version(),
            'tag3': utils.generate_tag_version(),
        }
        self._set_tag_versions()

    def _set_tag_versions(self):
        self.cache.set_many(
            {utils.make_tag_key(tag): tag_version for tag, tag_version in self.tag_versions.items()},
            3600
        )

    @staticmethod
    def _make_dependency():
        return mock.Mock(spec=interfaces.IDependency)

    def test_evaluate(self):
        self.lock.evaluate(self.dependency, self.transaction, 1)
        self.dependency.evaluate.assert_called_once_with(self.cache, self.transaction, 1)

    def run(self, result=None):
        if self.__class__.__name__.startswith('Abstract'):
            return
        super(AbstractDependencyLockTestCase, self).run(result)


class ReadUncommittedDependencyLockTestCase(AbstractDependencyLockTestCase):
    lock_factory = locks.ReadUncommittedDependencyLock

    def test_acquire(self):
        self.lock.acquire(self.dependency, self.transaction, 1)
        self.dependency.acquire.assert_not_called()

    def test_release(self):
        self.lock.release(self.dependency, self.transaction, 1)
        self.dependency.release.assert_not_called()


class ReadUncommittedDependencyLockDelayedTestCase(ReadUncommittedDependencyLockTestCase):
    delay = 1

    def test_release(self):
        super(ReadUncommittedDependencyLockDelayedTestCase, self).test_release()
        time.sleep(2)
        self.dependency.invalidate.assert_called_once_with(self.cache, 1)


class ReadCommittedDependencyLockTestCase(AbstractDependencyLockTestCase):
    lock_factory = locks.ReadCommittedDependencyLock

    def test_acquire(self):
        self.lock.acquire(self.dependency, self.transaction, 1)
        self.dependency.acquire.assert_not_called()

    def test_release(self):
        self.lock.release(self.dependency, self.transaction, 1)
        self.dependency.invalidate.assert_called_once_with(self.cache, 1)


class ReadCommittedDependencyLockDelayedTestCase(ReadCommittedDependencyLockTestCase):
    delay = 1

    def test_release(self):
        super(ReadCommittedDependencyLockDelayedTestCase, self).test_release()
        time.sleep(2)
        self.dependency.invalidate.assert_called_with(self.cache, 1)


class RepeatableReadDependencyLockTestCase(AbstractDependencyLockTestCase):
    lock_factory = locks.RepeatableReadDependencyLock

    def test_acquire(self):
        self.lock.acquire(self.dependency, self.transaction, 1)
        self.dependency.acquire.assert_called_once_with(self.cache, self.transaction, 1)

    def test_release(self):
        self.lock.release(self.dependency, self.transaction, 1)
        self.dependency.release.assert_called_once_with(self.cache, self.transaction, self.delay, 1)


class RepeatableReadDependencyLockDelayedTestCase(RepeatableReadDependencyLockTestCase):
    delay = 1


class SerializableDependencyLockTestCase(RepeatableReadDependencyLockTestCase):
    lock_factory = locks.SerializableDependencyLock


class SerializableDependencyLockDelayedTestCase(SerializableDependencyLockTestCase):
    delay = 1
