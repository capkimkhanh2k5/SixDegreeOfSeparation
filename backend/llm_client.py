import os
import json
import re
import asyncio
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# =============================================================================
# CONFIGURATION
# =============================================================================

# Model Hierarchy - VERIFIED WORKING MODELS (sorted by latency)
# Tested on 2025-12-08 with check_models.py
MODELS = [
    # Fast Gemini models
    "gemini-flash-lite-latest",              # 929ms  - Fastest!
    "gemini-2.5-flash-lite-preview-09-2025", # 2770ms
    "gemini-2.5-flash-lite",                 # 4468ms
    
    # Gemma models (good quality)
    "gemma-3-27b-it",                        # 1168ms
    "gemma-3n-e4b-it",                       # 1233ms
    "gemma-3n-e2b-it",                       # 1844ms
    "gemma-3-1b-it",                         # 2043ms
    "gemma-3-4b-it",                         # 3683ms
    
    # Specialty models
    "gemini-robotics-er-1.5-preview",        # 1402ms
    
    # Excluded: gemma-3-12b-it (62129ms - too slow)
]

# Load API Keys from environment (comma-separated)
api_keys_string = os.getenv("GEMINI_API_KEYS", "")
API_KEYS = [key.strip() for key in api_keys_string.split(",") if key.strip()]

if not API_KEYS:
    print("[LLM_CLIENT] ⚠️ WARNING: No API Keys found. Set GEMINI_API_KEYS in .env")

# =============================================================================
# CORE HELPER: Smart LLM Call with 2-Layer Fallback
# =============================================================================

async def call_llm_with_fallback(
    prompt: str,
    operation_name: str = "LLM Call"
) -> Optional[str]:
    """
    2-Layer Fallback Strategy:
    - Outer Loop: Iterate through MODELS (flash → pro → 1.0-pro)
    - Inner Loop: For each model, try ALL API keys before giving up
    
    Returns the response text or None if all attempts fail.
    """
    if not API_KEYS:
        print(f"[LLM_CLIENT] ❌ No API keys available for {operation_name}")
        return None
    
    for model_name in MODELS:
        # Try all keys for this model
        for key_index, api_key in enumerate(API_KEYS):
            try:
                # Configure with current key
                genai.configure(api_key=api_key)
                
                model = genai.GenerativeModel(model_name)
                response = await model.generate_content_async(prompt)
                
                # Check for empty response
                if not response.candidates or not response.candidates[0].content.parts:
                    print(f"[LLM_CLIENT] ⚠️ Empty response from {model_name} (Key {key_index})")
                    continue
                
                # Success!
                return response.text
                
            except Exception as e:
                error_str = str(e).lower()
                
                # Rate limit / Quota error - try next key
                if "429" in str(e) or "quota" in error_str or "resource" in error_str:
                    print(f"[LLM_CLIENT] ⚠️ Rate limit on {model_name} (Key {key_index}). Trying next key...")
                    await asyncio.sleep(0.5)  # Brief pause
                    continue
                
                # Model not found or unavailable - skip to next model
                elif "not found" in error_str or "unavailable" in error_str or "does not exist" in error_str:
                    print(f"[LLM_CLIENT] ⚠️ Model {model_name} unavailable. Skipping to next model...")
                    break  # Exit inner loop, try next model
                
                # Other errors - log and try next key
                else:
                    print(f"[LLM_CLIENT] ❌ Error on {model_name} (Key {key_index}): {e}")
                    continue
        
        # All keys exhausted for this model
        print(f"[LLM_CLIENT] 🔄 All keys exhausted on {model_name}. Falling back to next model...")
    
    # All models and keys exhausted
    print(f"[LLM_CLIENT] ❌ CRITICAL: All models and keys exhausted for {operation_name}")
    return None

# =============================================================================
# API FUNCTIONS (Keep signatures compatible with existing code)
# =============================================================================

def generate_extraction_prompt(wiki_text: str, subject_name: str) -> str:
    """Generates the prompt for entity extraction."""
    return f"""
    You are an expert Entity Relation Extraction system for a "Six Degrees of Separation" algorithm.
    Your task is to analyze a section of a Wikipedia article about the subject: "{subject_name}".

    ### GOAL
    Extract a list of unique people mentioned in the text who have a **factual, direct, and mutual connection** with "{subject_name}".

    ### STRICT FILTERING RULES (CRITICAL)
    1. **INCLUDE (Valid Connections):**
       - Family members (spouse, parents, children, siblings).
       - Professional associates with DIRECT interaction (co-stars, co-founders, direct rivals, coach/student).
       - Historical interactions (signed a treaty with, battled against, succeeded/preceded in office).
    
    2. **EXCLUDE (Invalid/Noise):**
       - **Meta-pages (CRITICAL):** Do NOT extract "List of...", "Category:...", "Template:...", "User:...", "Talk:...".
       - **Dates/Years:** Do not extract simple years (e.g., "2024") unless it's a specific event (e.g., "2024 Election").
       - **Comparisons:** "He is often compared to [Person B]".
       - **Inspirations (Passive):** "He was inspired by [Person D]" (unless they actually met).
       - **Fictional Characters:** Do not extract characters played by the subject.
       - **The Subject Themselves:** Do not include "{subject_name}" in the output.

    ### INPUT TEXT
    {wiki_text}

    ### OUTPUT FORMAT
    Return ONLY a raw JSON object (no markdown, no explanations) with this structure:
    {{
        "connections": [
            {{
                "name": "Name of Person",
                "relationship": "Brief description (e.g., 'Wife', 'Co-founder', 'Opponent')",
                "confidence_reason": "Why is this a direct connection and not a comparison?"
            }}
        ]
    }}
    """


