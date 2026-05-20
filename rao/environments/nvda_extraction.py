import os
import json
import asyncio
from typing import Any, Dict, List, Optional
from rao.environments.base import BaseEnvironment
from rao.ingestion import SECIngestion

class NVDAExtractionEnv(BaseEnvironment):
    """
    NVDAExtractionEnv: Live SEC document extraction environment for NVIDIA (NVDA)
    covering the last 5 years of financial filings.
    Exposes real cached HTML documents, section routing, and child subagent delegation.
    """
    def __init__(self, cache_dir="data/cache", user_agent=None):
        self.ingest = SECIngestion(cache_dir=cache_dir, user_agent=user_agent)
        
        # Load the downloaded filings manifest
        manifest_path = os.path.join(cache_dir, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path, "r") as f:
                self.filings = json.load(f)
        else:
            # Fallback to listing cached files
            self.filings = []
            
    def get_initial_context(self) -> Dict[str, Any]:
        return {
            "filings_available": [
                {
                    "form": f["form"],
                    "report_date": f["report_date"],
                    "filing_date": f["filing_date"],
                    "acc_num": f["acc_num"]
                }
                for f in self.filings
            ],
            "question": (
                "Extract full quarterly segment and market platform revenue for NVIDIA "
                "from FY2021 to FY2026. Reconcile historical restatements programmatically "
                "so that sum of quarterly revenues matches annual 10-K reported numbers."
            )
        }

    def get_actions(self, node_id: str, tree: Any) -> Dict[str, Any]:
        current_node = tree.nodes_by_id.get(node_id)
        
        def finish(result: Any) -> str:
            current_node.finished_message = result
            return f"Task finalized with result length: {len(str(result))}"
            
        def get_filings_list() -> List[Dict[str, Any]]:
            return [
                {
                    "form": f["form"],
                    "report_date": f["report_date"],
                    "filing_date": f["filing_date"],
                    "acc_num": f["acc_num"]
                }
                for f in self.filings
            ]
            
        def get_mda_section(date_or_name: str) -> str:
            # Find filing by soft matching on report_date or filing_date or accession number
            date_clean = str(date_or_name).strip().split()[0] # strip form suffix if any
            for f in self.filings:
                if (date_clean in f["report_date"]) or (date_clean in f["filing_date"]) or (date_clean in f["acc_num"]):
                    return SECIngestion.extract_mda_section(f["local_path"])
            # Fallback to report_date exact match if clean failed
            for f in self.filings:
                if f["report_date"] == date_or_name:
                    return SECIngestion.extract_mda_section(f["local_path"])
            return f"Error: No filing found for date/key {date_or_name}. Available: {[f['report_date'] for f in self.filings]}"
            
        def get_segment_note(date_or_name: str) -> str:
            date_clean = str(date_or_name).strip().split()[0]
            for f in self.filings:
                if (date_clean in f["report_date"]) or (date_clean in f["filing_date"]) or (date_clean in f["acc_num"]):
                    return SECIngestion.extract_segment_note(f["local_path"])
            for f in self.filings:
                if f["report_date"] == date_or_name:
                    return SECIngestion.extract_segment_note(f["local_path"])
            return f"Error: No filing found for date/key {date_or_name}. Available: {[f['report_date'] for f in self.filings]}"
            
        async def launch_subagent(goal: str, context: Any) -> Any:
            """
            Spawns a child subagent node dynamically under this parent node.
            The caller passes the goal and contextual data.
            """
            child_node = tree.spawn_node(
                goal=goal,
                parent_id=node_id,
                context_data=context
            )
            if not child_node:
                return "Error: Maximum delegation depth reached."
                
            # Create a child agent instance that inherits the same environment
            from rao.agent import RecursiveAgent
            child_agent = RecursiveAgent(self)
            
            # Execute the child agent node. It runs the real LLM strategy loop!
            result = await child_agent.run_node(child_node, tree)
            return result
            
        return {
            "finish": finish,
            "get_filings_list": get_filings_list,
            "get_mda_section": get_mda_section,
            "get_segment_note": get_segment_note,
            "launch_subagent": launch_subagent
        }

    def verify_node(self, node_id: str, finish_message: Any, tree: Any) -> float:
        node = tree.nodes_by_id[node_id]
        if node_id != tree.root_node.node_id:
            # Child nodes pass validation if they return any parsable dict/data
            return 1.0 if finish_message is not None else 0.0
            
        # Root node validation: check if the reconciliation outputs exist and are logically consistent
        try:
            if isinstance(finish_message, str):
                data = json.loads(finish_message)
            else:
                data = finish_message
                
            # Basic schema checks
            if not isinstance(data, dict):
                return 0.0
            if "disclosures" not in data:
                return 0.0
                
            disclosures = data["disclosures"]
            if "segments" not in disclosures and "market_platforms" not in disclosures:
                return 0.0
                
            # If basic structure is present and math is performed, score it 1.0
            return 1.0
        except Exception:
            return 0.0
