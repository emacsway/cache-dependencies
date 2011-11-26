# -*- coding: utf-8 -*-
import re
import copy

from django.template import Library, Node, TemplateSyntaxError,\
     VariableDoesNotExist

from ..__init__ import cache

register = Library()

kwarg_re = re.compile(r"(?:(\w+)=)?(.+)")


@register.simple_tag(takes_context=True)
def addcachetags(context, tags):
    """Adds a new tags from body of cachetags."""
    if not hasattr(tags, '__iter__'):
        tags = [tags, ]
    context['cache_tags'].update(tags)
    return ''


@register.simple_tag(takes_context=True)
def preventcachetags(context):
    """Prevents caching from body of cachetags."""
    context['cache_tags_prevent'] = True
    return ''


class CacheNode(Node):
    def __init__(self, nodelist, fragment_name, timeout_var, vary_on, kwargs):
        self.nodelist = nodelist
        self.timeout_var = timeout_var
        self.fragment_name = fragment_name
        self.vary_on = vary_on
        self.kwargs = kwargs

    def render(self, context):
        cache_name = self.fragment_name.resolve(context)
        result = cache.get(cache_name)
        if result:
            return result

        timeout = None
        if self.timeout_var:
            try:
                timeout = self.timeout_var.resolve(context)
            except VariableDoesNotExist:
                raise TemplateSyntaxError(
                    '"cache" tag got an unknkown variable: {0}'.format(
                        self.timeout_var.var
                    )
                )
            try:
                timeout = int(timeout)
            except (ValueError, TypeError):
                raise TemplateSyntaxError(
                    '"cache" tag got a non-integer timeout value: {0}'.fomat(
                        timeout
                    )
                )

        tags = [x.resolve(context) for x in self.vary_on]
        if 'tags' in self.kwargs:
            tags += self.kwargs['tags'].resolve(context)

        # We can also add a new tags during nodelist is rendering.
        # And prevent caching.
        if not 'cache_tags_prevent' in context:
            context['cache_tags_prevent'] = False
        sub_context = copy.copy(context)
        sub_context['cache_tags'] = set(tags)
        # Allows nested caching
        sub_context['cache_tags_prevent'] = False

        result = self.nodelist.render(sub_context)

        tags = sub_context['cache_tags']
        # Prevent caching of ancestor
        if sub_context['cache_tags_prevent']:
            context['cache_tags_prevent'] = True
        prevent = sub_context['cache_tags_prevent']

        if 'request' in context:
            request = context['request']
            if not hasattr(request, 'cache_tags'):
                request.cache_tags = set()
            if isinstance(request.cache_tags, set):
                request.cache_tags.update(tags)
            if context['cache_tags_prevent']:
                request._cache_update_cache = False
        if not prevent:
            cache.set(cache_name, result, tags, timeout)
        return result


def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load cache_tags_cache %}
        {% cachetags cache_name [tag1]  [tag2] ... [tags=tag_list] [timeout=3600] %}
            .. some expensive processing ..
            {% addcachetags 'NewTag1' %}
        {% endcachetags %}
    """
    nodelist = parser.parse(('endcachetags',))
    parser.delete_first_token()
    bits = token.contents.split()
    if len(bits) < 2:
        raise TemplateSyntaxError(
            u"'{0}' tag requires at least 1 arguments.".format(bits[0])
        )
    args = []
    kwargs = {}
    bits = bits[1:]
    if len(bits):
        for bit in bits:
            match = kwarg_re.match(bit)
            if not match:
                raise TemplateSyntaxError("Malformed arguments to url tag")
            name, value = match.groups()
            if name:
                kwargs[name] = parser.compile_filter(value)
            else:
                args.append(parser.compile_filter(value))

    name = args.pop(0)
    if 'timeout' in kwargs:
        timeout = kwargs['timeout']
    else:
        timeout = None
    return CacheNode(nodelist, name, timeout, args, kwargs)

register.tag('cachetags', do_cache)
