import time
import unittest
from cache_tagging import locks, utils
from cache_tagging.tests import helpers


class AbstractDependencyLockTestCase(unittest.TestCase):
    """Abstract class.

    See http://stackoverflow.com/questions/1323455/python-unit-test-with-base-and-sub-class
    """

    delay = 0
    lock_factory = None

    def setUp(self):
        self.transaction_start_time = time.time() - 2
        self.cache = helpers.CacheStub()
        self.lock = self.lock_factory(lambda: self.cache, self.delay)
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


class ReadUncommittedDependencyLockTestCase(AbstractDependencyLockTestCase):
    lock_factory = locks.ReadUncommittedDependencyLock
