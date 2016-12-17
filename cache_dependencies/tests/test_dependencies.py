import time
import unittest
from cache_dependencies import dependencies, exceptions, interfaces, utils
from cache_dependencies.tests import helpers

try:
    from unittest import mock
except ImportError:
    import mock


class AbstractTagsDependencyTestCase(unittest.TestCase):
    """Abstract class.

    See http://stackoverflow.com/questions/1323455/python-unit-test-with-base-and-sub-class
    """

    delay = 0

    def setUp(self):

        self.start_time = time.time() - 2
        self.end_time = self.start_time + 2

        self.cache = helpers.CacheStub()
        self.tag_versions = {
            'tag1': utils.generate_tag_version(),
            'tag2': utils.generate_tag_version(),
            'tag3': utils.generate_tag_version(),
        }
        self._set_tag_versions()

        self.transaction = mock.Mock(interfaces.ITransaction)
        self.transaction.get_start_time.return_value = self.start_time
        self.transaction.get_end_time.return_value = self.end_time
        self.transaction.get_session_id.return_value = 'ivan-X555LF.21920.140481146955584'

        self.dependency = dependencies.TagsDependency(*self.tag_versions.keys())
        self.dependency.tag_versions = self.tag_versions

        self.concurrent_transaction = mock.Mock(interfaces.ITransaction)
        self.concurrent_transaction.get_start_time.return_value = self.start_time
        self.concurrent_transaction.get_end_time.return_value = self.end_time
        self.concurrent_transaction.get_session_id.return_value = 'ivan-X555LF.21920.140481146955584' + '1'

        self.concurrent_dependency = dependencies.TagsDependency(*self.tag_versions.keys())
        self.concurrent_dependency.tag_versions = self.tag_versions

    def _set_tag_versions(self):
        self.cache.set_many(
            {utils.make_tag_key(tag): tag_version for tag, tag_version in self.tag_versions.items()},
            3600
        )


