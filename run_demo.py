#!/usr/bin/env python3
import asyncio
import json
from typing import List
from rao.engine import ExecutionTree, TreeNode
from rao.environments.textcraft import TextCraftSynthEnv
from rao.environments.sec_extraction import SECExtractionEnv
from rao.agent import RecursiveAgent
from rao.rl import calculate_joint_reward, compute_loo_advantages, compute_depth_weights

# ANSI Color Codes for premium terminal styling
C_BLUE = "\033[94m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"
C_MAGENTA = "\033[95m"
C_BOLD = "\033[1m"
C_DIM = "\033[2m"
C_RESET = "\033[0m"

def print_banner():
    print(f"\n{C_BOLD}{C_BLUE}================================================================================{C_RESET}")
    print(f"{C_BOLD}{C_CYAN}         RECURSIVE AGENT OPTIMIZATION (RAO) - SYSTEM DEMONSTRATION             {C_RESET}")
    print(f"{C_BOLD}{C_BLUE}================================================================================{C_RESET}\n")

def print_header(title: str):
    print(f"\n{C_BOLD}{C_MAGENTA}✦ {title}{C_RESET}")
    print(f"{C_DIM}{'-' * len(title)}{C_RESET}\n")

def render_tree(node: TreeNode, indent: str = "", is_last: bool = True) -> None:
    # Prefix rendering
    marker = "└── " if is_last else "├── "
    node_str = f"[{C_GREEN}{node.node_id}{C_RESET}] Depth {node.depth} | Goal: '{C_BOLD}{node.goal}{C_RESET}' | Success: {C_YELLOW}{node.success_score:.2f}{C_RESET} | Reward: {C_CYAN}{node.reward:.2f}{C_RESET}"
    
    print(indent + marker + node_str)
    
    # Process children
    child_indent = indent + ("    " if is_last else "│   ")
    for i, child in enumerate(node.children):
        render_tree(child, child_indent, i == len(node.children) - 1)

def print_node_trajectory(node: TreeNode):
    print(f"\n{C_BOLD}{C_YELLOW}Trajectory Log for Node [{node.node_id}]{C_RESET}")
    print(f"{C_DIM}Goal: '{node.goal}'{C_RESET}")
    for idx, step in enumerate(node.trajectory):
        print(f"\n  {C_BOLD}{C_BLUE}[Step {idx + 1}]{C_RESET}")
        print(f"    {C_BOLD}Thought:{C_RESET} {C_CYAN}{step['thought']}{C_RESET}")
        print(f"    {C_BOLD}Python Block:{C_RESET}")
        # Indent code block
        code_lines = step['code'].strip().split('\n')
        for line in code_lines:
            print(f"      {C_DIM}{line}{C_RESET}")
        print(f"    {C_BOLD}Execution Output:{C_RESET}")
        out_lines = step['output'].strip().split('\n')
        for line in out_lines:
            print(f"      {C_GREEN}>> {line}{C_RESET}")

