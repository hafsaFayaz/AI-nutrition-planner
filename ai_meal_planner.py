"""
ai_meal_planner.py
-------------------
Google Gemini integration for the AI Nutrition Planner group project.

Public interface (the ONLY function teammates should import):

    generate_meal_plan(user_data: dict, recommended_foods: list[dict]) -> dict

Everything else in this file is a private helper.

Same defensive design as the previous Mistral version: import problems,
API errors, and rate limits never crash the app or get silently hidden.
If Gemini can't be reached for ANY reason, generate_meal_plan() still
returns a usable fallback plan plus diagnostic info for the UI.
"""

import os
import sys
import json
import re
import time
import logging

from dotenv import load_dotenv

# ---------------------------------------------------------------------
# SETUP
# ---------------------------------------------------------------------

load_dotenv()  # reads GEMINI_API_KEY from a local .env file if present

logger = logging.getLogger("ai_meal_planner")
logging.basicConfig(level=logging.INFO)

MODEL_NAME = "gemini-3.6-flash"
MAX_RETRIES = 0  # don't burn extra requests against a limited free-tier quota

DISCLAIMER = (
    "This meal plan is AI-generated for informational purposes and is not "
    "medical or dietary advice. Consult a qualified nutrition professional "
    "for personalized medical guidance."
)

# ---------------------------------------------------------------------
# DEFENSIVE IMPORT OF THE GEMINI SDK
# ---------------------------------------------------------------------
# NOTE: the OLD package `google-generativeai` is deprecated. This uses the
# current `google-genai` package (import path: `from google import genai`).
# Install with: pip install google-genai

GEMINI_IMPORT_ERROR = None
genai = None
genai_types = None

try:
    from google import genai as _genai
    from google.genai import types as _genai_types
    genai = _genai
    genai_types = _genai_types
except Exception as e:  # broad on purpose: any failure here is diagnostic info
    GEMINI_IMPORT_ERROR = f"{type(e).__name__}: {e}"

# The SDK's error classes live in google.genai.errors. Import defensively —
# fall back to a plain Exception subclass rather than ever crashing the
# whole module over this.
APIError = None
if genai is not None:
    try:
        from google.genai.errors import APIError as _APIError
        APIError = _APIError
    except Exception:
        APIError = None

if APIError is None:
    class APIError(Exception):
        """Fallback stand-in used when the real APIError class can't be
        imported. Lets the except clauses below still work uniformly."""
        code = None


def get_diagnostics() -> dict:
    """
    Returns raw environment info for debugging setup problems.
    Safe to display in the UI — contains no secrets.
    """
    return {
        "python_executable": sys.executable,
        "gemini_sdk_available": genai is not None,
        "gemini_import_error": GEMINI_IMPORT_ERROR,
        "api_key_present": bool(os.getenv("GEMINI_API_KEY")),
    }


# ---------------------------------------------------------------------
# INTERNAL: build the client (created fresh per call — safe for Streamlit reruns)
# ---------------------------------------------------------------------

def _get_client():
    if genai is None:
        raise RuntimeError(
            f"Gemini SDK could not be imported ({GEMINI_IMPORT_ERROR}). "
            f"Running under: {sys.executable}"
        )

    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "GEMINI_API_KEY is missing. Set it in your .env file "
            "(or in Streamlit Cloud's Secrets manager)."
        )
    return genai.Client(api_key=api_key)


# ---------------------------------------------------------------------
# INTERNAL: prompt construction
# ---------------------------------------------------------------------

