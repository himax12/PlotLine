from typing import TypedDict, List, Annotated
import operator
import logging

logger = logging.getLogger(__name__)

from langgraph.graph import StateGraph, END
from langgraph.checkpoint.memory import MemorySaver

from backend.models.schemas import StoryState, NarrativeNode, NarrativeMemory
from backend.agents.deconstructor import deconstructor
from backend.agents.scribe import scribe
from backend.agents.mapper import mapper  # Phase 2
from backend.agents.oracle import oracle  # Phase 2

# We need a state compatible with LangGraph
# StoryState is our Pydantic model, but LangGraph usually likes TypedDict or Pydantic.
# Let's use StoryState as the state.

class GraphState(TypedDict):
    """
    LangGraph State Container.
    Wraps our main Pydantic StoryState to ensure compatibility.
    """
    story_state: StoryState
    current_node_index: int # specialized for the render loop

# --- Nodes ---

async def node_deconstruct(state: GraphState):
    """Node: Turn raw text into LogicGraph."""
    try:
        text = state["story_state"].input_text
        print(f"--- WORKFLOW NODE: DECONSTRUCT ---")
        print(f"Input: {text[:50]}...")
        logger.info(f"Workflow: Starting Deconstruction for input: {text[:50]}...")
        
        # Run Agent
        logic_graph = await deconstructor.run(text)
        print(f"Deconstruction returned graph with {len(logic_graph.nodes)} nodes.")
        logger.info(f"Workflow: Deconstruction complete. LogicGraph has {len(logic_graph.nodes)} nodes.")
        
        # Update State
        state["story_state"].graph = logic_graph
        # Reset index for rendering
        return {"story_state": state["story_state"], "current_node_index": 0}
    except Exception as e:
        print(f"!!! DECONSTRUCT NODE ERROR: {e} !!!")
        logger.error(f"Workflow: Deconstruction Node Failed: {e}")
        raise e

async def node_scribe(state: GraphState):
    """Node: Render one logic node into prose."""
    try:
        idx = state["current_node_index"]
        story = state["story_state"]
        nodes = story.graph.nodes
        
        if idx >= len(nodes):
            # Should be handled by conditional edge, but safety check
            print(f"Scribe called with idx {idx} >= len(nodes) {len(nodes)}. Returning empty.")
            logger.warning("Workflow: Scribe node called but index >= nodes length. Returning empty.")
            return {}
            
        current_node = nodes[idx]
        print(f"--- WORKFLOW NODE: SCRIBE ({idx+1}/{len(nodes)}) ---")
        print(f"Processing Node ID: {current_node.id}")
        logger.info(f"Workflow: Processing Node {idx+1}/{len(nodes)} (ID: {current_node.id})...")
        
        # Run Agent
        prose_chunk = await scribe.run(
            node=current_node,
            memory=story.memory,
            target_genre=story.target_genre,
            target_audience=story.target_audience,
            tone=story.tone,
            words_per_scene=story.words_per_scene,
            safety_level=story.safety_level
        )
        
        # Update State (Rendered Chunk)
        story.rendered_chunks[current_node.id] = prose_chunk
        
        # Update Memory (Simple Append for Phase 1)
        # Real implementation needs Summarizer Agent here
        story.memory.last_paragraph = prose_chunk
        story.memory.running_summary += f"\n{prose_chunk}" 
        
        return {"story_state": story, "current_node_index": idx + 1}
    except Exception as e:
        print(f"!!! SCRIBE NODE ERROR: {e} !!!")
        logger.error(f"Workflow: Scribe Node Failed: {e}")
        raise e

# --- Phase 2 Nodes ---

async def node_map(state: GraphState):
    """Node: Perform 4-layer analogical decomposition."""
    try:
        print("--- WORKFLOW NODE: MAP ---")
        logger.info("Workflow: Starting analogical mapping...")
        
        # Run MapperAgent
        mapping = await mapper.run(state["story_state"].graph)
        print(f"Mapper: Structure={mapping.structure_type}, Archetypes={len(mapping.entity_archetypes)}")
        logger.info(f"Workflow: Mapping complete. Structure: {mapping.structure_type}")
        
        # Update State
        state["story_state"].analogical_mapping = mapping
        return {"story_state": state["story_state"]}
    except Exception as e:
        print(f"!!! MAP NODE ERROR: {e} !!!")
        logger.error(f"Workflow: Map Node Failed: {e}")
        raise e

async def node_validate(state: GraphState):
    """Node: Validate story consistency (Tier 1 + Tier 2)."""
    try:
        print("--- WORKFLOW NODE: VALIDATE ---")
        logger.info("Workflow: Starting validation...")
        
        # Tier 1: Symbolic validation
        print("Oracle: Running Tier 1 (Symbolic)...")
        symbolic_result = await oracle.validate_symbolic(
            state["story_state"].graph,
            state["story_state"].world_state
        )
        state["story_state"].validation_results.append(symbolic_result)
        
        # Tier 2: Commonsense validation (optional, can be disabled for speed)
        # Uncomment to enable Tier 2:
        # print("Oracle: Running Tier 2 (Commonsense)...")
        # commonsense_result = await oracle.validate_commonsense(state["story_state"].graph)
        # state["story_state"].validation_results.append(commonsense_result)
        
        is_valid = all(r.is_valid for r in state["story_state"].validation_results)
        print(f"Validation: {'PASSED' if is_valid else 'FAILED'}")
        logger.info(f"Workflow: Validation complete. Valid: {is_valid}")
        
        return {"story_state": state["story_state"]}
    except Exception as e:
        print(f"!!! VALIDATE NODE ERROR: {e} !!!")
        logger.error(f"Workflow: Validate Node Failed: {e}")
        raise e

# --- Conditional Logic ---

def should_continue_scribing(state: GraphState):
    """Conditional Edge: Loop Scribe until all nodes are done."""
    idx = state["current_node_index"]
    total = len(state["story_state"].graph.nodes)
    
    if idx < total:
        return "scribe"
    return END

# --- Graph Definition ---

workflow = StateGraph(GraphState)

workflow.add_node("deconstruct", node_deconstruct)
workflow.add_node("map", node_map)  # Phase 2
workflow.add_node("validate", node_validate)  # Phase 2
workflow.add_node("scribe", node_scribe)

# Set Entry Point
workflow.set_entry_point("deconstruct")

# Edges
# Phase 2 Flow: DECONSTRUCT -> MAP -> VALIDATE -> SCRIBE_LOOP -> END
workflow.add_edge("deconstruct", "map")
workflow.add_edge("map", "validate")
workflow.add_edge("validate", "scribe")
workflow.add_conditional_edges(
    "scribe",
    should_continue_scribing,
    {
        "scribe": "scribe",
        END: END
    }
)

# Compilation
# Using MemorySaver for in-memory Checkpointing (Phase 1)
checkpointer = MemorySaver()
app_graph = workflow.compile(checkpointer=checkpointer)
