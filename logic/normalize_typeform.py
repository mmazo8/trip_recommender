import json

def normalize_typeform(tf_json: dict) -> dict:
    """
    Normalize a Typeform-style JSON response into a structured, model-friendly dict.

    - Keeps meta info (user_id, form_id, timestamps)
    - For each answer, attaches the human-readable question title and type
    """

    form = tf_json["form_response"]

    # Map field_id -> {title, type}
    fields_by_id = {
        f["id"]: {"title": f.get("title"), "type": f.get("type")}
        for f in form.get("definition", {}).get("fields", [])
    }

    # Meta info
    meta = {
        "form_id": form.get("form_id"),
        "token": form.get("token"),
        "landed_at": form.get("landed_at"),
        "submitted_at": form.get("submitted_at"),
        "hidden": form.get("hidden", {})
    }

    normalized_answers = []

    for ans in form.get("answers", []):
        field = ans.get("field", {})
        field_id = field.get("id")
        field_type = field.get("type")

        field_meta = fields_by_id.get(field_id, {})
        question_title = field_meta.get("title")
        question_type = field_meta.get("type") or field_type

        answer_type = ans.get("type")
        value = None

        if answer_type == "choice":
            value = ans.get("choice", {}).get("label")
        elif answer_type == "number":
            value = ans.get("number")
        elif answer_type == "text":
            value = ans.get("text")
        else:
            # Fallback – keep raw answer
            value = {k: v for k, v in ans.items() if k not in ("field",)}

        normalized_answers.append(
            {
                "field_id": field_id,
                "field_title": question_title,
                "field_type": question_type,
                "answer_type": answer_type,
                "value": value,
            }
        )

    return {
        "meta": meta,
        "answers": normalized_answers,
    }
