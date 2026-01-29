# autopsy
Debug your code, in your code!

Autopsy is based on a few simple ideas:
1. Debugging should be done _within_ your code
2. Debugging outputs deserve a dedicated interface for viewing and comprehension

Autopsy gives you all of the access of a breakpoint debugger, with the 

## Getting Started
```py
from autopsy import report, call_stack

def my_func():
    # Aggregate the set of all functions that call my_func
    # and add them to an output report section called "my_func callers"
    report.set(call_stack().caller, name="my_func callers")
    report.count(name="my_func called times")
    pass

def main():
    for _ in range(10):
        my_func()

if __name__ == "__main__":
    report.init() # See below for report configuration
    main()
    report.finish() # Output to autopsy.html by default

```

## Report Configuration
`report.init()` takes an optional configuration object that allows you to tailor the output to your needs.

| Option         | Type          | Default        | Description                 |
| -------------- | ------------- | -------------- | --------------------------- |
| log_to_console | bool          | False          | If True, log to the console |
| output_file    | Optional[str] | ./autopsy.html | If None, do not produce a file. Otherwise, write the report to the target path. |

## Recipes
### Save objects for querying
```py
def my_func(user_id):
    some_obj = Users.get(user_id)
    # When viewing the report, we'll be able to query this collection interactively
    report.log(user_id, some_obj)
```

### Filter call stacks
```py
from other_module import calls_my_func

def my_func():
    if call_stack.caller.is(calls_my_func):
        report.log("Called by calls_my_func")
```

### Retrieve variables from other scopes
```py
from other_module import calls_my_func

def my_func():
    report.log(call_stack.find_caller(calls_my_func).variable("computed_before")))
```

### Compose report items
```py
with report.section(name="all groups") as groups_report:
    for group in all_groups:
        with groups_report.log(name=f"group {group.name}") as group_report:
            for member in group:
                group_report.log(member.id, member.name, name=f"member")
```

## Pytest Integration
Add the following to `pyproject.toml`:
```toml
[project.entry-points.pytest11]
autopsy = "autopsy.pytest"
```