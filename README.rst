==============
Cache Tagging
==============

Tags are a way to categorize cache records.
When you save a cache, you can set a list of tags to apply for this record.
Then you will be able to invalidate all cache records tagged with a given tag (or tags).

Forked from https://github.com/Harut/django-cachecontrol

Some ideas from http://dklab.ru/lib/Dklab_Cache/

Cache tagging allows to manage cached values and easily link them to Model signals

Usage
======

project urls.py::

    from cache_tagging.django_cache_tagging import autodiscover
    autodiscover()

application example 1::

    # Default backend
    from cache_tagging.django_cache_tagging import cache

    value = cache.get('cache_name')
    if value is None:
        value = get_value_func()
        cache.set('cache_name', value, tags=('FirstModel', 'CategoryModel.pk:{0}'.format(obj.category_id)))

application example 2::

    # Custom backend
    from cache_tagging.django_cache_tagging import get_cache
    cache = get_cache('my_backend')

    value = cache.get('cache_name')
    if value is None:
        value = get_value_func()
        cache.set('cache_name', value, tags=('FirstModel', 'CategoryModel.pk:{0}'.format(obj.category_id)))

manual invalidation::

    from cache_tagging.django_cache_tagging import cache
    
    # ...
    cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
    # or
    tag_list = ['Tag1', 'Tag2', 'Tag3', ]
    cache.invalidate_tags(*tag_list)

appname.caches.py file::

    from cache_tagging.django_cache_tagging import registry, get_cache
    from models import MyModel
    from django.db.models.signals import post_save, post_delete

    # Variant 1. Using signals for invalidation.
    def invalidation_callback(sender, instance, **kwars):
        cache.invalidate_tags(
            'Tag1',
            'Tag2',
            'FirstModel.pk:{1}'.format(instance.pk)
        )
    post_save.connect(invalidation_callback, sender=FirstModel)
    post_delete.connect(invalidation_callback, sender=FirstModel)
    
    # Variant 2. Using registry.register().
    # Each item from list creates model's post_save and pre_delete signal.
    # Func takes changed model and returns list of tags.
    # When the signal is called, it gets varied tags and deletes all caches with this tags.
    caches = [
        #((model, func, [cache_object, ]), ),
        ((FirstModel, lambda obj: ('FirstModel.pk:{0}'.format(obj.pk), ), get_cache('my_cache_alias'), ), ),
        ((SecondModel, lambda obj: ('SecondModel.pk:{0}'.format(obj.pk),
                                    'CategoryModel.pk:{0}.TypeModel.pk:{1}'.format(obj.category_id, obj.type_id),
                                    'SecondModel', ), ), ),
    ]
    registry.register(caches)

template::

    {% load cache_tagging_tags %}
    {% cache_tagging 'cache_name' 'CategoryModel.pk:15' 'FirstModel' tags=tag_list_from_view timeout=3600 %}
        ...
        {% cache_add_tags 'NewTag1' %}
        ...
        {% cache_add_tags 'NewTag2' 'NewTag3' %}
        ...
        {% if do_not_cache_condition %}
            {% cache_tagging_prevent %}
        {% endif %}
    {% end_cache_tagging %}
    {% comment %}
        {% cache_tagging cache_name [tag1]  [tag2] ... [tags=tag_list] [timeout=3600] %}
        {% cache_add_tags tag_or_list_of_tags %}
        If context has attribute "request", then templatetag {% cache_tagging %}
        adds to request a new attribute "cache_tagging" (instance of set() object) with all tags.
        If request already has attribute "cache_tagging", and it's instance of set() object,
        then templatetag {% cache_tagging %} adds all tags to this object.
        You can use together templatetag {% cache_tagging %} and decorator @cache_page().
        In this case, when @cache_page() decorator will save response,
        it will also adds all tags from request.cache_tagging to cache.
        You need not worry about it.

        If need, you can prevent caching by templatetag {% cache_tagging_prevent %}.
        In this case also will be prevented @cache_page() decorator, if it's used,
        and context has attribute "request".
    {% endcomment %}

view decorator::

    from cache_tagging.django_cache_tagging.decorators import cache_page

    # See also useful decorator to bind view's args and kwargs to request
    # https://bitbucket.org/evotech/django-ext/src/d8b55d86680e/django_ext/middleware/view_args_to_request.py

    @cache_page(3600, tags=lambda request: ('FirstModel', ) + SecondModel.get_tags_for_request(request))
    def cached_view(request):
        result = get_result()
        return HttpResponse(result)

How about transaction and multithreading (multiprocessing)?::

    from django.db import transaction
    from cache_tagging.django_cache_tagging import cache

    cache.transaction_begin()
    with transaction.commit_on_success():
        # ... some code
        # Changes a some data
        cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
        # ... some long code
        # Another concurrent process/thread can obtain old data at this time,
        # after changes but before commit, and create cache with old data,
        # if isolation level is not "Read uncommitted".
        # Otherwise, if isolation level is "Read uncommitted", and transaction will rollback,
        # the concurrent and current process/thread can creates cache with dirty data.

    cache.transaction_finish()  # Invalidates cache tags again, after transaction commit/rollback.

Transaction handler as decorator::

    from django.db import transaction
    from cache_tagging.django_cache_tagging import cache
    from cache_tagging.django_cache_tagging.decorators import cache_transaction

    @cache_transaction
    @transaction.commit_on_success():
    def some_view(request):
        # ... some code
        cache.invalidate_tags('Tag1', 'Tag2', 'Tag3')
        # ... some long code
        # Another concurrent process/thread can obtain old data at this time,
        # after changes but before commit, and create cache with old data,
        # if isolation level is not "Read uncommitted".
        # Otherwise, if isolation level is "Read uncommitted", and transaction will rollback,
        # the concurrent and current process/thread can creates cache with dirty data.
        #
        # We can also invalidate cache before data changes,
        # by signals django.db.models.signals.pre_save()
        # or django.db.models.signals.pre_delete(), and do not worry.

Transaction handler as middleware::

    MIDDLEWARE_CLASSES = [
        # ...
        "cache_tagging.django_cache_tagging.middleware.TransactionMiddleware",  # Should be before
        "django.middleware.transaction.TransactionMiddleware",
        # ...
    ]
