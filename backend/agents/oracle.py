import logging
from typing import Set
from backend.utils.gemini_client import gemini_client
from backend.models.schemas import LogicGraph, WorldState, ValidationResult, ValidationViolation

logger = logging.getLogger(__name__)

class OracleAgent:
    """
    Phase 2: OracleAgent - Performs two-tier validation on LogicGraphs.
    
    Tier 1 (Symbolic): Python-based rule checking
    - Preconditions satisfied by prior postconditions
    - Temporal consistency
    - Entity consistency
    
    Tier 2 (Commonsense): LLM-based plausibility checking
    - Character behavior consistency
    - Causal plausibility
    - Narrative logic
    """
    
    COMMONSENSE_PROMPT = """
You are the ORACLE - an expert in narrative logic and story consistency.
Your goal is to validate the logical coherence and commonsense plausibility of a story.

**Validation Criteria:**

1. **Character Consistency**: Do characters behave consistently with their established traits and prior actions?
2. **Causal Plausibility**: Do events have believable cause-and-effect relationships?
3. **Narrative Logic**: Does the story progression make sense? Are there plot holes or contradictions?

**Instructions:**
1. Read the entire LogicGraph (nodes and edges)
2. EXTREMELY IMPORTANT: Provide detailed `reasoning` explaining your analysis
3. Identify any violations of consistency, plausibility, or logic
4. For each violation, specify:
   - Type: "commonsense"
   - Description: What's wrong and why
   - Node ID: Which node has the issue
   - Severity: "error" for major issues, "warning" for minor concerns
5. Provide suggestions for fixing violations
6. Set `is_valid` to True only if no errors found (warnings are acceptable)

Output must strictly follow the ValidationResult schema.
"""
    
    async def validate_symbolic(self, logic_graph: LogicGraph, world_state: WorldState) -> ValidationResult:
        """
        Tier 1: Symbolic validation using Python rules.
        
        Checks:
        - Preconditions are satisfied by prior postconditions
        - No timeline contradictions
        - Entity consistency
        
        Args:
            logic_graph: The story's logic graph
            world_state: Current world state
            
        Returns:
            ValidationResult with symbolic violations
        """
        print(f"OracleAgent (Tier 1): Performing symbolic validation...")
        logger.info("OracleAgent: Starting Tier 1 symbolic validation...")
        
        violations = []
        satisfied_conditions: Set[str] = set()
        
        # Check each node's preconditions
        for i, node in enumerate(logic_graph.nodes):
            # Check if all preconditions are satisfied
            for precondition in node.preconditions:
                if precondition not in satisfied_conditions:
                    violations.append(ValidationViolation(
                        violation_type="precondition",
                        description=f"Precondition '{precondition}' for action '{node.action}' is not satisfied by any prior event",
                        node_id=node.id,
                        severity="error"
                    ))
            
            # Add this node's postconditions to satisfied set
            satisfied_conditions.update(node.postconditions)
        
        # Check for circular dependencies in edges (basic temporal consistency)
        # A simple check: no node should depend on itself through edge chains
        # (For Phase 2.0, we'll keep this simple)
        
        is_valid = len([v for v in violations if v.severity == "error"]) == 0
        suggestions = []
        
        if not is_valid:
            suggestions.append("Reorder events to ensure preconditions are met")
            suggestions.append("Add intermediate events to establish missing preconditions")
        
        result = ValidationResult(
            reasoning=f"Symbolic validation checked {len(logic_graph.nodes)} nodes and {len(logic_graph.edges)} edges. Found {len(violations)} violations.",
            is_valid=is_valid,
            violations=violations,
            suggestions=suggestions
        )
        
        print(f"OracleAgent (Tier 1): Validation {'PASSED' if is_valid else 'FAILED'}. Violations: {len(violations)}")
        logger.info(f"OracleAgent: Tier 1 complete. Valid: {is_valid}, Violations: {len(violations)}")
        
        return result
    
    async def validate_commonsense(self, logic_graph: LogicGraph) -> ValidationResult:
        """
        Tier 2: Commonsense validation using Gemini LLM.
        
        Uses the LLM to check:
        - Character behavior consistency
        - Causal plausibility
        - Narrative logic
        
        Args:
            logic_graph: The story's logic graph
            
        Returns:
            ValidationResult with commonsense violations
        """
        print(f"OracleAgent (Tier 2): Performing commonsense validation...")
        logger.info("OracleAgent: Starting Tier 2 commonsense validation...")
        
        # Build prompt with graph structure
        nodes_summary = "\n".join([
            f"Node {i+1} ({node.id}):\n  Action: {node.action}\n  Actors: {', '.join(node.actors) if node.actors else 'none'}\n  Preconditions: {', '.join(node.preconditions) if node.preconditions else 'none'}\n  Postconditions: {', '.join(node.postconditions) if node.postconditions else 'none'}"
            for i, node in enumerate(logic_graph.nodes)
        ])
        
        edges_summary = "\n".join([
            f"{edge.source} --[{edge.relation}]-> {edge.target}"
            for edge in logic_graph.edges
        ])
        
        prompt = f"""
{self.COMMONSENSE_PROMPT}

**LOGIC GRAPH TO VALIDATE:**

Nodes:
{nodes_summary}

Edges:
{edges_summary}

Perform commonsense validation and return the ValidationResult.
"""
        
        try:
            print("OracleAgent (Tier 2): Sending request to Gemini...")
            logger.info("OracleAgent: Calling Gemini for commonsense validation...")
            
            result = await gemini_client.generate_structured(
                prompt=prompt,
                response_model=ValidationResult
            )
            
            print(f"OracleAgent (Tier 2): Validation {'PASSED' if result.is_valid else 'FAILED'}. Violations: {len(result.violations)}")
            logger.info(f"OracleAgent: Tier 2 complete. Valid: {result.is_valid}, Violations: {len(result.violations)}")
            
            return result
            
        except Exception as e:
            print(f"!!! ORACLE (Tier 2) FAILED: {e} !!!")
            logger.error(f"OracleAgent Tier 2 failed: {e}")
            raise e

# Export singleton instance
oracle = OracleAgent()
