"""Validate generator output against schemas/event.schema.json and schemas/match.schema.json.

No third-party packages: `check` below implements only the JSON Schema keywords our schemas use
($ref, type, enum, required, properties, additionalProperties, items, anyOf, minimum, maximum,
minLength, pattern, minItems, maxItems). If a schema starts using a keyword this file does not
know, the test fails loudly instead of silently passing.
"""
from __future__ import annotations

import copy
import json
import os
import re
import unittest
from typing import Any, Dict, List

from matchlab import generate_match

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "schemas")

# Keywords that carry no checking logic (documentation / identification).
IGNORED = {"$schema", "$id", "title", "description", "$defs"}
KNOWN = IGNORED | {"$ref", "type", "enum", "required", "properties", "additionalProperties", "items",
                   "anyOf", "minimum", "maximum", "minLength", "pattern", "minItems", "maxItems"}


def load_schema(name: str) -> Dict[str, Any]:
    with open(os.path.join(SCHEMA_DIR, name), encoding="utf-8") as fh:
        return json.load(fh)


def _type_ok(value: Any, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return isinstance(value, bool)
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    if expected == "integer":
        return isinstance(value, int) and not isinstance(value, bool)
    if expected == "number":
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    raise ValueError("unknown type in schema: %r" % expected)


def _resolve(ref: str, root: Dict[str, Any], current: Dict[str, Any]):
    """Return (schema, root_of_that_schema). Supports '#/path' and 'other.schema.json'."""
    file_part, _, fragment = ref.partition("#")
    target_root = load_schema(file_part) if file_part else root
    node = target_root
    for part in [p for p in fragment.split("/") if p]:
        node = node[part]
    return node, target_root


def check(value: Any, schema: Dict[str, Any], root: Dict[str, Any], path: str = "$") -> List[str]:
    """Return a list of error strings (empty list = valid)."""
    unknown = set(schema) - KNOWN
    if unknown:
        raise ValueError("%s: validator does not support keyword(s) %s" % (path, sorted(unknown)))
    errors: List[str] = []

    if "$ref" in schema:
        target, target_root = _resolve(schema["$ref"], root, schema)
        return check(value, target, target_root, path)

    if "anyOf" in schema:
        branches = [check(value, sub, root, path) for sub in schema["anyOf"]]
        if not any(len(b) == 0 for b in branches):
            errors.append("%s: matches none of the anyOf branches (%s)" % (path, "; ".join(b[0] for b in branches)))

    if "type" in schema:
        types = schema["type"] if isinstance(schema["type"], list) else [schema["type"]]
        if not any(_type_ok(value, t) for t in types):
            return ["%s: expected type %s, got %r" % (path, "/".join(types), value)]

    if "enum" in schema and not any(value == option and type(value) == type(option) for option in schema["enum"]):
        errors.append("%s: %r not in enum %r" % (path, value, schema["enum"]))

    if isinstance(value, (int, float)) and not isinstance(value, bool):
        if "minimum" in schema and value < schema["minimum"]:
            errors.append("%s: %r < minimum %r" % (path, value, schema["minimum"]))
        if "maximum" in schema and value > schema["maximum"]:
            errors.append("%s: %r > maximum %r" % (path, value, schema["maximum"]))

    if isinstance(value, str):
        if "minLength" in schema and len(value) < schema["minLength"]:
            errors.append("%s: shorter than minLength %d" % (path, schema["minLength"]))
        if "pattern" in schema and not re.search(schema["pattern"], value):
            errors.append("%s: %r does not match %r" % (path, value, schema["pattern"]))

    if isinstance(value, dict):
        for key in schema.get("required", []):
            if key not in value:
                errors.append("%s: missing required %r" % (path, key))
        props = schema.get("properties", {})
        for key, sub in value.items():
            if key in props:
                errors.extend(check(sub, props[key], root, "%s.%s" % (path, key)))
            elif schema.get("additionalProperties") is False:
                errors.append("%s: unexpected property %r" % (path, key))
            elif isinstance(schema.get("additionalProperties"), dict):
                errors.extend(check(sub, schema["additionalProperties"], root, "%s.%s" % (path, key)))

    if isinstance(value, list):
        if "minItems" in schema and len(value) < schema["minItems"]:
            errors.append("%s: fewer than %d items" % (path, schema["minItems"]))
        if "maxItems" in schema and len(value) > schema["maxItems"]:
            errors.append("%s: more than %d items" % (path, schema["maxItems"]))
        if "items" in schema:
            for i, item in enumerate(value):
                errors.extend(check(item, schema["items"], root, "%s[%d]" % (path, i)))

    return errors


def validate_match(match: Dict[str, Any]) -> List[str]:
    schema = load_schema("match.schema.json")
    return check(match, schema, schema)


class CheckerSelfTest(unittest.TestCase):
    """The mini validator must reject bad data, otherwise a green test means nothing."""

    @classmethod
    def setUpClass(cls):
        cls.match = generate_match(1)

    def assertRejected(self, mutate, expect: str) -> None:
        bad = copy.deepcopy(self.match)
        mutate(bad)
        errors = validate_match(bad)
        self.assertTrue(any(expect in e for e in errors), "expected an error containing %r, got %r" % (expect, errors[:3]))

    def test_out_of_pitch_coordinate(self):
        self.assertRejected(lambda m: m["events"][5]["start"].update(x=105.5), "maximum")

    def test_unknown_event_type(self):
        self.assertRejected(lambda m: m["events"][0].update(type="dive"), "enum")

    def test_missing_field(self):
        self.assertRejected(lambda m: m["events"][0].pop("outcome"), "missing required 'outcome'")

    def test_extra_field(self):
        self.assertRejected(lambda m: m["events"][0].update(real_name="x"), "unexpected property")

    def test_wrong_type(self):
        self.assertRejected(lambda m: m["events"][0].update(t_ms="12"), "expected type integer")

    def test_pressure_level_range(self):
        self.assertRejected(lambda m: m["events"][0].update(pressure_level=6), "maximum")

    def test_bad_player_id(self):
        self.assertRejected(lambda m: m["events"][0].update(player_id="Messi"), "does not match")

    def test_bad_set_piece(self):
        def mutate(m):
            corner = next(e for e in m["events"] if e["type"] == "corner")
            corner["set_piece"]["routine"] = "dance"
        self.assertRejected(mutate, "anyOf")

    def test_bad_stoppage_type(self):
        self.assertRejected(lambda m: m["stoppages"][0].update(type="lunch"), "enum")


class GeneratorOutputIsValid(unittest.TestCase):
    def test_seed_1_validates(self):
        errors = validate_match(generate_match(1))
        self.assertEqual(errors, [], errors[:5])

    def test_a_few_more_seeds_and_custom_priors_validate(self):
        for seed, home, away in ((2, None, None), (3, {"corner_short_share": 0.0}, {"corner_short_share": 1.0}),
                                 (4, {"press_intensity": 1.0, "sub_attack_bias": 1.0}, {"press_intensity": 0.0})):
            errors = validate_match(generate_match(seed, home, away))
            self.assertEqual(errors, [], "seed %d: %s" % (seed, errors[:5]))


if __name__ == "__main__":
    unittest.main()
