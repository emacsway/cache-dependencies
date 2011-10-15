#!/usr/bin/python
# -*- coding: utf-8 -*-

from django.template import Library, Node, TemplateSyntaxError,\
     Variable, VariableDoesNotExist
from django.template import resolve_variable
from cache_tags import view_set_cache

register = Library()


class CacheNode(Node):
    def __init__(self, nodelist, timeout_var, fragment_name, vary_on):
        self.nodelist = nodelist
        self.timeout_var = Variable(timeout_var)
        self.fragment_name = fragment_name
        self.vary_on = vary_on

    def render(self, context):
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

        def render_nodelist():
            return self.nodelist.render(context)
        vary_on = [resolve_variable(x, context) for x in self.vary_on]

        return view_set_cache(self.fragment_name,
                              tags=vary_on,
                              cache_func=render_nodelist,
                              timeout=timeout)


def do_cache(parser, token):
    """
    This will cache the contents of a template fragment for a given amount
    of time.

    Usage::

        {% load cache_tags_cache %}
        {% cachetags timeout cache_name [var1]  [var2] ... %}
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
