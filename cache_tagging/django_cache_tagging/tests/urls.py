from __future__ import absolute_import, unicode_literals
from django.conf.urls import patterns, url
from cache_tagging.django_cache_tagging.decorators import cache_page
from cache_tagging.django_cache_tagging.tests.views import TestDecoratorView1, TestDecoratorView2


urlpatterns = patterns(
    "cache_tagging.django_cache_tagging.tests.views",
    url(r"^cache_tagging_test_decorator/$",
        'test_decorator',
        name="cache_tagging_test_decorator"),
    url(r"^cache_tagging_test_decorator_cbv1/$",
        TestDecoratorView1.as_view(),
        name="cache_tagging_test_decorator_cbv1"),
    url(r"^cache_tagging_test_decorator_cbv2/$",
        cache_page(3600, tags=lambda request: ('tests.firsttestmodel', ))(TestDecoratorView2.as_view()),
        name="cache_tagging_test_decorator_cbv2"),
)
