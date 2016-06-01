try:
    import _thread
except ImportError:
    import thread as _thread  # Python < 3.*


class ThreadSafeDecoratorMixIn(object):

    def __init__(self, delegate):
        """
        :type delegate: cache_tagging.interfaces.ITransactionManager
        """
        self._delegate = delegate
        self._thread_id = self._get_thread_id()

    @staticmethod
    def _get_thread_id():
        return _thread.get_ident()

    def _validate_thread_sharing(self):
        if self._thread_id != self._get_thread_id():
            raise RuntimeError(
                "%s objects created in a "
                "thread can only be used in that same thread. The object "
                "with %s was created in thread id %s and this is "
                "thread id %s."
                % (self.__class__, id(self), self._thread_id, self._get_thread_id())
            )

    def __getattr__(self, name):
        return getattr(self._delegate, name)
