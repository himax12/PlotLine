"""
DYNAMIC Copyright Guardrail (Uses Gemini for Detection)

NO HARDCODED LISTS - Truly dynamic detection using AI

Strategy:
- Use Gemini API ONLY for copyright checking (minimal cost)
- AI can detect ANY copyrighted work without hardcoded lists
- Cache results to minimize API calls
- Falls back to basic checks if API unavailable
"""

import logging
import re
from typing import List, Optional
from enum import Enum
from pydantic import BaseModel, Field
import json
import hashlib

logger = logging.getLogger(__name__)


# ============================================================================
# Data Models
# ============================================================================

class ViolationType(str, Enum):
    """Types of content violations"""
    COPYRIGHT = "copyright"
    DERIVATIVE_WORK = "derivative_work"


class RiskLevel(str, Enum):
    """Risk severity levels"""
    SAFE = "safe"
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class ContentViolation(BaseModel):
    """A single detected violation"""
    violation_type: ViolationType
    severity: RiskLevel
    description: str
    confidence: float = 0.0
    matched_elements: List[str] = Field(default_factory=list)


class GuardrailResult(BaseModel):
    """Result from guardrail validation"""
    is_safe: bool
    overall_risk: RiskLevel
    violations: List[ContentViolation] = Field(default_factory=list)
    reasoning: str
    transformation_hint: Optional[str] = None


class CopyrightCheckResponse(BaseModel):
    """AI response for copyright check"""
    is_copyrighted: bool
    risk_level: str  # "safe", "low", "medium", "high"
    detected_works: List[str] = Field(default_factory=list)
    reasoning: str
    is_reproduction_attempt: bool = False


# ============================================================================
# Dynamic Copyright Detector
# ============================================================================

