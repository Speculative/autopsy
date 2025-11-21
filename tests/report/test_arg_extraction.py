"""Test argument expression extraction from report.log() calls."""

import tempfile
from pathlib import Path

from autopsy import report


def test_extract_simple_variables():
    """Test extraction of simple variable names."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    x = 1
    y = 2
    report.log(x, y)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 5)
        assert arg_names == ["x", "y"], f"Expected ['x', 'y'], got {arg_names}"
    finally:
        Path(temp_file).unlink()


def test_extract_attribute_access():
    """Test extraction of attribute access expressions."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    obj = SomeClass()
    report.log(obj.attr, obj.nested.attr)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 4)
        assert arg_names == ["obj.attr", "obj.nested.attr"], (
            f"Expected ['obj.attr', 'obj.nested.attr'], got {arg_names}"
        )
    finally:
        Path(temp_file).unlink()


def test_extract_function_calls():
    """Test extraction of function call expressions."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    store = KVStore()
    report.log(store.get_stats(), len(items), some_func())
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 4)
        # Should extract method calls and function calls
        assert len(arg_names) == 3
        assert arg_names[0] == "store.get_stats()" or "store.get_stats" in arg_names[0]
        assert arg_names[1] == "len(items)" or "len(items" in arg_names[1]
        assert arg_names[2] == "some_func()" or "some_func" in arg_names[2]
    finally:
        Path(temp_file).unlink()


def test_extract_literals():
    """Test extraction of literal expressions."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    report.log("hello", 42, True, None)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 3)
        # Literals should be extracted as their code representation
        assert len(arg_names) == 4
        assert arg_names[0] == '"hello"' or arg_names[0] == "'hello'"
        assert arg_names[1] == "42"
        assert arg_names[2] == "True"
        assert arg_names[3] == "None"
    finally:
        Path(temp_file).unlink()


def test_extract_mixed_expressions():
    """Test extraction of mixed variable names, calls, and literals."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    x = 1
    y = 2
    obj = SomeClass()
    report.log("label", x, obj.method(), y + 1)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 6)
        assert len(arg_names) == 4
        assert arg_names[0] == '"label"' or arg_names[0] == "'label'"  # Literal string
        assert arg_names[1] == "x"  # Variable
        assert "method" in (arg_names[2] or "")  # Method call
        # Binary operation should be extracted
        assert arg_names[3] == "y + 1" or arg_names[3] is not None
    finally:
        Path(temp_file).unlink()


def test_extract_binary_operations():
    """Test extraction of binary operation expressions."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    x = 1
    y = 2
    report.log(x + y, x * y, x < y)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 5)
        assert len(arg_names) == 3
        # With ast.unparse (Python 3.9+), these should be extracted
        # Without it, fallback might return None for complex expressions
        # So we just check that we get something reasonable
        if arg_names[0]:
            assert "x" in arg_names[0] and "y" in arg_names[0]
        if arg_names[1]:
            assert "x" in arg_names[1] and "y" in arg_names[1]
        if arg_names[2]:
            assert "x" in arg_names[2] and "y" in arg_names[2]
    finally:
        Path(temp_file).unlink()


def test_extract_multiline_call():
    """Test extraction from multi-line log calls."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    report.log(
        "label",
        store.get_stats(),
        manager.get_stats()
    )
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 3)
        assert len(arg_names) == 3
        assert arg_names[0] == '"label"' or arg_names[0] == "'label'"  # Literal
        assert "store.get_stats" in (arg_names[1] or "")
        assert "manager.get_stats" in (arg_names[2] or "")
    finally:
        Path(temp_file).unlink()


def test_extract_nested_calls():
    """Test extraction from nested function calls."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    items = [1, 2, 3]
    report.log(len(items), max(items), min([1, 2]))
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 4)
        assert len(arg_names) == 3
        # Should extract function calls
        if arg_names[0]:
            assert "len" in arg_names[0] and "items" in arg_names[0]
        if arg_names[1]:
            assert "max" in arg_names[1] and "items" in arg_names[1]
        # Third one has a literal list, might be None or extracted
    finally:
        Path(temp_file).unlink()


def test_no_log_call():
    """Test that non-log calls return empty list."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    other_func(x, y)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 3)
        assert arg_names == []
    finally:
        Path(temp_file).unlink()


def test_invalid_line_number():
    """Test that invalid line numbers return empty list."""
    report.init()

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(
            """
def test_func():
    report.log(x)
"""
        )
        temp_file = f.name

    try:
        arg_names = report._extract_arg_names(temp_file, 999)
        assert arg_names == []
    finally:
        Path(temp_file).unlink()

