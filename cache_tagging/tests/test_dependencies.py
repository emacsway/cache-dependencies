import time
import unittest
from cache_tagging import dependencies, exceptions, interfaces, utils
from cache_tagging.tests import helpers

try:
    from unittest import mock
except ImportError:
    import mock


class TagsDependency(dependencies.TagsDependency):
    thread_id = 'ivan-X555LF.21920.140481146955584'

    def _get_thread_id(self):
        return self.thread_id


class AbstractTagsDependencyTestCase(unittest.TestCase):
    """Abstract class.

    See http://stackoverflow.com/questions/1323455/python-unit-test-with-base-and-sub-class
    """

    delay = 0

    def setUp(self):
        self.transaction_start_time = time.time() - 2
        self.cache = helpers.CacheStub()
        self.tag_versions = {
            'tag1': utils.generate_tag_version(),
            'tag2': utils.generate_tag_version(),
            'tag3': utils.generate_tag_version(),
        }
        self._set_tag_versions()
        self.dependency = TagsDependency(*self.tag_versions.keys())
        self.dependency.tag_versions = self.tag_versions

        self.concurrent_dependency = TagsDependency(*self.tag_versions.keys())
        self.concurrent_dependency.tag_versions = self.tag_versions
        self.concurrent_dependency.thread_id += '1'

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

        self.dependency.evaluate(self.cache, self.transaction_start_time, None)
        self.assertDictEqual(self.dependency.tag_versions, self.tag_versions)

        self.dependency.invalidate(self.cache, self.cache.version + 1)
        self.dependency.evaluate(self.cache, self.transaction_start_time, None)
        self.assertDictEqual(self.dependency.tag_versions, self.tag_versions)

        self.dependency.invalidate(self.cache, None)
        self.dependency.evaluate(self.cache, self.transaction_start_time, None)
        self.assertEqual(len(self.dependency.tag_versions), 3)
        for k, v in self.dependency.tag_versions.items():
            self.assertNotEqual(v, self.tag_versions[k])

    def test_acquire(self):
        tags = set(self.tag_versions.keys())
        acquire_time = time.time()
        self.dependency.acquire(self.cache, 0, None)
        self.dependency.evaluate(self.cache, self.transaction_start_time, None)
        tag_versions = self.dependency.tag_versions
        self.assertDictEqual(tag_versions, self.tag_versions)

        self.dependency.evaluate(
            self.cache, self.transaction_start_time, self.cache.version + 1
        )
        tag_versions_in_other_cache_version = self.dependency.tag_versions
        self.assertEqual(len(tag_versions_in_other_cache_version), 3)
        for k, v in tag_versions_in_other_cache_version.items():
            self.assertNotEqual(v, self.tag_versions[k])

        # Earlier concurrent transaction.
        try:
            self.concurrent_dependency.evaluate(
                self.cache, acquire_time - 1, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        try:
            self.concurrent_dependency.evaluate(
                self.cache, acquire_time + 1, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

    def test_release(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, 0, None)
        release_time = time.time()
        self.dependency.release(self.cache, 0, None)
        self.dependency.evaluate(self.cache, self.transaction_start_time, None)
        tag_versions = self.dependency.tag_versions
        self.assertDictEqual(tag_versions, self.tag_versions)

        self.dependency.evaluate(
            self.cache, self.transaction_start_time, self.cache.version + 1
        )
        tag_versions_in_other_cache_version = self.dependency.tag_versions
        self.assertEqual(len(tag_versions_in_other_cache_version), 3)
        for k, v in tag_versions_in_other_cache_version.items():
            self.assertNotEqual(v, self.tag_versions[k])

        # Earlier concurrent transaction.
        try:
            self.concurrent_dependency.evaluate(
                self.cache, release_time - 1, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction

        self.concurrent_dependency.evaluate(
            self.cache, release_time + 1, None
        )
        tag_versions_in_later_concurrent_transaction = self.concurrent_dependency.tag_versions
        self.assertDictEqual(tag_versions_in_later_concurrent_transaction, self.tag_versions)

    def test_release_delay(self):
        tags = set(self.tag_versions.keys())
        self.dependency.acquire(self.cache, 2, None)
        release_time = time.time()
        self.dependency.release(self.cache, 2, None)
        self.dependency.evaluate(self.cache, self.transaction_start_time, None)
        tag_versions = self.dependency.tag_versions
        self.assertDictEqual(tag_versions, self.tag_versions)

        self.dependency.evaluate(
            self.cache, self.transaction_start_time, self.cache.version + 1
        )
        tag_versions_in_other_cache_version = self.dependency.tag_versions
        self.assertEqual(len(tag_versions_in_other_cache_version), 3)
        for k, v in tag_versions_in_other_cache_version.items():
            self.assertNotEqual(v, self.tag_versions[k])

        # Earlier concurrent transaction.
        try:
            self.concurrent_dependency.evaluate(
                self.cache, release_time - 1, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        # Later concurrent transaction
        try:
            self.concurrent_dependency.evaluate(
                self.cache, release_time + 1, None
            )
        except exceptions.TagsLocked as e:
            self.assertSetEqual(tags, e.args[0])
        else:
            self.fail("Exception is not raised!")

        self.concurrent_dependency.evaluate(
            self.cache, release_time + 3, None
        )
        tag_versions_in_later_concurrent_transaction = self.concurrent_dependency.tag_versions
        self.assertDictEqual(tag_versions_in_later_concurrent_transaction, self.tag_versions)


class ValidationStatusTestCase(unittest.TestCase):
    def test_false(self):
        errors = ('err1', 'err2')
        self.assertFalse(dependencies.ValidationStatus(self._make_dep(), errors))

    def test_true(self):
        self.assertTrue(dependencies.ValidationStatus(self._make_dep(), ()))

    @staticmethod
    def _make_dep():
        return mock.Mock(spec=interfaces.IDependency)


class CompositeValidationStatusTest2Case(unittest.TestCase):
    def test_false(self):
        errors1 = ('err1', 'err2')
        errors2 = ('err3', 'err4')
        validation_status = dependencies.CompositeValidationStatus(
            self._make_dep(),
            (
                dependencies.ValidationStatus(self._make_dep(), ()),
                dependencies.ValidationStatus(self._make_dep(), errors1),
                dependencies.CompositeValidationStatus(
                    self._make_dep(),
                    (
                        dependencies.ValidationStatus(self._make_dep(), errors2),
                    )
                )
            )
        )
        self.assertFalse(validation_status)
        self.assertTupleEqual(tuple(validation_status.errors), errors1 + errors2)
        self.assertEqual(len(list(validation_status)), 3)

    def test_true(self):
        validation_status = dependencies.CompositeValidationStatus(
            self._make_dep(),
            (
                dependencies.ValidationStatus(self._make_dep(), ()),
                dependencies.ValidationStatus(self._make_dep(), ()),
                dependencies.CompositeValidationStatus(
                    self._make_dep(),
                    (
                        dependencies.ValidationStatus(self._make_dep(), ()),
                    )
                )
            )
        )
        self.assertTrue(validation_status)
        self.assertTupleEqual(tuple(validation_status.errors), ())
        self.assertEqual(len(list(validation_status)), 3)

    @staticmethod
    def _make_dep():
        return mock.Mock(spec=interfaces.IDependency)