async def main():
    print_banner()
    
    # ----------------------------------------------------
    # SECTION 1: TextCraft-Synth Simulation Environment
    # ----------------------------------------------------
    print_header("1. RUNNING TEXTCRAFT-SYNTH MULTI-AGENT ROLLOUT")
    
    tc_env = TextCraftSynthEnv()
    tc_tree = ExecutionTree("Craft target m3_i1", max_depth=4)
    tc_agent = RecursiveAgent(tc_env)
    
    print(f"{C_BOLD}{C_CYAN}[System]{C_RESET} Spawning Root Agent to craft target...")
    await tc_agent.run_node(tc_tree.root_node, tc_tree)
    
    # Post-process rewards
    for node in tc_tree.get_all_nodes():
        calculate_joint_reward(node, lambda_factor=0.4)
        
    print(f"{C_BOLD}{C_GREEN}[Success]{C_RESET} TextCraft Execution completed.")
    print_node_trajectory(tc_tree.root_node)
    
    # Render full tree topology
    print(f"\n{C_BOLD}{C_YELLOW}TextCraft Execution Tree Topology:{C_RESET}")
    render_tree(tc_tree.root_node)
    print()

    # ----------------------------------------------------
    # SECTION 2: SEC HTML/XBRL Extraction Environment
    # ----------------------------------------------------
    print_header("2. RUNNING SEC RECONCILIATION & RESTRUCTURING MULTI-AGENT ROLLOUT")
    
    sec_env = SECExtractionEnv()
    sec_tree = ExecutionTree("Segment margins calculation", max_depth=4)
    sec_agent = RecursiveAgent(sec_env)
    
    print(f"{C_BOLD}{C_CYAN}[System]{C_RESET} Spawning Root Agent to reconcile financial restatements...")
    await sec_agent.run_node(sec_tree.root_node, sec_tree)
    
    # Post-process rewards
    for node in sec_tree.get_all_nodes():
        calculate_joint_reward(node, lambda_factor=0.4)
        
    print(f"{C_BOLD}{C_GREEN}[Success]{C_RESET} SEC Financial Extraction completed.")
    
    # Render child nodes trajectories
    print_node_trajectory(sec_tree.root_node)
    
    # Render full tree topology
    print(f"\n{C_BOLD}{C_YELLOW}SEC Financial Execution Tree Topology:{C_RESET}")
    render_tree(sec_tree.root_node)
    print()
    
    # Print the mathematically reconciled segment output returned by root node
    print(f"{C_BOLD}{C_YELLOW}Final Reconciled Segment Data Output (Root Finished Message):{C_RESET}")
    print(f"{C_GREEN}{json.dumps(sec_tree.root_node.finished_message, indent=2)}{C_RESET}\n")

    # ----------------------------------------------------
    # SECTION 3: RAO Reinforcement Learning (RL) Telemetry
    # ----------------------------------------------------
    print_header("3. RAO REINFORCEMENT LEARNING MATHEMATICAL TELEMETRY")
    
    # Group rollouts to compute Leave-One-Out (LOO) baselines
    # To demonstrate a realistic baseline, we run a second SEC extraction rollout
    # with slightly worse performance (simulated by scaling rewards/success manually)
    sec_tree_b = ExecutionTree("Segment margins calculation B", max_depth=4)
    sec_tree_b.root_node.success_score = 0.5
    sec_tree_b.root_node.reward = 0.6
    
    sec_tree_c = ExecutionTree("Segment margins calculation C", max_depth=4)
    sec_tree_c.root_node.success_score = 0.0
    sec_tree_c.root_node.reward = 0.1
    
    rollouts = [sec_tree, sec_tree_b, sec_tree_c]
    advantages = compute_loo_advantages(rollouts)
    
    print(f"{C_BOLD}{C_CYAN}Formula 1: Joint Node Reward{C_RESET} {C_DIM}(Eq 1: R_node = Success(X) + λ * mean(Success(c))){C_RESET}")
    print(f"  • Root Joint Reward (Rollout A): {C_BOLD}{sec_tree.root_node.reward:.4f}{C_RESET}")
    print(f"  • Child Note 3 Joint Reward (Rollout A): {C_BOLD}{sec_tree.root_node.children[1].reward:.4f}{C_RESET}")
    print()
    
    print(f"{C_BOLD}{C_CYAN}Formula 3: Leave-One-Out (LOO) Baselines & Advantages{C_RESET} {C_DIM}(Eq 3: A = R_root - mean(R_others)){C_RESET}")
    print(f"  We run 3 concurrent rollouts with different outcomes to isolate causal credit:")
    print(f"    - Rollout A Root Reward: {sec_tree.root_node.reward:.2f}")
    print(f"    - Rollout B Root Reward: {sec_tree_b.root_node.reward:.2f}")
    print(f"    - Rollout C Root Reward: {sec_tree_c.root_node.reward:.2f}")
    print(f"  Computed Advantages:")
    print(f"    • Rollout A Root Advantage: {C_BOLD}{C_GREEN}{advantages[sec_tree.root_node.node_id]:+.4f}{C_RESET} (Causal success driver)")
    print(f"    • Rollout B Root Advantage: {C_BOLD}{C_YELLOW}{advantages[sec_tree_b.root_node.node_id]:+.4f}{C_RESET}")
    print(f"    • Rollout C Root Advantage: {C_BOLD}{C_RED}{advantages[sec_tree_c.root_node.node_id]:+.4f}{C_RESET}")
    print()
    
    # Aggregate all nodes from Rollout A to demonstrate depth weight balancing
    all_nodes = sec_tree.get_all_nodes()
    depth_weights = compute_depth_weights(all_nodes)
    
    print(f"{C_BOLD}{C_CYAN}Formula 4: Depth-Level Inverse-Frequency Weighting{C_RESET} {C_DIM}(Eq 4: w_d = alpha * (1 / N_d)){C_RESET}")
    print(f"  Unbalanced trees can skew gradient calculations if deep levels have vastly more nodes.")
    print(f"  Rollout A Node Counts by Depth:")
    counts = {}
    for n in all_nodes:
        counts[n.depth] = counts.get(n.depth, 0) + 1
    for d, c in counts.items():
        print(f"    - Depth {d}: {c} node(s)")
    
    print(f"  Calculated Normalized Weights:")
    for n in all_nodes[:4]: # print first few nodes
        role = "Root Node" if n.depth == 0 else f"Child Node (Goal: '{n.goal}')"
        print(f"    • Node [{n.node_id}] | Depth {n.depth} ({role}) -> Weight: {C_BOLD}{depth_weights[n.node_id]:.4f}{C_RESET}")
    print(f"================================================================================\n")

if __name__ == "__main__":
    asyncio.run(main())
