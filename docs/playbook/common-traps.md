# Common Traps That Bite Workers

These aren't Maestro bugs — they're Python and framework gotchas that recur often enough
in worker output to be worth pre-empting. Each one has a recovery, but the cheaper move
is to recognise them up front and bake the workaround into your spec.

## The import-by-name monkeypatch trap

**The symptom**: a test does
`monkeypatch.setattr("some_module.some_helper", lambda: ...)`. The code under test does
`from some_module import some_helper` and calls `some_helper()`. The monkeypatch doesn't
take effect.

**The cause**: `from some_module import some_helper` rebinds `some_helper` into the
caller's namespace at import time. After that, the caller has its own local reference to
the original function. When the test rewrites `some_module.some_helper`, the caller's
reference is unchanged.

**The fix**: prefer module-level imports and call through the module reference. Instead
of:

```python
# In caller.py — vulnerable to the trap
from some_module import some_helper

def do_stuff():
    return some_helper()
```

Use:

```python
# In caller.py — monkeypatch-friendly
from some_module import some_module as sm  # or just: import some_module

def do_stuff():
    return sm.some_helper()  # lookup happens at call time
```

Or in the test, monkeypatch both locations:

```python
monkeypatch.setattr("some_module.some_helper", fake)
monkeypatch.setattr("caller.some_helper", fake)  # also rebind the caller's local reference
```

**How to bake the workaround into specs**: when your spec asks for a function that will
be monkeypatched in tests, mention it explicitly:

> "The `_project_root()` helper will be monkeypatched in tests. To make this work, import
> the containing module (not the function symbol directly) and call
> `module._project_root()` so the lookup happens at call time."

Coder will follow this if you say it. Otherwise it tends to default to the
`from X import f` shape, and your test will fail in a confusing way.

## starlette `TemplateResponse` API migration

**The symptom**: your route does
`templates.TemplateResponse("foo.html", {"context_var": value})` and tests fail with
`TypeError: unhashable type: 'dict'` from somewhere inside Jinja's LRU cache.

**The cause**: starlette changed `TemplateResponse`'s signature. The current form is
`(request, name, context)`. The legacy form `(name, context)` is interpreted as
`(name=context_dict, context=...)`, which means a dict object is being looked up as a
cache key — and dicts aren't hashable.

**The fix**: use the new signature everywhere.

```python
# Legacy — will hit the cache error
return templates.TemplateResponse("foo.html", {"version": "1.0"})

# Current — works
return templates.TemplateResponse(request, "foo.html", {"version": "1.0"})
```

Note that `request` must be a parameter of your route function (FastAPI injects it).

**How to bake the workaround into specs**: when dispatching to coder for FastAPI work,
include a hard constraint:

> "Use starlette's new `TemplateResponse(request, name, context)` API; the legacy
> `(name, context)` form is broken in current starlette versions."

The reason this matters: training data for many models predates the API change, so coder
will default to the legacy form unless prompted otherwise.

## Pydantic v1 vs v2 idioms

**The symptom**: code uses `@validator` decorator or `Config` inner class; modern Pydantic
emits deprecation warnings or outright errors.

**The cause**: Pydantic v2 (current as of this writing) uses different decorators and
configuration syntax than v1. Workers often default to v1 patterns from older training
data.

**The fix**: use v2 idioms explicitly:

```python
# v1 — deprecated in v2
class Foo(BaseModel):
    name: str

    class Config:
        extra = "forbid"

    @validator("name")
    def check_name(cls, v):
        ...

# v2 — current
class Foo(BaseModel):
    name: str

    model_config = ConfigDict(extra="forbid")

    @field_validator("name")
    @classmethod
    def check_name(cls, v):
        ...
```

**How to bake the workaround into specs**: state the Pydantic version explicitly:

> "Pydantic v2 (`pydantic>=2`). Use `model_validator(mode='after')`, `field_validator`,
> `ConfigDict` per v2 idioms. Do NOT use v1-style `@validator` or `Config` inner class."

## Async fixture / sync test mismatch

**The symptom**: a pytest test of an async function silently doesn't run, or emits
"coroutine was never awaited" warnings.

**The cause**: pytest doesn't run async functions natively. You need `pytest-asyncio` or
a fixture that runs the coroutine.

**The fix**: either use `asyncio.run(...)` inside a synchronous test, or use
`pytest-asyncio` with the `@pytest.mark.asyncio` decorator. For occasional async tests
the inline-run pattern is lighter:

```python
import asyncio

def test_async_handler(server):
    result = asyncio.run(server.some_async_handler(arguments))
    assert ...
```

**How to bake the workaround into specs**: if a test needs to call async code, say so:

> "The handler under test is an `async def`. Use `asyncio.run(handler(args))` inside a
> regular synchronous test rather than adding `pytest-asyncio` as a dependency."

## What to do when a trap bites you anyway

Every trap above has been pre-empted in specs and still occasionally bit, because
training data is what it is. The recovery in each case is the same:

1. Recognise the symptom (the error message is usually unambiguous once you know what
   to look for).
2. Apply the fix to the produced code. If the change is genuinely one line, you can
   apply it in your orchestrator session as a small surgical edit; if it's spread across
   multiple files, re-dispatch with the fix called out as a hard constraint.
3. Update your local CLAUDE.md to mention the workaround so the next dispatch in this
   project gets it baked in.

## What this looks like in your CLAUDE.md

```markdown
## Known dispatch traps to bake into specs

- Pydantic v2 idioms only (`model_validator`, `field_validator`, `ConfigDict`); no v1
  `@validator` or `Config` inner class.
- starlette `TemplateResponse(request, name, context)` API — the legacy `(name, context)`
  form triggers a Jinja cache error.
- For helpers that get monkeypatched in tests, use module-reference imports
  (`from x import y_module` then `y_module.helper()`), not symbol imports
  (`from x.y_module import helper`).
- For async tests, prefer `asyncio.run(...)` inline over adding `pytest-asyncio`.
```
