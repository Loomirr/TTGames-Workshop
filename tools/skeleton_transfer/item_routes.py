"""Read-only diagnostics for observed braced TT item text declarations.

This is a bounded declaration inspector, not a game parser or item writer.
Backslashes in quoted TT paths are literal, including before the closing quote.
"""
import argparse
from dataclasses import dataclass
import hashlib
import json
import math
from pathlib import Path
import sys

MAX_INPUT = 8 * 1024 * 1024
MAX_TOKENS = 200_000
MAX_DEPTH = 64


@dataclass(frozen=True)
class Token:
    value: str
    kind: str
    line: int


def tokens(text):
    if "\0" in text:
        raise ValueError("NUL bytes are not supported item text")
    result = []
    pos, line = 0, 1
    while pos < len(text):
        char = text[pos]
        if char == "\n":
            result.append(Token("\n", "newline", line)); line += 1; pos += 1
        elif char.isspace():
            pos += 1
        elif text.startswith("//", pos):
            end = text.find("\n", pos)
            pos = len(text) if end < 0 else end
        elif text.startswith("/*", pos):
            raise ValueError(f"Block comments are outside the observed item subset at line {line}")
        elif char in "{}":
            result.append(Token(char, "brace", line)); pos += 1
        elif char == '"':
            end = text.find('"', pos + 1)
            if end < 0 or "\n" in text[pos + 1:end] or "\r" in text[pos + 1:end]:
                raise ValueError(f"Unterminated or multiline quoted value at line {line}")
            result.append(Token(text[pos + 1:end], "quoted", line)); pos = end + 1
        else:
            start = pos
            while pos < len(text) and not text[pos].isspace() and text[pos] not in '{}"':
                if text.startswith(("//", "/*"), pos):
                    break
                pos += 1
            if pos == start:
                raise ValueError(f"Unsupported token at line {line}")
            result.append(Token(text[start:pos], "word", line))
        if len(result) > MAX_TOKENS:
            raise ValueError("Item declaration token budget exceeded")
    return result


def declarations(text):
    stream = tokens(text)
    items, notices = [], []

    def skip_newlines(pos):
        while pos < len(stream) and stream[pos].kind == "newline":
            pos += 1
        return pos

    def block(pos):
        assert stream[pos].value == "{"
        fields, depth = [], 1
        cursor = pos + 1
        while cursor < len(stream):
            token = stream[cursor]
            if token.kind == "brace":
                depth += 1 if token.value == "{" else -1
                if depth > MAX_DEPTH:
                    raise ValueError("Item nesting depth exceeded")
                if depth == 0:
                    return fields, cursor + 1
                cursor += 1
            elif depth != 1 or token.kind == "newline":
                cursor += 1
            else:
                if token.kind != "word":
                    raise ValueError(f"Expected item field at line {token.line}")
                end = cursor + 1
                while end < len(stream) and stream[end].kind not in ("newline", "brace"):
                    end += 1
                args = [x.value for x in stream[cursor + 1:end]]
                child = skip_newlines(end)
                fields.append(dict(key=token.value, args=args, line=token.line,
                                   nested=child < len(stream) and stream[child].value == "{"))
                cursor = end
        raise ValueError(f"Unclosed item block at line {stream[pos].line}")

    pos = 0
    while (pos := skip_newlines(pos)) < len(stream):
        token = stream[pos]
        if token.kind == "word" and token.value.casefold() == "item_type":
            if pos + 1 >= len(stream) or stream[pos + 1].kind not in ("word", "quoted"):
                raise ValueError(f"Missing item name at line {token.line}")
            name = stream[pos + 1].value
            start = skip_newlines(pos + 2)
            if start == len(stream) or stream[start].value != "{":
                raise ValueError(f"Expected braced item declaration at line {token.line}")
            fields, pos = block(start)
            items.append(dict(name=name, line=token.line, fields=fields))
        elif token.kind == "brace" and token.value == "{":
            _, pos = block(pos)
            notices.append(dict(code="orphan_top_level_block", line=token.line,
                                message="Block has no active item_type owner; not treated as an item"))
        elif token.kind == "brace":
            raise ValueError(f"Unexpected closing brace at line {token.line}")
        else:
            end = pos + 1
            while end < len(stream) and stream[end].kind not in ("newline", "brace"):
                end += 1
            notices.append(dict(code="uninspected_top_level_directive", line=token.line,
                                message="Top-level declaration outside the observed item subset"))
            pos = end
    return items, notices


