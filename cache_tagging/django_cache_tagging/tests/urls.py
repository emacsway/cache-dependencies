from __future__ import absolute_import, unicode_literals
from django.conf.urls import patterns, url
from cache_tagging.django_cache_tagging.decorators import cache_page
from cache_tagging.django_cache_tagging.tests import views


urlpatterns = patterns(
    "cache_tagging.django_cache_tagging.tests.views",
    url(r"^cache_tagging_test_decorator/$",
        'test_decorator',
        name="cache_tagging_test_decorator"),
    url(r"^cache_tagging_test_decorator_cbv1/$",
        views.TestDecoratorView1.as_view(),
        name="cache_tagging_test_decorator_cbv1"),
    url(r"^cache_tagging_test_decorator_cbv2/$",
        cache_page(3600, tags=lambda request: ('tests.firsttestmodel', ))(views.TestDecoratorView2.as_view()),
        name="cache_tagging_test_decorator_cbv2"),
    url(r"^cache_tagging_test_decorator_cbv3/$",
        views.TestDecoratorView3.as_view(),
        name="cache_tagging_test_decorator_cbv3"),
    url(r"^cache_tagging_test_decorator_cbv4/$",
        views.TestDecoratorView4.as_view(),
        name="cache_tagging_test_decorator_cbv4"),
)
