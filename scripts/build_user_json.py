"""
build_true_typeform_json.py
---------------------------
Creates a fully accurate Typeform-style webhook JSON from:
  - macro_survey_pretty.json (schema)
  - corinne_ref_aligned.txt (cleaned text file with Q_ref and answers)

Usage:
    python scripts/build_true_typeform_json.py \
        --form data/macro_survey_pretty.json \
        --input data/users/corinne_ref_aligned.txt \
        --output data/users/corinne_response_true.json
"""

import json, re, argparse
from pathlib import Path
from datetime import datetime


# === Load Schema ===
def load_schema(form_path: Path):
    schema_data = json.loads(form_path.read_text(encoding="utf-8"))
    ref_map = {}
    form_id = schema_data.get("id", "mock_form_001")
    title = schema_data.get("title", "Untitled Form")

    for field in schema_data.get("fields", []):
        ref = field.get("ref")
        if ref:
            ref_map[ref] = {
                "id": field.get("id", f"id_{ref[:6]}"),
                "title": field.get("title", ""),
                "type": field.get("type", "text"),
            }

    print(f"📋 Loaded {len(ref_map)} fields from {form_path.name}")
    return ref_map, form_id, title


# === Parse ref-aligned text file ===
def parse_ref_text(input_path: Path):
    text = input_path.read_text(encoding="utf-8").strip()

    # Remove any lines that start with A_ref or Match (case-insensitive)
    clean_text = "\n".join(
        [line for line in text.splitlines() if not re.match(r"^\s*(A_ref|Match)\s*:", line, re.IGNORECASE)]
    )

    # Split on numbered blocks or blank lines
    blocks = re.split(r"(?:\n\s*\d+\.\s*)|\n\s*\n", clean_text)
    entries = []

    current_q, current_ref, current_a = "", "", ""
    for block in blocks:
        if not block.strip():
            continue

        # Extract Q, Q_ref, A
        q_match = re.search(r"Q:\s*(.+)", block, re.IGNORECASE | re.DOTALL)
        qref_match = re.search(r"Q_ref:\s*([a-z0-9\-]+)", block, re.IGNORECASE)
        a_match = re.search(r"A:\s*(.+)", block, re.IGNORECASE | re.DOTALL)

        question = q_match.group(1).strip() if q_match else current_q
        q_ref = qref_match.group(1).strip() if qref_match else current_ref
        answer = a_match.group(1).strip() if a_match else current_a

        if q_ref and answer:
            entries.append({"ref": q_ref, "question": question, "answer": answer})
            current_q, current_ref, current_a = "", "", ""
        else:
            # Handle multi-line continuation
            if not q_ref:
                current_q += " " + question
            elif not answer:
                current_a += " " + answer

    print(f"🧾 Parsed {len(entries)} Q/A pairs from {input_path.name}")
    return entries


# === Detect Answer Type ===
def detect_answer_type(field_type: str, answer: str):
    """Return appropriate Typeform 'type' and data structure."""
    field_type = field_type.lower()
    answer = answer.strip()

    # Opinion scale or number
    if "number" in field_type or "scale" in field_type or re.match(r"^\d+", answer):
        try:
            return "number", {"number": float(re.findall(r"\d+", answer)[0])}
        except Exception:
            return "text", {"text": answer}

    # Multiple choice
    if "choice" in field_type or "dropdown" in field_type or "multiple" in field_type:
        return "choice", {"choice": {"label": answer}}

    # Default: text
    return "text", {"text": answer}


# === Build Typeform-like Payload ===
def build_typeform_json(entries, schema_map, form_id, form_title):
    fields = []
    answers = []

    for e in entries:
        ref = e["ref"]
        answer = e["answer"]

        if ref not in schema_map:
            print(f"⚠️ Warning: ref {ref} not found in schema; adding as text field.")
            field_type = "text"
            field_id = f"id_{ref[:6]}"
            field_title = e["question"]
        else:
            field = schema_map[ref]
            field_type = field["type"]
            field_id = field["id"]
            field_title = field["title"]

        # Create definition field
        fields.append({
            "id": field_id,
            "title": field_title,
            "type": field_type
        })

        # Create answer field
        ans_type, ans_data = detect_answer_type(field_type, answer)
        answer_entry = {
            "field": {
                "id": field_id,
                "type": field_type
            },
            "type": ans_type,
        }
        answer_entry.update(ans_data)
        answers.append(answer_entry)

    # Build final payload
    payload = {
        "event_id": "mock_event_001",
        "event_type": "form_response",
        "form_response": {
            "form_id": form_id,
            "token": "mock_token_123",
            "landed_at": datetime.utcnow().isoformat() + "Z",
            "submitted_at": datetime.utcnow().isoformat() + "Z",
            "hidden": {"user_id": "12345"},
            "definition": {
                "id": form_id,
                "title": form_title,
                "fields": fields
            },
            "answers": answers
        }
    }

    print(f"✅ Built payload with {len(answers)} answers.")
    return payload


def main():
    parser = argparse.ArgumentParser(description="Build a real Typeform-style JSON")
    parser.add_argument("--form", required=True, help="Path to macro_survey_pretty.json")
    parser.add_argument("--input", required=True, help="Path to ref-aligned text file")
    parser.add_argument("--output", required=True, help="Path to save JSON output")
    args = parser.parse_args()

    schema_map, form_id, form_title = load_schema(Path(args.form))
    entries = parse_ref_text(Path(args.input))
    payload = build_typeform_json(entries, schema_map, form_id, form_title)

    Path(args.output).write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"\n🎉 Typeform JSON saved → {args.output}\n")


if __name__ == "__main__":
    main()
