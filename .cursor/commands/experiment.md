# Experiment Command

When the user invokes `/experiment`, create a new experiment file in the `experiments/` directory.

## Steps

1. Ask the user for the experiment name (e.g., "test_feature" or "validate_behavior")
2. Ask the user for the experiment purpose (1-2 sentences describing what they're trying to figure out)
3. Create a new Python file at `experiments/<experiment_name>.py` with the following structure:

```python
# Purpose: [User's purpose description]
#
# Conclusion: [To be filled in after running the experiment]

import inspect

if __name__ == "__main__":
    pass
```

4. If the file already exists, ask the user if they want to overwrite it
5. After creating the file, inform the user they can run it with:
   ```bash
   uv run python -m experiments.<experiment_name>
   ```

## Notes

- Use `import inspect` as the default import (user can add others as needed)
- The Conclusion field should be left as a placeholder for the user to fill in after running the experiment
- Ensure the experiment name is a valid Python filename (no spaces, use underscores)