def inspect_items(text, item_name):
    items, notices = declarations(text)
    indexed = {}
    for item in items:
        indexed.setdefault(item["name"], []).append(item)
    for name, matches in indexed.items():
        if len(matches) > 1:
            notices.append(dict(code="duplicate_item", item=name,
                                message="Duplicate active declaration; override order is not assumed"))
    case_groups = {}
    for name in indexed:
        case_groups.setdefault(name.casefold(), []).append(name)
    for names in case_groups.values():
        if len(names) > 1:
            notices.append(dict(code="case_ambiguous_items", items=names,
                                message="Item name case semantics are not inferred"))
    selected = indexed.get(item_name, [])
    if len(selected) != 1:
        raise ValueError("Select an exact, unique active item_type name")
    if len(case_groups[item_name.casefold()]) != 1:
        raise ValueError("Selected item has a case-ambiguous declaration")
    chain, effective = [], {}

    def resolve(name, ancestry=()):
        if name in ancestry or len(ancestry) >= MAX_DEPTH:
            notices.append(dict(code="reference_cycle_or_depth", item=name,
                                message="Reference chain cannot be resolved"))
            return False
        matches = indexed.get(name, [])
        if len(matches) != 1 or len(case_groups.get(name.casefold(), [])) != 1:
            notices.append(dict(code="unresolved_reference", item=name,
                                message="Reference not unique in the supplied text; inherited fields remain unknown"))
            return False
        item = matches[0]
        fields = {}
        for field in item["fields"]:
            fields.setdefault(field["key"].casefold(), []).append(field)
        refs = fields.get("reference", [])
        resolved = True
        if refs:
            if len(refs) != 1 or len(refs[0]["args"]) != 1 or refs[0]["nested"]:
                notices.append(dict(code="ambiguous_reference", item=name,
                                    message="Reference declaration cannot be resolved"))
                resolved = False
            else:
                resolved = resolve(refs[0]["args"][0], ancestry + (name,))
        chain.append(name)
        effective.update(fields)
        return resolved

    resolved = resolve(item_name)
    actions = {key: [row["args"] for row in rows] for key, rows in effective.items()
               if key.startswith("act_")}
    fights = {key: value for key, value in actions.items()
              if key.startswith("act_fight") and key[9:].isdigit()}
    flags = {}
    for key in ("combo", "sword", "lunge", "can_combat_roll"):
        rows = effective.get(key, [])
        flags[key] = "declared" if len(rows) == 1 and not rows[0]["args"] and not rows[0]["nested"] else (
            "absent" if not rows and resolved else "unknown")
    if fights and flags["combo"] == "absent":
        notices.append(dict(code="fight_routes_without_combo", item=item_name,
                            message="Fight actions are declared without a combo flag; compare with the native combat item"))
    damage = effective.get("damage", [])
    damage_value = None
    if len(damage) == 1 and len(damage[0]["args"]) == 1 and not damage[0]["nested"]:
        try:
            damage_value = float(damage[0]["args"][0])
            if not math.isfinite(damage_value) or damage_value < 0:
                damage_value = None
        except ValueError:
            pass
    if fights and resolved and not damage:
        notices.append(dict(code="fight_routes_without_damage", item=item_name,
                            message="No item damage declaration found; combat behavior is not established by action names"))
    elif damage and damage_value is None:
        notices.append(dict(code="uninspected_damage", item=item_name,
                            message="Damage is not a single finite nonnegative number"))
    return dict(item=item_name, declarations=len(items), reference_chain=chain,
                references_resolved=resolved, combat_flags=flags, damage=damage_value,
                animsets=[row["args"] for row in effective.get("animset", [])],
                actions=actions, notices=notices, runtime_binding_certified=False,
                scope="Observed braced item subset only; AS/CD/CPD and binary tracks are not inspected")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--items", type=Path, required=True)
    parser.add_argument("--item", required=True, help="Exact active item_type name")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        with args.items.open("rb") as handle:
            raw = handle.read(MAX_INPUT + 1)
        if len(raw) > MAX_INPUT:
            raise ValueError("Item text exceeds the 8 MiB inspection limit")
        result = inspect_items(raw.decode("utf-8-sig"), args.item)
        result.update(input=str(args.items), sha256=hashlib.sha256(raw).hexdigest())
        if args.items.resolve() == args.output.resolve():
            raise ValueError("Report must be separate from the source")
        with args.items.open("rb") as handle:
            if handle.read(MAX_INPUT + 1) != raw:
                raise ValueError("Source changed during inspection")
        with args.output.open("x", encoding="utf-8") as handle:
            json.dump(result, handle, indent=2, allow_nan=False); handle.write("\n")
    except (OSError, ValueError, UnicodeError) as error:
        parser.error(str(error))
    print("Item declaration report saved; game action binding remains unverified.")


if __name__ == "__main__":
    main()
