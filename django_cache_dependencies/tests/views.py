from __future__ import absolute_import, unicode_literals
from uuid import uuid4
from django.http import HttpResponse
from django.views.generic import View
from django.utils.decorators import method_decorator

from cache_tagging.django_cache_tagging.decorators import cache_page


@cache_page(3600, tags=lambda request: ('tests.firsttestmodel', ))
def test_decorator(request):
    now = uuid4()
    html = "<html><body>It is now {0}.</body></html>".format(now)
    return HttpResponse(html)


class TestDecoratorView1(View):

    @method_decorator(cache_page(3600, tags=lambda request: ('tests.firsttestmodel', )))
    def get(self, request):
        now = uuid4()
        html = "<html><body>It is now {0}.</body></html>".format(now)
        return HttpResponse(html)


class TestDecoratorView2(View):

    def get(self, request):
        now = uuid4()
        html = "<html><body>It is now {0}.</body></html>".format(now)
        return HttpResponse(html)


class TestDecoratorView3(View):

    def get(self, request):
        now = uuid4()
        html = "<html><body>It is now {0}.</body></html>".format(now)
        return HttpResponse(html)

    @method_decorator(cache_page(3600, tags=lambda request: ('tests.firsttestmodel', )))
    def dispatch(self, *args, **kwargs):
        return super(TestDecoratorView3, self).dispatch(*args, **kwargs)


class TestDecoratorView4(View):

    def get_tags(self, request):
        return ('tests.firsttestmodel', )

    def get(self, request):
        now = uuid4()
        html = "<html><body>It is now {0}.</body></html>".format(now)
        return HttpResponse(html)

    def dispatch(self, *args, **kwargs):
        return cache_page(3600, tags=self.get_tags)(
            super(TestDecoratorView4, self).dispatch
        )(*args, **kwargs)
