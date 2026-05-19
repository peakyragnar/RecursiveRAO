from typing import Any, Dict, List, Tuple
from rao.environments.base import BaseEnvironment
import asyncio

class TextCraftSynthEnv(BaseEnvironment):
    """
    TextCraft-Synth: A controlled synthetic benchmark for compositional crafting.
    Recipes form dynamic dependency trees that map target items to base ingredients.
    """
    def __init__(self):
        # A hardcoded deterministic crafting recipe graph for testing
        # Structure: target_item -> { "ingredients": {ingredient: count}, "result_count": int, "crafting_depth": int }
        self.recipes = {
            # Depth 1 items (Directly craftable from base items)
            "m1_i1": {"ingredients": {"raw_m0": 2}, "result_count": 1, "crafting_depth": 1},
            "m1_i2": {"ingredients": {"raw_m0": 1, "raw_coal": 1}, "result_count": 2, "crafting_depth": 1},
            
            # Depth 2 items (Requires intermediate ingredients)
            "m2_i1": {"ingredients": {"m1_i1": 2, "raw_iron": 1}, "result_count": 1, "crafting_depth": 2},
            "m2_i2": {"ingredients": {"m1_i1": 1, "m1_i2": 2}, "result_count": 2, "crafting_depth": 2},
            
            # Depth 3 items (High compositional complexity)
            "m3_i1": {"ingredients": {"m2_i1": 1, "m2_i2": 2}, "result_count": 1, "crafting_depth": 3},
            "m3_i2": {"ingredients": {"m2_i2": 4, "raw_gold": 2}, "result_count": 1, "crafting_depth": 3}
        }
        
        # Ground truth inventory starts with base materials
        self.inventory: Dict[str, int] = {
            "raw_m0": 50,
            "raw_coal": 20,
            "raw_iron": 10,
            "raw_gold": 5
        }
        
    def get_initial_context(self) -> Dict[str, Any]:
        return {
            "inventory": self.inventory.copy(),
            "target": "m3_i1",
            "quantity": 1
        }
        
    def get_actions(self, node_id: str, tree: Any) -> Dict[str, Any]:
        # Bind parent-child spawning via closure
        current_node = tree.nodes_by_id.get(node_id)
        
        # View current inventory state
        def view_inventory() -> dict:
            return self.inventory.copy()
            
        # Get recipe list details
        def get_info(items: list) -> list[dict]:
            out = []
            for item in items:
                if item in self.recipes:
                    rec = self.recipes[item]
                    out.append({
                        "item": item,
                        "can_craft": True,
                        "is_base": False,
                        "in_inventory": self.inventory.get(item, 0),
                        "crafting_depth": rec["crafting_depth"],
                        "recipes": [{"ingredients": rec["ingredients"], "result_count": rec["result_count"]}]
                    })
                else:
                    out.append({
                        "item": item,
                        "can_craft": False,
                        "is_base": True,
                        "in_inventory": self.inventory.get(item, 0),
                        "crafting_depth": 0,
                        "recipes": []
                    })
            return out
            
        # Craft function consuming ingredients and adding target to inventory
        def craft(ingredients: dict, target: tuple[str, int]) -> str:
            target_name, target_count = target
            
            # Verify recipe matches
            if target_name not in self.recipes:
                return f"Error: No recipe known for item '{target_name}'."
            recipe = self.recipes[target_name]
            
            # Count verification
            if target_count % recipe["result_count"] != 0:
                return f"Error: Target count {target_count} must be divisible by recipe yield {recipe['result_count']}."
                
            multiplier = target_count // recipe["result_count"]
            required_ingredients = {k: v * multiplier for k, v in recipe["ingredients"].items()}
            
            # Verify inventory levels
            for ing, req_count in required_ingredients.items():
                if self.inventory.get(ing, 0) < req_count:
                    return f"Error: Insufficient ingredient '{ing}'. Need {req_count}, have {self.inventory.get(ing, 0)}."
                    
            # Consume and credit
            for ing, req_count in required_ingredients.items():
                self.inventory[ing] -= req_count
            self.inventory[target_name] = self.inventory.get(target_name, 0) + target_count
            
            return f"Successfully crafted {target_count} {target_name}."
            
        # Complete task
        def finish(message: str) -> str:
            current_node.finished_message = message
            return f"Task completed with output: {message}"
            
        # Asynchronous child spawning primitive
        async def launch_subagent(targets: dict, num_steps: int, context: str = "") -> str:
            # Check maximum depth constraint before spawning
            child_node = tree.spawn_node(
                goal=f"Craft ingredients: {targets}",
                parent_id=node_id,
                context_data=context
            )
            if not child_node:
                return "Error: Maximum delegation depth exceeded."
                
            # Simulate child agent processing in background
            # We mock the child execution tree path recursively
            await asyncio.sleep(0.01)
            
            # Subagent automatically solves sub-goals programmatically to simulate a trained policy
            for item_name, count in targets.items():
                # Child executes recursive sub-crafting
                self.resolve_craft_recursively(item_name, count)
                
            child_node.finished_message = f"Successfully crafted all requested targets: {targets}"
            child_node.success_score = 1.0  # Perfect execution of the sub-agent
            
            return child_node.finished_message

        return {
            "view_inventory": view_inventory,
            "get_info": get_info,
            "craft": craft,
            "finish": finish,
            "launch_subagent": launch_subagent
        }
        
    def resolve_craft_recursively(self, item_name: str, count: int):
        """
        Internal simulator helper to recursively resolve child/grandchild sub-crafts
        directly in the global inventory to maintain simulation integrity.
        """
        if item_name not in self.recipes:
            return
            
        recipe = self.recipes[item_name]
        multiplier = (count + recipe["result_count"] - 1) // recipe["result_count"]
        
        # Verify and recursively craft missing sub-ingredients
        for ing, req_count in recipe["ingredients"].items():
            needed = req_count * multiplier
            in_inv = self.inventory.get(ing, 0)
            if in_inv < needed:
                self.resolve_craft_recursively(ing, needed - in_inv)
                
            # Consume
            self.inventory[ing] -= needed
            
        # Add yield
        self.inventory[item_name] = self.inventory.get(item_name, 0) + (recipe["result_count"] * multiplier)

    def verify_node(self, node_id: str, finish_message: Any, tree: Any) -> float:
        node = tree.nodes_by_id[node_id]
        
        # Root target verification
        if node_id == tree.root_node.node_id:
            target = "m3_i1"
            # Checks if target item resides in inventory
            if self.inventory.get(target, 0) >= 1:
                return 1.0
            return 0.0
            
        # If child finished its specific goals
        return 1.0