async def extract_relations(wiki_text: str, subject_name: str) -> List[str]:
    """
    Extracts related people from the given text using Gemini.
    Uses 2-layer fallback (models + keys).
    """
    if not API_KEYS:
        return []

    prompt = generate_extraction_prompt(wiki_text, subject_name)
    
    response_text = await call_llm_with_fallback(prompt, f"extract_relations({subject_name})")
    
    if not response_text:
        return []
    
    try:
        # Parse JSON from response
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            connections = data.get("connections", [])
            return [item["name"] for item in connections if "name" in item]
        
        # Fallback: try direct parse
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.startswith("```"):
            cleaned = cleaned[3:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        data = json.loads(cleaned)
        connections = data.get("connections", [])
        return [item["name"] for item in connections if "name" in item]
        
    except Exception as e:
        print(f"[LLM_CLIENT] Error parsing extraction response: {e}")
        return []


async def verify_relations(wiki_text: str, subject_name: str, target_name: str, candidates: List[str]) -> List[Dict[str, Any]]:
    """
    Verifies candidates using LLM.
    Uses 2-layer fallback.
    """
    if not API_KEYS or not candidates:
        return []

    candidates_subset = candidates[:100]
    candidates_str = ", ".join([f'"{c}"' for c in candidates_subset])
    context_text = wiki_text[:5000]

    prompt = f"""
    ### ROLE
    You are the core engine of a "Six Degrees of Separation" algorithm. Your goal is to find a factual path from "{subject_name}" to "{target_name}".
    
    ### INPUT DATA
    - **Current Subject:** "{subject_name}"
    - **Target Person:** "{target_name}"
    - **Candidate Links:** [{candidates_str}]
    - **Context Text:** "{context_text}"

    ### TASK
    Analyze the "Candidate Links" and determine if they have a **factual, direct connection** to the "Current Subject".
    
    **RANKING INSTRUCTION:**
    Rank valid candidates based on how likely they are to lead to the "Target Person" ("{target_name}").

    ### FILTERING RULES (STRICT)
    1. INCLUDE: Family, professional associates, historical interactions
    2. EXCLUDE: Meta-pages, dates, comparisons, inspirations, fictional characters

    ### OUTPUT FORMAT
    Return ONLY valid JSON. Sort valid_candidates by relevance (most relevant first).
    {{
        "valid_candidates": [
            {{
                "name": "Exact Name from List",
                "type": "Brief reason",
                "is_bridge": true/false
            }}
        ]
    }}
    """

    response_text = await call_llm_with_fallback(prompt, f"verify_relations({subject_name})")
    
    if not response_text:
        return []
    
    try:
        match = re.search(r'\{.*\}', response_text, re.DOTALL)
        if match:
            data = json.loads(match.group(0))
            return data.get("valid_candidates", [])
        
        cleaned = response_text.strip()
        if cleaned.startswith("```json"):
            cleaned = cleaned[7:]
        if cleaned.endswith("```"):
            cleaned = cleaned[:-3]
        
        data = json.loads(cleaned)
        return data.get("valid_candidates", [])
        
    except Exception as e:
        print(f"[LLM_CLIENT] Error parsing verification response: {e}")
        return []


# Alias for compatibility
verify_candidates_with_llm = verify_relations


async def generate_relationship_context(person1: str, person2: str) -> str:
    """
    Generates a brief description of the relationship between two people.
    Uses 2-layer fallback.
    """
    if not API_KEYS:
        return "Connected"

    prompt = f"""
    ### TASK
    Explain the specific, factual connection between "{person1}" and "{person2}" in one short sentence.
    
    ### EXAMPLES
    - "Co-starred in the movie 'Pulp Fiction'."
    - "Both served as US Senators from Illinois."
    - "Signed the Paris Peace Accords together."
    - "Married from 1990 to 2005."
    
    ### OUTPUT
    Return ONLY the sentence. No intro, no quotes.
    """

    response_text = await call_llm_with_fallback(prompt, f"context({person1}->{person2})")
    
    if response_text:
        return response_text.strip()
    
    return "Connected via Wikipedia"


# =============================================================================
# INITIALIZATION
# =============================================================================

if API_KEYS:
    print(f"[LLM_CLIENT] ✅ Initialized with {len(API_KEYS)} API keys and {len(MODELS)} model fallbacks")
    print(f"[LLM_CLIENT] 📋 Model hierarchy: {' → '.join(MODELS)}")
