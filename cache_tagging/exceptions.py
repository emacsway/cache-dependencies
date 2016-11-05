

class DependencyLocked(Exception):
    pass


class TagsLocked(DependencyLocked):
    pass


class CompositeDependencyLocked(DependencyLocked):
    pass
