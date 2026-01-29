"""Test argument extraction via public API with various function shapes.

This test suite ensures that autopsy correctly extracts argument names when
called from functions with different signatures and decorators.
"""

import tempfile
from pathlib import Path

import autopsy


def test_simple_function():
    """Test extraction from a simple function with positional args."""
    autopsy.init(clear=True, warn=False)

    def simple_func(source, expected):
        autopsy.log(source, expected)

    simple_func('hello', 'world')

    report = autopsy.get_report()
    logs = report.get_logs()

    # Should have exactly one call site
    assert len(logs) == 1

    call_site, log_groups = list(logs.items())[0]
    assert len(log_groups) == 1

    arg_names = log_groups[0].get('arg_names', [])
    # Should see the actual arguments, not '*args'
    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_function_with_default_args():
    """Test extraction from function with default arguments."""
    autopsy.init(clear=True, warn=False)

    def func_with_defaults(source, expected, verbose=True, debug=False):
        autopsy.log(source, expected)

    func_with_defaults('foo', 'bar')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_function_with_star_args():
    """Test extraction from function that accepts *args."""
    autopsy.init(clear=True, warn=False)

    def func_with_star_args(*args):
        # Log specific values, not unpacking
        if len(args) >= 2:
            autopsy.log(args[0], args[1])

    func_with_star_args('a', 'b', 'c')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    # Should see the indexed access
    assert 'args[0]' in str(arg_names[0]), f"Got {arg_names}"
    assert 'args[1]' in str(arg_names[1]), f"Got {arg_names}"


def test_function_with_kwargs():
    """Test extraction from function with **kwargs."""
    autopsy.init(clear=True, warn=False)

    def func_with_kwargs(source, expected, **kwargs):
        autopsy.log(source, expected)

    func_with_kwargs('hello', 'world', extra='data', more='stuff')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_function_with_all_arg_types():
    """Test extraction from function with positional, *args, and **kwargs."""
    autopsy.init(clear=True, warn=False)

    def func_with_all(pos1, pos2, default='value', *args, **kwargs):
        autopsy.log(pos1, pos2)

    func_with_all('a', 'b', 'c', 'd', key='val')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['pos1', 'pos2'], f"Got {arg_names}"


def test_decorated_function():
    """Test extraction from a decorated function."""
    autopsy.init(clear=True, warn=False)

    def my_decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper

    @my_decorator
    def decorated_func(source, expected):
        autopsy.log(source, expected)

    decorated_func('foo', 'bar')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    # Should still see the actual arguments from inside the function
    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_method_on_class():
    """Test extraction from a class method."""
    autopsy.init(clear=True, warn=False)

    class MyClass:
        def my_method(self, source, expected):
            autopsy.log(source, expected)

    obj = MyClass()
    obj.my_method('hello', 'world')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_classmethod():
    """Test extraction from a classmethod."""
    autopsy.init(clear=True, warn=False)

    class MyClass:
        @classmethod
        def my_classmethod(cls, source, expected):
            autopsy.log(source, expected)

    MyClass.my_classmethod('foo', 'bar')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_staticmethod():
    """Test extraction from a staticmethod."""
    autopsy.init(clear=True, warn=False)

    class MyClass:
        @staticmethod
        def my_staticmethod(source, expected):
            autopsy.log(source, expected)

    MyClass.my_staticmethod('baz', 'qux')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_nested_function():
    """Test extraction from a nested function."""
    autopsy.init(clear=True, warn=False)

    def outer(x):
        def inner(source, expected):
            autopsy.log(source, expected, x)
        inner('a', 'b')

    outer('closure_val')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected', 'x'], f"Got {arg_names}"


def test_lambda_context():
    """Test extraction when autopsy.log is called in a context with lambdas."""
    autopsy.init(clear=True, warn=False)

    def func_with_lambda(source, expected):
        # Lambda nearby shouldn't confuse extraction
        processor = lambda x: x.upper()
        autopsy.log(source, expected)

    func_with_lambda('hello', 'world')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_function_with_type_hints():
    """Test extraction from function with type hints."""
    autopsy.init(clear=True, warn=False)

    def typed_func(source: str, expected: str) -> None:
        autopsy.log(source, expected)

    typed_func('foo', 'bar')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_async_function():
    """Test extraction from an async function."""
    import asyncio

    autopsy.init(clear=True, warn=False)

    async def async_func(source, expected):
        autopsy.log(source, expected)
        return 'done'

    # Run the async function
    asyncio.run(async_func('hello', 'world'))

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"


def test_multiline_log_call():
    """Test extraction when log() call spans multiple lines."""
    autopsy.init(clear=True, warn=False)

    def multiline_func(source, expected, extra):
        autopsy.log(
            source,
            expected,
            extra
        )

    multiline_func('a', 'b', 'c')

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected', 'extra'], f"Got {arg_names}"


def test_real_world_test_method():
    """Test case that mimics the user's assertMarkdownRenders method."""
    autopsy.init(clear=True, warn=False)

    class MarkdownTestCase:
        def __init__(self):
            self.default_kwargs = {'strict': True}

        def assertMarkdownRenders(self, source, expected, expected_attrs=None, **kwargs):
            """Real-world test method pattern."""
            expected_attrs = expected_attrs or {}
            kws = self.default_kwargs.copy()
            kws.update(kwargs)
            # Simulate markdown conversion
            output = source.upper()  # Mock conversion
            autopsy.log(output, expected)

    test = MarkdownTestCase()
    test.assertMarkdownRenders('hello', 'HELLO', extra_option=True)

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    # Should see the variable names, not '*args'
    assert arg_names == ['output', 'expected'], f"Got {arg_names}"


def test_generator_function():
    """Test extraction from a generator function."""
    autopsy.init(clear=True, warn=False)

    def generator_func(source, expected):
        autopsy.log(source, expected)
        yield 1
        yield 2

    # Consume the generator
    list(generator_func('a', 'b'))

    report = autopsy.get_report()
    logs = report.get_logs()

    assert len(logs) == 1
    call_site, log_groups = list(logs.items())[0]
    arg_names = log_groups[0].get('arg_names', [])

    assert arg_names == ['source', 'expected'], f"Got {arg_names}"
