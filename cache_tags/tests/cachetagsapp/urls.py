from django.conf.urls.defaults import patterns, include, url

urlpatterns = patterns("cache_tags.tests.cachetagsapp.views",
    url(r"^$", 'test_decorator', name="cache_tags_test_decorator"),
)
