#!/usr/bin/env python3
"""
Model Availability & Latency Checker for Gemini API
Tests all API keys against all potential models to find the fastest working ones.
"""

import os
import time
import asyncio
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()

# =============================================================================
# MODEL LISTS
# =============================================================================

# Manual override list - models from user screenshot + common ones
MANUAL_MODELS = [
    # Newest (2.5 series)
    "gemini-2.5-flash",
    "gemini-2.5-flash-lite", 
    "gemini-2.5-pro",
    
    # 2.0 series (experimental)
    "gemini-2.0-flash",
    "gemini-2.0-flash-exp",
    "gemini-2.0-flash-lite",
    
    # 1.5 series (stable)
    "gemini-1.5-flash",
    "gemini-1.5-flash-latest",
    "gemini-1.5-pro",
    "gemini-1.5-pro-latest",
    
    # 1.0 series (legacy)
    "gemini-1.0-pro",
    "gemini-pro",
    
    # Gemma series
    "gemma-3-27b",
    "gemma-2-27b-it",
    "gemma-2-9b-it",
]

# =============================================================================
# HELPER FUNCTIONS
# =============================================================================

def get_api_keys():
    """Load API keys from environment."""
    api_keys_string = os.getenv("GEMINI_API_KEYS", "")
    keys = [key.strip() for key in api_keys_string.split(",") if key.strip()]
    return keys

def discover_models(api_key):
    """Get list of models available for this API key."""
    genai.configure(api_key=api_key)
    discovered = []
    try:
        for model in genai.list_models():
            if "generateContent" in model.supported_generation_methods:
                discovered.append(model.name.replace("models/", ""))
    except Exception as e:
        print(f"⚠️ Could not list models: {e}")
    return discovered

async def test_model(api_key, model_name, test_prompt="Hello, respond with just 'OK'."):
    """Test a single model and return result with latency."""
    genai.configure(api_key=api_key)
    
    start_time = time.time()
    try:
        model = genai.GenerativeModel(model_name)
        response = await model.generate_content_async(test_prompt)
        latency = (time.time() - start_time) * 1000  # ms
        
        if response.text:
            return {
                "status": "✅",
                "latency_ms": round(latency),
                "model": model_name,
                "response_preview": response.text[:50].replace("\n", " ")
            }
        else:
            return {
                "status": "⚠️",
                "latency_ms": round(latency),
                "model": model_name,
                "error": "Empty response"
            }
    except Exception as e:
        latency = (time.time() - start_time) * 1000
        error_str = str(e)
        
        # Categorize error
        if "404" in error_str or "not found" in error_str.lower():
            status = "❌ 404"
        elif "403" in error_str or "permission" in error_str.lower():
            status = "🔒 403"
        elif "429" in error_str or "quota" in error_str.lower():
            status = "⏳ 429"
        else:
            status = "❌ ERR"
        
        return {
            "status": status,
            "latency_ms": round(latency),
            "model": model_name,
            "error": error_str[:80]
        }

async def run_all_tests():
    """Run tests for all models with all keys."""
    api_keys = get_api_keys()
    
    if not api_keys:
        print("❌ No API keys found! Set GEMINI_API_KEYS in .env")
        return
    
    print(f"\n{'='*70}")
    print(f"🔍 GEMINI MODEL AVAILABILITY & LATENCY CHECKER")
    print(f"{'='*70}")
    print(f"📋 API Keys loaded: {len(api_keys)}")
    
    # Use first key for discovery
    primary_key = api_keys[0]
    print(f"🔑 Primary key: ...{primary_key[-4:]}")
    
    # Discover models dynamically
    print(f"\n📡 Discovering models via API...")
    discovered = discover_models(primary_key)
    print(f"   Found {len(discovered)} models via API")
    
    # Combine with manual list
    all_models = list(set(MANUAL_MODELS + discovered))
    all_models.sort()
    
    print(f"📊 Total models to test: {len(all_models)}")
    print(f"\n{'='*70}")
    print(f"{'MODEL':<35} {'STATUS':<12} {'LATENCY':<10} {'NOTES'}")
    print(f"{'-'*70}")
    
    results = []
    
    for model in all_models:
        result = await test_model(primary_key, model)
        results.append(result)
        
        # Format output
        status = result["status"]
        latency = f"{result['latency_ms']}ms" if result['latency_ms'] else "-"
        notes = result.get("response_preview", result.get("error", ""))[:30]
        
        print(f"{model:<35} {status:<12} {latency:<10} {notes}")
        
        # Small delay to avoid rate limiting
        await asyncio.sleep(0.3)
    
    # Summary
    print(f"\n{'='*70}")
    print(f"📊 SUMMARY")
    print(f"{'='*70}")
    
    working = [r for r in results if r["status"] == "✅"]
    working_sorted = sorted(working, key=lambda x: x["latency_ms"])
    
    print(f"\n✅ WORKING MODELS ({len(working)}):")
    print(f"{'='*50}")
    for r in working_sorted[:10]:  # Top 10 fastest
        print(f"   [{r['latency_ms']:>4}ms] {r['model']}")
    
    if working_sorted:
        print(f"\n🏆 RECOMMENDED MODELS LIST (by latency):")
        print(f"MODELS = [")
        for r in working_sorted[:5]:  # Top 5
            print(f'    "{r["model"]}",')
        print(f"]")

# =============================================================================
# MAIN
# =============================================================================

if __name__ == "__main__":
    asyncio.run(run_all_tests())