class TagsDependencyTestCase(AbstractTagsDependencyTestCase):

    def setUp(self):
        super(TagsDependencyTestCase, self).setUp()

    def test_invalidate(self):
        self.assertDictEqual(self.dependency.tag_versions, self.tag_versions)

        self.dependency.evaluate(self.cache, self.transaction, None)
        self.assertDictEqual(self.dependency.tag_versions, self.tag_versions)

        self.dependency.invalidate(self.cache, self.cache.version + 1)
        self.dependency.evaluate(self.cache, self.transaction, None)
        self.assertDictEqual(self.dependency.tag_versions, self.tag_versions)

        self.dependency.invalidate(self.cache, None)
        self.dependency.evaluate(self.cache, self.transaction, None)
        self.assertEqual(len(self.dependency.tag_versions), 3)
        for k, v in self.dependency.tag_versions.items():
            self.assertNotEqual(v, self.tag_versions[k])

    def test_acquire(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, self.transaction, None)
        self.dependency.evaluate(self.cache, self.transaction, None)
        tag_versions = self.dependency.tag_versions
        self.assertDictEqual(tag_versions, self.tag_versions)

        self.dependency.evaluate(
            self.cache, self.transaction, self.cache.version + 1
        )
        tag_versions_in_other_cache_version = self.dependency.tag_versions
        self.assertEqual(len(tag_versions_in_other_cache_version), 3)
        for k, v in tag_versions_in_other_cache_version.items():
            self.assertNotEqual(v, self.tag_versions[k])

        # Earlier concurrent transaction.
        self.concurrent_transaction.get_start_time.return_value = self.start_time - 1
        try:
            self.concurrent_dependency.evaluate(
                self.cache, self.concurrent_transaction, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        self.concurrent_transaction.get_start_time.return_value = self.start_time + 1
        try:
            self.concurrent_dependency.evaluate(
                self.cache, self.concurrent_transaction, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

    def test_concurrent_repeat_acquire(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, self.transaction, None)

        self.concurrent_transaction.get_start_time.return_value = self.start_time + 1
        self.concurrent_dependency.acquire(self.cache, self.concurrent_transaction, None)

        self.dependency.release(self.cache, self.transaction, 0, None)

        try:
            self.dependency.evaluate(self.cache, self.transaction, None)
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

    def test_concurrent_release(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, self.transaction, None)

        self.concurrent_transaction.get_start_time.return_value = self.start_time + 1
        self.concurrent_dependency.acquire(self.cache, self.concurrent_transaction, None)
        self.concurrent_dependency.release(self.cache, self.concurrent_transaction, 0, None)

        try:
            self.dependency.evaluate(self.cache, self.transaction, None)
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

    def test_concurrent_repeat_release(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, self.transaction, None)

        self.concurrent_transaction.get_start_time.return_value = self.start_time + 1
        self.concurrent_dependency.acquire(self.cache, self.concurrent_transaction, None)
        self.concurrent_dependency.release(self.cache, self.concurrent_transaction, 0, None)

        self.dependency.release(self.cache, self.transaction, 0, None)

        try:
            self.dependency.evaluate(self.cache, self.transaction, None)
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

    def test_release(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, self.transaction, None)
        self.dependency.release(self.cache, self.transaction, 0, None)
        self.dependency.evaluate(self.cache, self.transaction, None)
        tag_versions = self.dependency.tag_versions
        self.assertDictEqual(tag_versions, self.tag_versions)

        self.dependency.evaluate(
            self.cache, self.transaction, self.cache.version + 1
        )
        tag_versions_in_other_cache_version = self.dependency.tag_versions
        self.assertEqual(len(tag_versions_in_other_cache_version), 3)
        for k, v in tag_versions_in_other_cache_version.items():
            self.assertNotEqual(v, self.tag_versions[k])

        # Earlier concurrent transaction.
        self.concurrent_transaction.get_start_time.return_value = self.end_time - 1
        try:
            self.concurrent_dependency.evaluate(
                self.cache, self.concurrent_transaction, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        self.concurrent_transaction.get_start_time.return_value = self.end_time + 1
        self.concurrent_dependency.evaluate(
            self.cache, self.concurrent_transaction, None
        )
        tag_versions_in_later_concurrent_transaction = self.concurrent_dependency.tag_versions
        self.assertDictEqual(tag_versions_in_later_concurrent_transaction, self.tag_versions)

    def test_release_delay(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, self.transaction, None)
        self.dependency.release(self.cache, self.transaction, 2, None)
        self.dependency.evaluate(self.cache, self.transaction, None)
        tag_versions = self.dependency.tag_versions
        self.assertDictEqual(tag_versions, self.tag_versions)

        self.dependency.evaluate(
            self.cache, self.transaction, self.cache.version + 1
        )
        tag_versions_in_other_cache_version = self.dependency.tag_versions
        self.assertEqual(len(tag_versions_in_other_cache_version), 3)
        for k, v in tag_versions_in_other_cache_version.items():
            self.assertNotEqual(v, self.tag_versions[k])

        # Earlier concurrent transaction.
        self.concurrent_transaction.get_start_time.return_value = self.end_time - 1
        try:
            self.concurrent_dependency.evaluate(
                self.cache, self.concurrent_transaction, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        self.concurrent_transaction.get_start_time.return_value = self.end_time + 1
        try:
            self.concurrent_dependency.evaluate(
                self.cache, self.concurrent_transaction, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, set(e.items))
        else:
            self.fail("Exception is not raised!")


        self.concurrent_transaction.get_start_time.return_value = self.end_time + 3
        self.concurrent_dependency.evaluate(
            self.cache, self.concurrent_transaction, None
        )
        tag_versions_in_later_concurrent_transaction = self.concurrent_dependency.tag_versions
        self.assertDictEqual(tag_versions_in_later_concurrent_transaction, self.tag_versions)


class CompositeDependencyInvalidTestCase(unittest.TestCase):
    def test_invalid(self):
        errors1 = ('err1', 'err2')
        errors2 = ('err3', 'err4')
        validation_status = exceptions.CompositeDependencyInvalid(
            self._make_dep(),
            (
                exceptions.DependencyInvalid(self._make_dep(), ()),
                exceptions.DependencyInvalid(self._make_dep(), errors1),
                exceptions.CompositeDependencyInvalid(
                    self._make_dep(),
                    (
                        exceptions.DependencyInvalid(self._make_dep(), errors2),
                    )
                )
            )
        )
        self.assertTupleEqual(tuple(validation_status.errors), errors1 + errors2)
        self.assertEqual(len(list(validation_status)), 3)

    @staticmethod
    def _make_dep():
        return mock.Mock(spec=interfaces.IDependency)


class CompositeDependencyLockedTestCase(unittest.TestCase):
    def test_locked(self):
        items1 = ('item1', 'item2')
        items2 = ('item3', 'item4')
        validation_status = exceptions.CompositeDependencyLocked(
            self._make_dep(),
            (
                exceptions.DependencyLocked(self._make_dep(), ()),
                exceptions.DependencyLocked(self._make_dep(), items1),
                exceptions.CompositeDependencyLocked(
                    self._make_dep(),
                    (
                        exceptions.DependencyLocked(self._make_dep(), items2),
                    )
                )
            )
        )
        self.assertTupleEqual(tuple(validation_status.items), items1 + items2)
        self.assertEqual(len(list(validation_status)), 3)

    @staticmethod
    def _make_dep():
        return mock.Mock(spec=interfaces.IDependency)
