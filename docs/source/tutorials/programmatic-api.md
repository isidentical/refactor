# Programmable API

Refactor provides a top-level API for you to freely use your rules on any
sort of input. You might want to use this API if you are interested in:

- Writing your own command line interface
- Testing the rules and the actions you wrote
- Going to next-level and building GitHub bots on top of Refactor.

## Sessions

A ["session"](refactor.core.Session) is a collection of {term}`rule`s that will run together on the
same {term}`context`.

```pycon
>>> from refactor import Session
>>> from previous_tutorial import FoldMyConstants, PropagateMyConstants
```

You can initialize session with the rules that you want to include (so if you are building your own CLI,
you can read user's configuration to see what rules they disabled and exclude them at this step).

```pycon
>>> session = Session(rules=[FoldMyConstants, PropagateMyConstants])
```

```{tip}
You can also optionally pass a [config](refactor.context.Configuration) object to customize some internal behaviors
(e.g. enabling the debug mode or changing the default unparser).
```

With session in our hands, we can start exploring the two entry points it offers: [`run()`](refactor.core.Session.run) and [`run_file()`](refactor.core.Session.run_file).

### `run()`

`run()` takes the raw source code as *text*, transforms it, and returns to you as a *text*. With this property, it is very useful for tests (especially the parametrized
ones).

```pycon
>>> session.run("a = 2 + 2")
'a = 4'
```

::::{warning}
If you pass a problematic source code (e.g. code that contains invalid syntax), it won't raise any errors and will return the given source code unchanged.

:::{code-block} pycon
>>> session.run("$$$ invalid $$$")
>>> '$$$ invalid $$$'
>>>
:::

::::

### `run_file()`

`run_file()` is however a bit different, in the sense that it takes a `pathlib.Path` object instead of the source code
and returns a [`Change`](refactor.change.Change) object instead of returning the transformed result directly. As you might
have guessed, this is an API suitable for tools that process files and something that you might consider using in your CLI
interface.

```pycon
>>> from pathlib import Path
>>> target_file = Path("test.py")
>>>
>>> with open(target_file, "w") as stream:
...     stream.write("a = 2 + 2\n")
...     stream.write("print('hello')\n")
...     stream.write("b = 5 + a\n")
...     stream.write("print(b)\n")
...     stream.write("print('done')")
...
```

```pycon
>>> change = session.run_file(target_file)
```

If any of the rules changed the source code in any way, `run_file()` returns a [`Change`](refactor.change.Change) object (otherwise,
if there are no changes, it will just return `None`). The `change` object contains both the original source code, as well as the potential
transformation so we can compare it and apply it depending on our case. Let's view the diff:

```pycon
>>> print(change.compute_diff())
```

```diff
--- test.py
+++ test.py

@@ -1,5 +1,5 @@

-a = 2 + 2
+a = 4
 print('hello')
-b = 5 + a
+b = 9
-print(b)
+print(9)
 print('done')
```

As you can see, it shows what sort of changes would have been made without actually doing them. In some cases, the ability of a dry
run like this would be very meaningful to observe how a rule interacts with source code before blindly trusting it. Now that we have
verified that all the transformations make sense, we'll continue and apply it directly to the source file.

`run_file()` won't actually cause any changes until the user applies the diff manually so the file is still untouched.

```pycon
>>> print(target_file.read_text())
a = 2 + 2
print('hello')
b = 5 + a
print(b)
print('done')
```

But once we move forward and call [`apply_diff()`](refactor.change.Change.apply_diff), it will be transformed in place.

```pycon
>>> change.apply_diff()
```

And we can read the file again to verify the results:

```pycon
>>> print(target_file.read_text())
a = 4
print('hello')
b = 9
print(9)
print('done')
```

Now if you try calling `run_file()` again on this file, you'll get a `None` since there were no changes made.

```pycon
>>> assert session.run_file(target_file) is None
>>>
```
