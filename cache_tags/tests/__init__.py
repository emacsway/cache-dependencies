from uuid import uuid4

from django.core.urlresolvers import reverse
from django.db import models
from django.template import Context, Template
from django.test import TestCase
from django.test.client import RequestFactory

from cache_tags import cache, registry


class FirstTestModel(models.Model):
    title = models.CharField(u'title', max_length=255)


class SecondTestModel(models.Model):
    title = models.CharField(u'title', max_length=255)

CACHES = (
    (FirstTestModel,
     lambda obj: ('FirstTestModel.pk:{0}'.format(obj.pk),
                  'FirstTestModel', ), ),
    (SecondTestModel,
     lambda obj: ('SecondTestModel.pk:{0}'.format(obj.pk), ), ),
)

registry.register(CACHES)


class CacheTagsTest(TestCase):

    urls = 'cache_tags.tests.urls'

    def setUp(self):
        self.obj1 = FirstTestModel.objects.create(title='title1')
        self.obj2 = SecondTestModel.objects.create(title='title2')

    def test_cache(self):
        tags1 = ('FirstTestModel.pk:{0}'.format(self.obj1.pk), )
        cache.set('name1', 'value1', tags1, 3600)

        tags2 = ('SecondTestModel.pk:{0}'.format(self.obj2.pk),
                 'FirstTestModel', )
        cache.set('name2', 'value2', tags2, 3600)

        self.assertEqual(cache.get('name1'), 'value1')
        self.assertEqual(cache.get('name2'), 'value2')

        self.obj1.title = 'title1.2'
        self.obj1.save()
        self.assertEqual(cache.get('name1', None), None)
        self.assertEqual(cache.get('name2', None), None)

        cache.set('name1', 'value1', tags1, 3600)
        cache.set('name2', 'value2', tags2, 3600)
        self.assertEqual(cache.get('name1'), 'value1')
        self.assertEqual(cache.get('name2'), 'value2')

        self.obj2.title = 'title2.2'
        self.obj2.save()
        self.assertEqual(cache.get('name1'), 'value1')
        self.assertEqual(cache.get('name2', None), None)

        cache.invalidate_tags(*(tags1 + tags2))
        cache.invalidate_tags('NonExistenTag')
        self.assertEqual(cache.get('name1', None), None)

    def test_decorator(self):
        resp1 = self.client.get(reverse("cache_tags_test_decorator"))
        # The first call is blank.
        # Some applications, such as django-localeurl
        # need to activate translation object in middleware.
        resp1 = self.client.get(reverse("cache_tags_test_decorator"))
        self.assertFalse(resp1.has_header('Expires'))
        self.assertFalse(resp1.has_header('Cache-Control'))
        self.assertTrue(resp1.has_header('Last-Modified'))

        resp2 = self.client.get(reverse("cache_tags_test_decorator"))
        self.assertFalse(resp2.has_header('Expires'))
        self.assertFalse(resp2.has_header('Cache-Control'))
        self.assertTrue(resp2.has_header('Last-Modified'))
        self.assertEqual(resp1.content, resp2.content)

        cache.invalidate_tags('FirstTestModel')
        resp3 = self.client.get(reverse("cache_tags_test_decorator"))
        self.assertFalse(resp3.has_header('Expires'))
        self.assertFalse(resp3.has_header('Cache-Control'))
        self.assertTrue(resp3.has_header('Last-Modified'))
        self.assertNotEqual(resp1.content, resp3.content)
        cache.invalidate_tags('FirstTestModel')

    def test_templatetag(self):
        t = Template("{% load cache_tags %}{% cachetags cachename|striptags tag1|striptags 'SecondTestModel' tags=empty_val|default:tags timeout='3600' %}{{ now }}{% addcachetags tag3 %}{% endcachetags %}")
        c = Context({
            'request': RequestFactory().get('/'),
            'now': uuid4(),
            'cachename': 'cachename',
            'tag1': 'FirstTestModel',
            'tag3': 'Tag3',
            'empty_val': '',
            'tags': ['SecondTestModel.pk:{0}'.format(self.obj2.pk), ],
        })

        # Case 1
        # Tags from arguments.
        r1 = t.render(c)
        self.assertTrue(hasattr(c['request'], 'cache_tags'))
        self.assertTrue('FirstTestModel' in c['request'].cache_tags)
        self.assertTrue('SecondTestModel.pk:{0}'.format(self.obj2.pk)\
                        in c['request'].cache_tags)
        self.assertTrue('Tag3' in c['request'].cache_tags)

        c.update({'now': uuid4(), })
        r2 = t.render(c)
        self.assertEqual(r1, r2)

        cache.invalidate_tags('FirstTestModel')
        c.update({'now': uuid4(), })
        r3 = t.render(c)
        self.assertNotEqual(r1, r3)

        # Case 2
        # Tags from keyword arguments.
        c.update({'now': uuid4(), })
        r4 = t.render(c)
        self.assertEqual(r3, r4)

        cache.invalidate_tags('SecondTestModel.pk:{0}'.format(self.obj2.pk))
        c.update({'now': uuid4(), })
        r5 = t.render(c)
        self.assertNotEqual(r3, r5)

        # Case 3
        # Tags from templatetag {% addcachetags ... %}
        c.update({'now': uuid4(), })
        r6 = t.render(c)
        self.assertEqual(r5, r6)

        cache.invalidate_tags('Tag3')
        c.update({'now': uuid4(), })
        r7 = t.render(c)
        self.assertNotEqual(r5, r7)

        cache.invalidate_tags('Tag3',
                              'FirstTestModel',
                              'SecondTestModel.pk:{0}'.format(self.obj2.pk))
