"""
build_ref_aligned_text_output.py
--------------------------------
Reads a cleaned survey response text file and a Typeform schema JSON,
matches questions to schema (by title or fuzzy similarity),
and outputs a human-readable .txt file including BOTH question and answer refs.

Usage:
    python scripts/build_ref_aligned_text_output.py \
        --form data/macro_survey_pretty.json \
        --input data/users/corinne_text_response.txt \
        --output data/users/corinne_ref_aligned.txt
"""

import json, re, argparse, difflib
from pathlib import Path


# === Utility ===
def normalize(text: str) -> str:
    """Normalize text for fuzzy matching."""
    return re.sub(r"[^a-z0-9 ]+", "", text.lower().strip())


# === Load Schema ===
def load_schema(form_path: Path):
    data = json.loads(form_path.read_text(encoding="utf-8"))
    fields = []
    for f in data.get("fields", []):
        fields.append({
            "title": f.get("title", "").strip(),
            "ref": f.get("ref", ""),
            "type": f.get("type", "text")
        })
    print(f"📋 Loaded {len(fields)} questions from {form_path.name}")
    return fields


# === Parse Responses ===
def parse_text_responses(text_path: Path):
    """Split a cleaned text file into question/answer pairs."""
    text = text_path.read_text(encoding="utf-8").strip()
    blocks = re.split(r"\n\s*\n", text)
    qa_pairs = []
    for block in blocks:
        lines = [line.strip() for line in block.split("\n") if line.strip()]
        if len(lines) >= 2:
            question = lines[0]
            answer = " ".join(lines[1:])
            qa_pairs.append((question, answer))
    print(f"🧾 Parsed {len(qa_pairs)} Q/A pairs from {text_path.name}")
    return qa_pairs


# === Matching ===
def match_questions(qa_pairs, fields):
    schema_map = {normalize(f["title"]): f for f in fields}
    all_titles = list(schema_map.keys())

    matched = []
    unmatched = []

    for question, answer in qa_pairs:
        norm_q = normalize(question)
        if norm_q in schema_map:
            field = schema_map[norm_q]
            match_type = "EXACT"
        else:
            match = difflib.get_close_matches(norm_q, all_titles, n=1, cutoff=0.45)
            if match:
                field = schema_map[match[0]]
                match_type = "FUZZY"
            else:
                unmatched.append((question, answer))
                continue

        matched.append({
            "question": field["title"],
            "question_ref": field["ref"],
            "answer": answer,
            "answer_ref": field["ref"],
            "match_type": match_type
        })
    return matched, unmatched


# === Export Text File ===
def export_text(matched, output_path: Path):
    with open(output_path, "w", encoding="utf-8") as f:
        for i, m in enumerate(matched, 1):
            f.write(f"{i}. Q: {m['question']}\n")
            f.write(f"   Q_ref: {m['question_ref']}\n")
            f.write(f"   A: {m['answer']}\n")
            f.write(f"   A_ref: {m['answer_ref']}\n")
            f.write(f"   Match: {m['match_type']}\n\n")
    print(f"✅ Exported {len(matched)} Q/A pairs → {output_path}")


# === Main ===
def main():
    parser = argparse.ArgumentParser(description="Export text file with question + answer refs")
    parser.add_argument("--form", required=True, help="Path to macro_survey_pretty.json")
    parser.add_argument("--input", required=True, help="Path to cleaned text response file")
    parser.add_argument("--output", required=True, help="Path to output text file")
    args = parser.parse_args()

    fields = load_schema(Path(args.form))
    qa_pairs = parse_text_responses(Path(args.input))
    matched, unmatched = match_questions(qa_pairs, fields)

    export_text(matched, Path(args.output))

    if unmatched:
        print(f"\n⚠️ Unmatched ({len(unmatched)}):")
        for q, _ in unmatched[:5]:
            print(f"   - {q[:80]}")
        if len(unmatched) > 5:
            print("   ...")
    else:
        print("✅ All questions matched successfully!")


if __name__ == "__main__":
    main()

