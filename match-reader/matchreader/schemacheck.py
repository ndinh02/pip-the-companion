"""Mini JSON Schema validator, copied from match-lab/tests/test_schema.py (task 03,
step 3.4) with maxLength support added, which overlay_card.schema.json needs.

No third-party packages: implements only the keywords our schemas use. If a schema
starts using a keyword this file does not know, check() fails loudly instead of
silently passing.
"""
from __future__ import annotations

import json
import os
import re
from typing import Any, Dict, List

SCHEMA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "..", "schemas")

# Keywords that carry no checking logic (documentation / identification).
IGNORED = {"$schema", "$id", "title", "description", "$defs"}
KNOWN = IGNORED | {"$ref", "type", "enum", "required", "properties", "additionalProperties",
                   "items", "anyOf", "minimum", "maximum", "minLength", "maxLength", "pattern",
                   "minItems", "maxItems"}


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
        if "maxLength" in schema and len(value) > schema["maxLength"]:
            errors.append("%s: longer than maxLength %d" % (path, schema["maxLength"]))
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


def validate_card(card: Dict[str, Any]) -> List[str]:
    """One output card against schemas/overlay_card.schema.json."""
    schema = load_schema("overlay_card.schema.json")
    return check(card, schema, schema)
