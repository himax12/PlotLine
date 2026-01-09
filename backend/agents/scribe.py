from backend.utils.gemini_client import gemini_client
from backend.models.schemas import NarrativeNode, NarrativeMemory, ReasoningMixin
from pydantic import BaseModel, Field
import logging

logger = logging.getLogger(__name__)

# Define a specific output model for Scribe to ensure it captures reasoning + prose
class ScribeOutput(ReasoningMixin):
    prose: str = Field(..., description="The rendered prose for this story beat (approx 200 words).")

class ScribeAgent:
    """
    Agent responsible for rendering a single NarrativeNode into prose.
    Uses context from NarrativeMemory to ensure coherence.
    """
    
    SYSTEM_PROMPT = """
You are the SCRIBE - a master storyteller.
Your goal is to render a single logical event into vivid, engaging prose.
Do not advance the plot beyond this single event.

Instructions:
1. Read the Current Event (Node) and the Previous Context.
2. Adopt the target style/genre.
3. Write approximately {{words}} words covering ONLY this event.
4. EXTREMELY IMPORTANT: Provide a `reasoning` trace first. Explain how you are bridging from the last paragraph, what sensory details you are adding, and why.
"""

    async def run(
        self, 
        node: NarrativeNode, 
        memory: NarrativeMemory,
        target_genre: str = "General Fiction",
        target_audience: str = "General",
        tone: str = "Neutral",
        words_per_scene: int = 200,
        safety_level: str = "none"
    ) -> str:
        """
        Generates prose for a node.
        Returns the prose string.
        """
        print(f"\n📝 === SCRIBE AGENT STARTED ===")
        print(f"   Node ID: {node.id}")
        print(f"   Action: {node.action}")
        print(f"   Genre: {target_genre}")
        print(f"   🎯 Target Words: {words_per_scene}")
        print(f"   🛡️ Safety: {safety_level}")
        
        logger.info(f"Scribe running. Genre: {target_genre}, Audience: {target_audience}, Tone: {tone}")
        prompt = f"""
{self.SYSTEM_PROMPT.replace('{{words}}', str(words_per_scene))}

TARGET GENRE: {target_genre}
TARGET AUDIENCE: {target_audience}
TONE: {tone}
WORD COUNT TARGET: ~{words_per_scene} words

CONTEXT:
- Running Summary: {memory.running_summary}
- Last Paragraph: {memory.last_paragraph}
- Entity Registry: {memory.entity_registry}

CURRENT EVENT (Node ID: {node.id}):
- Action: {node.action}
- Actors: {', '.join(node.actors)}
- Preconditions: {node.preconditions}
- Postconditions: {node.postconditions}

Write the prose for ONLY this event. ~{words_per_scene} words.
"""
        try:
            # TRANSPARENCY: Log the prompt for debugging
            print(f"📝 SCRIBE PROMPT for node {node.id}:")
            print(f"   Genre: {target_genre}, Audience: {target_audience}, Tone: {tone}")
            print(f"   Action: {node.action}")
            print(f"   Actors: {node.actors}")
            print(f"   Target words: {words_per_scene}")
            
            logger.info(f"Scribe: Generating prose for node {node.id}...")
            
            # Call Gemini for prose
            response = await gemini_client.generate_structured(
                prompt=prompt,
                response_model=ScribeOutput,
                safety_level=safety_level
            )
            
            # TRANSPARENCY: Show what was generated
            print(f"✅ Scribe: Generated {len(response.prose.split())} words.")
            print(f"   First 100 chars: {response.prose[:100]}...")
            
            logger.info(f"Scribe: Successfully generated {len(response.prose.split())} words.")
            return response.prose
        except Exception as e:
            print(f"!!! SCRIBE FAILED: {e} !!!")
            logger.error(f"Scribe failed for node {node.id}: {e}")
            raise e

scribe = ScribeAgent()
