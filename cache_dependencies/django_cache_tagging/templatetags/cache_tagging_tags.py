# -*- coding: utf-8 -*-
from __future__ import absolute_import, unicode_literals
import re
import copy

from django.core import urlresolvers
from django.template.loader import render_to_string
from django.template import (Library, Node, TemplateSyntaxError,
    VariableDoesNotExist, base)
from django.utils.translation import ugettext_lazy, pgettext_lazy
from django.utils.safestring import mark_safe

from .. import cache, nocache as nocache_handler
from ..utils import prevent_cache_page

try:
    from phased.utils import second_pass_render as phased_render
except ImportError:
    phased_render = None

register = Library()

kwarg_re = re.compile(r"(?:(\w+)=)?(.+)")


class CacheAddTagsNode(Node):
    """Adds a new tags from body of {% cache_tagging %}."""
    def __init__(self, tags):
        self.tags = tags

    def render(self, context):
        tags = [tag.resolve(context) for tag in self.tags]
        if len(tags) == 1 and isinstance(tags[0], (list, tuple, set, frozenset)):
            tags = tags[0]
        context['cache_tagging'].update(tags)
        return ''


def do_cache_add_tags(parser, token):
    """Adds a new tags from body of {% cache_tagging %}."""
    bits = token.split_contents()
    tag_name = bits.pop(0)
    tags = []
    for tag in bits:
        tags.append(parser.compile_filter(tag))
    if len(tags) < 1:
        raise TemplateSyntaxError(
            "'{0}' tag requires at least 1 arguments.".format(tag_name)
        )

    return CacheAddTagsNode(tags)

register.tag('cache_add_tags', do_cache_add_tags)


class CacheNode(Node):
    def __init__(self, nodelist, fragment_name, timeout_var, vary_on, kwargs, filters):
        self.nodelist = nodelist
        self.timeout_var = timeout_var
        self.fragment_name = fragment_name
        self.vary_on = vary_on
        self.kwargs = kwargs
        self.filters = filters

    def render(self, context):
        cache_name = self.fragment_name.resolve(context)
        result = cache.get(cache_name)

        if not result:
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
            if not 'cache_tagging_prevent' in context:
                context['cache_tagging_prevent'] = False

            sub_context = copy.copy(context)
            sub_context['cache_tagging'] = set(tags)
            # Allows nested caching
            sub_context['cache_tagging_prevent'] = False
            result = self.nodelist.render(sub_context)
            tags = sub_context['cache_tagging']

            # Prevent caching of ancestor
            if sub_context['cache_tagging_prevent']:
                context['cache_tagging_prevent'] = True
            prevent = sub_context['cache_tagging_prevent']

            if 'request' in context:
                request = context['request']
                if not hasattr(request, 'cache_tagging'):
                    request.cache_tagging = set()
                if isinstance(request.cache_tagging, set):
                    request.cache_tagging.update(tags)
                if context['cache_tagging_prevent']:
                    prevent_cache_page(request)

            if not prevent:
                cache.set(cache_name, result, tags, timeout)
            else:
                cache.abort(cache_name)

        if 'nocache' in self.kwargs and self.kwargs['nocache'].resolve(context):
            context_dict = {}
            for d in context.dicts:
                context_dict.update(d)

            class Filters(object):
                pass

            filters = Filters()
            for k, v in self.filters.items():
                setattr(filters, k, v)
            filters.escape = filters.force_escape

            context_dict.update({
                'context': context,
                'render_to_string': render_to_string,
                'cache': cache,
                'nocache': nocache_handler,
                'filters': filters,
                'reverse': urlresolvers.reverse,
                '_': ugettext_lazy,
                'ugettext_lazy': ugettext_lazy,
                '_p': pgettext_lazy,
                'pgettext_lazy': pgettext_lazy,
            })
            result = nocache_handler.handle(result, **context_dict)

        if 'phased' in self.kwargs and self.kwargs['phased'].resolve(context) and phased_render:
            # support for django-phased https://github.com/codysoyland/django-phased
            result = phased_render(context['request'], result)

        return result


def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load cache_tagging_tags %}
        {% cache_tagging cache_name [tag1]  [tag2] ... [tags=tag_list] [timeout=3600] [nocache=1] [phased=1] %}
            .. some expensive processing ..
            {% cache_add_tags 'NewTag1' 'NewTag2' %}
        {% end_cache_tagging %}
    """
    nodelist = parser.parse(('end_cache_tagging',))
    parser.delete_first_token()
    bits = token.contents.split()
    if len(bits) < 2:
        raise TemplateSyntaxError(
            "'{0}' tag requires at least 1 arguments.".format(bits[0])
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
    timeout = kwargs.pop('timeout', None)
    try:
        filters = {}
        for lib in base.builtins:
            filters.update(lib.filters)
    except AttributeError:
        filters = parser.filters

    return CacheNode(nodelist, name, timeout, args, kwargs, filters)


@register.simple_tag(takes_context=True)
def cache_tagging_prevent(context):
    """Prevents caching from body of cachetags."""
    context['cache_tagging_prevent'] = True
    return ''

register.tag('cache_tagging', do_cache)


@register.simple_tag
def nocache(**kwargs):
    return mark_safe(nocache_handler.start(**kwargs))


@register.simple_tag
def endnocache():
    return mark_safe(nocache_handler.end())


@register.filter
def concat(value, arg):
    return "{0}{1}".format(value, arg)
