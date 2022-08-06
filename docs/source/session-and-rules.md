# Session and Rules

Each transformation in Refactor corresponds to a rule and those rules come
together to create a refactoring [session](refactor.core.Session). The session
then can be used for processing the given set of files and applying the initialized
transformations.

## Rules -- and why we need them?

A rule is a class that inherits from [refactor.Rule](refactor.core.Rule) and
implements the [match()](refactor.core.Rule.match) method in order to receive
some nodes, filter them, and apply the defined transformation to the ones that
it filtered.
