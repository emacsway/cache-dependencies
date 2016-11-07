import operator
import itertools


class DependencyLocked(Exception):
    pass


class TagsLocked(DependencyLocked):
    pass


class CompositeDependencyLocked(DependencyLocked):
    pass


class DependencyInvalid(Exception):
    def __init__(self, dependency, errors):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type errors: tuple[str]
        """
        self.dependency = dependency
        self.errors = errors


class TagsInvalid(DependencyInvalid):
    pass


class CompositeDependencyInvalid(DependencyInvalid):
    def __init__(self, dependency, children):
        """
        :type dependency: cache_tagging.interfaces.IDependency
        :type children: tuple[DependencyInvalid]
        """
        self.dependency = dependency
        self.children = children

    @property
    def errors(self):
        return itertools.chain(*map(operator.attrgetter('errors'), self.children))

    def __iter__(self):
        return iter(self.children)
