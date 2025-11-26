import sys, os
import json

from dotenv import load_dotenv
from openai import OpenAI

from logic.normalize_typeform import normalize_typeform

def find_key(data: dict, possible_keys: list):
    """
    Search a dict for any of the given possible keys (case-insensitive, underscore-insensitive).
    Returns the first matching value or None.
    """
    if not isinstance(data, dict):
        return None

    normalized_map = {k.lower().replace("_", ""): v for k, v in data.items()}

    for key in possible_keys:
        norm = key.lower().replace("_", "")
        if norm in normalized_map:
            return normalized_map[norm]

    return None



def load_json(path: str):
    with open(path, "r") as f:
        return json.load(f)


def main():
    # Load env vars
    load_dotenv()

    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise RuntimeError("OPENAI_API_KEY is not set in your .env file")

    client = OpenAI(api_key=api_key)

    if len(sys.argv) > 1:
        input_filename = sys.argv[1]
    else:
        raise RuntimeError(
            "You must provide a user JSON file.\n"
            "Example: python run_local.py corinne_response_final.json"
        )

    # Build correct path
    user_json_path = os.path.join("data", "typeform_responses", input_filename)

    # Get name without .json for naming outputs
    base_name = input_filename.replace(".json", "")
    # Convert filename into readable user name
    user_name = base_name.replace("_", " ").replace("-", " ").title()


    # Fixed paths for shared files
    trips_json_path = "data/trip_catalog.json"
    logic_path = "TransferKit_v4.txt"

    print(f"Processing: {input_filename}")

    user_json = load_json(user_json_path)
    trip_catalog = load_json(trips_json_path)
    with open(logic_path, "r") as f:
        logic_text = f.read()

      
    # 2. Normalize user survey
    normalized_user = normalize_typeform(user_json)

    # 3. Load TransferKit logic text
    with open(logic_path, "r") as f:
        logic_text = f.read()

    # 1. Load data files
    #user_json_path = "data/typeform_responses/corinne_response_final.json"
    #trips_json_path = "data/trip_catalog.json"
    #logic_path = "TransferKit_v4.txt"

    #user_json = load_json(user_json_path)
    #trip_catalog = load_json(trips_json_path)*/

    # 4. Build system + user content for the Responses API
    json_schema = """
    {
    "top_8": [
        { "title": "string", "score": 0, "rationale": "string" }
    ],
    "next_5": [
        { "title": "string", "score": 0, "rationale": "string" }
    ],
    "audit_table": [
        { 
        "title": "string",
        "score": 0,
        "tier": "string",
        "pb_sd": "string",
        "continent": "string"
        }
    ]
    }
    """
    
    
    system_prompt = f"""
You are the Transfer Kit v4 — 34-Trip Recommender Logic System (Global-First v7).

You MUST return ONLY the JSON object in the EXACT schema below.
- Do NOT change ANY key names.
- Do NOT add keys.
- Do NOT wrap the JSON in another object.
- Do NOT change casing, spelling, underscores, or structure.
- Only fill VALUES inside the schema.
- Values must be floats/ints/strings exactly matching the schema.

THE REQUIRED OUTPUT SCHEMA:

{json_schema}

Your job:
- Compute the Top 8 + Next 5 trips using TransferKit logic.
- Provide 3–5 sentence rationales for top_8 and next_5.
- Audit table must contain all 34 trips with normalized final scores.
- All numbers must be floats or ints.
- No other fields are allowed. No other keys. No other structure.

Here is the logic spec you must apply:

{logic_text}

Key requirements:
- Respect Tier and PB/SD precedence (Tier → PB → SD).
- Enforce continent balance: soft-caps (Europe ≤ 3; others ≤ 2) and diversity floor (+10 boost to a missing continent if <3 represented).
- Apply all modifiers described (ISE Elevation, Galápagos Deferral, Age/Breadth Bias, Alpine Redundancy, Islands Independent Count, etc.).
- Apply hard penalties first (Home, Visited, Familiarity Smoothing), then core scaling, then regional & cultural modifiers, then balance passes, then diversity floor & normalization.
- Normalize final scores to 100.
- Produce Output 1 (Pure Fit): Top 8 + Next 5 with normalized scores and short rationales.
- Also produce an audit structure with all 34 trips ranked and their final scores.

You are allowed to infer reasonable numeric weights consistent with the description if exact numbers are not provided, but you must keep Tier/PB precedence and continent diversity constraints intact.
Return ONLY JSON, no prose.

"""

    user_payload = {
        "trip_catalog": trip_catalog,
        "user_profile_normalized": normalized_user,
        # You can also include the raw Typeform JSON if you want:
        # "raw_typeform": user_json,
    }

    print("Calling OpenAI…")

    response = client.chat.completions.create(
        model="gpt-4.1-mini",  # or gpt-4.1
        response_format={"type": "json_object"},
        messages=[
            {
                "role": "system",
                "content": system_prompt
            },
            {
                "role": "user",
                "content": json.dumps(user_payload)
            }
        ]
    )

    # Extract JSON string from model response
    msg = response.choices[0].message

    # Some SDK versions return a single string
    if isinstance(msg.content, str):
        raw_output_text = msg.content

    # Some versions return a list of content parts
    elif isinstance(msg.content, list):
        # Each item may be { "type": "output_text", "text": "..." }
        all_text_parts = []
        for part in msg.content:
            if isinstance(part, dict) and "text" in part:
                all_text_parts.append(part["text"])
            elif isinstance(part, str):
                all_text_parts.append(part)
        raw_output_text = "\n".join(all_text_parts)

    else:
        raise RuntimeError(f"Unexpected message.content format: {msg.content}")


    try:
        output_json = json.loads(raw_output_text)
    except Exception as e:
        print("Failed to parse JSON. Raw output:")
        print(raw_output_text)
        raise e


    # Save full output
    out_path = f"output_{base_name}.json"
    with open(out_path, "w") as f:
        json.dump(output_json, f, indent=2)

    # 6. Upload data to Supabase
    from supabase_client import supabase

    # Insert into form_responses
    response_insert = supabase.table("form_responses").insert({
        "raw_json": user_json,
        "normalized_json": normalized_user,
        "user_id": normalized_user["meta"].get("hidden", {}).get("user_id")
    }).execute()

    if not response_insert.data:
        raise RuntimeError(f"Insert into form_responses failed: {response_insert}")

    response_id = response_insert.data[0]["id"]
    print(f"Inserted form_responses row: {response_id}")

    # Insert into trip_outputs
    top8 = output_json.get("top_8", [])
    next5 = output_json.get("next_5", [])
    audit = output_json.get("audit_table", [])


    # --- INSERT INTO SUPABASE USING STABLE FIELDS ---
    output_insert = supabase.table("trip_outputs").insert({
        "response_id": response_id,
        "user_name": user_name,
        "top8": top8,
        "next5": next5,
        "audit_table": audit,
        "final_json": output_json,  # full output for debugging
    }).execute()

    if not output_insert.data:
        raise RuntimeError(f"Insert into trip_outputs failed: {output_insert}")

    output_id = output_insert.data[0]["id"]
    print(f"Inserted trip_outputs row: {output_id}")


    if not output_insert.data:
        raise RuntimeError(f"Insert into trip_outputs failed: {output_insert}")


    output_id = output_insert.data[0]["id"]
    print(f"Inserted trip_outputs row: {output_id}")


    # Print a quick summary to console if keys exist
    top8 = output_json.get("top_8") or output_json.get("top8") or []
    next5 = output_json.get("next_5") or output_json.get("next5") or []

    print("\n=== TOP 8 (from model) ===")
    for i, t in enumerate(top8, start=1):
        title = t.get("title") or t.get("trip_title") or str(t)
        score = t.get("score") or t.get("normalized_score")
        print(f"{i}. {title} — {score}")

    print("\n=== NEXT 5 (from model) ===")
    for i, t in enumerate(next5, start=1):
        title = t.get("title") or t.get("trip_title") or str(t)
        score = t.get("score") or t.get("normalized_score")
        print(f"{i}. {title} — {score}")

    print(f"\nFull JSON saved to {out_path}\n")


if __name__ == "__main__":
    main()
