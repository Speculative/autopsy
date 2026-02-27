# Running Code
- Always manage python dependencies and run python code using `uv run`.
- This project structures all imports to use absolute path modules starting from
  the repo root, e.g., `report` is at `import autopsy.report`.

# Using Autopsy's report.log()
- `report.log()` is a **variadic function** that takes multiple positional arguments, NOT keyword arguments.
- Each argument becomes a separate column in the streams view.
- If the first argument is a string literal, it's treated specially as a message/label.
- Examples:
  - `report.log("value1", "value2", "value3")` - creates 3 columns
  - `report.log("Processed item", item)` - "Processed item" is the message, item is the data
  - INCORRECT: `report.log(col1="value1", col2="value2")` - keyword args not supported
  - INCORRECT: `report.log({"col1": "value1", "col2": "value2"})` - creates one column with a dict
- For structured data (objects/dicts/lists), create a named variable first, then pass it:
  ```python
  result = {"key": "value", "count": 42}
  report.log("Processing result", result)  # Message + object as data
  ```