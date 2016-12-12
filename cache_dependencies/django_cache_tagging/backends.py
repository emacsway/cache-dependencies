import os
import random
import time
import tempfile
import threading
from django.core.cache.backends.filebased import pickle, FileBasedCache as DjangoFileBasedCache


class FileBasedCache(DjangoFileBasedCache):
    """Faile based backend with some improvements."""

    _fs_transaction_suffix = '.__dj_cache'

    def set(self, key, value, timeout=None, version=None):
        key = self.make_key(key, version=version)
        self.validate_key(key)

        fname = self._key_to_file(key)
        dirname = os.path.dirname(fname)

        if timeout is None:
            timeout = self.default_timeout

        if random.random() > 0.8:
            threading.Thread(target=self._cull).start()

        try:
            if not os.path.exists(dirname):
                os.makedirs(dirname)

            fd, tmp = tempfile.mkstemp(suffix=self._fs_transaction_suffix,
                                       dir=dirname)

            with os.fdopen(fd, 'wb') as f:
                now = time.time()
                pickle.dump(now + timeout, f, pickle.HIGHEST_PROTOCOL)
                pickle.dump(value, f, pickle.HIGHEST_PROTOCOL)
            os.rename(tmp, fname)
        except (IOError, OSError):
            pass
