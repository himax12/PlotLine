import logging
from backend.utils.gemini_client import gemini_client
from backend.models.schemas import LogicGraph, AnalogicalMapping, EntityArchetype

logger = logging.getLogger(__name__)

class MapperAgent:
    """
    Phase 2: MapperAgent - Performs 4-layer analogical decomposition.
    
    Analyzes the LogicGraph to extract:
    1. Entity Layer: Character archetypes
    2. Action Layer: Plot patterns
    3. Structure Layer: Narrative structure
    4. Emotion Layer: Emotional arc
    """
    
    SYSTEM_PROMPT = """
You are the MAPPER - an expert in narrative analysis and analogical reasoning.
Your goal is to perform a 4-layer decomposition of a story's logic graph to identify universal patterns.

**4-Layer Decomposition:**

1. **Entity Layer**: Map characters to universal archetypes
   - Examples: "Hero", "Mentor", "Shadow", "Ally", "Trickster", "Threshold Guardian"
   - For each actor in the graph, identify their archetypal role

2. **Action Layer**: Identify recurring plot patterns
   - Examples: "Quest", "Betrayal", "Discovery", "Sacrifice", "Transformation", "Return"
   - Look for sequences of actions that match known narrative patterns

3. **Structure Layer**: Classify the overall narrative structure
   - Examples: "Three-Act Structure", "Hero's Journey", "Tragedy Arc", "Rags to Riches", "Quest Narrative"
   - Analyze the flow of events and their relationships

4. **Emotion Layer**: Track the emotional trajectory
   - Examples: ["Hope", "Fear", "Despair", "Redemption"], ["Joy", "Loss", "Acceptance"]
   - Map the emotional progression through the story events

**Instructions:**
1. Read the entire LogicGraph (nodes and edges)
2. EXTREMELY IMPORTANT: Provide detailed `reasoning` explaining your analysis process
3. For entity archetypes, map each unique actor to their role
4. For action patterns, list the major patterns you observe
5. For structure, choose the single best-fitting narrative structure
6. For emotional arc, provide an ordered list of 3-5 emotions

Output must strictly follow the AnalogicalMapping schema.
"""

    async def run(self, logic_graph: LogicGraph) -> AnalogicalMapping:
        """
        Analyzes a LogicGraph and returns 4-layer analogical decomposition.
        
        Args:
            logic_graph: The story's logic graph
            
        Returns:
            AnalogicalMapping with entity archetypes, action patterns, structure, and emotional arc
        """
        print(f"MapperAgent: Analyzing LogicGraph with {len(logic_graph.nodes)} nodes...")
        logger.info(f"MapperAgent: Starting analogical decomposition...")
        
        # Build prompt with graph structure
        nodes_summary = "\n".join([
            f"- Node {i+1} ({node.id}): {node.action} by {', '.join(node.actors) if node.actors else 'unknown'}"
            for i, node in enumerate(logic_graph.nodes)
        ])
        
        edges_summary = "\n".join([
            f"- {edge.source} -> {edge.target} ({edge.relation})"
            for edge in logic_graph.edges
        ])
        
        prompt = f"""
{self.SYSTEM_PROMPT}

**LOGIC GRAPH TO ANALYZE:**

Nodes:
{nodes_summary}

Edges:
{edges_summary}

Perform the 4-layer decomposition and return the AnalogicalMapping.
"""
        
        try:
            print("MapperAgent: Sending request to Gemini...")
            logger.info("MapperAgent: Calling Gemini for analogical mapping...")
            
            result = await gemini_client.generate_structured(
                prompt=prompt,
                response_model=AnalogicalMapping
            )
            
            print(f"MapperAgent: Identified {len(result.entity_archetypes)} archetypes, {len(result.action_patterns)} patterns")
            logger.info(f"MapperAgent: Completed. Structure: {result.structure_type}, Archetypes: {len(result.entity_archetypes)}")
            
            return result
            
        except Exception as e:
            print(f"!!! MAPPER FAILED: {e} !!!")
            logger.error(f"MapperAgent failed: {e}")
            raise e

# Export singleton instance
mapper = MapperAgent()
