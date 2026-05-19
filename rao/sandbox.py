import sys
import traceback
import io
import asyncio
from typing import Any, Dict, Optional

class AsyncREPLSandbox:
    """
    An isolated, asynchronous in-memory Python REPL execution sandbox.
    Allows language models to execute code blocks containing async control flow
    (like await asyncio.gather or await launch_subagent) and captures stdout/exceptions.
    """
    def __init__(self, globals_dict: Optional[Dict[str, Any]] = None):
        import builtins
        # Heavy-duty restriction of globals for safety in prototype
        self.globals = {
            "__builtins__": builtins.__dict__.copy(),
            "asyncio": asyncio,
        }
        if globals_dict:
            self.globals.update(globals_dict)
            
        self.globals_init = set(self.globals.keys())
        
    async def execute_async(self, code_str: str) -> str:
        """
        Executes a string of code containing optional asynchronous constructs.
        Captures and returns the standard output.
        """
        # Parse the block and clean whitespace/formatting
        code_str = code_str.strip()
        if not code_str:
            return "Empty code block."

        # Parse variables to declare them as global inside the wrapper function
        top_names = []
        try:
            import ast
            tree = ast.parse(code_str)
            for node in tree.body:
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name):
                            top_names.append(target.id)
                        elif isinstance(target, (ast.Tuple, ast.List)):
                            for elt in target.elts:
                                if isinstance(elt, ast.Name):
                                    top_names.append(elt.id)
                elif isinstance(node, ast.AnnAssign):
                    if isinstance(node.target, ast.Name):
                        top_names.append(node.target.id)
                elif isinstance(node, ast.AugAssign):
                    if isinstance(node.target, ast.Name):
                        top_names.append(node.target.id)
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        top_names.append(alias.asname or alias.name)
                elif isinstance(node, ast.ImportFrom):
                    for alias in node.names:
                        top_names.append(alias.asname or alias.name)
                elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    top_names.append(node.name)
                elif isinstance(node, ast.ClassDef):
                    top_names.append(node.name)
        except Exception:
            # If ast parsing fails (e.g. syntax error in raw code), exec will throw it, which we catch.
            pass

        global_decl = ""
        if top_names:
            # filter out duplicates
            unique_names = list(dict.fromkeys(top_names))
            global_decl = "    global " + ", ".join(unique_names) + "\n"
        
        # We wrap the code inside an async function template so we can use await at the top level
        # safely and execute it asynchronously.
        indented = "\n".join("    " + line for line in code_str.splitlines())
        wrapper = f"async def _run_sandbox_code():\n{global_decl}{indented}\n"
        
        stdout_capture = io.StringIO()
        original_stdout = sys.stdout
        
        try:
            # Execute definition in globals
            exec(wrapper, self.globals)
            
            # Retrieve the created async function object
            run_func = self.globals.get("_run_sandbox_code")
            if not run_func:
                return "Error: Could not compile executable block."
                
            # Intercept stdout during execution
            sys.stdout = stdout_capture
            
            # Execute the compiled async function in the current running event loop
            await run_func()
            
            # Recover execution output
            output = stdout_capture.getvalue()
            return output if output else "Code executed successfully with no output."
            
        except Exception as e:
            # Capture the traceback nicely and format it for the agent context
            sys.stdout = original_stdout
            tb = traceback.format_exc()
            return f"Runtime Exception:\n{tb}"
            
        finally:
            sys.stdout = original_stdout
            stdout_capture.close()
            # Clean up the run wrapper function to avoid polluting namespace
            self.globals.pop("_run_sandbox_code", None)
