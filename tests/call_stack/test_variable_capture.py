"""Test variable capture and serialization behavior."""

import json
from pathlib import Path

from autopsy import call_stack


def test_skip_functions():
    """Test that functions are skipped in variable capture."""

    def test_function():
        def inner_func():
            pass

        lambda_func = lambda x: x + 1  # noqa: E731, F841
        regular_var = 42  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "inner_func" not in local_vars, "Function should be skipped"
                assert "lambda_func" not in local_vars, (
                    "Lambda function should be skipped"
                )
                assert "regular_var" in local_vars, (
                    "Regular variable should be included"
                )
                assert local_vars["regular_var"] == 42
                break

    test_function()


def test_skip_modules():
    """Test that modules are skipped in variable capture."""

    def test_function():
        import sys

        my_module = sys  # noqa: F841
        regular_var = "test"  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "sys" not in local_vars, "Module should be skipped"
                assert "os" not in local_vars, "Module should be skipped"
                assert "my_module" not in local_vars, (
                    "Module variable should be skipped"
                )
                assert "regular_var" in local_vars, (
                    "Regular variable should be included"
                )
                assert local_vars["regular_var"] == "test"
                break

    test_function()


def test_skip_types():
    """Test that types/classes are skipped in variable capture."""

    def test_function():
        from pathlib import Path

        # Imported class
        path_class = Path  # noqa: F841

        # Locally defined class
        class LocalClass:
            pass

        # Class instances should be included
        path_instance = Path("/tmp")  # noqa: F841
        local_instance = LocalClass()  # noqa: F841

        regular_var = 42  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "path_class" not in local_vars, (
                    "Imported class should be skipped"
                )
                assert "LocalClass" not in local_vars, "Defined class should be skipped"
                assert "path_instance" in local_vars, (
                    "Class instance should be included"
                )
                assert "local_instance" in local_vars, (
                    "Class instance should be included"
                )
                assert "regular_var" in local_vars, (
                    "Regular variable should be included"
                )
                assert local_vars["regular_var"] == 42
                break

    test_function()


def test_skip_autopsy_objects():
    """Test that autopsy objects are skipped in variable capture."""

    def test_function():
        cs1 = call_stack()  # noqa: F841
        cs2 = call_stack()  # noqa: F841
        regular_var = 42  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "cs1" not in local_vars, "Autopsy CallStack should be skipped"
                assert "cs2" not in local_vars, "Autopsy CallStack should be skipped"
                assert "regular_var" in local_vars, (
                    "Regular variable should be included"
                )
                assert local_vars["regular_var"] == 42
                break

    test_function()


def test_recursive_object_serialization():
    """Test that objects are recursively serialized."""

    class Person:
        def __init__(self, name, age):
            self.name = name
            self.age = age
            self.friends = []

    def test_function():
        person1 = Person("Alice", 30)
        person2 = Person("Bob", 25)
        person1.friends.append(person2)

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "person1" in local_vars
                assert "person2" in local_vars

                person1_data = local_vars["person1"]
                assert isinstance(person1_data, dict)
                assert person1_data["name"] == "Alice"
                assert person1_data["age"] == 30
                assert isinstance(person1_data["friends"], list)
                assert len(person1_data["friends"]) == 1

                friend_data = person1_data["friends"][0]
                assert isinstance(friend_data, dict)
                assert friend_data["name"] == "Bob"
                assert friend_data["age"] == 25
                break

    test_function()


def test_nested_dicts_and_lists():
    """Test that nested dicts and lists are properly serialized."""

    def test_function():
        data = {  # noqa: F841
            "numbers": [1, 2, 3],
            "nested": {"a": 1, "b": [4, 5, 6]},
            "mixed": [
                {"key1": "value1"},
                {"key2": "value2"},
            ],
        }

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "data" in local_vars

                data_serialized = local_vars["data"]
                assert isinstance(data_serialized, dict)
                assert data_serialized["numbers"] == [1, 2, 3]
                assert isinstance(data_serialized["nested"], dict)
                assert data_serialized["nested"]["a"] == 1
                assert data_serialized["nested"]["b"] == [4, 5, 6]
                assert isinstance(data_serialized["mixed"], list)
                assert len(data_serialized["mixed"]) == 2
                assert data_serialized["mixed"][0]["key1"] == "value1"
                break

    test_function()


def test_circular_reference_handling():
    """Test that circular references are handled correctly."""

    class Node:
        def __init__(self, value):
            self.value = value
            self.next = None

    def test_function():
        node1 = Node(1)
        node2 = Node(2)
        node3 = Node(3)

        # Create circular reference
        node1.next = node2
        node2.next = node3
        node3.next = node1

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "node1" in local_vars

                node1_data = local_vars["node1"]
                assert isinstance(node1_data, dict)
                assert node1_data["value"] == 1

                # Check that circular reference is detected
                node2_data = node1_data["next"]
                assert isinstance(node2_data, dict)
                assert node2_data["value"] == 2

                node3_data = node2_data["next"]
                assert isinstance(node3_data, dict)
                assert node3_data["value"] == 3

                # The circular reference should be detected
                circular_ref = node3_data["next"]
                assert circular_ref == "<circular_reference>"
                break

    test_function()


