from django.conf.urls import include, url

from django_cache_dependencies.tests import urls as test_urls

from django.contrib import admin
admin.autodiscover()

from django_cache_dependencies import autodiscover
autodiscover()

urlpatterns = [
    # Examples:
    # url(r'^$', 'testproject.views.home', name='home'),
    # url(r'^blog/', include('blog.urls')),

    url(r'^admin/', include(admin.site.urls)),
    url(r'^test/', include(test_urls)),
]
