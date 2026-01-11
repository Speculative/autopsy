# Purpose: Test if pickling/unpickling works on custom classes in an isolated
# Python environment where the original class definition isn't accessible.
# Can pickled objects be unpickled without importing the corresponding class?
# If not, can we at least extract the attributes as a POPO even if methods aren't available?
#
# Conclusion:
# 1. Direct unpickling FAILS without the class definition - pickle needs to import
#    the original class and will raise AttributeError if it can't find it.
#
# 2. The pickle format DOES contain all instance attributes as plain data - visible
#    in the pickle disassembly showing 'name', 'value', and 'computed' as BINUNICODE
#    strings and their values.
#
# 3. SUCCESS: By subclassing pickle.Unpickler and overriding find_class(), we can
#    intercept class loading and substitute a dummy/generic class. The pickle
#    protocol then populates the dummy object's __dict__ with all the original
#    attributes via __setstate__.
#
# 4. This means we CAN extract pickled object attributes as a POPO (Plain Old Python
#    Object) even without access to the original class definition. All instance data
#    is preserved and accessible, though methods and class-level behavior are lost.
#
# 5. This technique is useful for:
#    - Inspecting pickled data from external/unavailable codebases
#    - Extracting data from legacy pickle files where classes have changed
#    - Creating "read-only" views of pickled objects without their behavior
#    - Debugging and data recovery scenarios

import inspect
import pickle
import subprocess
import sys
import tempfile
from pathlib import Path


# Define a custom class with attributes and methods
class MyCustomClass:
    def __init__(self, name, value):
        self.name = name
        self.value = value
        self.computed = value * 2

    def get_info(self):
        return f"{self.name}: {self.value}"

    def __repr__(self):
        return f"MyCustomClass(name={self.name!r}, value={self.value})"


def test_direct_unpickle():
    """Test 1: Try to unpickle directly without class definition"""
    print("=" * 60)
    print("Test 1: Direct unpickle without class definition")
    print("=" * 60)

    # Create and pickle an instance
    obj = MyCustomClass("test", 42)
    pickled = pickle.dumps(obj)
    print(f"Original object: {obj}")
    print(f"Pickled size: {len(pickled)} bytes")

    # Try to unpickle in subprocess without class definition
    code = '''
import pickle
import sys

pickled_data = sys.stdin.buffer.read()
try:
    obj = pickle.loads(pickled_data)
    print(f"SUCCESS: Unpickled object: {obj}")
    print(f"Type: {type(obj)}")
    print(f"Attributes: {vars(obj)}")
except Exception as e:
    print(f"FAILED: {type(e).__name__}: {e}")
'''

    result = subprocess.run(
        [sys.executable, "-c", code],
        input=pickled,
        capture_output=True,
    )
    print(result.stdout.decode())
    if result.stderr:
        print("STDERR:", result.stderr.decode())


def test_pickle_module_inspection():
    """Test 2: Inspect pickle structure to extract attributes"""
    print("\n" + "=" * 60)
    print("Test 2: Inspect pickle structure")
    print("=" * 60)

    obj = MyCustomClass("test", 42)
    pickled = pickle.dumps(obj)

    # Use pickletools to disassemble
    import pickletools
    print("\nPickle disassembly:")
    pickletools.dis(pickled)


def test_attribute_extraction():
    """Test 3: Try to extract just the __dict__ as a plain dict"""
    print("\n" + "=" * 60)
    print("Test 3: Extract attributes without class")
    print("=" * 60)

    obj = MyCustomClass("test", 42)
    pickled = pickle.dumps(obj)

    # Try using pickle's internals to extract the state
    code = '''
import pickle
import sys
import io

captured_data = {}

class CustomUnpickler(pickle.Unpickler):
    """Subclass Unpickler to override find_class"""
    def find_class(self, module, name):
        """Intercept class loading"""
        captured_data['module'] = module
        captured_data['class'] = name

        # Return a dummy class that captures the state
        class DummyClass:
            def __setstate__(self, state):
                captured_data['state'] = state
                self.__dict__.update(state if isinstance(state, dict) else {})

        return DummyClass

pickled_data = sys.stdin.buffer.read()

try:
    unpickler = CustomUnpickler(io.BytesIO(pickled_data))
    obj = unpickler.load()

    print(f"Captured class: {captured_data.get('module')}.{captured_data.get('class')}")
    print(f"Extracted state: {captured_data.get('state')}")
    print(f"Object __dict__: {obj.__dict__}")
    print(f"\\nSUCCESS: Extracted attributes as POPO")
except Exception as e:
    import traceback
    print(f"FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
'''

    result = subprocess.run(
        [sys.executable, "-c", code],
        input=pickled,
        capture_output=True,
    )
    print(result.stdout.decode())
    if result.stderr:
        print("STDERR:", result.stderr.decode())


def test_custom_unpickler():
    """Test 4: Use a custom unpickler to intercept and extract data"""
    print("\n" + "=" * 60)
    print("Test 4: Custom unpickler with generic object wrapper")
    print("=" * 60)

    obj = MyCustomClass("test", 42)
    pickled = pickle.dumps(obj)

    code = '''
import pickle
import sys
import io

class GenericObject:
    """A generic object that can hold any attributes"""
    _class_info = None

    def __repr__(self):
        attrs = {k: v for k, v in self.__dict__.items() if not k.startswith('_')}
        return f"GenericObject({self._class_info}, {attrs})"

class ExtractingUnpickler(pickle.Unpickler):
    """Custom unpickler that converts all objects to GenericObject"""
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._class_info_cache = {}

    def find_class(self, module, name):
        """Replace any class with our generic object"""
        class_key = f"{module}.{name}"
        # Create a dynamic class that inherits from GenericObject
        class DynamicGeneric(GenericObject):
            _class_info = class_key
        return DynamicGeneric

pickled_data = sys.stdin.buffer.read()

try:
    unpickler = ExtractingUnpickler(io.BytesIO(pickled_data))
    obj = unpickler.load()

    print(f"Object type: {type(obj)}")
    print(f"Original class: {obj._class_info}")
    print(f"Extracted attributes: {dict((k, v) for k, v in obj.__dict__.items() if not k.startswith('_'))}")
    print(f"\\nSUCCESS: Converted pickled object to plain dict-like object")
    print(f"Can access attributes: name={getattr(obj, 'name', 'N/A')}, value={getattr(obj, 'value', 'N/A')}, computed={getattr(obj, 'computed', 'N/A')}")
except Exception as e:
    import traceback
    print(f"FAILED: {type(e).__name__}: {e}")
    traceback.print_exc()
'''

    result = subprocess.run(
        [sys.executable, "-c", code],
        input=pickled,
        capture_output=True,
    )
    print(result.stdout.decode())
    if result.stderr:
        print("STDERR:", result.stderr.decode())


if __name__ == "__main__":
    test_direct_unpickle()
    test_pickle_module_inspection()
    test_attribute_extraction()
    test_custom_unpickler()

    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    print("Fill in the Conclusion section at the top of this file")
    print("with your findings about pickle behavior in isolated environments.")
