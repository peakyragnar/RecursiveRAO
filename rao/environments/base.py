from typing import Any, Dict, List, Optional

class BaseEnvironment:
    """
    Abstract Base Class for RAO environment tasks.
    Enforces a standardized interface for inventories, step verification, and scoring.
    """
    def get_initial_context(self) -> Any:
        """
        Returns the initial top-level context (e.g. initial inventory or complete document).
        """
        raise NotImplementedError
        
    def get_actions(self, node_id: str, tree: Any) -> Dict[str, Any]:
        """
        Returns a dictionary of pre-loaded sandbox python operations exposed for the agent.
        """
        raise NotImplementedError
        
    def verify_node(self, node_id: str, finish_message: Any, tree: Any) -> float:
        """
        Verifies a node's output against the ground truth and assigns a success score in [0.0, 1.0].
        """
        raise NotImplementedError
