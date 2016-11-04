import time
import unittest
from cache_tagging import locks, utils
from cache_tagging.exceptions import TagLocked
from cache_tagging.tests import helpers


class RepeatableReadsTagsLock(locks.RepeatableReadsTagsLock):
    thread_id = 'ivan-X555LF.21920.140481146955584'

    def _get_thread_id(self):
        return self.thread_id


class AbstractTagsLockTestCase(unittest.TestCase):
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


class ReadUncommittedTagsLockTestCase(AbstractTagsLockTestCase):
    lock_factory = locks.ReadUncommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)


class ReadUncommittedTagsLockDelayedTestCase(AbstractTagsLockTestCase):
    delay = 1
    lock_factory = locks.ReadUncommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)

        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

        time.sleep(1)

        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)


class ReadCommittedTagsLockTestCase(AbstractTagsLockTestCase):
    lock_factory = locks.ReadCommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)


class ReadCommittedTagsLockDelayedTestCase(AbstractTagsLockTestCase):
    delay = 1
    lock_factory = locks.ReadCommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)

        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

        self._set_tag_versions()

        time.sleep(1)

        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)


class RepeatableReadsTagsLockTestCase(AbstractTagsLockTestCase):
    lock_factory = RepeatableReadsTagsLock

    def setUp(self):
        super(RepeatableReadsTagsLockTestCase, self).setUp()
        self.concurrent_lock = self.lock_factory(lambda: self.cache, self.delay)
        self.concurrent_lock.thread_id += '1'

    def test_acquire_tags(self):

        tags = set(self.tag_versions.keys())
        acquire_time = time.time()
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

        # Earlier concurrent transaction.
        try:
            self.concurrent_lock.get_tag_versions(
                tags, acquire_time - 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        try:
            self.concurrent_lock.get_tag_versions(
                tags, acquire_time + 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        release_time = time.time()
        self.lock.release_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

        # Earlier concurrent transaction.
        try:
            self.concurrent_lock.get_tag_versions(
                tags, release_time - 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        tag_versions_in_later_concurrent_transaction = self.concurrent_lock.get_tag_versions(
            tags, release_time + 1
        )
        self.assertDictEqual(tag_versions_in_later_concurrent_transaction, self.tag_versions)


class RepeatableReadsTagsLockDelayedTestCase(AbstractTagsLockTestCase):
    lock_factory = RepeatableReadsTagsLock
    delay = 2

    def setUp(self):
        super(RepeatableReadsTagsLockDelayedTestCase, self).setUp()
        self.concurrent_lock = self.lock_factory(lambda: self.cache, self.delay)
        self.concurrent_lock.thread_id += '1'

    def test_acquire_tags(self):

        tags = set(self.tag_versions.keys())
        acquire_time = time.time()
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

        # Earlier concurrent transaction.
        try:
            self.concurrent_lock.get_tag_versions(
                tags, acquire_time - 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        try:
            self.concurrent_lock.get_tag_versions(
                tags, acquire_time + 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        release_time = time.time()
        self.lock.release_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.transaction_start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_in_other_cache_version = self.lock.get_tag_versions(
            tags, self.transaction_start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_in_other_cache_version), 0)

        # Earlier concurrent transaction.
        try:
            self.concurrent_lock.get_tag_versions(
                tags, release_time - 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        try:
            self.concurrent_lock.get_tag_versions(
                tags, release_time + 1
            )
        except TagLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        tag_versions_in_later_concurrent_transaction = self.concurrent_lock.get_tag_versions(
            tags, release_time + 3
        )
        self.assertDictEqual(tag_versions_in_later_concurrent_transaction, self.tag_versions)
