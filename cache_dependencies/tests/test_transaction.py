import time
import unittest
from cache_dependencies import interfaces, transaction

try:
    from unittest import mock
except ImportError:
    import mock


try:
    str = unicode  # Python 2.* compatible
    string_types = (basestring,)
    integer_types = (int, long)
except NameError:
    string_types = (str,)
    integer_types = (int,)


class AbstractTransactionTestCase(unittest.TestCase):
    def setUp(self):
        self.current_time = mock.Mock(return_value=time.time())
        self.lock = mock.Mock(spec=interfaces.IDependency)
        self.parent = mock.Mock(spec=interfaces.ITransaction)
        self.transaction = self._make_transaction(self.lock, self.parent, self.current_time)
        self.dependency = self._make_dependency()

    def _make_transaction(self, lock, parent, current_time_accessor):
        raise NotImplementedError

    @staticmethod
    def _make_dependency():
        instance = mock.Mock(spec=interfaces.IDependency)
        instance.extend = mock.Mock(return_value=True)
        return instance

    def test_evaluate(self):
        self.transaction.evaluate(self.dependency, 1)
        self.lock.evaluate.assert_called_once_with(self.dependency, self.transaction, 1)

    def test_get_session_id(self):
        session1_id = self.transaction.get_session_id()
        session2_id = self.transaction.get_session_id()
        self.assertEqual(session1_id, session2_id)
        self.assertIsInstance(session2_id, string_types)

    def run(self, result=None):
        if self.__class__.__name__.startswith('Abstract'):
            return
        super(AbstractTransactionTestCase, self).run(result)


class TransactionTestCase(AbstractTransactionTestCase):
    def _make_transaction(self, lock, parent, current_time_accessor):

        class Transaction(transaction.Transaction):
            _current_time = current_time_accessor

        return Transaction(lock)

    def test_parent(self):
        self.assertIsNone(self.transaction.parent())

    def test_get_start_time(self):
        self.current_time.reset_mock()
        self.assertAlmostEqual(self.transaction.get_start_time(), self.current_time.return_value)
        initial_return_value = self.current_time.return_value
        self.current_time.return_value += 1
        time.sleep(1)
        self.assertAlmostEqual(self.transaction.get_start_time(), initial_return_value)
        self.current_time.assert_not_called()

    def test_get_end_time(self):
        self.current_time.reset_mock()
        with self.assertRaises(RuntimeError):
            self.transaction.get_end_time()
        self.current_time.return_value += 1
        self.transaction.finish()
        self.assertAlmostEqual(self.transaction.get_end_time(), self.current_time.return_value)
        initial_return_value = self.current_time.return_value
        self.current_time.return_value += 1
        time.sleep(1)
        self.assertAlmostEqual(self.transaction.get_end_time(), initial_return_value)
        self.current_time.assert_called_once_with()

    def test_add_dependency_and_finish(self):
        dependency1 = self._make_dependency()
        dependency1.id = 1
        dependency2 = self._make_dependency()
        dependency2.id = 2
        dependency3 = self._make_dependency()
        dependency3.id = 3
        self.transaction.add_dependency(dependency1, None)
        self.lock.acquire.assert_called_once_with(dependency1, self.transaction, None)
        self.lock.reset_mock()

        self.transaction.add_dependency(dependency2, None)
        self.lock.acquire.assert_called_once_with(dependency2, self.transaction, None)
        self.lock.reset_mock()
        dependency1.extend.assert_called_once_with(dependency2)
        dependency1.reset_mock()

        self.transaction.add_dependency(dependency3, 1)
        self.lock.acquire.assert_called_once_with(dependency3, self.transaction, 1)
        self.lock.reset_mock()
        dependency1.extend.assert_not_called()

        self.transaction.finish()
        self.assertEqual(self.lock.release.call_count, 2)

        args, kwargs = self.lock.release.call_args_list[-1]
        self.assertEqual(len(args[0].delegates), 1)
        self.assertEqual(args[0].delegates[0].id, 1)
        self.assertIs(args[1], self.transaction)
        self.assertIsNone(args[2])

        args, kwargs = self.lock.release.call_args_list[-2]
        self.assertEqual(len(args[0].delegates), 1)
        self.assertEqual(args[0].delegates[0].id, 3)
        self.assertIs(args[1], self.transaction)
        self.assertEqual(args[2], 1)

    def test_bool(self):
        self.assertTrue(self.transaction)


