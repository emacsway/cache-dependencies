import operator
import itertools


class DependencyLocked(Exception):
    def __init__(self, dependency, items):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type items: collections.Iterable[str]
        """
        self.dependency = dependency
        self.items = tuple(items)


class TagsLocked(DependencyLocked):
    pass


class CompositeDependencyLocked(DependencyLocked):
    def __init__(self, dependency, children):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type children: collections.Iterable[DependencyInvalid]
        """
        self.dependency = dependency
        self.children = tuple(children)

    @property
    def items(self):
        return itertools.chain(*map(operator.attrgetter('items'), self.children))

    def __iter__(self):
        return iter(self.children)


class DependencyInvalid(Exception):
    def __init__(self, dependency, errors):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type errors: collections.Iterable[str]
        """
        self.dependency = dependency
        self.errors = tuple(errors)


class TagsInvalid(DependencyInvalid):
    pass


class CompositeDependencyInvalid(DependencyInvalid):
    def __init__(self, dependency, children):
        """
        :type dependency: cache_dependencies.interfaces.IDependency
        :type children: collections.Iterable[DependencyInvalid]
        """
        self.dependency = dependency
        self.children = tuple(children)

    @property
    def errors(self):
        return itertools.chain(*map(operator.attrgetter('errors'), self.children))

    def __iter__(self):
        return iter(self.children)
