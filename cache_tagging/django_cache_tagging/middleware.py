from __future__ import absolute_import, unicode_literals
"""
Cache middleware. If enabled, each Django-powered page will be cached based on
URL. The canonical way to enable cache middleware is to set
``UpdateCacheMiddleware`` as your first piece of middleware, and
``FetchFromCacheMiddleware`` as the last::

    MIDDLEWARE_CLASSES = [
        'django.middleware.cache.UpdateCacheMiddleware',
        ...
        'django.middleware.cache.FetchFromCacheMiddleware'
    ]

This is counter-intuitive, but correct: ``UpdateCacheMiddleware`` needs to run
last during the response phase, which processes middleware bottom-up;
``FetchFromCacheMiddleware`` needs to run last during the request phase, which
processes middleware top-down.

The single-class ``CacheMiddleware`` can be used for some simple sites.
However, if any other piece of middleware needs to affect the cache key, you'll
need to use the two-part ``UpdateCacheMiddleware`` and
``FetchFromCacheMiddleware``. This'll most often happen when you're using
Django's ``LocaleMiddleware``.

More details about how the caching works:

* Only GET or HEAD-requests with status code 200 are cached.

* The number of seconds each page is stored for is set by the "max-age" section
  of the response's "Cache-Control" header, falling back to the
  CACHE_MIDDLEWARE_SECONDS setting if the section was not found.

* If CACHE_MIDDLEWARE_ANONYMOUS_ONLY is set to True, only anonymous requests
  (i.e., those not made by a logged-in user) will be cached. This is a simple
  and effective way of avoiding the caching of the Django admin (and any other
  user-specific content).

* This middleware expects that a HEAD request is answered with the same response
  headers exactly like the corresponding GET request.

* When a hit occurs, a shallow copy of the original response object is returned
  from process_request.

* Pages will be cached based on the contents of the request headers listed in
  the response's "Vary" header.

* This middleware also sets ETag, Last-Modified, Expires and Cache-Control
  headers on the response object.

"""
import collections
from django.conf import settings
from django.utils.cache import get_cache_key, get_max_age

from . import caches, DEFAULT_CACHE_ALIAS
from .utils import patch_response_headers, learn_cache_key


class TransactionMiddleware(object):
    """
    Transaction middleware.
    Used before django.middleware.transaction.TransactionMiddleware
    in settings.MIDDLEWARE_CLASSES.
    """
    def __init__(self, **kwargs):
        try:
            self.cache_alias = kwargs['cache_alias']
            if self.cache_alias is None:
                self.cache_alias = DEFAULT_CACHE_ALIAS
        except KeyError:
            self.cache_alias = DEFAULT_CACHE_ALIAS
            # self.cache_alias = settings.CACHE_MIDDLEWARE_ALIAS

    def process_request(self, request):
        """Enters transaction management"""
        caches[self.cache_alias].transaction.begin()

    def process_exception(self, request, exception):
        """Rolls back the database and leaves transaction management"""
        caches[self.cache_alias].transaction.flush()

    def process_response(self, request, response):
        """Commits and leaves transaction management."""
        caches[self.cache_alias].transaction.flush()
        return response


class UpdateCacheMiddleware(object):
    """
    Response-phase cache middleware that updates the cache if the response is
    cacheable.

    Must be used as part of the two-part update/fetch cache middleware.
    UpdateCacheMiddleware must be the first piece of middleware in
    MIDDLEWARE_CLASSES so that it'll get called last during the response phase.
    """
    def __init__(self):
        self.cache_timeout = settings.CACHE_MIDDLEWARE_SECONDS
        self.key_prefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
        self.cache_anonymous_only = getattr(settings, 'CACHE_MIDDLEWARE_ANONYMOUS_ONLY', False)
        self.cache_alias = settings.CACHE_MIDDLEWARE_ALIAS

    # patch start
    @property
    def cache(self):
        return caches[self.cache_alias]
    # patch end

    def _session_accessed(self, request):
        try:
            return request.session.accessed
        except AttributeError:
            return False

    def _should_update_cache(self, request, response):
        if not hasattr(request, '_cache_update_cache') or not request._cache_update_cache:
            return False
        # If the session has not been accessed otherwise, we don't want to
        # cause it to be accessed here. If it hasn't been accessed, then the
        # user's logged-in status has not affected the response anyway.
        if self.cache_anonymous_only and self._session_accessed(request):
            assert hasattr(request, 'user'), "The Django cache middleware with CACHE_MIDDLEWARE_ANONYMOUS_ONLY=True requires authentication middleware to be installed. Edit your MIDDLEWARE_CLASSES setting to insert 'django.contrib.auth.middleware.AuthenticationMiddleware' before the CacheMiddleware."
            if request.user.is_authenticated():
                # Don't cache user-variable requests from authenticated users.
                return False
        return True

    def process_response(self, request, response):
        """Sets the cache, if needed."""
        if not self._should_update_cache(request, response):
            # We don't need to update the cache, just return.
            return response

        if getattr(response, 'streaming', None) or response.status_code != 200:
            return response
        # Try to get the timeout from the "max-age" section of the "Cache-
        # Control" header before reverting to using the default cache_timeout
        # length.
        timeout = get_max_age(response)
        if timeout is None:
            timeout = self.cache_timeout
        elif timeout == 0:
            # max-age was set to 0, don't bother caching.
            return response
        # patch start
        patch_response_headers(response, timeout)
        tags = set()
        if self.tags:
            # Usefull to bind view, args and kwargs to request.
            # See https://bitbucket.org/emacsway/django-ext/src/d8b55d86680e/django_ext/middleware/view_args_to_request.py
            tags = self.tags(request)
        tags = set(tags)
        # Adds tags from request, see templatetag {% cache_add_tags ... %}
        if hasattr(request, 'cache_tagging'):
            tags.update(request.cache_tagging)
        if timeout:
            cache_key = learn_cache_key(request, response, tags, timeout, self.key_prefix, cache=self.cache)  # patched
            if hasattr(response, 'render') and isinstance(response.render, collections.Callable):
                response.add_post_render_callback(
                    lambda r: self.cache.set(cache_key, r, tags, timeout)  # patched
                )
            else:
                self.cache.set(cache_key, response, tags, timeout)  # patched
        # patch end
        return response


