from __future__ import absolute_import, unicode_literals
from django.conf.urls.defaults import patterns, url

urlpatterns = patterns("cache_tagging.django_cache_tagging.tests.views",
    url(r"^cache_tagging_test_decorator/$",
        'test_decorator',
        name="cache_tagging_test_decorator"),
)
