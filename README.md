Cache Tags
============

Tags are a way to categorize cache records.
When you save a cache, you can set a list of tags to apply for this record.
Then you will be able to invalidate all cache records tagged with a given tag (or tags).

Forked from https://github.com/Harut/django-cachecontrol

Some ideas from http://dklab.ru/lib/Dklab_Cache/

See also related articles:

http://ivan.allindustry.net/en/blog/2011/10/15/cache-tagging/ (English)

http://ivan.allindustry.net/blog/2011/10/16/tagetirovanie-kesha/ (Russian)

Cache tags allows to manage cached values and easily link them to Model signals

Usage
-----

#### root urls.py
    import cache_tags
    cache_tags.autodiscover()

#### appname.caches.py file
Method to attach cache to the model is to define keypairs. Each defined keypair
creates model's save and delete signal. func takes chenged model and returns
number of changed vary_on arg and value of this arg. When the signal is called,
it gets varied arg and deletes all caches with this arg.

    from cache_tags import registry, get_cache
    from models import MyModel


    caches = [
        #((model, func, [cache_object, ]), ),
        ((FirstModel, lambda obj: ('FirstModel_{0}'.format(obj.pk), ), get_cache('my_cache_alias'), ), ),
        ((SecondModel, lambda obj: ('SecondModel_{0}'.format(obj.pk),
                                    'CategoryModel_{0}_TypeModel_{1}'.format(obj.category_id, obj.type_id),
                                    'SecondModel', ), ), ),
    ]

    registry.register(caches)

#### template
    {% load cache_tags %}
    {% cachetags 600 cache_of_2_args object.pk page_number %}
    {# cachetags timeout cache_name [vary_on args|...] #}
       ..............
    {% endcachetags %}

