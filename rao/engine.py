from typing import Any, Dict, List, Optional
import uuid

class TreeNode:
    """
    Represents a single node (agent execution instance) within the dynamic recursive execution tree.
    """
    def __init__(
        self, 
        node_id: str,
        goal: str, 
        depth: int, 
        parent_id: Optional[str] = None, 
        context_data: Optional[Any] = None
    ):
        self.node_id = node_id
        self.goal = goal
        self.depth = depth
        self.parent_id = parent_id
        self.context_data = context_data  # Isolated input context (e.g. HTML chunk)
        
        self.children: List[TreeNode] = []
        self.trajectory: List[Dict[str, Any]] = [] # Sequence of thoughts, code blocks, and execution outputs
        self.success_score: float = 0.0            # Node success score ˜s(X, 𝜏_X) between 0.0 and 1.0
        self.reward: float = 0.0                   # Calculated joint local node reward R(X, 𝜏_X)
        self.finished_message: Optional[Any] = None # Output returned via the finish() function

    def add_child(self, child: 'TreeNode'):
        self.children.append(child)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "node_id": self.node_id,
            "goal": self.goal,
            "depth": self.depth,
            "parent_id": self.parent_id,
            "success": self.success_score,
            "reward": self.reward,
            "finished_message": self.finished_message,
            "trajectory_steps": len(self.trajectory),
            "children": [c.to_dict() for c in self.children]
        }


class ExecutionTree:
    """
    Orchestrates the dynamic recursive execution tree structure, ensuring limits
    on recursion depth and tracks overall trajectory generation.
    """
    def __init__(self, root_goal: str, max_depth: int = 6, root_context: Optional[Any] = None):
        root_id = f"root_{uuid.uuid4().hex[:6]}"
        self.root_node = TreeNode(
            node_id=root_id,
            goal=root_goal,
            depth=0,
            parent_id=None,
            context_data=root_context
        )
        self.max_depth = max_depth
        self.nodes_by_id: Dict[str, TreeNode] = {root_id: self.root_node}

    def spawn_node(self, goal: str, parent_id: str, context_data: Optional[Any] = None) -> Optional[TreeNode]:
        """
        Spawns a child node under the specified parent node if limits are not breached.
        """
        parent = self.nodes_by_id.get(parent_id)
        if not parent:
            raise ValueError(f"Parent node '{parent_id}' not found in execution tree.")
            
        child_depth = parent.depth + 1
        if child_depth > self.max_depth:
            # Depth ceiling reached; return None to signal delegation limit hit
            return None
            
        node_id = f"node_{uuid.uuid4().hex[:6]}"
        child_node = TreeNode(
            node_id=node_id,
            goal=goal,
            depth=child_depth,
            parent_id=parent_id,
            context_data=context_data
        )
        
        parent.add_child(child_node)
        self.nodes_by_id[node_id] = child_node
        return child_node

    def get_all_nodes(self) -> List[TreeNode]:
        """
        Returns a flat list of all nodes currently spawned in the execution tree.
        """
        return list(self.nodes_by_id.values())
