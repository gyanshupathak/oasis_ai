"""Quick test for _parse_llm_json."""
from scene_planner import _parse_llm_json

# Trailing comma
raw1 = '{"total_duration": 30, "scenes": [{"scene_id": 1, "duration": 6}],}'
assert _parse_llm_json(raw1)["total_duration"] == 30
print("Trailing comma: OK")

# Markdown wrapped
raw2 = '```json\n{"caption": "test"}\n```'
assert _parse_llm_json(raw2)["caption"] == "test"
print("Markdown: OK")

print("All OK")
