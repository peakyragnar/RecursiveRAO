import os
import sys
import json
import asyncio
from typing import Dict, Any

# Ensure rao module can be imported
sys.path.insert(0, "/Users/michael/RecursiveRAO")

from rao.engine import ExecutionTree
from rao.environments.nvda_extraction import NVDAExtractionEnv
from rao.agent import RecursiveAgent
from rao.rl import calculate_joint_reward

def load_env(file_path):
    env = {}
    if not os.path.exists(file_path):
        return env
    with open(file_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' in line:
                key, val = line.split('=', 1)
                key = key.strip()
                val = val.strip()
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                env[key] = val
    return env

async def main():
    print("================================================================================")
    print("          NVIDIA (NVDA) 5-YEAR SEC RECONCILIATION PIPELINE - RAO                ")
    print("================================================================================")
    
    # Load env vars manually
    env = load_env("/Users/michael/RecursiveRAO/.env")
    for k, v in env.items():
        os.environ[k] = v
        
    if not os.environ.get("GEMINI_API_KEY"):
        print("❌ Error: GEMINI_API_KEY is not set in .env. Please configure it first.")
        sys.exit(1)
        
    print("🔄 Loading live NVDA Ingestion & Extraction Environment...")
    env_instance = NVDAExtractionEnv(cache_dir="/Users/michael/RecursiveRAO/data/cache")
    
    # Check if filings are cached
    initial_ctx = env_instance.get_initial_context()
    available_filings = initial_ctx.get("filings_available", [])
    print(f"📊 Available cached filings: {len(available_filings)} files loaded.")
    
    if len(available_filings) == 0:
        print("❌ Error: No filings found in cache. Run the ingestion step first.")
        sys.exit(1)
        
    # Initialize Execution Tree
    goal = (
        "Extract quarterly segment (Graphics vs Compute & Networking) and market platform "
        "(Data Center, Gaming, Professional Visualization, Automotive, OEM & IP) revenue "
        "for NVDA from 2021 to 2026. Reconcile historical restatements programmatically "
        "and output a unified, mathematically reconciled time series JSON."
    )
    
    print("\n🌲 Initializing Recursive Agent Execution Tree...")
    tree = ExecutionTree(goal, max_depth=4)
    agent = RecursiveAgent(env_instance)
    
    print("🔥 Starting dynamic multi-agent tree search rollout...")
    result = await agent.run_node(tree.root_node, tree)
    
    print("\n🏁 Rollout completed!")
    
    # Calculate rewards for telemetry
    print("\n⚖️ Computing joint local rewards across tree nodes...")
    for node in tree.get_all_nodes():
        calculate_joint_reward(node, lambda_factor=0.4)
        
    # Write the final output JSON
    output_dir = "/Users/michael/RecursiveRAO/data"
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, "nvda_reconciled_5year.json")
    
    with open(output_path, "w") as f:
        json.dump(result, f, indent=2)
        
    print(f"✅ Final reconciled data successfully exported to: {output_path}")
    
    # Save the execution tree trace for telemetry analysis
    tree_path = os.path.join(output_dir, "nvda_execution_tree.json")
    with open(tree_path, "w") as f:
        json.dump(tree.root_node.to_dict(), f, indent=2)
    print(f"✅ Full RAO Execution Tree trace exported to: {tree_path}")
    
    # Run structural validation check
    print("\n📈 Programmatic Reconciled Math Checks:")
    try:
        if isinstance(result, str):
            data = json.loads(result)
        else:
            data = result
            
        disclosures = data.get("disclosures", {})
        segments = disclosures.get("segments", {})
        
        print("\nReconciliation Verification by Segment & Fiscal Year:")
        for seg_name, seg_data in segments.items():
            print(f"\n  • Segment: {seg_name}")
            for fy, fy_data in seg_data.items():
                if not isinstance(fy_data, dict):
                    continue
                orig = fy_data.get("as_originally_reported_usd_m")
                restated = fy_data.get("fully_restated_comparative_usd_m")
                quarters = fy_data.get("quarterly_reconciliation", {})
                
                if quarters and isinstance(quarters, dict):
                    sum_q = sum(quarters.values())
                    diff = abs(sum_q - restated) if restated else 0
                    status = "✅ PERFECT" if diff < 10 else f"⚠️ DIFF: {diff:.2f}M"
                    print(f"    - {fy}: Originally Reported: {orig}M | Restated: {restated}M | Sum of Quarters: {sum_q:.2f}M -> {status}")
                else:
                    print(f"    - {fy}: Originally Reported: {orig}M | Restated: {restated}M | Quarters: Missing")
    except Exception as e:
        print(f"⚠️ Could not perform verification checks: {str(e)}")
        
    print("\n================================================================================")
    print("🎉 Pipeline run complete!")
    print("================================================================================")

if __name__ == "__main__":
    asyncio.run(main())