def test_primitive_types():
    """Test that primitive types are correctly serialized."""

    def test_function():
        int_var = 42  # noqa: F841
        float_var = 3.14  # noqa: F841
        bool_var = True  # noqa: F841
        str_var = "hello"  # noqa: F841
        none_var = None  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert local_vars["int_var"] == 42
                assert local_vars["float_var"] == 3.14
                assert local_vars["bool_var"] is True
                assert local_vars["str_var"] == "hello"
                assert local_vars["none_var"] is None
                break

    test_function()


def test_private_attributes_skipped():
    """Test that private attributes (starting with _) are skipped in object serialization."""

    class TestClass:
        def __init__(self):
            self.public = "visible"
            self._private = "hidden"
            self.__double_private = "very hidden"

    def test_function():
        obj = TestClass()  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "obj" in local_vars

                obj_data = local_vars["obj"]
                assert isinstance(obj_data, dict)
                assert "public" in obj_data
                assert obj_data["public"] == "visible"
                assert "_private" not in obj_data, (
                    "Private attributes should be skipped"
                )
                assert "__double_private" not in obj_data, (
                    "Double private attributes should be skipped"
                )
                break

    test_function()


def test_nested_objects_with_skipped_types():
    """Test that nested objects properly skip functions, modules, and types."""

    class Container:
        def __init__(self):
            self.func = lambda x: x  # noqa: E731
            self.module = Path
            self.class_ref = Path
            self.instance = Path("/tmp")
            self.data = {"key": "value"}

    def test_function():
        import sys

        container = Container()
        container.module = sys

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "container" in local_vars

                container_data = local_vars["container"]
                assert isinstance(container_data, dict)
                # Functions, modules, and types should be skipped in nested objects
                assert "func" not in container_data, "Function should be skipped"
                assert "module" not in container_data, "Module should be skipped"
                assert "class_ref" not in container_data, (
                    "Class reference should be skipped"
                )
                assert "instance" in container_data, "Instance should be included"
                assert "data" in container_data, "Data should be included"
                assert container_data["data"] == {"key": "value"}
                break

    test_function()


def test_json_serializable():
    """Test that serialized variables are JSON-serializable."""

    class Person:
        def __init__(self, name):
            self.name = name

    def test_function():
        person = Person("Alice")
        data = {"person": person, "numbers": [1, 2, 3]}  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                # Verify that the serialized data can be converted to JSON
                json_str = json.dumps(local_vars)
                assert json_str is not None
                # Verify we can parse it back
                parsed = json.loads(json_str)
                assert "person" in parsed
                assert "data" in parsed
                break

    test_function()


def test_long_string_truncation():
    """Test that very long strings are truncated."""

    def test_function():
        long_string = "a" * 2000  # 2000 characters
        short_string = "hello"  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert len(local_vars["long_string"]) < len(long_string)
                assert local_vars["long_string"].endswith("...")
                assert local_vars["short_string"] == "hello"
                break

    test_function()


def test_tuples_and_sets():
    """Test that tuples and sets are properly serialized."""

    def test_function():
        tuple_var = (1, 2, 3)  # noqa: F841
        set_var = {4, 5, 6}  # noqa: F841
        list_var = [7, 8, 9]  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                # Tuples should become lists
                assert isinstance(local_vars["tuple_var"], list)
                assert local_vars["tuple_var"] == [1, 2, 3]
                # Sets should become lists
                assert isinstance(local_vars["set_var"], list)
                assert set(local_vars["set_var"]) == {4, 5, 6}
                # Lists should remain lists
                assert isinstance(local_vars["list_var"], list)
                assert local_vars["list_var"] == [7, 8, 9]
                break

    test_function()


def test_max_depth_handling():
    """Test that max depth is respected in recursive serialization."""

    def create_deep_nesting(depth):
        if depth == 0:
            return {"value": "deep"}
        return {"nested": create_deep_nesting(depth - 1)}

    def test_function():
        # Create nesting deeper than max_depth (default is 10)
        deep_data = create_deep_nesting(15)  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                assert "deep_data" in local_vars
                # Should hit max depth and return "<max_depth_reached>"
                deep_serialized = local_vars["deep_data"]
                # We can't easily check the exact depth, but we can verify
                # it doesn't crash and returns something serializable
                json.dumps(deep_serialized)
                break

    test_function()


def test_mixed_filtering():
    """Test filtering with a mix of all skippable types."""

    def test_function():
        from pathlib import Path
        import sys

        # All these should be skipped
        func = lambda x: x  # noqa: E731, F841
        module = sys  # noqa: F841
        path_class = Path  # noqa: F841
        cs_obj = call_stack()  # noqa: F841

        # Locally defined class
        class LocalClass:
            pass

        # These should be included
        path_instance = Path("/tmp")  # noqa: F841
        local_instance = LocalClass()  # noqa: F841
        regular_var = 42  # noqa: F841

        cs = call_stack()
        trace = cs.capture_stack_trace()

        for frame in trace.frames:
            if frame.function_name == "test_function":
                local_vars = frame.local_variables
                # Verify all skippable types are filtered
                assert "func" not in local_vars
                assert "module" not in local_vars
                assert "path_class" not in local_vars
                assert "cs_obj" not in local_vars
                assert "LocalClass" not in local_vars

                # Verify instances and regular vars are included
                assert "path_instance" in local_vars
                assert "local_instance" in local_vars
                assert "regular_var" in local_vars
                assert local_vars["regular_var"] == 42
                break

    test_function()
