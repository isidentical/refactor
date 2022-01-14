# API

`refactor` offers a simple programmatic API through `refactor.core.Session`.

## Session

Each session is basically a list of refactoring rules that you want to apply for the same
source code;

```py
from my_rules import ReplaceAdd

session = refactor.Session([ReplaceAdd])
```

### run

`run()` is a simple method that takes the source code and returns the same code

```py
>>> print(session.run("2 + 2"))
2 - 2
>>> print(session.run("'nothing to change'"))
'nothing to change'
```

### run_file

`run_file()` is just like the `run()` but it takes a `pathlib.Path` object and
either returns `None` (when the source code is not change by any rules) or a
`Change` object.

```py
>>> from pathlib import Path
>>> file = Path("test.py")
>>>
>>> file.write_text("2 + 2")
>>> change = session.run_file(file)
>>> print(change)
Change(file=PosixPath('test.py'), original_source='2 + 2', refactored_source='2 - 2')
```

If you want to compute the diff, you can just call `compute_diff()` on the `Change` object;

```diff
>>> print(change.compute_diff())
--- test.py
+++ test.py

@@ -1 +1 @@

-2 + 2
+2 - 2
```

If nothing is changed on the given file, it will just return `None`

```py
>>> file.write_text("'nothing to change'")
>>> print(session.run_file(file))
None
```