class DynamicCopyrightGuardrail:
    """
    Truly dynamic copyright detection with ZERO HARDCODED LISTS.
    
    Uses Gemini AI to detect copyrighted content by reasoning about:
    - Character names from any franchise
    - Plot structures from any book/movie/show
    - Reproduction attempts of any copyrighted work
    
    Features:
    - NO hardcoded character lists
    - NO hardcoded concept patterns
    - AI analyzes intent and content dynamically
    - Caches results to minimize API costs
    """
    
    def __init__(self):
        """Initialize dynamic copyright detector"""
        self.cache = {}  # Simple in-memory cache
        
        # Only import Gemini if available
        try:
            from backend.utils.gemini_client import gemini_client
            self.gemini = gemini_client
            self.gemini_available = True
            print("🛡️  Dynamic Copyright Guardrail loaded (Gemini-powered)")
            print("   Can detect ANY copyrighted work without hardcoded lists")
        except ImportError:
            self.gemini = None
            self.gemini_available = False
            print("⚠️  Gemini not available - using fallback basic checks only")
        
        # Fallback: only check for explicit reproduction keywords (minimal hardcoding)
        self.reproduction_keywords = [
            "retell", "reproduce", "rewrite", "copy", "summarize",
            "chapter by chapter", "scene by scene", "recreate", "transcribe"
        ]
    
    def validate_input(self, user_input: str) -> GuardrailResult:
        """
        Dynamic copyright validation using AI
        
        The AI analyzes the input and determines:
        1. Is this asking to reproduce copyrighted content?
        2. Does this reference specific copyrighted characters/works?
        3. Is this a derivative of a copyrighted work?
        """
        print(f"\n🛡️ === DYNAMIC COPYRIGHT CHECK (INPUT) ===")
        print(f"   Analyzing: {user_input[:100]}...")
        
        # Check cache first
        cache_key = self._get_cache_key(user_input)
        if cache_key in self.cache:
            print("   ✅ Using cached result")
            return self.cache[cache_key]
        
        # Use AI detection if available
        if self.gemini_available:
            result = self._ai_copyright_check(user_input, is_input=True)
        else:
            result = self._fallback_check(user_input)
        
        # Cache the result
        self.cache[cache_key] = result
        
        print(f"   Risk Level: {result.overall_risk}")
        print(f"   Violations: {len(result.violations)}")
        
        return result
    
    def validate_output(self, generated_text: str, original_prompt: str) -> GuardrailResult:
        """
        Validate generated output for copyright elements
        """
        print(f"\n🛡️ === DYNAMIC COPYRIGHT CHECK (OUTPUT) ===")
        print(f"   Analyzing {len(generated_text)} characters...")
        
        # Check cache
        cache_key = self._get_cache_key(generated_text)
        if cache_key in self.cache:
            print("   ✅ Using cached result")
            return self.cache[cache_key]
        
        # Use AI detection
        if self.gemini_available:
            result = self._ai_copyright_check(generated_text, is_input=False)
        else:
            result = self._fallback_check(generated_text)
        
        # Cache the result
        self.cache[cache_key] = result
        
        print(f"   Risk Level: {result.overall_risk}")
        
        return result
    
    def _ai_copyright_check(self, text: str, is_input: bool = True) -> GuardrailResult:
        """
        Use Gemini AI to dynamically detect copyrighted content
        WITHOUT any hardcoded lists
        """
        
        prompt = f"""You are a copyright compliance expert. Analyze this {'user input' if is_input else 'generated text'} for copyright violations.

ANALYZE FOR:
1. **Reproduction Attempts**: Is the user asking to reproduce/retell a specific copyrighted book, movie, TV show, or game?
2. **Character Names**: Does it reference specific characters from copyrighted franchises? (e.g., Harry Potter, Star Wars, Marvel, DC, Game of Thrones, etc.)
3. **Distinctive Elements**: Does it use unique settings, objects, or concepts from copyrighted works? (e.g., Hogwarts, lightsaber, Westeros, etc.)
4. **Plot Structure**: Does it ask to recreate a specific copyrighted plot or storyline?

INPUT TO ANALYZE:
```
{text}
```

IMPORTANT DISTINCTIONS:
- ✅ SAFE: Generic archetypes ("wizard story", "space adventure", "dystopian future")
- ⚠️ MEDIUM: References copyrighted work for inspiration ("story like Harry Potter but different")
- ❌ HIGH: Explicit reproduction ("retell chapter 1 of Harry Potter") or uses multiple specific copyrighted elements

Return ONLY valid JSON matching this schema:
{{
    "is_copyrighted": true/false,
    "risk_level": "safe" | "low" | "medium" | "high",
    "detected_works": ["list of detected copyrighted works"],
    "reasoning": "explain your analysis",
    "is_reproduction_attempt": true/false
}}
"""
        
        try:
            # Call Gemini API for dynamic detection
            import asyncio
            response = asyncio.run(self.gemini.generate_structured(
                prompt=prompt,
                response_model=CopyrightCheckResponse,
                temperature=0.0  # Deterministic
            ))
            
            # Convert AI response to GuardrailResult
            violations = []
            
            if response.is_copyrighted:
                violations.append(ContentViolation(
                    violation_type=ViolationType.COPYRIGHT if response.is_reproduction_attempt else ViolationType.DERIVATIVE_WORK,
                    severity=RiskLevel[response.risk_level.upper()],
                    description=response.reasoning,
                    confidence=1.0 if response.is_reproduction_attempt else 0.8,
                    matched_elements=response.detected_works
                ))
            
            # Build result
            risk_level = RiskLevel[response.risk_level.upper()]
            is_safe = risk_level in [RiskLevel.SAFE, RiskLevel.LOW]
            
            hint = None
            if risk_level == RiskLevel.MEDIUM:
                hint = "Transform into original content: change character names, settings, and specific plot details while keeping archetypal story structure"
            
            return GuardrailResult(
                is_safe=is_safe,
                overall_risk=risk_level,
                violations=violations,
                reasoning=response.reasoning,
                transformation_hint=hint
            )
            
        except Exception as e:
            logger.error(f"AI copyright check failed: {e}")
            # Fallback to basic check
            return self._fallback_check(text)
    
    def _fallback_check(self, text: str) -> GuardrailResult:
        """
        Minimal fallback check if Gemini unavailable
        Only checks for explicit reproduction keywords
        """
        text_lower = text.lower()
        
        # Check for explicit reproduction keywords
        for keyword in self.reproduction_keywords:
            if keyword in text_lower:
                return GuardrailResult(
                    is_safe=False,
                    overall_risk=RiskLevel.HIGH,
                    violations=[
                        ContentViolation(
                            violation_type=ViolationType.COPYRIGHT,
                            severity=RiskLevel.HIGH,
                            description=f"Explicit reproduction keyword detected: '{keyword}'",
                            confidence=1.0
                        )
                    ],
                    reasoning=f"Contains reproduction keyword '{keyword}' - likely attempting to reproduce copyrighted content"
                )
        
        # If no obvious keywords, assume safe (can't detect without AI)
        return GuardrailResult(
            is_safe=True,
            overall_risk=RiskLevel.SAFE,
            violations=[],
            reasoning="No explicit reproduction keywords detected (AI analysis unavailable for deeper check)"
        )
    
    def _get_cache_key(self, text: str) -> str:
        """Generate cache key from text hash"""
        return hashlib.md5(text.encode()).hexdigest()


# Export singleton instance
guardrail = DynamicCopyrightGuardrail()
