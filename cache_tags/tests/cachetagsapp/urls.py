from django.conf.urls.defaults import patterns, url

urlpatterns = patterns("cache_tags.tests.cachetagsapp.views",
    url(r"^cache_tags_test_decorator/$",
        'test_decorator',
        name="cache_tags_test_decorator"),
)
