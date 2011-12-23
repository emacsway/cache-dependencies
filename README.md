Cache Tags
============

Tags are a way to categorize cache records.
When you save a cache, you can set a list of tags to apply for this record.
Then you will be able to invalidate all cache records tagged with a given tag (or tags).

Forked from https://github.com/Harut/django-cachecontrol

Some ideas from http://dklab.ru/lib/Dklab_Cache/

See also related articles:

http://ivan.allindustry.net/en/blog/2011/10/15/cache-tagging/ (English)

http://ivan.allindustry.net/blog/2011/10/16/cache-tagging/ (Russian)

Cache tags allows to manage cached values and easily link them to Model signals

Usage
-----

#### root urls.py
    import cache_tags
    cache_tags.autodiscover()

#### appname.caches.py file
    # Each item from list creates model's save and delete signal.
    # Func takes changed model and returns list of tags.
    # When the signal is called, it gets varied tags and deletes all caches with this tags.

    from cache_tags import registry, get_cache
    from models import MyModel

    caches = [
        #((model, func, [cache_object, ]), ),
        ((FirstModel, lambda obj: ('FirstModel.pk:{0}'.format(obj.pk), ), get_cache('my_cache_alias'), ), ),
        ((SecondModel, lambda obj: ('SecondModel.pk:{0}'.format(obj.pk),
                                    'CategoryModel.pk:{0}.TypeModel.pk:{1}'.format(obj.category_id, obj.type_id),
                                    'SecondModel', ), ), ),
    ]

    registry.register(caches)

#### template
    {% load cache_tags %}
    {% cachetags 'cache_name' 'CategoryModel.pk:15' 'FirstModel' tags=tag_list_from_view timeout=3600 %}
        ...
        {% addcachetags 'NewTag1' %}
        ...
        {% addcachetags 'NewTag2' %}
        ...
        {% if do_not_cache_condition %}
            {% preventcachetags %}
        {% endif %}
    {% endcachetags %}
    {% comment %}
        {% cachetags cache_name [tag1]  [tag2] ... [tags=tag_list] [timeout=3600] %}
        {% addcachetags tag_or_list_of_tags %}
        If context has attribute "request", then templatetag "cachetags"
        adds to request a new attribute "cache_tags" (instance of set() object) with all tags.
        If request already has attribute "cache_tags", and it's instance of set() object,
        then templatetag "cachetags" adds all tags to this object.
        You can use both, templatetag "cachetags" and decorator @cache_page().
        In this case, when @cache_page() decorator will save response,
        it will also adds all tags from request.cache_tags to cache.
        You need not worry about it.

        If need, you can prevent caching by templatetag {% preventcachetags %}.
        In this case also will be prevented @cache_page() decorator, if it's used,
        and context has attribute "request".
    {% endcomment %}

#### view decorator

    from cache_tags.decorators import cache_page

    # See also useful decorator to bind view's args and kwargs to request
    # https://bitbucket.org/evotech/django-ext/src/d8b55d86680e/django_ext/middleware/view_args_to_request.py

    @cache_page(3600, tags=lambda request: ('FirstModel', ) + SecondModel.get_tags_for_request(request))
    def cached_view(request):
        result = get_result()
        return HttpResponse(result)

#### application example 1

    from cache_tags import cache

    # ...
    value = cache.get('cache_name')
    if value is None:
        value = get_value_func()
        cache.set('cache_name', value, tags=('FirstModel', 'CategoryModel.pk:{0}'.format(obj.category_id)))

#### application example 2

    from cache_tags import get_cache

    # ...
    cache = get_cache('my_backend')
    value = cache.get('cache_name')
    if value is None:
        value = cache.set('cache_name', value, tags=('FirstModel', 'CategoryModel.pk:{0}'.format(obj.category_id)))

#### manual invalidation

    from cache_tags import cache
    
    # ...
    cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
    # or
    tag_list = ['Tag1', 'Tag2', 'Tag3', ]
    cache.invalidate_tags(*tag_list)

#### How about transaction (not "Read uncommitted") and multithreading (multiprocessing)?
    from django.db import transaction
    from cache_tags import cache

    cache.transaction_begin()
    with transaction.commit_on_success():
        # ... some code
        # Changes a some data
        cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
        # ... some long code
        # Another process/thread can obtain old data here (after changes but before commit),
        # and create cache with old data.

    cache.transaction_finish()  # Invalidates cache tags again.

#### Transaction handler as decorator
    from django.db import transaction
    from cache_tags import cache
    from cache_tags.decorators import cache_transaction

    @cache_transaction
    @transaction.commit_on_success():
    def some_view(request):
        # ... some code
        cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
        # ... some long code
        # Another process/thread can obtain old data here (after changes but before commit),
        # and create cache with old data.
        # We can also invalidate cache in django.db.models.signals.pre_save()
        # or django.db.models.signals.pre_delete(), and do not worry.