def _build_prompt(user_data: dict, recommended_foods: list) -> tuple:
    """
    Returns (system_instruction, user_prompt) — Gemini takes system
    instructions as a separate config field, not a chat message.
    """
    allergies = user_data.get("allergies", []) or []
    avoid_foods = user_data.get("avoid_foods", []) or []
    meals_per_day = user_data.get("meals_per_day", 3)

    system_instruction = (
        "You are a nutrition meal-planning assistant embedded in a student "
        "software project. You generate practical daily meal plans strictly "
        "from the nutrition targets and food pool you are given. "
        "You must NEVER include any food that conflicts with the user's "
        "dietary preference or allergies, even if it would improve macro "
        "accuracy. You must treat the provided 'recommended_foods' list as "
        "the preferred pool to build meals from — you may add very common, "
        "obviously safe complementary items (e.g. water, plain rice, salt) "
        "only if needed to complete a balanced meal. "
        "Respond with ONLY valid JSON. No prose, no markdown, no code fences."
    )

    user_payload = {
        "profile": {
            "age": user_data.get("age"),
            "gender": user_data.get("gender"),
            "height_cm": user_data.get("height"),
            "weight_kg": user_data.get("weight"),
            "bmi": user_data.get("bmi"),
            "bmr": user_data.get("bmr"),
            "tdee": user_data.get("tdee"),
        },
        "targets": {
            "calories": user_data.get("calorie_target"),
            "protein_g": user_data.get("protein_target"),
            "carbs_g": user_data.get("carbs_target"),
            "fat_g": user_data.get("fat_target"),
        },
        "dietary_preference": user_data.get("diet"),
        "allergies": allergies,
        "foods_to_avoid": avoid_foods,
        "recommended_foods_pool": recommended_foods,
        "meals_per_day": meals_per_day,
    }

    required_json_shape = {
        "daily_summary": {
            "calories": "number",
            "protein_g": "number",
            "carbs_g": "number",
            "fat_g": "number",
        },
        "meals": [
            {
                "meal": "string (e.g. Breakfast, Lunch, Snack, Dinner)",
                "foods": [
                    {
                        "name": "string",
                        "quantity": "string (e.g. '50 g', '1 medium')",
                        "calories": "number",
                        "protein_g": "number",
                        "carbs_g": "number",
                        "fat_g": "number",
                    }
                ],
                "meal_calories": "number",
            }
        ],
        "notes": ["string"],
    }

    user_prompt = (
        "Generate a one-day personalized meal plan using ONLY the data below.\n\n"
        f"DATA:\n{json.dumps(user_payload, indent=2)}\n\n"
        f"Return JSON in EXACTLY this shape (keys and nesting must match):\n"
        f"{json.dumps(required_json_shape, indent=2)}\n\n"
        f"Produce exactly {meals_per_day} entries in 'meals'. "
        "Numbers must be plain numbers (no units inside number fields). "
        "'notes' should briefly mention any allergy/diet exclusions you applied."
    )

    return system_instruction, user_prompt


# ---------------------------------------------------------------------
# INTERNAL: safe JSON extraction
# ---------------------------------------------------------------------

def _extract_json(raw_text: str) -> dict:
    if not raw_text or not raw_text.strip():
        raise ValueError("Empty response from model.")

    text = raw_text.strip()
    text = re.sub(r"^```(?:json)?", "", text).strip()
    text = re.sub(r"```$", "", text).strip()

    try:
        return json.loads(text)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        raise


def _validate_shape(plan: dict) -> dict:
    plan.setdefault("daily_summary", {})
    for key in ("calories", "protein_g", "carbs_g", "fat_g"):
        plan["daily_summary"].setdefault(key, None)

    plan.setdefault("meals", [])
    for meal in plan["meals"]:
        meal.setdefault("meal", "Meal")
        meal.setdefault("foods", [])
        meal.setdefault("meal_calories", None)
        for food in meal["foods"]:
            food.setdefault("name", "Unknown item")
            food.setdefault("quantity", "")
            food.setdefault("calories", None)
            food.setdefault("protein_g", None)
            food.setdefault("carbs_g", None)
            food.setdefault("fat_g", None)

    plan.setdefault("notes", [])
    return plan


# ---------------------------------------------------------------------
# INTERNAL: fallback plan if the API/SDK is unavailable
# ---------------------------------------------------------------------