class SavePointTestCase(AbstractTransactionTestCase):
    def _make_transaction(self, lock, parent, current_time_accessor):
        return transaction.SavePoint(lock, parent)

    def test_parent(self):
        self.assertIs(self.transaction.parent(), self.parent)

    def test_get_start_time(self):
        self.transaction.get_start_time()
        self.parent.get_start_time.assert_called_once_with()

    def test_get_end_time(self):
        self.transaction.get_end_time()
        self.parent.get_end_time.assert_called_once_with()

    def test_add_dependency(self):
        self.transaction.add_dependency(self.dependency, 1)
        self.lock.acquire.assert_called_once_with(self.dependency, self.transaction, 1)
        self.parent.add_dependency.assert_called_once_with(self.dependency, 1)

    def test_bool(self):
        self.assertTrue(self.transaction)


class DummyTransactionTestCase(AbstractTransactionTestCase):
    def _make_transaction(self, lock, parent, current_time_accessor):

        class DummyTransaction(transaction.DummyTransaction):
            _current_time = current_time_accessor

        return DummyTransaction(lock)

    def test_parent(self):
        self.assertIsNone(self.transaction.parent())

    def test_get_start_time(self):
        self.current_time.reset_mock()
        self.assertAlmostEqual(self.transaction.get_start_time(), self.current_time.return_value)
        initial_return_value = self.current_time.return_value
        self.current_time.return_value += 1
        time.sleep(1)
        self.assertAlmostEqual(self.transaction.get_start_time(), self.current_time.return_value)
        self.assertEqual(self.current_time.call_count, 2)

    def test_get_end_time(self):
        self.current_time.reset_mock()
        self.current_time.return_value += 1
        self.assertAlmostEqual(self.transaction.get_end_time(), self.current_time.return_value)
        self.current_time.return_value += 1
        time.sleep(1)
        self.assertAlmostEqual(self.transaction.get_end_time(), self.current_time.return_value)
        self.assertEqual(self.current_time.call_count, 2)

    def test_bool(self):
        self.assertFalse(self.transaction)


class TransactionManagerTestCase(unittest.TestCase):
    def setUp(self):
        self.transaction = mock.Mock(spec=interfaces.ITransaction)
        self.lock = mock.Mock(spec=interfaces.IDependency)
        self.transaction_manager = transaction.TransactionManager(self.lock)

    def test_current_none(self):
        current_transaction = self.transaction_manager.current()
        self.assertIsInstance(current_transaction, transaction.DummyTransaction)

    def test_current_set_get(self):
        self.transaction_manager.current(self.transaction)
        self.assertIs(self.transaction_manager.current(), self.transaction)

    def test_begin(self):
        initial_transaction = self.transaction_manager.begin()
        self.assertIsInstance(initial_transaction, transaction.Transaction)

        save_point = self.transaction_manager.begin()
        self.assertIsInstance(save_point, transaction.SavePoint)
        self.assertIs(save_point.parent(), initial_transaction)

        nested_save_point = self.transaction_manager.begin()
        self.assertIsInstance(nested_save_point, transaction.SavePoint)
        self.assertIs(nested_save_point.parent(), save_point)

    def test_finish_delegate_transaction(self):
        self.transaction_manager.current(self.transaction)
        self.transaction_manager.finish()
        self.transaction.finish.assert_called_once_with()

    def test_finish_transaction(self):
        self.transaction_manager.begin()
        self.transaction_manager.finish()
        self.assertIsInstance(self.transaction_manager.current(), transaction.DummyTransaction)

    def test_finish_savepoint(self):
        initial_transaction = self.transaction_manager.begin()
        self.transaction_manager.begin()
        self.transaction_manager.finish()
        self.assertIs(self.transaction_manager.current(), initial_transaction)

    def test_flush(self):
        self.transaction_manager.begin()
        self.transaction_manager.begin()
        self.transaction_manager.begin()
        self.transaction_manager.flush()
        self.assertIsInstance(self.transaction_manager.current(), transaction.DummyTransaction)
