Cache Tags
============

Forked from https://github.com/Harut/django-cachecontrol

Some ideas from http://dklab.ru/lib/Dklab_Cache/

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

    from cache_tags import registry
    from models import MyModel


    caches = [
        #((model, func), ),
        ((MyModel, lambda obj: ('MyModel_{0}'.format(obj.pk)) )),
    ]

    registry.register(caches)

#### template
    {% load cache_tags %}
    {% cachetags 600 cache_of_2_args object.pk page_number %}
    {# cachetags timeout cache_name [vary_on args|...] #}
       ..............
    {% endcachetags %}

