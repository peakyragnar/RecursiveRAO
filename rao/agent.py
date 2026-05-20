import os
import re
import asyncio
import google.generativeai as genai
from typing import Any, Dict, List, Optional
from rao.sandbox import AsyncREPLSandbox
from rao.engine import TreeNode, ExecutionTree
from rao.environments.base import BaseEnvironment

class RecursiveAgent:
    """
    Coordinates execution of a single agent instance, parsing thought/python blocks
    and evaluating them within the asynchronous sandbox. Supports both live Google Gemini
    execution (if GEMINI_API_KEY is present) and deterministic simulated execution.
    """
    # Class-level token and cost tracking for live runs
    total_input_tokens = 0
    total_output_tokens = 0
    total_cost = 0.0

    def __init__(self, env: BaseEnvironment):
        self.env = env
        self.api_key = os.environ.get("GEMINI_API_KEY")
        if self.api_key:
            genai.configure(api_key=self.api_key)
            
    async def run_node(self, node: TreeNode, tree: ExecutionTree) -> Any:
        """
        Executes the agent logic at a specific node in the tree.
        Exposes environmental actions inside a fresh, isolated REPL sandbox.
        """
        # Create a clean execution environment
        actions = self.env.get_actions(node.node_id, tree)
        
        # Inject standard financial analysis tools
        import pandas as pd
        import numpy as np
        from bs4 import BeautifulSoup
        import io
        
        sandbox_globals = {
            "pd": pd,
            "pandas": pd,
            "np": np,
            "numpy": np,
            "BeautifulSoup": BeautifulSoup,
            "io": io,
        }
        sandbox_globals.update(actions)
        
        sandbox = AsyncREPLSandbox(globals_dict=sandbox_globals)
        
        # We pre-load context data if available
        if node.context_data is not None:
            sandbox.globals["context"] = node.context_data
            
        print(f"\n🚀 Spawning Agent Node [{node.node_id}] | Depth {node.depth} | Goal: '{node.goal}'")
        
        # Check if we are running in Live Mode or Simulated Mode
        if self.api_key:
            # --- Live Mode: Run the real LLM Agent loop ---
            await self._run_live_loop(node, tree, sandbox)
        else:
            # --- Simulated Mode: Run the mock generation ---
            simulated_generation = self.generate_simulated_code(node, tree)
            for step in simulated_generation:
                thought = step.get("thought", "")
                code = step.get("code", "")
                
                stdout = await sandbox.execute_async(code)
                node.trajectory.append({
                    "thought": thought,
                    "code": code,
                    "output": stdout
                })
                
        # Verify success score at node finish
        node.success_score = self.env.verify_node(node.node_id, node.finished_message, tree)
        print(f"✅ Node [{node.node_id}] finished. Success Score: {node.success_score:.2f}")
        return node.finished_message

    async def _run_live_loop(self, node: TreeNode, tree: ExecutionTree, sandbox: AsyncREPLSandbox):
        """
        Runs the live agent loop powered by Google Gemini.
        Iteratively prompts the model, executes generated code inside the sandbox,
        and feeds the outputs back until finish() is called or step limit is reached.
        """
        # Select model: use pro for root, flash for children
        model_name = "gemini-2.5-pro" if node.depth == 0 else "gemini-2.5-flash"
        model = genai.GenerativeModel(model_name)
        
        max_steps = 6
        step_idx = 0
        
        while step_idx < max_steps:
            step_idx += 1
            
            # Format system prompt and current history
            system_prompt = self._get_system_prompt(sandbox)
            user_prompt = self._get_user_prompt(node, step_idx, max_steps)
            
            # Request response from model
            try:
                # Run the model call inside asyncio's executor to avoid blocking the main loop
                loop = asyncio.get_event_loop()
                response = await loop.run_in_executor(
                    None,
                    lambda: model.generate_content(
                        contents=f"{system_prompt}\n\n{user_prompt}",
                        generation_config={"temperature": 0.1}
                    )
                )
                response_text = response.text
                
                # Dynamic Token and Cost Tracking
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    prompt_tokens = getattr(usage, "prompt_token_count", 0)
                    candidates_tokens = getattr(usage, "candidates_token_count", 0)
                    total_tokens = getattr(usage, "total_token_count", 0)
                    
                    # Calculate cost based on model
                    if model_name == "gemini-2.5-pro":
                        input_cost = (prompt_tokens / 1_000_000.0) * 1.25
                        output_cost = (candidates_tokens / 1_000_000.0) * 10.00
                    else:
                        input_cost = (prompt_tokens / 1_000_000.0) * 0.30
                        output_cost = (candidates_tokens / 1_000_000.0) * 2.50
                        
                    step_cost = input_cost + output_cost
                    
                    RecursiveAgent.total_input_tokens += prompt_tokens
                    RecursiveAgent.total_output_tokens += candidates_tokens
                    RecursiveAgent.total_cost += step_cost
                    
                    print(f"    📊 Tokens - In: {prompt_tokens} | Out: {candidates_tokens} | Total: {total_tokens}")
                    print(f"    💰 Step Cost: ${step_cost:.5f} | Run Cumulative Cost: ${RecursiveAgent.total_cost:.5f}")
            except Exception as e:
                error_msg = f"LLM Generation Exception: {str(e)}"
                print(f"❌ Node [{node.node_id}]: {error_msg}")
                node.trajectory.append({
                    "thought": "Failed to query Gemini API.",
                    "code": "",
                    "output": error_msg
                })
                break
                
            # Parse thought and code block
            thought, code = self._parse_llm_response(response_text)
            
            print(f"  🧠 Node [{node.node_id}] Thought Step {step_idx}: {thought[:80]}...")
            
            if not code:
                # If no code block is found, report a syntax error in sandbox
                stdout = "Error: No python code block found. Please wrap your Python code in a markdown block."
            else:
                # Execute python block asynchronously in the stateful sandbox
                stdout = await sandbox.execute_async(code)
                
            # Log step in trajectory
            node.trajectory.append({
                "thought": thought,
                "code": code,
                "output": stdout
            })
            
            # Check if finish was successfully invoked
            if node.finished_message is not None:
                print(f"  🏁 Node [{node.node_id}] called finish() successfully.")
                break
                
            # Prevent infinite loops if sandbox returns repeated errors
            if "Runtime Exception:" in stdout and step_idx >= max_steps - 1:
                print(f"  ⚠️ Node [{node.node_id}] reached limit with unresolved errors.")
                break

    def _get_system_prompt(self, sandbox: AsyncREPLSandbox) -> str:
        # Document the available local variables and functions in the sandbox
        available_tools = []
        for key, val in sandbox.globals.items():
            if key.startswith("_") or key in ["asyncio", "numpy", "pandas", "BeautifulSoup"]:
                continue
            available_tools.append(f"  • {key} (type: {type(val).__name__})")
            
        tools_str = "\n".join(available_tools)
        
        return f"""You are an expert financial analyst agent working in an interactive stateful Python REPL shell to extract and reconcile quarterly financial statements and segment/market platform details.

Your role is to write clean, programmatic Python code to load SEC filings, parse HTML tables using pandas and BeautifulSoup, verify calculations, and mathematically reconcile restatements.

### Execution Protocol:
In each step, you must output exactly two parts:
1. **Thought**: Explain your reasoning, planned calculations, or delegation strategies.
2. **Python Block**: A markdown code block containing valid Python code to execute.

Example Format:
Thought: I need to fetch the manifest of filings to locate NVDA 10-K and 10-Q reports.
```python
list_of_files = get_filings_list()
print(f"Loaded {{len(list_of_files)}} filings.")
```

 ### Critical Rules:
1. **REPL Sandbox Statefulness**: The sandbox is stateful. Variables assigned in one step persist to subsequent steps. Do not re-define functions or variables unless necessary.
2. **Standard Libraries**: You have `pandas` (as `pd`), `numpy` (as `np`), `BeautifulSoup`, and `io` pre-injected into your global namespace.
3. **Synchronous vs Asynchronous APIs**: 
   - `get_segment_note(date_or_name: str)` and `get_mda_section(date_or_name: str)` are **SYNCHRONOUS** functions. Do NOT use `await` with them; call them directly, e.g. `html_str = get_segment_note('2024-01-28')`.
   - `launch_subagent(goal: str, context: Any)` is **ASYNCHRONOUS**. You MUST use `await` with it, e.g. `result = await launch_subagent(goal, context)`. It takes EXACTLY 2 arguments. Do NOT pass a third argument. You can use `asyncio.gather` for parallel subagent executions.
4. **Completion**: When you have successfully extracted and reconciled the required figures, you MUST conclude by calling:
   `finish(result_data)`
   where `result_data` is your final structured output (dict or list). The loop will not end until you call `finish()`.

### Critical Pandas 2.0+ HTML Parsing Rule:
When using `pd.read_html(html_str)` inside the sandbox, you MUST wrap the HTML string in `io.StringIO` to prevent path/URL parsing errors.
Example:
```python
import io
df = pd.read_html(io.StringIO(html_str))[0]
```

### Available Local APIs & Tools:
{tools_str}
"""

    def _get_user_prompt(self, node: TreeNode, step_idx: int, max_steps: int) -> str:
        # Render trajectory steps
        trajectory_str = ""
        for idx, step in enumerate(node.trajectory):
            trajectory_str += f"\n--- Step {idx+1} ---\n"
            trajectory_str += f"Thought: {step['thought']}\n"
            trajectory_str += f"Code:\n```python\n{step['code']}\n```\n"
            trajectory_str += f"Execution Output:\n{step['output']}\n"
            
        context_str = f"Isolated Context Data:\n{str(node.context_data)[:1000]}" if node.context_data else "None"
        
        return f"""### Current System State:
- **Node ID**: {node.node_id}
- **Current Depth**: {node.depth}
- **Current Goal**: {node.goal}
- **Step Count**: {step_idx} of {max_steps}
- **Isolated Input Context**:
{context_str}

### Trajectory History inside this Node:
{trajectory_str if trajectory_str else "No steps executed yet."}

### Instruction:
Analyze the history and outputs. Write the next Thought and Python Block to advance the goal. 
If you are finished, write a Python block that computes your final result and calls `finish()`.
"""

    def _parse_llm_response(self, text: str) -> tuple[str, str]:
        # Parse thought
        thought_match = re.search(r"Thought:\s*(.*?)(?=Python Block:|```python|Code:|$)", text, re.DOTALL | re.IGNORECASE)
        thought = thought_match.group(1).strip() if thought_match else "Analyzing next steps."
        
        # Parse code block
        code_match = re.search(r"```python\s*(.*?)\s*```", text, re.DOTALL | re.IGNORECASE)
        code = code_match.group(1).strip() if code_match else ""
        
        return thought, code

    def generate_simulated_code(self, node: TreeNode, tree: ExecutionTree) -> List[Dict[str, str]]:
        """
        Generates simulated reasoning and Python code outputs conforming to a trained policy.
        Allows testing of deep recursive execution trees deterministically.
        """
        if node.node_id == tree.root_node.node_id and "m3_i1" in node.goal:
            return [
                {
                    "thought": "I need to craft m3_i1. Let me check the recipe and determine intermediate dependencies.",
                    "code": "info = get_info(['m3_i1'])\nprint(f'Recipe info: {info}')"
                },
                {
                    "thought": "m3_i1 requires m2_i1 (1) and m2_i2 (2). I will launch parallel subagents to craft these targets concurrently.",
                    "code": """
import asyncio
t1 = launch_subagent({"m2_i1": 1}, 20)
t2 = launch_subagent({"m2_i2": 2}, 20)
results = await asyncio.gather(t1, t2)
print(f'Subagents spawned successfully: {results}')
"""
                },
                {
                    "thought": "Now that the subagents have crafted the dependencies, I will proceed to craft the target item and finish.",
                    "code": "craft({'m2_i1': 1, 'm2_i2': 2}, ('m3_i1', 1))\nfinish('Successfully crafted target m3_i1.')"
                }
            ]
            
        if node.node_id == tree.root_node.node_id and "segment" in node.goal.lower():
            return [
                {
                    "thought": "I need to perform mathematical reconciliation of segment data. I will launch children to parse Item 7, Note 3, and Note 14 concurrently.",
                    "code": """
import asyncio
t1 = launch_subagent("Extract Item 7 main tables", get_chunk(1))
t2 = launch_subagent("Extract Note 3 discontinued items", get_chunk(8))
t3 = launch_subagent("Extract Note 14 reorganizations", get_chunk(12))
results = await asyncio.gather(t1, t2, t3)
print(f'Subagent details returned: Segment, Footnote, and Reorg tables collected.')
"""
                },
                {
                    "thought": "With all child data payloads returned, I will reconcile the calculations inside my REPL block.",
                    "code": """
reconciled = {
    "Intelligent Systems": {
        "2023": {"organic_revenue_usd_m": 450.0 + 40.0, "operating_margin": round(105.0 / (450.0 + 40.0), 3)},
        "2024": {"organic_revenue_usd_m": 520.0 + 45.0, "operating_margin": round(128.0 / (520.0 + 45.0), 3)},
        "2025": {"organic_revenue_usd_m": 680.0, "operating_margin": round(156.0 / 680.0, 3)}
    },
    "Consumer Devices": {
        "2023": {"organic_revenue_usd_m": 210.0 - 40.0, "operating_margin": round((21.0 - 5.0) / (210.0 - 40.0), 3)},
        "2024": {"organic_revenue_usd_m": 230.0 - 45.0, "operating_margin": round((25.0 - 7.0) / (230.0 - 45.0), 3)},
        "2025": {"organic_revenue_usd_m": 190.0, "operating_margin": round(15.0 / 190.0, 3)}
    }
}
finish(reconciled)
"""
                }
            ]
            
        return [
            {
                "thought": "Solving task directly without child delegation.",
                "code": "finish('Completed task successfully.')"
            }
        ]
