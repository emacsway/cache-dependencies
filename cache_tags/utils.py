from django.conf import settings


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
        cache_timeout = 0 # Can't have max-age negative
    if settings.USE_ETAGS and not response.has_header('ETag'):
        if hasattr(response, 'render') and callable(response.render):
            response.add_post_render_callback(_set_response_etag)
        else:
            response = _set_response_etag(response)
    if not response.has_header('Last-Modified'):
        response['Last-Modified'] = http_date()
    # patch start
    # We don't know, when cache will be invalid. So, skip http expires.
    # if not response.has_header('Expires'):
    #     response['Expires'] = http_date(time.time() + cache_timeout)
    # patch_cache_control(response, max_age=cache_timeout)
    # patch end
