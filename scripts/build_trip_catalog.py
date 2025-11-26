import json
from pathlib import Path

# Path to your input/output files
INPUT_FILE = Path("../data/trip_list.txt")
OUTPUT_FILE = Path("../data/trip_catalog.json")

def parse_trip_line(line):
    """Parse a single trip line from trip_list.txt into structured fields."""
    # Skip empty lines or comments
    if not line.strip() or line.strip().startswith("#"):
        return None

    try:
        # Split by pipes
        parts = [p.strip() for p in line.split("|")]
        # Example: [ "Classic Europe: London, Paris, Rome", "train, plane", "Tier 1", "Primary Breadth", "Europe" ]

        # ---- TITLE + LOCATIONS ----
        title_part = parts[0]
        title, regions = title_part.split(":", 1)
        title = title.strip()
        region_examples = [r.strip() for r in regions.split(",")]

        # ---- TRANSPORT ----
        transport_modes = [t.strip() for t in parts[1].split(",")]

        # ---- TIER ----
        tier = int(parts[2].replace("Tier", "").strip())

        # ---- PB/SD ----
        pb_sd_raw = parts[3].lower()
        if "primary" in pb_sd_raw:
            pb_sd = "PB"
        elif "secondary" in pb_sd_raw:
            pb_sd = "SD"
        else:
            pb_sd = "SD"

        # ---- CONTINENT ----
        continent = parts[4].strip()

        # ---- THEMES, ACTIVITY, CULTURE ----
        # (rough defaults per continent/tier)
        theme_defaults = {
            "Europe": ["culture", "food", "history", "architecture"],
            "Asia": ["culture", "temples", "food", "nature"],
            "North America": ["cities", "nature", "road trip"],
            "South America": ["mountains", "wildlife", "culture", "hiking"],
            "Africa": ["safari", "wildlife", "nature", "culture"],
            "Oceania": ["beach", "outdoors", "scenery"],
            "Central America": ["wildlife", "rainforest", "beaches"],
            "Asia/Africa": ["history", "religion", "desert"]
        }
        themes = theme_defaults.get(continent, ["culture", "nature"])

        # Roughly set difficulty & culture
        activity_level = 5 if tier == 1 else 6
        cultural_depth = 8 if continent in ["Europe", "Asia", "Asia/Africa"] else 6

        # ---- DESCRIPTION ----
        description = f"{title} visiting {', '.join(region_examples[:3])} and nearby regions."

        return {
            "title": title,
            "tier": tier,
            "pb_sd": pb_sd,
            "continent": continent,
            "transport_modes": transport_modes,
            "themes": themes,
            "activity_level": activity_level,
            "cultural_depth": cultural_depth,
            "region_examples": region_examples,
            "description": description
        }

    except Exception as e:
        print("⚠️ Error parsing line:", line)
        print("   ", e)
        return None


def build_catalog():
    trips = []
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        for line in f:
            parsed = parse_trip_line(line)
            if parsed:
                trips.append(parsed)

    with open(OUTPUT_FILE, "w", encoding="utf-8") as out:
        json.dump(trips, out, indent=2)

    print(f"✅ Created {OUTPUT_FILE} with {len(trips)} trips.")


if __name__ == "__main__":
    build_catalog()
