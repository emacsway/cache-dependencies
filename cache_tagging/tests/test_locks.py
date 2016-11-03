import time
import unittest
from cache_tagging import locks, utils
from cache_tagging.tests import helpers


class AbstractTagsLockTestCase(unittest.TestCase):
    """Abstract class.

    See http://stackoverflow.com/questions/1323455/python-unit-test-with-base-and-sub-class
    """

    delay = None
    lock_factory = None

    def setUp(self):
        self.start_time = time.time()
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
        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)


class ReadUncommittedTagsLockDelayedTestCase(AbstractTagsLockTestCase):
    delay = 1
    lock_factory = locks.ReadUncommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)

        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)

        time.sleep(1)

        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)


class ReadCommittedTagsLockTestCase(AbstractTagsLockTestCase):
    lock_factory = locks.ReadCommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)


class ReadCommittedTagsLockDelayedTestCase(AbstractTagsLockTestCase):
    delay = 1
    lock_factory = locks.ReadCommittedTagsLock

    def test_acquire_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertDictEqual(tag_versions, self.tag_versions)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)

    def test_release_tags(self):
        tags = set(self.tag_versions.keys())
        self.lock.acquire_tags(tags)
        self.lock.release_tags(tags)

        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)

        self._set_tag_versions()

        time.sleep(1)

        tag_versions = self.lock.get_tag_versions(tags, self.start_time)
        self.assertEqual(len(tag_versions), 0)

        tag_versions_from_other_cache_version = self.lock.get_tag_versions(
            tags, self.start_time, self.cache.version + 1
        )
        self.assertEqual(len(tag_versions_from_other_cache_version), 0)