def _fallback_plan(user_data: dict, recommended_foods: list, reason: str) -> dict:
    meals_per_day = max(1, int(user_data.get("meals_per_day", 3)))
    meal_labels = ["Breakfast", "Lunch", "Snack", "Dinner"][:meals_per_day]
    if len(meal_labels) < meals_per_day:
        meal_labels += [f"Meal {i+1}" for i in range(len(meal_labels), meals_per_day)]

    foods = recommended_foods or []
    meals = []
    for i, label in enumerate(meal_labels):
        chunk = foods[i::meals_per_day] if foods else []
        meal_cal = sum((f.get("calories") or 0) for f in chunk)
        meals.append({
            "meal": label,
            "foods": [
                {
                    "name": f.get("food", "Unknown item"),
                    "quantity": "as available",
                    "calories": f.get("calories"),
                    "protein_g": f.get("protein"),
                    "carbs_g": f.get("carbs"),
                    "fat_g": f.get("fat"),
                }
                for f in chunk
            ],
            "meal_calories": meal_cal or None,
        })

    return {
        "daily_summary": {
            "calories": user_data.get("calorie_target"),
            "protein_g": user_data.get("protein_target"),
            "carbs_g": user_data.get("carbs_target"),
            "fat_g": user_data.get("fat_target"),
        },
        "meals": meals,
        "notes": [
            "Fallback plan: AI meal generation was unavailable, so this plan "
            "was assembled directly from your recommended foods.",
        ],
        "is_fallback": True,
        "error_reason": reason,
        "diagnostics": get_diagnostics(),
    }


# ---------------------------------------------------------------------
# PUBLIC ENTRY POINT
# ---------------------------------------------------------------------

def generate_meal_plan(user_data: dict, recommended_foods: list) -> dict:
    """
    Main function teammates call. Never raises — always returns a dict
    with daily_summary / meals / notes / disclaimer, and on failure also
    is_fallback / error_reason / diagnostics (safe to show in the UI).
    """
    try:
        client = _get_client()
    except RuntimeError as e:
        logger.error("Config/import error: %s", e)
        plan = _fallback_plan(user_data, recommended_foods, str(e))
        plan["disclaimer"] = DISCLAIMER
        return plan

    system_instruction, user_prompt = _build_prompt(user_data, recommended_foods)

    last_error = "Unknown error."
    for attempt in range(1, MAX_RETRIES + 2):
        try:
            response = client.models.generate_content(
                model=MODEL_NAME,
                contents=user_prompt,
                config=genai_types.GenerateContentConfig(
                    system_instruction=system_instruction,
                    response_mime_type="application/json",
                    temperature=0.4,
                ),
            )

            raw_text = response.text
            parsed = _extract_json(raw_text)
            parsed = _validate_shape(parsed)
            parsed["disclaimer"] = DISCLAIMER
            parsed["is_fallback"] = False
            return parsed

        except APIError as e:
            status = getattr(e, "code", None)
            if status == 401 or status == 403:
                last_error = f"Invalid API key or permission error: {e}"
                logger.error("Gemini auth error: %s", e)
                break
            elif status == 429:
                last_error = "Rate limit reached."
                logger.warning("Rate limited (attempt %s): %s", attempt, e)
                time.sleep(5 * attempt)  # back off 5s, then 10s, etc.
            elif status and 500 <= status < 600:
                last_error = "Gemini service error."
                logger.warning("Server error (attempt %s): %s", attempt, e)
                time.sleep(2 * attempt)
            else:
                last_error = f"API request failed: {e}"
                logger.warning("API error (attempt %s): %s", attempt, e)

        except (json.JSONDecodeError, ValueError) as e:
            last_error = f"Model returned invalid JSON: {e}"
            logger.warning("JSON parse error (attempt %s): %s", attempt, e)

        except Exception as e:
            last_error = f"Connection or timeout error: {type(e).__name__}: {e}"
            logger.warning("Unexpected error (attempt %s): %s", attempt, e)

    plan = _fallback_plan(user_data, recommended_foods, last_error)
    plan["disclaimer"] = DISCLAIMER
    return plan
