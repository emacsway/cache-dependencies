from __future__ import absolute_import, unicode_literals
from django.utils.decorators import decorator_from_middleware_with_args

from ..tagging import CacheTagging
from . import cache
from .middleware import CacheMiddleware
import collections


def cache_transaction(f=None, cache=None):
    """Decorator for any callback,

    that automatically handles database transactions."""
    import warnings
    warnings.warn(
        "Decorators @cache_transaction is deprecated.  Use @cache.transaction instead",
        PendingDeprecationWarning,
        stacklevel=2
    )
    if not cache and isinstance(f, CacheTagging):
        cache = f
        f = None
    elif not cache:
        cache = globals()['cache']
    if f:
        return cache.transaction(f)
    return cache.transaction


def cache_transaction_all(f=None, cache=None):
    """Decorator for any callback,

    that automatically handles database transactions,
    and calls CacheTagging.transaction_finish_all() instead of
    CacheTagging.transaction_finish().
    So. It will handles all transaction's scopes."""
    import warnings
    warnings.warn(
        "Decorators @cache_transaction_all is deprecated. Use cache.transaction.flush() instead",
        PendingDeprecationWarning,
        stacklevel=2
    )
    if not cache and isinstance(f, CacheTagging):
        cache = f
        f = None
    elif not cache:
        cache = globals()['cache']

    def wrapper(*args, **kwargs):
        cache.transaction.begin()
        result = f(*args, **kwargs)
        cache.transaction.flush()
        return result

    if f:
        return wrapper

    def wrapper_outer(f):
        def wrapper(*args, **kwargs):
            cache.transaction.begin()
            result = f(*args, **kwargs)
            cache.transaction.flush()
            return result

    return wrapper_outer


def cache_page(*args, **kwargs):
    """
    Decorator for views that tries getting the page from the cache and
    populates the cache if the page isn't in the cache yet.

    The cache is keyed by the URL and some data from the headers.
    Additionally there is the key prefix that is used to distinguish different
    cache areas in a multi-site setup. You could use the
    sites.get_current().domain, for example, as that is unique across a Django
    project.

    Additionally, all headers from the response's Vary header will be taken
    into account on caching -- just like the middleware does.
    """
    # We need backwards compatibility with code which spells it this way:
    #   def my_view(): pass
    #   my_view = cache_page(my_view, 123)
    # and this way:
    #   my_view = cache_page(123)(my_view)
    # and this:
    #   my_view = cache_page(my_view, 123, key_prefix="foo")
    # and this:
    #   my_view = cache_page(123, key_prefix="foo")(my_view)
    # and possibly this way (?):
    #   my_view = cache_page(123, my_view)
    # and also this way:
    #   my_view = cache_page(my_view)
    # and also this way:
    #   my_view = cache_page()(my_view)

    # We also add some asserts to give better error messages in case people are
    # using other ways to call cache_page that no longer work.
    cache_alias = kwargs.pop('cache', None)
    key_prefix = kwargs.pop('key_prefix', None)
    # patch start
    tags = kwargs.pop('tags', ())
    assert not kwargs, "The only keyword arguments are cache and key_prefix"

    def warn():
        import warnings
        warnings.warn('The cache_page decorator must be called like: '
                      'cache_page(timeout, [cache=cache name], [key_prefix=key prefix]). '
                      'All other ways are deprecated.',
                      PendingDeprecationWarning)

    if len(args) > 1:
        assert len(args) == 2, "cache_page accepts at most 2 arguments"
        warn()
        if isinstance(args[0], collections.Callable):
            return decorator_from_middleware_with_args(CacheMiddleware)(cache_timeout=args[1], cache_alias=cache_alias, key_prefix=key_prefix, tags=tags)(args[0])
        elif isinstance(args[1], collections.Callable):
            return decorator_from_middleware_with_args(CacheMiddleware)(cache_timeout=args[0], cache_alias=cache_alias, key_prefix=key_prefix, tags=tags)(args[1])
        else:
            assert False, "cache_page must be passed a view function if called with two arguments"
    elif len(args) == 1:
        if isinstance(args[0], collections.Callable):
            warn()
            return decorator_from_middleware_with_args(CacheMiddleware)(cache_alias=cache_alias, key_prefix=key_prefix, tags=tags)(args[0])
        else:
            # The One True Way
            return decorator_from_middleware_with_args(CacheMiddleware)(cache_timeout=args[0], cache_alias=cache_alias, key_prefix=key_prefix, tags=tags)
    else:
        warn()
        # patch end
        return decorator_from_middleware_with_args(CacheMiddleware)(cache_alias=cache_alias, key_prefix=key_prefix, tags=tags)
