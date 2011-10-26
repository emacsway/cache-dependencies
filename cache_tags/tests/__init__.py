from django.core.urlresolvers import reverse
from django.db import models
from django.test import TestCase

from cache_tags import cache, registry


class FirstTestModel(models.Model):
    title = models.CharField(u'title', max_length=255)


class SecondTestModel(models.Model):
    title = models.CharField(u'title', max_length=255)

CACHES = (
    (FirstTestModel, lambda obj: ('FirstTestModel_{0}'.format(obj.pk),
                                  'FirstTestModel', ), ),
    (SecondTestModel, lambda obj: ('SecondTestModel_{0}'.format(obj.pk), ), ),
)

registry.register(CACHES)


class CacheTagsTest(TestCase):

    urls = 'cache_tags.tests.cachetagsapp.urls'

    def setUp(self):
        self.obj1 = FirstTestModel.objects.create(title='title1')
        self.obj2 = SecondTestModel.objects.create(title='title2')

    def test_cache(self):
        tags1 = ('FirstTestModel_{0}'.format(self.obj1.pk), )
        cache.set('name1', 'value1', tags1, 3600)

        tags2 = ('SecondTestModel_{0}'.format(self.obj2.pk),
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

        cache.delete('name1')
        self.assertEqual(cache.get('name1', None), None)

    def test_decorator(self):
        resp = self.client.get(reverse("cache_tags_test_decorator"))
