import os
import json
import google.generativeai as genai
from typing import List, Dict, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Load API Keys from environment variables (comma-separated)
# Example in .env: GEMINI_API_KEYS=key1,key2,key3
api_keys_string = os.getenv("GEMINI_API_KEYS", "")
API_KEYS = [key.strip() for key in api_keys_string.split(",") if key.strip()]

CURRENT_KEY_INDEX = 0

def configure_genai():
    """Configures Gemini with the current API key."""
    global CURRENT_KEY_INDEX
    if not API_KEYS:
        print("ERROR: No API Keys found. Please set GEMINI_API_KEYS in .env file.")
        return
    
    current_key = API_KEYS[CURRENT_KEY_INDEX]
    genai.configure(api_key=current_key)
    print(f"[LLM_CLIENT] Configured with API Key index {CURRENT_KEY_INDEX} (Ends with ...{current_key[-4:]})")

def rotate_api_key():
    """Switches to the next API key in the list."""
    global CURRENT_KEY_INDEX
    CURRENT_KEY_INDEX = (CURRENT_KEY_INDEX + 1) % len(API_KEYS)
    configure_genai()
    print(f"[LLM_CLIENT] ⚠️ Rate Limit Hit. Rotated to API Key index {CURRENT_KEY_INDEX}")

# Initial Configuration
configure_genai()

def generate_extraction_prompt(wiki_text: str, subject_name: str) -> str:
    """
    Generates the prompt for the LLM to extract factual relationships.
    """
    system_prompt = f"""
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
       - **NON-PEOPLE (CRITICAL):** Do NOT extract movies, albums, songs, bands, organizations, places, awards, or events.
       - **Comparisons:** "He is often compared to [Person B]", "She writes like [Person C]".
       - **Inspirations (Passive):** "He was inspired by [Person D]" (unless they actually met).
       - **Name Dropping/Lists:** "He is in the list of Time 100 alongside [Person E]" (unless they interacted).
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
    return system_prompt

async def extract_relations(wiki_text: str, subject_name: str) -> List[str]:
    """
    Extracts related people from the given text using Gemini.
    Returns a list of names.
    """
    if not API_KEYS:
        print("WARNING: No API Keys configured. Returning empty list.")
        return []

    prompt = generate_extraction_prompt(wiki_text, subject_name)
    
    import re
    import time
    
    retries = 0
    max_retries = 5
    base_delay = 2
    
    while retries < max_retries:
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            response = await model.generate_content_async(prompt)
            
            text_response = response.text
            
            # Use regex to find the first JSON object
            match = re.search(r'\{.*\}', text_response, re.DOTALL)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                
                connections = data.get("connections", [])
                names = [item["name"] for item in connections]
                return names
            else:
                # Fallback
                if text_response.startswith("```json"):
                    text_response = text_response[7:]
                if text_response.startswith("```"):
                    text_response = text_response[3:]
                if text_response.endswith("```"):
                    text_response = text_response[:-3]
                
                data = json.loads(text_response.strip())
                connections = data.get("connections", [])
                names = [item["name"] for item in connections]
                return names
                
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"Rate limit hit for {subject_name}. Rotating key and retrying...")
                rotate_api_key()
                # Short delay to allow config to propagate/reset
                await asyncio.sleep(1) 
                retries += 1
            else:
                print(f"Error calling LLM for {subject_name}: {e}")
                return []
    
    print(f"Max retries exceeded for {subject_name} (tried all keys).")
    return []
            
async def verify_relations(wiki_text: str, subject_name: str, target_name: str, candidates: List[str]) -> List[Dict[str, Any]]:
    """
    Verifies candidates using the 'Strict Verification Prompt'.
    Returns a list of dicts: [{'name': '...', 'type': '...', 'is_bridge': bool}]
    """
    if not API_KEYS or not candidates:
        return []

    # Limit batch size to avoid overload (User suggested 100, let's stick to it)
    # If candidates > 100, we might need to batch? For now let's just take top 100.
    candidates_subset = candidates[:100]
    candidates_str = ", ".join([f'"{c}"' for c in candidates_subset])
    
    # Truncate context to 5000 chars as per user request
    context_text = wiki_text[:5000]

    system_prompt = f"""
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
    You MUST rank the valid candidates based on how likely they are to lead to the "Target Person" ("{target_name}").
    - If the target is a politician, prioritize other politicians or world leaders.
    - If the target is a musician, prioritize other musicians or producers.
    - If no specific connection is obvious, prioritize the most famous/influential people (hubs).

    ### FILTERING RULES (STRICT - DIRECT CONNECTIONS ONLY)
    1. **INCLUDE (Valid Connections):**
       - **Direct Interaction:** People who have met, worked together, or had a significant public interaction with the subject.
       - **Family & Partners:** Spouse, parents, children, siblings, partners.
       - **Professional Associates:** Co-stars, co-founders, bandmates, direct rivals, coach/student.
       - **Historical Interactions:** Signed a treaty with, battled against, succeeded/preceded in office (direct succession).
    
    2. **EXCLUDE (Invalid/Noise):**
       - **NON-PEOPLE (CRITICAL):** Do NOT extract movies, albums, songs, bands, organizations, places, awards, or events.
       - **Comparisons:** "He is often compared to [Person B]", "She writes like [Person C]".
       - **Inspirations (Passive):** "He was inspired by [Person D]" (unless they actually met).
       - **Lists/Awards:** "He is in the list of Time 100 alongside [Person E]" (unless they interacted).
       - **Unrelated Politicians:** Do NOT include presidents or leaders just because they were in power at the time, unless there was a specific interaction.
       - **Fictional Characters:** Do not extract characters.
       - **The Subject Themselves:** Do not include "{subject_name}".
    
    3. **BRIDGE DETECTION:**
       - Mark as `is_bridge=true` ONLY if the person is a politician/leader AND they have a valid direct connection.

    ### OUTPUT FORMAT
    Return ONLY valid JSON. The list `valid_candidates` MUST be sorted by relevance (most relevant first).
    {{
        "valid_candidates": [
            {{
                "name": "Exact Name from List",
                "type": "Brief reason (e.g., 'Co-star', 'Spouse', 'Met at summit')",
                "is_bridge": true/false
            }}
        ]
    }}
    """
    
    import re
    import asyncio
    
    retries = 0
    max_retries = 5
    base_delay = 5  # Higher delay for verification as it's heavier
    
    while retries < max_retries:
        try:
            model = genai.GenerativeModel('gemini-flash-latest')
            response = await model.generate_content_async(system_prompt)
            text_response = response.text
            
            match = re.search(r'\{.*\}', text_response, re.DOTALL)
            if match:
                json_str = match.group(0)
                data = json.loads(json_str)
                return data.get("valid_candidates", [])
            else:
                # Fallback cleanup
                if text_response.startswith("```json"): text_response = text_response[7:]
                if text_response.startswith("```"): text_response = text_response[3:]
                if text_response.endswith("```"): text_response = text_response[:-3]
                
                data = json.loads(text_response.strip())
                return data.get("valid_candidates", [])
                
        except Exception as e:
            if "429" in str(e) or "quota" in str(e).lower():
                print(f"Rate limit hit during verification for {subject_name}. Rotating key and retrying...")
                rotate_api_key()
                await asyncio.sleep(1)
                retries += 1
            else:
                print(f"Error verifying relations for {subject_name}: {e}")
                return []
    
    print(f"Max retries exceeded for {subject_name} verification (tried all keys).")
    return []

# Alias for the new BFS engine
verify_candidates_with_llm = verify_relations

