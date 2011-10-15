#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.template import Library, Node, TemplateSyntaxError,\
     Variable, VariableDoesNotExist
from django.template import resolve_variable
from cache_tags import view_set_cache

register = Library()


class CacheNode(Node):
    def __init__(self, nodelist, expire_time_var, fragment_name, vary_on):
        self.nodelist = nodelist
        self.expire_time_var = Variable(expire_time_var)
        self.fragment_name = fragment_name
        self.vary_on = vary_on

    def render(self, context):
        try:
            expire_time = self.expire_time_var.resolve(context)
        except VariableDoesNotExist:
            raise TemplateSyntaxError(
                '"cache" tag got an unknkown variable: {0}'.format(
                    self.expire_time_var.var
                )
            )
        try:
            expire_time = int(expire_time)
        except (ValueError, TypeError):
            raise TemplateSyntaxError(
                '"cache" tag got a non-integer timeout value: {0}'.fomat(
                    expire_time
                )
            )

        def render_nodelist():
            return self.nodelist.render(context)
        vary_on = [resolve_variable(x, context) for x in self.vary_on]

        return view_set_cache(self.fragment_name, expire_time,
                              tags=vary_on, cache_func=render_nodelist)


def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load cache_tags_cache %}
        {% cachetags expire_time cache_name [var1]  [var2] ... %}
            .. some expensive processing ..
        {% cachetags %}
    """
    nodelist = parser.parse(('endcachetags',))
    parser.delete_first_token()
    tokens = token.contents.split()
    if len(tokens) < 3:
        raise TemplateSyntaxError(
            u"'{0}' tag requires at least 2 arguments.".format(tokens[0])
        )
    return CacheNode(nodelist, tokens[1], tokens[2], tokens[3:])

register.tag('cachetags', do_cache)
