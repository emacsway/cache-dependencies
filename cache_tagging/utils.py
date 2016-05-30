import os
import socket
import warnings

try:
    import _thread
except ImportError:
    import thread as _thread  # Python < 3.*


class Undef(object):
    pass


def get_thread_id():  # TODO: Cache result in thread-safe variable
    """Returs id for current thread."""
    return '{0}.{1}.{2}'.format(
        socket.gethostname(), os.getpid(), _thread.get_ident()
    )


def warn(old, new, stacklevel=3):
    warnings.warn(
        "{0} is deprecated. Use {1} instead".format(old, new),
        PendingDeprecationWarning,
        stacklevel=stacklevel
    )
