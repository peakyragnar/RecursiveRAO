from typing import Any, Dict, List, Optional
import re
from rao.sandbox import AsyncREPLSandbox
from rao.engine import TreeNode, ExecutionTree
from rao.environments.base import BaseEnvironment

class RecursiveAgent:
    """
    Coordinates execution of a single agent instance, parsing thought/python blocks
    and evaluating them within the asynchronous sandbox.
    """
    def __init__(self, env: BaseEnvironment):
        self.env = env
        
    async def run_node(self, node: TreeNode, tree: ExecutionTree) -> Any:
        """
        Executes the agent logic at a specific node in the tree.
        Exposes environmental actions inside a fresh, isolated REPL sandbox.
        """
        # Create a clean execution environment
        actions = self.env.get_actions(node.node_id, tree)
        sandbox = AsyncREPLSandbox(globals_dict=actions)
        
        # We pre-load context data if available (e.g. Oolong-Real document context)
        if node.context_data is not None:
            sandbox.globals["context"] = node.context_data
            
        # Get simulated generation (thought + python blocks) conforming to the task type
        simulated_generation = self.generate_simulated_code(node, tree)
        
        # Record trajectory steps
        for step in simulated_generation:
            thought = step.get("thought", "")
            code = step.get("code", "")
            
            # Execute python block asynchronously in sandbox
            stdout = await sandbox.execute_async(code)
            
            node.trajectory.append({
                "thought": thought,
                "code": code,
                "output": stdout
            })
            
        # Verify success score at node finish
        node.success_score = self.env.verify_node(node.node_id, node.finished_message, tree)
        return node.finished_message

    def generate_simulated_code(self, node: TreeNode, tree: ExecutionTree) -> List[Dict[str, str]]:
        """
        Generates simulated reasoning and Python code outputs conforming to a trained policy.
        Allows testing of deep recursive execution trees deterministically.
        """
        # --- TextCraft-Synth Root Agent Strategy ---
        if node.node_id == tree.root_node.node_id and "m3_i1" in node.goal:
            return [
                {
                    "thought": "I need to craft m3_i1. Let me check the recipe and determine intermediate dependencies.",
                    "code": "info = get_info(['m3_i1'])\nprint(f'Recipe info: {info}')"
                },
                {
                    "thought": "m3_i1 requires m2_i1 (1) and m2_i2 (2). I will launch parallel subagents to craft these targets concurrently.",
                    "code": """
# Parallel subagent execution using asyncio
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
            
        # --- SEC HTML Extraction Root Agent Strategy ---
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
# Perform organic segment revenue and margin calculations programmatically
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
            
        # Default fallback
        return [
            {
                "thought": "Solving task directly without child delegation.",
                "code": "finish('Completed task successfully.')"
            }
        ]
