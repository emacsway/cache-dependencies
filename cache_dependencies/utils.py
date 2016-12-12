import os
import time
import random
import socket
import hashlib
import warnings
from threading import local
from cache_dependencies import __version__

try:
    import _thread
except ImportError:
    import thread as _thread  # Python < 3.*

# Use the system (hardware-based) random number generator if it exists.
if hasattr(random, 'SystemRandom'):
    randrange = random.SystemRandom().randrange
else:
    randrange = random.randrange

MAX_TAG_KEY = 18446744073709551616     # 2 << 63

_thread_local = local()


class UndefType(object):

    def __repr__(self):
        return "Undef"

    def __reduce__(self):
        return "Undef"

Undef = UndefType()


def get_thread_id():
    """Returns id for current thread."""
    try:
        return _thread_local.thread_id
    except AttributeError:
        _thread_local.thread_id = '{0}.{1}.{2}'.format(
            socket.gethostname(), os.getpid(), _thread.get_ident()
        )
        return get_thread_id()


def warn(old, new, stacklevel=3):
    warnings.warn(
        "{0} is deprecated. Use {1} instead".format(old, new),
        PendingDeprecationWarning,
        stacklevel=stacklevel
    )


def make_tag_key(name):
    """Adds prefixed namespace for tag name"""
    version = str(__version__).replace('.', '')
    name = hashlib.md5(str(name).encode('utf-8')).hexdigest()
    return 'tag_{0}_{1}'.format(version, name)


def generate_tag_version():
    """ Generates a new unique identifier for tag version."""
    hash_value = hashlib.md5("{0}{1}{2}".format(
        randrange(0, MAX_TAG_KEY), get_thread_id(), time.time()
    ).encode('utf8')).hexdigest()
    return hash_value


def to_hashable(obj):
    """
    Makes a hashable object from a dictionary, list, tuple, set etc.
    """
    if isinstance(obj, (list, tuple)):
        return tuple(to_hashable(i) for i in obj)
    elif isinstance(obj, (set, frozenset)):
        return frozenset(to_hashable(i) for i in obj)
    elif isinstance(obj, dict):
        return frozenset((k, to_hashable(v)) for k, v in obj.items())
    return obj
