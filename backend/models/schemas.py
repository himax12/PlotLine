from typing import List, Dict, Any, Optional
from pydantic import BaseModel, Field
import uuid

# --- Sub-Problem 9: Reasoning Visibility ---
class ReasoningMixin(BaseModel):
    """Mixin to add Thinking Process visibility to any model."""
    reasoning: str = Field(
        ..., 
        description="Internal monologue explaining the why. Step-by-step reasoning."
    )

    # Removed alias="_reasoning" to avoid schema issues with Gemini.
    # We will update prompts to ask for "reasoning".

# --- Sub-Problem 1: 3-Layer Memory ---

class NarrativeMemory(BaseModel):
    """Layer 3: Rolling Context for Coherence"""
    running_summary: str = Field(default="", description="High-level plot summary")
    last_paragraph: str = Field(default="", description="Verbatim last rendered text")
    style_guide: str = Field(default="", description="Current tone/style instructions")
    critical_facts: List[str] = Field(default_factory=list, description="Facts that must never be forgotten")
    entity_registry: Dict[str, str] = Field(default_factory=dict, description="Canonical entity names (id -> name)")

class WorldState(BaseModel):
    """Layer 2: Entity State Tracking"""
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Global variables (e.g. time, location)")
    # LogicGraph is layer 1

# --- Core Logic Graph ---

class NarrativeNode(ReasoningMixin):
    """A single atomic unit of story logic."""
    # We make ID optional or required. Let's make it required for Gemini to generate unique IDs.
    id: str = Field(..., description="Unique UUID for this node")
    action: str = Field(..., description="The core action verb (e.g., 'Arrive', 'Betray')")
    actors: List[str] = Field(default_factory=list, description="Entities involved")
    preconditions: List[str] = Field(default_factory=list, description="What must be true before this")
    postconditions: List[str] = Field(default_factory=list, description="What becomes true after this")
    
    # Removing model_config extra ignore to be safe
    model_config = {
        "extra": "ignore" 
    }

    model_config = {
        "extra": "ignore" 
    }

class NarrativeEdge(BaseModel):
    """A directed edge between narrative nodes."""
    source: str = Field(..., description="ID of the source node")
    target: str = Field(..., description="ID of the target node")
    relation: str = Field(default="next", description="Type of relationship (e.g. 'causes', 'then')")

class LogicGraph(BaseModel):
    nodes: List[NarrativeNode] = Field(default_factory=list, description="List of all narrative events")
    edges: List[NarrativeEdge] = Field(default_factory=list, description="List of connections between events")

# --- Phase 2: Analogical Mapping ---

class EntityArchetype(BaseModel):
    """Mapping of an entity to its archetypal role"""
    entity_name: str = Field(..., description="Name of the entity/character")
    archetype: str = Field(..., description="Archetypal role (e.g., 'Hero', 'Mentor', 'Shadow')")

class AnalogicalMapping(ReasoningMixin):
    """Output from MapperAgent - 4-layer analogical decomposition"""
    entity_archetypes: List[EntityArchetype] = Field(default_factory=list, description="Entity to archetype mappings")
    action_patterns: List[str] = Field(default_factory=list, description="Identified plot patterns (e.g., 'Quest', 'Betrayal')")
    structure_type: str = Field(default="Unknown", description="Overall narrative structure (e.g., 'Three-Act', 'Hero's Journey')")
    emotional_arc: List[str] = Field(default_factory=list, description="Emotional trajectory (e.g., ['Hope', 'Despair', 'Redemption'])")

# --- Phase 2: Validation ---

class ValidationViolation(BaseModel):
    """A single validation violation found by OracleAgent"""
    violation_type: str = Field(..., description="Type: 'precondition', 'temporal', 'commonsense'")
    description: str = Field(..., description="Human-readable explanation of the violation")
    node_id: Optional[str] = Field(default=None, description="ID of the node where violation occurred")
    severity: str = Field(default="error", description="Severity level: 'error' or 'warning'")

class ValidationResult(ReasoningMixin):
    """Output from OracleAgent - validation results"""
    is_valid: bool = Field(..., description="Overall validation status")
    violations: List[ValidationViolation] = Field(default_factory=list, description="List of violations found")
    suggestions: List[str] = Field(default_factory=list, description="Suggested fixes for violations")

# --- State Object (The Source of Truth) ---

class StoryState(BaseModel):
    """Complete state object passed between LangGraph nodes."""
    input_text: str = ""
    target_genre: str = ""
    target_audience: str = "General"
    tone: str = "Neutral"
    
    # Phase 3a: User Controls
    words_per_scene: int = 200  # User-configurable word count target
    safety_level: str = "none"  # Content filtering: "none", "low", "medium", "high"
    
    graph: LogicGraph = Field(default_factory=LogicGraph)
    world_state: WorldState = Field(default_factory=WorldState)
    memory: NarrativeMemory = Field(default_factory=NarrativeMemory)
    rendered_chunks: Dict[str, str] = Field(default_factory=dict, description="Node ID -> Prose mapping")
    error_logs: List[str] = Field(default_factory=list)
    
    # Phase 2: Intelligence
    analogical_mapping: Optional[AnalogicalMapping] = Field(default=None, description="4-layer analogical analysis")
    validation_results: List[ValidationResult] = Field(default_factory=list, description="Validation results from OracleAgent")
    
    # Guardrails: Input/Output Safety
    input_guardrail_result: Optional[Any] = Field(default=None, description="Input validation result from GuardrailAgent")
    output_guardrail_results: List[Any] = Field(default_factory=list, description="Output validation results per chunk")
    
    # Checkpointing is handled by LangGraph natively, but we can store explicit snapshots if needed.
