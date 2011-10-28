Cache Tags
============

Tags are a way to categorize cache records.
When you save a cache, you can set a list of tags to apply for this record.
Then you will be able to invalidate all cache records tagged with a given tag (or tags).

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
Each item from list creates model's save and delete signal.
Func takes changed model and returns list of tags.
When the signal is called, it gets varied tags and deletes all caches with this tags.

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
    {# {% cachetags cache_name [tag1]  [tag2] ... [tags=tag_list] [timeout=3600] %} #}
    {% cachetags 'cache_name' 'CategoryModel_15' 'FirstModel' tags=tag_list_from_view timeout=3600 %}
        ...
        {% cache_tags_append 'NewTag1' %}
        ...
        {% cache_tags_append 'NewTag2' %}
        ...
    {% endcachetags %}

#### view decorator

    from cache_tags.decorators import cache_page

    # See also useful decorator to bind view's args and kwargs to request
    # https://bitbucket.org/evotech/django-ext/src/d8b55d86680e/django_ext/middleware/view_args_to_request.py

    @cache_page(3600, tags=lambda request: ('FirstModel', ) + SecondModel.get_tags_for_request(request))
    def cached_view(request):
        result = get_result()
        return HttpResponse(result)

#### application example 1

    from from cache_tags import cache

    # ...
    value = cache.get('cache_name')
    if value is None:
        value = get_value_func()
        cache.set('cache_name', value, tags=('FirstModel', 'CategoryModel_{0}'.format(obj.category_id)))

#### application example 2

    from from cache_tags import get_cache

    # ...
    cache = get_cache('my_backend')
    value = cache.get('cache_name')
    if value is None:
        value = cache.set('cache_name', value, tags=('FirstModel', 'CategoryModel_{0}'.format(obj.category_id)))

#### manual invalidation

    from from cache_tags import cache
    
    # ...
    cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
    # or
    tag_list = ['Tag1', 'Tag2', 'Tag3', ]
    cache.invalidate_tags(*tag_list)
