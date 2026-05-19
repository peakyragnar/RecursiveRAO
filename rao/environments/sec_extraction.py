from typing import Any, Dict, List
from rao.environments.base import BaseEnvironment
import asyncio
import json

class SECExtractionEnv(BaseEnvironment):
    """
    SECExtractionEnv: Synthetic SEC 10-K document processing environment.
    Exposes split chunks containing segment tables, reorganizations, and discontinued footnotes.
    Requires dynamic child delegation and mathematical reconciliation.
    """
    def __init__(self):
        # Simulated multi-page HTML content chunks
        self.chunks = {
            1: """
            <html>
            <h3>Item 7. Management's Discussion and Analysis</h3>
            <p>Reported Segment Revenues and Operating Incomes for recent years are outlined below.</p>
            <table border="1" id="main_segment_table">
                <tr>
                    <th>Segment</th>
                    <th>2023 Revenue ($M)</th>
                    <th>2024 Revenue ($M)</th>
                    <th>2025 Revenue ($M)</th>
                    <th>2023 OpInc ($M)</th>
                    <th>2024 OpInc ($M)</th>
                    <th>2025 OpInc ($M)</th>
                </tr>
                <tr>
                    <td>Cloud & Enterprise</td>
                    <td>450.0</td>
                    <td>520.0</td>
                    <td>-</td>
                    <td>90.0</td>
                    <td>110.0</td>
                    <td>-</td>
                </tr>
                <tr>
                    <td>Intelligent Systems</td>
                    <td>-</td>
                    <td>-</td>
                    <td>680.0</td>
                    <td>-</td>
                    <td>-</td>
                    <td>156.0</td>
                </tr>
                <tr>
                    <td>Consumer Devices</td>
                    <td>210.0</td>
                    <td>230.0</td>
                    <td>190.0</td>
                    <td>21.0</td>
                    <td>25.0</td>
                    <td>15.0</td>
                </tr>
                <tr>
                    <td>Legacy Media*</td>
                    <td>85.0</td>
                    <td>92.0</td>
                    <td>-</td>
                    <td>5.0</td>
                    <td>6.0</td>
                    <td>-</td>
                </tr>
            </table>
            <p>*The Legacy Media segment operations are detailed further in Note 3 (Discontinued Operations).</p>
            </html>
            """,
            8: """
            <html>
            <h3>Note 3. Discontinued Operations</h3>
            <p>In Q4 2025, the Company completed the spinoff of its Legacy Media division. 
            Historically, all assets and revenues associated with Legacy Media have been classified
            within discontinued operations. Consequently, for organic YoY comparisons,
            the spinoff revenues must be fully backed out from historical segment figures.</p>
            <p>Legacy Media discontinued revenues: 2023: $85.0M, 2024: $92.0M.</p>
            </html>
            """,
            12: """
            <html>
            <h3>Note 14. Segment Reorganization</h3>
            <p>Effective January 1, 2025, the Company restructured its reporting segments. 
            The former Cloud & Enterprise segment was merged with the premium smart home product lines
            previously reported under Consumer Devices to form the new <b>Intelligent Systems</b> segment.</p>
            <p>To enable comparative analysis, historical segment results have been restated to conform
            to the 2025 reporting structure. Under this restated configuration:</p>
            <ul>
                <li>Consumer Devices 2023 revenue reallocated to Intelligent Systems: $40.0M</li>
                <li>Consumer Devices 2024 revenue reallocated to Intelligent Systems: $45.0M</li>
                <li>Restated 2023 Intelligent Systems Operating Income: $105.0M</li>
                <li>Restated 2024 Intelligent Systems Operating Income: $128.0M</li>
            </ul>
            </html>
            """
        }
        
        # Ground Truth database for mathematical reconciliation
        self.ground_truth = {
            "Intelligent Systems": {
                "2023": {"organic_revenue_usd_m": 490.0, "operating_margin": 0.214}, # (450+40) = 490 revenue; restated OpInc = 105. Margin = 105/490 = 0.21428
                "2024": {"organic_revenue_usd_m": 565.0, "operating_margin": 0.226}, # (520+45) = 565 revenue; restated OpInc = 128. Margin = 128/565 = 0.22654
                "2025": {"organic_revenue_usd_m": 680.0, "operating_margin": 0.229}  # 680 revenue; OpInc = 156. Margin = 156/680 = 0.22941
            },
            "Consumer Devices": {
                "2023": {"organic_revenue_usd_m": 170.0, "operating_margin": 0.094}, # (210-40) = 170 revenue; OpInc = 21-5 = 16. Margin = 16/170 = 0.09411
                "2024": {"organic_revenue_usd_m": 185.0, "operating_margin": 0.097}, # (230-45) = 185 revenue; OpInc = 25-7 = 18. Margin = 18/185 = 0.09729
                "2025": {"organic_revenue_usd_m": 190.0, "operating_margin": 0.079}  # 190 revenue; OpInc = 15. Margin = 15/190 = 0.07894
            }
        }
        
    def get_initial_context(self) -> Dict[str, Any]:
        return {
            "chunks_available": list(self.chunks.keys()),
            "question": "Calculate reorganized segment revenues and operating margins."
        }
        
    def get_actions(self, node_id: str, tree: Any) -> Dict[str, Any]:
        current_node = tree.nodes_by_id.get(node_id)
        
        def finish(result: Any) -> str:
            current_node.finished_message = result
            return f"Task finalized with result length: {len(str(result))}"
            
        async def launch_subagent(goal: str, context: str) -> Any:
            child_node = tree.spawn_node(
                goal=goal,
                parent_id=node_id,
                context_data=context
            )
            if not child_node:
                return "Error: Maximum delegation depth reached."
                
            # Asynchronous simulation sleep
            await asyncio.sleep(0.01)
            
            # The simulator intercepts sub-agent goals and answers them deterministically
            # to match a highly capable joint policy rollout
            result = ""
            if "Note 3" in goal or "discontinued" in goal.lower():
                result = {"2023_legacy_media_rev": 85.0, "2024_legacy_media_rev": 92.0}
                child_node.success_score = 1.0
            elif "Note 14" in goal or "reorganization" in goal.lower():
                result = {
                    "2023_reallocated_rev": 40.0, "2024_reallocated_rev": 45.0,
                    "2023_restated_opinc": 105.0, "2024_restated_opinc": 128.0
                }
                child_node.success_score = 1.0
            elif "Item 7" in goal or "main segment" in goal.lower():
                result = {
                    "Cloud_Enterprise": {"2023_rev": 450.0, "2024_rev": 520.0, "2023_opinc": 90.0, "2024_opinc": 110.0},
                    "Consumer_Devices": {"2023_rev": 210.0, "2024_rev": 230.0, "2025_rev": 190.0, "2023_opinc": 21.0, "2024_opinc": 25.0, "2025_opinc": 15.0}
                }
                child_node.success_score = 1.0
            else:
                result = "Goal not recognized by mock environment."
                child_node.success_score = 0.0
                
            child_node.finished_message = result
            return result
            
        def get_chunk(chunk_id: int) -> str:
            return self.chunks.get(chunk_id, "Error: Chunk not found.")
            
        return {
            "finish": finish,
            "launch_subagent": launch_subagent,
            "get_chunk": get_chunk
        }
        
    def verify_node(self, node_id: str, finish_message: Any, tree: Any) -> float:
        node = tree.nodes_by_id[node_id]
        if node_id != tree.root_node.node_id:
            return node.success_score
            
        # Mathematical verification of root output
        try:
            if isinstance(finish_message, str):
                data = json.loads(finish_message)
            else:
                data = finish_message
                
            # Verify segments exist
            for seg in ["Intelligent Systems", "Consumer Devices"]:
                if seg not in data:
                    return 0.0
                    
                for year in ["2023", "2024", "2025"]:
                    if year not in data[seg]:
                        return 0.0
                        
                    agent_rev = data[seg][year]["organic_revenue_usd_m"]
                    agent_margin = data[seg][year]["operating_margin"]
                    
                    gt_rev = self.ground_truth[seg][year]["organic_revenue_usd_m"]
                    gt_margin = self.ground_truth[seg][year]["operating_margin"]
                    
                    # Revenue validation
                    if abs(agent_rev - gt_rev) > 1e-2:
                        return 0.0
                        
                    # Margin validation within strict float tolerance
                    if abs(agent_margin - gt_margin) > 1e-2:
                        return 0.0
                        
            return 1.0
        except Exception:
            return 0.0
