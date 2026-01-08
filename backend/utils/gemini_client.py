import asyncio
import time
import typing
from typing import Type, TypeVar, Optional, Any
from google import genai
from google.genai import types
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
from pydantic import BaseModel
import logging

from backend.config import settings

# Configure logger
logger = logging.getLogger(__name__)

T = TypeVar("T", bound=BaseModel)

# --- Sub-Problem 7: Rate Limiter (Token Bucket) ---

class TokenBucket:
    """
    Async Token Bucket Rate Limiter.
    Ensures we don't exceed API quotas (e.g., 15 RPM).
    """
    def __init__(self, capacity: int = 15, refill_rate: float = 0.25):
        """
        Args:
            capacity: Max burst size (tokens).
            refill_rate: Tokens added per second. (15 RPM = 0.25 TPS)
        """
        self.capacity = capacity
        self._tokens = float(capacity)
        self.refill_rate = refill_rate
        self.last_refill = time.monotonic()
        self._lock = asyncio.Lock()

    async def acquire(self):
        """Waits until a token is available."""
        async with self._lock:
            while True:
                now = time.monotonic()
                elapsed = now - self.last_refill
                
                # Refill tokens
                new_tokens = elapsed * self.refill_rate
                if new_tokens > 0:
                    self._tokens = min(self.capacity, self._tokens + new_tokens)
                    self.last_refill = now
                
                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return
                else:
                    # Calculate wait time for 1 token
                    wait_time = (1.0 - self._tokens) / self.refill_rate
                    logger.info(f"Rate Limit: Waiting {wait_time:.2f}s for token...")
                    await asyncio.sleep(wait_time)

# Initialize global limiter (Singleton pattern for the app)
# Use configured rate limit from settings
from backend.config import settings
global_rate_limiter = TokenBucket(
    capacity=settings.GEMINI_RPM_LIMIT, 
    refill_rate=settings.GEMINI_RPM_LIMIT / 60.0
)

logger.setLevel(logging.DEBUG) # Force debug level for now

class GeminiClient:
    def __init__(self):
        # google.genai SDK uses a single Client class (not AsyncClient)
        # Async operations work through async methods on the client
        print(f"Initializing GeminiClient with google.genai SDK...")
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = settings.GEMINI_MODEL
        print(f"GeminiClient initialized. Model: {self.model_name}")
    
    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type(Exception)
    )
    async def generate_structured(
        self, 
        prompt: str, 
        response_model: Type[T],
        temperature: float = 0.7,
        safety_level: str = "none"
    ) -> T:
        """
        Generates content enforcing the Pydantic schema (Native JSON).
        Includes Rate Limiting and Retry logic.
        """
        # 1. Acquire Token (Rate Limit)
        print(f"GeminiClient: Acquiring rate limit token...")
        await global_rate_limiter.acquire()
        print(f"GeminiClient: Token acquired. Calling Gemini API...")
        
        try:
            # 2. Call Gemini with response_schema
            print(f"GeminiClient: Calling generate_content with model={self.model_name}")
            print(f"GeminiClient: Prompt length: {len(prompt)} chars")
            print(f"GeminiClient: Response model: {response_model.__name__}")
            
            # Using genai.Client - the SDK handles async internally
            # Check if there's an agenerate_content or similar async method
            response = await self.client.aio.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_schema=response_model,
                    temperature=temperature,
                    safety_settings=[
                        types.SafetySetting(
                            category="HARM_CATEGORY_HARASSMENT",
                            threshold=settings.SAFETY_PRESETS.get(safety_level, "BLOCK_NONE"),
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_HATE_SPEECH",
                            threshold=settings.SAFETY_PRESETS.get(safety_level, "BLOCK_NONE"),
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                            threshold=settings.SAFETY_PRESETS.get(safety_level, "BLOCK_NONE"),
                        ),
                        types.SafetySetting(
                            category="HARM_CATEGORY_DANGEROUS_CONTENT",
                            threshold=settings.SAFETY_PRESETS.get(safety_level, "BLOCK_NONE"),
                        ),
                    ]
                )
            )
            
            # 3. Parse Output
            print(f"GeminiClient: Response received from Gemini API")
            print(f"GeminiClient: Response type: {type(response)}")
            logger.debug(f"Gemini Response received. Inspecting candidates...")
            
            # Check for candidates
            if not response.candidates:
                print(f"!!! GeminiClient: NO CANDIDATES in response !!!")
                logger.error(f"Gemini returned NO candidates.")
                raise ValueError("Gemini returned no candidates (blocked?)")

            candidate = response.candidates[0]
            print(f"GeminiClient: Found {len(response.candidates)} candidate(s)")

            try:
                print(f"GeminiClient: Extracting text from response...")
                json_text = response.text
                if not json_text:
                    print(f"!!! GeminiClient: response.text is EMPTY !!!")
                    raise ValueError("Empty text in response")
                print(f"GeminiClient: Extracted JSON text (length: {len(json_text)} chars)")
                print(f"GeminiClient: JSON preview: {json_text[:200]}...")
            except Exception as ve:
                print(f"!!! GeminiClient: FAILED to access response.text: {ve} !!!")
                logger.error("Failed to access response.text. The response might be blocked.")
                try:
                    logger.error(f"Safety Ratings: {candidate.safety_ratings}")
                except:
                    pass
                raise ve

            print(f"GeminiClient: Validating JSON against {response_model.__name__}...")
            result = response_model.model_validate_json(json_text)
            print(f"GeminiClient: Validation successful! Returning result.")
            return result
            
        except Exception as e:
            print(f"!!! GeminiClient: CRITICAL ERROR !!!")
            print(f"Error type: {type(e).__name__}")
            print(f"Error message: {e}")
            logger.error(f"CRITICAL GEMINI ERROR in generate_structured: {type(e).__name__}: {e}")
            logger.error(f"Failed Prompt (truncated): {prompt[:1000]}...")
            import traceback
            print(f"Full traceback:")
            traceback.print_exc()
            logger.error(f"Traceback: {traceback.format_exc()}")
            raise e

# Export a default client instance
gemini_client = GeminiClient()
