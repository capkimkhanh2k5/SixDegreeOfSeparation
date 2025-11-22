import os
import json
import google.generativeai as genai
from typing import List, Dict, Any, Optional
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure API Key
GENAI_API_KEY = os.environ.get("GEMINI_API_KEY")
print(f"[LLM_CLIENT] GEMINI_API_KEY loaded: {bool(GENAI_API_KEY)}")
if GENAI_API_KEY:
    genai.configure(api_key=GENAI_API_KEY)

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
    if not GENAI_API_KEY:
        print("WARNING: GEMINI_API_KEY not found. Returning empty list.")
        return []

    prompt = generate_extraction_prompt(wiki_text, subject_name)
    
    import re
    
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
            # Fallback: try cleaning markdown as before if regex fails (unlikely if valid JSON exists)
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
        print(f"Error calling LLM for {subject_name}: {e}")
        return []
            
async def verify_relations(wiki_text: str, subject_name: str, target_name: str, candidates: List[str]) -> List[Dict[str, Any]]:
    """
    Verifies candidates using the 'Strict Verification Prompt'.
    Returns a list of dicts: [{'name': '...', 'type': '...', 'is_bridge': bool}]
    """
    if not GENAI_API_KEY or not candidates:
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
    Analyze the "Context Text" and filter the "Candidate Links" based on VERY RELAXED rules.

    ### FILTERING RULES (EXTREMELY PERMISSIVE - FAVOR INCLUSION)
    1. **INCLUDE (Keep almost everything):**
       - **ANY** real person mentioned, even in passing
       - Politicians, presidents, world leaders (CRITICAL FOR BRIDGING)
       - Historical figures, activists, diplomats
       - Family, friends, colleagues, co-workers
       - Anyone mentioned in the same sentence as the subject
       - People from different domains (music, politics, sports, entertainment)
       - **SPECIAL PRIORITY:** Politicians and historical figures like presidents, ministers, diplomats - these are BRIDGES
    
    2. **EXCLUDE (Very minimal - only obvious non-people):**
       - Fictional characters or characters from TV/movies
       - The subject themselves ("{subject_name}")
       - Awards or events (unless it's a person's name)
    
    3. **CROSS-DOMAIN CONNECTIONS:**
       - If the target is in politics/history and subject is in entertainment, PRIORITIZE political figures
       - If you see any politician, president, or historical leader, INCLUDE THEM
       - These cross-domain links are ESSENTIAL for bridging different fields
    
    4. **BRIDGE DETECTION:**
       - Mark ANY politician, president, world leader, or historical figure as is_bridge=true
       - These are the most valuable connections in the game

    ### OUTPUT FORMAT
    Return ONLY valid JSON. err on the side of inclusion. When in doubt, INCLUDE the person.
    {{
        "valid_candidates": [
            {{
                "name": "Exact Name from List",
                "type": "Brief reason (e.g., 'Mentioned in same context', 'Political figure')",
                "is_bridge": true/false (True if politician, president, historical leader, diplomat)
            }}
        ]
    }}
    
    REMEMBER: It's better to include too many than to miss a connection. The path-finding algorithm will handle the rest.
    """
    
    import re
    
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
        print(f"Error verifying relations for {subject_name}: {e}")
        return []

# Alias for the new BFS engine
verify_candidates_with_llm = verify_relations

