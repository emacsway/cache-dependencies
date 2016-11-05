

class DependencyLocked(Exception):
    pass


class DependencyInvalid(Exception):
    pass


class TagsLocked(DependencyLocked):
    pass


class TagsInvalid(DependencyInvalid):
    pass


class CompositeDependencyLocked(DependencyLocked):
    pass


class CompositeDependencyInvalid(DependencyInvalid):
    pass
