# Contributing

Start by forking the `refactor` [repository](https://github.com/isidentical/refactor), so you would have a place to push your changes. Once it is ready, clone it locally:

```console
$ git clone git@github.com:<your username>/refactor
```

Also don't forget to add the `upstream` as a remote as well:

```console
$ cd refactor
$ git remote add upstream https://github.com/isidentical/refactor.git
```

Create a branch from a fresh version of `upstream/main`:

```console
$ git fetch upstream
$ git checkout -b <your branch name> upstream/main
```

Install `pre-commit` and other dev dependencies locally and don't forget to enable the hooks for this repository:

```console
$ pip install pre-commit
$ pip install -r requirements-dev.txt
$ pre-commit install
```

From here, make your changes, commit them and push them to your fork. Then you can create a PR with an adequate description of what you tried to achieve and 🥳