class FetchFromCacheMiddleware(object):
    """
    Request-phase cache middleware that fetches a page from the cache.

    Must be used as part of the two-part update/fetch cache middleware.
    FetchFromCacheMiddleware must be the last piece of middleware in
    MIDDLEWARE_CLASSES so that it'll get called last during the request phase.
    """
    def __init__(self):
        self.cache_timeout = settings.CACHE_MIDDLEWARE_SECONDS
        self.key_prefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
        self.cache_anonymous_only = getattr(settings, 'CACHE_MIDDLEWARE_ANONYMOUS_ONLY', False)
        self.cache_alias = settings.CACHE_MIDDLEWARE_ALIAS

    # patch start
    @property
    def cache(self):
        return caches[self.cache_alias]
    # patch end

    def process_request(self, request):
        """
        Checks whether the page is already cached and returns the cached
        version if available.
        """
        if request.method not in ('GET', 'HEAD'):
            request._cache_update_cache = False
            return None  # Don't bother checking the cache.

        # try and get the cached GET response
        cache_key = get_cache_key(request, self.key_prefix, 'GET', cache=self.cache)
        if cache_key is None:
            request._cache_update_cache = True
            return None  # No cache information available, need to rebuild.
        response = self.cache.get(cache_key)
        # if it wasn't found and we are looking for a HEAD, try looking just for that
        if response is None and request.method == 'HEAD':
            cache_key = get_cache_key(request, self.key_prefix, 'HEAD', cache=self.cache)
            response = self.cache.get(cache_key)

        if response is None:
            request._cache_update_cache = True
            return None  # No cache information available, need to rebuild.

        # hit, return cached response
        request._cache_update_cache = False
        return response


class CacheMiddleware(UpdateCacheMiddleware, FetchFromCacheMiddleware):
    """
    Cache middleware that provides basic behavior for many simple sites.

    Also used as the hook point for the cache decorator, which is generated
    using the decorator-from-middleware utility.
    """
    def __init__(self, cache_timeout=None, cache_anonymous_only=None, **kwargs):
        # We need to differentiate between "provided, but using default value",
        # and "not provided". If the value is provided using a default, then
        # we fall back to system defaults. If it is not provided at all,
        # we need to use middleware defaults.

        # patch start
        try:
            self.tags = kwargs['tags']
        except KeyError:
            self.tags = set()
        # patch end

        try:
            key_prefix = kwargs['key_prefix']
            if key_prefix is None:
                key_prefix = ''
        except KeyError:
            key_prefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
        self.key_prefix = key_prefix

        try:
            cache_alias = kwargs['cache_alias']
            if cache_alias is None:
                cache_alias = DEFAULT_CACHE_ALIAS
        except KeyError:
            cache_alias = settings.CACHE_MIDDLEWARE_ALIAS
        self.cache_alias = cache_alias

        if cache_anonymous_only is None:
            self.cache_anonymous_only = getattr(settings, 'CACHE_MIDDLEWARE_ANONYMOUS_ONLY', False)
        else:
            self.cache_anonymous_only = cache_anonymous_only

        if cache_timeout is None:
            cache_timeout = settings.CACHE_MIDDLEWARE_SECONDS
        self.cache_timeout = cache_timeout
