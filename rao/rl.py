from typing import Dict, List
import math
from rao.engine import TreeNode, ExecutionTree

def calculate_joint_reward(node: TreeNode, lambda_factor: float = 0.4) -> float:
    """
    Implements the joint node reward equation (Eq 1):
    R(X, 𝜏_X) = Success(X) + \lambda * (1 / |C(X)|) * \sum_{c \in C(X)} Success(c)
    """
    success_x = node.success_score
    
    if not node.children:
        # If no child agents spawned, delegation bonus is exactly 0
        node.reward = success_x
        return node.reward
        
    children_success_sum = sum(c.success_score for c in node.children)
    avg_children_success = children_success_sum / len(node.children)
    
    node.reward = success_x + lambda_factor * avg_children_success
    return node.reward


def compute_loo_advantages(rollouts: List[ExecutionTree]) -> Dict[str, float]:
    """
    Computes Leave-One-Out (LOO) baselines and node-level advantages (Eq 3):
    A(𝜏^(g)) = R(𝜏^(g)) - b_(-g)
    where b_(-g) = (1 / (G - 1)) * \sum_{g' != g} R^(g')_root
    
    Returns a mapping of node_id to its computed advantage value.
    """
    G = len(rollouts)
    advantages: Dict[str, float] = {}
    
    if G <= 1:
        # If we have only 1 rollout, baseline falls back to 0 (cannot do counterfactual average)
        for tree in rollouts:
            for node in tree.get_all_nodes():
                advantages[node.node_id] = node.reward
        return advantages
        
    # Pre-calculate root rewards for all rollouts
    root_rewards = [tree.root_node.reward for tree in rollouts]
    
    for g, tree in enumerate(rollouts):
        # Calculate the counterfactual baseline excluding rollout g
        other_roots_sum = sum(root_rewards[i] for i in range(G) if i != g)
        baseline = other_roots_sum / (G - 1)
        
        # Every node within execution tree g gets evaluated against this baseline
        for node in tree.get_all_nodes():
            advantages[node.node_id] = node.reward - baseline
            
    return advantages


def compute_depth_weights(nodes: List[TreeNode]) -> Dict[str, float]:
    """
    Computes depth-level inverse-frequency weights to prevent deeper tree layers
    from dominating the policy optimization objective (Eq 4).
    
    Returns a mapping of node_id to its depth-level weight.
    """
    # Count occurrences at each depth
    depth_counts: Dict[int, int] = {}
    for node in nodes:
        depth_counts[node.depth] = depth_counts.get(node.depth, 0) + 1
        
    total_trajectories = len(nodes)
    
    # Calculate unnormalized depth weights (1 / N_d)
    # Sum over depths (1 / N_d) to compute normalization scale alpha
    inverse_sum = sum(1.0 / depth_counts[d] for d in depth_counts)
    
    if total_trajectories == 0:
        return {}
        
    # alpha preserves the overall scale of updates across the batch
    alpha = total_trajectories / inverse_sum
    
    # Map each node to its normalized weight: w_d = alpha * (1 / N_d)
    node_weights: Dict[str, float] = {}
    for node in nodes:
        n_d = depth_counts[node.depth]
        node_weights[node.node_id] = alpha * (1.0 / n_d)
        
    return node_weights
