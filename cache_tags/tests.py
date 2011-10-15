from django.db import models
from django.test import TestCase

import cache_tags as ct


class FirstTestModel(models.Model):
    title = models.CharField(u'title', max_length=255)


class SecondTestModel(models.Model):
    title = models.CharField(u'title', max_length=255)

CACHES = (
    (FirstTestModel, lambda obj: ('FirstTestModel_{0}'.format(obj.pk),
                                  'FirstTestModel', ), ),
    (SecondTestModel, lambda obj: ('SecondTestModel_{0}'.format(obj.pk), ), ),
)

ct.registry.register(CACHES)


class CacheTagsTest(TestCase):

    def setUp(self):
        self.obj1 = FirstTestModel.objects.create(title='title1')
        self.obj2 = FirstTestModel.objects.create(title='title2')

    def test_cache(self):
        tags1 = ('FirstTestModel_{0}'.format(self.obj1.pk), )
        ct.set_cache('name1', 'value1', tags1, 3600)

        tags2 = ('SecondTestModel_{0}'.format(self.obj2.pk),
                 'FirstTestModel', )
        ct.set_cache('name2', 'value2', tags2, 3600)

        self.assertEqual(ct.get_cache('name1'), 'value1')
        self.assertEqual(ct.get_cache('name2'), 'value2')

        self.obj1.title = 'title1.2'
        self.obj1.save()
        self.assertEqual(ct.get_cache('name1', None), None)
        self.assertEqual(ct.get_cache('name2', None), None)

        ct.set_cache('name1', 'value1', tags1, 3600)
        ct.set_cache('name2', 'value2', tags2, 3600)
        self.assertEqual(ct.get_cache('name1'), 'value1')
        self.assertEqual(ct.get_cache('name2'), 'value2')

        self.obj2.title = 'title2.2'
        self.obj2.save()
        self.assertEqual(ct.get_cache('name1'), 'value1')
        self.assertEqual(ct.get_cache('name2', None), None)
