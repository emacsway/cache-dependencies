from __future__ import absolute_import, unicode_literals
import hashlib
from django.conf import settings
from django.utils.http import http_date
from django.utils.cache import cc_delim_re, _generate_cache_key,\
    _generate_cache_header_key

from . import caches


def prevent_cache_page(request):
    """Prevent page caching"""
    request._cache_update_cache = False


def set_response_etag(response):  # Compatible with Django 1.3
    if not getattr(response, 'streaming', None):
        response['ETag'] = '"{0}"'.format(hashlib.md5(response.content).hexdigest())
    return response


def patch_response_headers(response, cache_timeout=None):
    """
    Adds some useful headers to the given HttpResponse object:
        ETag, Last-Modified, Expires and Cache-Control

    Each header is only added if it isn't already set.

    cache_timeout is in seconds. The CACHE_MIDDLEWARE_SECONDS setting is used
    by default.
    """
    if cache_timeout is None:
        cache_timeout = settings.CACHE_MIDDLEWARE_SECONDS
    if cache_timeout < 0:
        cache_timeout = 0  # Can't have max-age negative
    if settings.USE_ETAGS and not response.has_header('ETag'):
        if hasattr(response, 'render') and callable(response.render):
            response.add_post_render_callback(set_response_etag)
        else:
            response = set_response_etag(response)
    # patch start
    # Fixed issue #2
    # if not response.has_header('Last-Modified'):
    #     response['Last-Modified'] = http_date()
    # We don't know, when cache will be invalid. So, skip http expires.
    # if not response.has_header('Expires'):
    #     response['Expires'] = http_date(time.time() + cache_timeout)
    # patch_cache_control(response, max_age=cache_timeout)
    # patch end


def learn_cache_key(request, response, tags=(), cache_timeout=None, key_prefix=None, cache=None):  # patched
    """
    Learns what headers to take into account for some request path from the
    response object. It stores those headers in a global path registry so that
    later access to that path will know what headers to take into account
    without building the response object itself. The headers are named in the
    Vary header of the response, but we want to prevent response generation.

    The list of headers to use for cache key generation is stored in the same
    cache as the pages themselves. If the cache ages some data out of the
    cache, this just means that we have to build the response once to get at
    the Vary header and so at the list of headers to use for the cache key.
    """
    if key_prefix is None:
        key_prefix = settings.CACHE_MIDDLEWARE_KEY_PREFIX
    if cache_timeout is None:
        cache_timeout = settings.CACHE_MIDDLEWARE_SECONDS
    cache_key = _generate_cache_header_key(key_prefix, request)
    if cache is None:
        cache = caches[settings.CACHE_MIDDLEWARE_ALIAS]
    if response.has_header('Vary'):
        is_accept_language_redundant = settings.USE_I18N or settings.USE_L10N
        # If i18n or l10n are used, the generated cache key will be suffixed
        # with the current locale. Adding the raw value of Accept-Language is
        # redundant in that case and would result in storing the same content
        # under multiple keys in the cache. See #18191 for details.
        headerlist = []
        for header in cc_delim_re.split(response['Vary']):
            header = header.upper().replace('-', '_')
            if header == 'ACCEPT_LANGUAGE' and is_accept_language_redundant:
                continue
            headerlist.append('HTTP_' + header)
        headerlist.sort()
        cache.set(cache_key, headerlist, tags, cache_timeout)  # patched
        return _generate_cache_key(request, request.method, headerlist, key_prefix)
    else:
        # if there is no Vary header, we still need a cache key
        # for the request.build_absolute_uri()
        cache.set(cache_key, [], tags, cache_timeout)  # patched
        return _generate_cache_key(request, request.method, [], key_prefix)
