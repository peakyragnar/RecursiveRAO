import pytest
import asyncio
from rao.sandbox import AsyncREPLSandbox
from rao.engine import ExecutionTree, TreeNode
from rao.environments.textcraft import TextCraftSynthEnv
from rao.environments.sec_extraction import SECExtractionEnv
from rao.rl import calculate_joint_reward, compute_loo_advantages, compute_depth_weights
from rao.agent import RecursiveAgent

@pytest.mark.asyncio
async def test_repl_sandbox_basic():
    """
    Validates AsyncREPLSandbox standard outputs and error tracebacks.
    """
    sandbox = AsyncREPLSandbox()
    code = """
print("Step 1: Running basic calculation")
x = 10 + 20
print(f"Result: {x}")
"""
    output = await sandbox.execute_async(code)
    assert "Result: 30" in output
    assert "Step 1" in output


@pytest.mark.asyncio
async def test_repl_sandbox_async():
    """
    Validates async sleep/awaits execution capabilities in Sandbox.
    """
    sandbox = AsyncREPLSandbox()
    code = """
import asyncio
print("Before sleep")
await asyncio.sleep(0.01)
print("After sleep")
"""
    output = await sandbox.execute_async(code)
    assert "Before sleep" in output
    assert "After sleep" in output


def test_execution_tree_depth():
    """
    Validates that engine enforces depth restrictions flawlessly.
    """
    tree = ExecutionTree(root_goal="Target", max_depth=3)
    
    node_1 = tree.spawn_node("Subtask 1", tree.root_node.node_id)
    assert node_1 is not None
    assert node_1.depth == 1
    
    node_2 = tree.spawn_node("Subtask 2", node_1.node_id)
    assert node_2 is not None
    assert node_2.depth == 2
    
    node_3 = tree.spawn_node("Subtask 3", node_2.node_id)
    assert node_3 is not None
    assert node_3.depth == 3
    
    # Depth 4 should exceed max_depth = 3 and return None
    node_4 = tree.spawn_node("Subtask 4", node_3.node_id)
    assert node_4 is None


def test_joint_reward_calculation():
    """
    Validates joint local node rewards with child average success rate.
    """
    tree = ExecutionTree("Root Goal")
    root = tree.root_node
    root.success_score = 1.0
    
    # Spawn 2 children
    child_1 = tree.spawn_node("Child 1", tree.root_node.node_id)
    child_2 = tree.spawn_node("Child 2", tree.root_node.node_id)
    
    child_1.success_score = 0.0
    child_2.success_score = 1.0
    
    # Expected: 1.0 + 0.4 * ((0.0 + 1.0) / 2) = 1.2
    reward = calculate_joint_reward(root, lambda_factor=0.4)
    assert abs(reward - 1.2) < 1e-6


def test_loo_advantage_computation():
    """
    Validates LOO baselines calculations across concurrent rollouts.
    """
    tree_a = ExecutionTree("Goal A")
    tree_b = ExecutionTree("Goal B")
    tree_c = ExecutionTree("Goal C")
    
    # Setup manual rewards
    tree_a.root_node.reward = 1.5
    tree_b.root_node.reward = 1.0
    tree_c.root_node.reward = 0.5
    
    # Group rollouts together
    rollouts = [tree_a, tree_b, tree_c]
    
    # Compute advantages
    advantages = compute_loo_advantages(rollouts)
    
    # Expected baseline for Tree A: (1.0 + 0.5) / 2 = 0.75. Advantage: 1.5 - 0.75 = 0.75
    assert abs(advantages[tree_a.root_node.node_id] - 0.75) < 1e-6
    
    # Expected baseline for Tree B: (1.5 + 0.5) / 2 = 1.0. Advantage: 1.0 - 1.0 = 0.0
    assert abs(advantages[tree_b.root_node.node_id] - 0.0) < 1e-6


def test_depth_frequency_weighting():
    """
    Validates mathematical balancing of depth frequencies.
    """
    tree = ExecutionTree("Root")
    
    # Create unbalanced frequencies: 1 root (depth 0), 4 children (depth 1), 8 grandchildren (depth 2)
    nodes = [tree.root_node]
    
    c_nodes = []
    for i in range(4):
        c = tree.spawn_node(f"Child {i}", tree.root_node.node_id)
        nodes.append(c)
        c_nodes.append(c)
        
    for c in c_nodes:
        for j in range(2):
            nodes.append(tree.spawn_node(f"Grandchild {j}", c.node_id))
            
    weights = compute_depth_weights(nodes)
    
    # Total nodes = 13
    assert len(weights) == 13
    
    # Depth 0 weight should be significantly higher than Depth 2 weight
    root_w = weights[tree.root_node.node_id]
    grandchild_node_id = [n.node_id for n in nodes if n.depth == 2][0]
    grandchild_w = weights[grandchild_node_id]
    
    assert root_w > grandchild_w


@pytest.mark.asyncio
async def test_textcraft_agent_run():
    """
    Runs an integration test of the TextCraft-Synth environment.
    """
    env = TextCraftSynthEnv()
    tree = ExecutionTree("Craft target m3_i1", max_depth=6)
    agent = RecursiveAgent(env)
    
    # Run the root node execution
    result = await agent.run_node(tree.root_node, tree)
    
    # Verify inventory crafted Successfully
    assert env.inventory.get("m3_i1", 0) >= 1
    assert tree.root_node.success_score == 1.0


@pytest.mark.asyncio
async def test_sec_extraction_agent_run():
    """
    Runs an integration test of the SECExtraction environment.
    """
    env = SECExtractionEnv()
    tree = ExecutionTree("Segment margins calculation", max_depth=6)
    agent = RecursiveAgent(env)
    
    # Run root extraction execution
    result = await agent.run_node(tree.root_node, tree)
    
    # Verify segment margining accuracy
    assert tree.root_node.success_score == 1.0
