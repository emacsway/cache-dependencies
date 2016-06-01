from django.conf.urls import patterns, include, url

from cache_tagging.django_cache_tagging.tests import urls as test_urls

from django.contrib import admin
admin.autodiscover()

from cache_tagging.django_cache_tagging import autodiscover
autodiscover()

urlpatterns = patterns('',
    # Examples:
    # url(r'^$', 'testproject.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^test/', include(test_urls)),
)
