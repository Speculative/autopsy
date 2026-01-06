/**
 * Generic Python executor using Pyodide
 * Loads Pyodide from CDN and provides batch execution capabilities for Python code
 */

export interface PythonExecutionResult {
  value: unknown;
  error?: string;
}

export interface PythonExecutor {
  initialize(): Promise<void>;
  executeBatch<T>(
    userCode: string,
    dataItems: T[],
    variableName: string
  ): Promise<PythonExecutionResult[]>;
  isReady(): boolean;
  getStatus(): 'uninitialized' | 'loading' | 'ready' | 'error';
}

class PythonExecutorImpl implements PythonExecutor {
  private pyodide: any = null;
  private status: 'uninitialized' | 'loading' | 'ready' | 'error' = 'uninitialized';
  private loadingPromise: Promise<void> | null = null;

  async initialize(): Promise<void> {
    if (this.status === 'ready') return;
    if (this.loadingPromise) return this.loadingPromise;

    this.status = 'loading';
    this.loadingPromise = this.loadPyodide();

    try {
      await this.loadingPromise;
      this.status = 'ready';
    } catch (error) {
      this.status = 'error';
      throw error;
    }
  }

  private async loadPyodide(): Promise<void> {
    // Load Pyodide script from CDN
    const script = document.createElement('script');
    script.src = 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/pyodide.js';
    document.head.appendChild(script);

    await new Promise<void>((resolve, reject) => {
      script.onload = () => resolve();
      script.onerror = () => reject(new Error('Failed to load Pyodide'));
    });

    // Initialize Pyodide
    this.pyodide = await (window as any).loadPyodide({
      indexURL: 'https://cdn.jsdelivr.net/pyodide/v0.25.0/full/'
    });
  }

  async executeBatch<T>(
    userCode: string,
    dataItems: T[],
    variableName: string
  ): Promise<PythonExecutionResult[]> {
    if (!this.pyodide) {
      throw new Error('Pyodide not initialized');
    }

    // Indent user code for function body
    const indentedCode = this.indentCode(userCode);

    // Serialize data items
    const dataJson = JSON.stringify(dataItems);

    // Build Python code with function wrapper and batch evaluation
    // We need to handle the last line specially - if it's an expression,
    // we want to return it automatically
    const pythonCode = `
import json

# Parse input data
__data_items = json.loads('''${this.escapeString(dataJson)}''')

# User code will be executed in a way that the last expression is returned
# We'll wrap it in eval() to capture the last expression's value
def __autopsy_eval_fn(${variableName}):
${indentedCode}

# Execute batch
__results = []
for __item in __data_items:
    try:
        if __item is None:
            __results.append({'value': None, 'error': None})
        else:
            __result = __autopsy_eval_fn(__item)
            __results.append({'value': __result, 'error': None})
    except Exception as __e:
        __results.append({'value': None, 'error': type(__e).__name__})

# Return results
__results
`;

    try {
      // Execute Python code - returns the Python list directly
      const resultsPy = await this.pyodide.runPythonAsync(pythonCode);

      // Convert Python object to JavaScript
      const resultsJs = resultsPy.toJs({ dict_converter: Object.fromEntries });

      // Convert to PythonExecutionResult format
      return Array.from(resultsJs).map((r: any) => ({
        value: r.value,
        error: r.error || undefined
      }));
    } catch (error) {
      // Syntax error or other global error - return error for all items
      const errorName = error instanceof Error ? error.name : 'Error';
      return dataItems.map(() => ({ value: undefined, error: errorName }));
    }
  }

  private indentCode(code: string): string {
    const lines = code.split('\n');

    // Find the last non-empty, non-comment line
    let lastLineIndex = -1;
    for (let i = lines.length - 1; i >= 0; i--) {
      const trimmed = lines[i].trim();
      if (trimmed && !trimmed.startsWith('#')) {
        lastLineIndex = i;
        break;
      }
    }

    // If we found a last line and it doesn't start with return/raise/pass/break/continue
    if (lastLineIndex >= 0) {
      const lastLine = lines[lastLineIndex];
      const trimmed = lastLine.trim();
      if (!trimmed.match(/^(return|raise|pass|break|continue|if|for|while|def|class|try|except|finally|with)\b/)) {
        // Prepend 'return ' to the last line, preserving indentation
        const indent = lastLine.match(/^\s*/)?.[0] || '';
        lines[lastLineIndex] = indent + 'return ' + trimmed;
      }
    }

    // Add 4-space indentation to each line
    return lines
      .map(line => line.length > 0 ? `    ${line}` : line)
      .join('\n');
  }

  private escapeString(str: string): string {
    // Escape backslashes and triple quotes for triple-quoted string
    return str.replace(/\\/g, '\\\\').replace(/'''/g, "\\'\\'\\'");
  }

  isReady(): boolean {
    return this.status === 'ready';
  }

  getStatus() {
    return this.status;
  }
}

// Export singleton instance
export const pythonExecutor: PythonExecutor = new PythonExecutorImpl();
