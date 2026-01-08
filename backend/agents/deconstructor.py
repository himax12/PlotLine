from backend.utils.gemini_client import gemini_client
from backend.models.schemas import LogicGraph, NarrativeNode
from typing import List
import logging

logger = logging.getLogger(__name__)

class DeconstructorAgent:
    """
    Agent responsible for breaking down raw source text into a structured LogicGraph.
    Uses Gemini 2.5 Pro to identify atomic events, entities, and causality.
    """
    
    SYSTEM_PROMPT = """
You are the DECONSTRUCTOR - an expert narratologist.
Your goal is to perform diverse "lossy compression" on a story.
Convert the prose into a directed graph of atomic events (NarrativeNodes).

Instructions:
1. Identify key events that drive the plot forward.
2. For each event, identify the Actors, Action, Preconditions, and Postconditions.
3. EXTREMELY IMPORTANT: Provide a detailed `reasoning` step before the final output. 
   Explain your thought process: specific sentences you focused on, why you chose specific verbs, and how you linked events.
4. Normalize entities (e.g., "The Boy" -> "Hero").

Output must strictly follow the LogicGraph schema.
"""

    async def run(self, source_text: str) -> LogicGraph:
        """
        Extracts logic graph from text.
        """
        logger.info(f"Deconstructor running on text: {source_text[:50]}...")
        prompt = f"""
{self.SYSTEM_PROMPT}

SOURCE TEXT:
{source_text}
"""
        # We ask Gemini to return a LogicGraph directly
        try:
            print("Deconstructor: Sending prompt to Gemini...")
            logger.info("Deconstructor: Sending request to Gemini...")
            result = await gemini_client.generate_structured(
                prompt=prompt,
                response_model=LogicGraph
            )
            print(f"Deconstructor: Gemini returned {len(result.nodes)} nodes.")
            logger.info(f"Deconstructor: Successfully generated {len(result.nodes)} nodes and {len(result.edges)} edges.")
            return result
        except Exception as e:
            print(f"!!! DECONSTRUCTOR FAILED: {e} !!!")
            logger.error(f"Deconstructor failed: {e}")
            raise e

deconstructor = DeconstructorAgent()
