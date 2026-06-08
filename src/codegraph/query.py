from __future__ import annotations

import json
import re
from collections import deque
from pathlib import Path
from typing import Any

from codegraph.graph.types import UnifiedGraph

CLASSIFICATION_FILE = ".codegraph/classification.json"

DICT_LIKE_METHODS: set[str] = {
    "get", "setdefault", "pop", "popitem", "update", "items",
    "keys", "values", "__getitem__", "__setitem__", "__delitem__",
    "__contains__",
}

PYTHON_BUILTINS: set[str] = {
    "abs", "all", "any", "ascii", "bin", "bool", "bytearray", "bytes",
    "callable", "chr", "classmethod", "compile", "complex", "delattr",
    "dict", "dir", "divmod", "enumerate", "eval", "exec", "filter",
    "float", "format", "frozenset", "getattr", "globals", "hasattr",
    "hash", "hex", "id", "input", "int", "isinstance", "issubclass",
    "iter", "len", "list", "locals", "map", "max", "memoryview", "min",
    "next", "object", "oct", "open", "ord", "pow", "print", "property",
    "range", "repr", "reversed", "round", "set", "setattr", "slice",
    "sorted", "staticmethod", "str", "sum", "super", "tuple", "type",
    "vars", "zip",
    "__import__", "__build_class__",
}


def _match(name: str, pattern: str) -> bool:
    try:
        return re.search(pattern, name) is not None
    except re.error:
        return pattern in name


def _make_snippet(signature: str) -> str | None:
    if not signature:
        return None
    lines = signature.split("\n")
    def_line = lines[0].rstrip()
    doc_lines: list[str] = []
    for line in lines[1:]:
        stripped = line.strip()
        if stripped in ('"""', "'''", '"""', "'''"):
            doc_lines.append(line)
            break
        if stripped.startswith(('"""', "'''")) and stripped.endswith(('"""', "'''")):
            doc_lines.append(line)
            break
        if stripped.startswith(('"""', "'''")):
            doc_lines.append(line)
            continue
        if doc_lines:
            doc_lines.append(line)
            if stripped.endswith(('"""', "'''")):
                break
            continue
        if not doc_lines and not stripped:
            continue
        break
    if doc_lines:
        return def_line + "\n" + "\n".join(doc_lines)
    return def_line


def _load_classifications(root: str) -> dict[str, Any]:
    path = Path(root) / CLASSIFICATION_FILE
    if path.exists():
        try:
            data: dict[str, Any] = json.loads(path.read_text())
            return data
        except (OSError, json.JSONDecodeError):
            pass
    return {"symbols": {}, "entries": {}}


def _save_classifications(root: str, data: dict[str, Any]) -> None:
    path = Path(root) / CLASSIFICATION_FILE
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2))


def _classify_apply(
    data: dict[str, Any],
    kind: str,
    names: list[str],
    section: str,
) -> dict[str, Any]:
    section_data: dict[str, Any] = data.setdefault(section, {})
    for name in names:
        existing: dict[str, Any] = section_data.get(name, {})
        existing["kind"] = kind
        section_data[name] = existing
    root: str = data.get("_root", ".")
    _save_classifications(root, data)
    return data


def _unclassify_section(
    data: dict[str, Any],
    names: list[str],
    section: str,
) -> dict[str, Any]:
    section_data: dict[str, Any] = data.get(section, {})
    for name in names:
        section_data.pop(name, None)
    root: str = data.get("_root", ".")
    _save_classifications(root, data)
    return data


class WorkspaceQuery:
    def __init__(self, graph: UnifiedGraph, root: str = ".") -> None:
        self.graph = graph
        self.root = root
        self._symbols_by_name: dict[str, list[dict[str, Any]]] = {}
        self._symbols_by_id: dict[str, dict[str, Any]] = {}
        self._callees_of: dict[str, list[dict[str, Any]]] = {}
        self._callers_by_name: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self._methods_by_class: dict[str, list[dict[str, Any]]] = {}
        self._own_methods_by_class: dict[str, list[dict[str, Any]]] = {}
        self._class_by_method_name: dict[str, str] = {}
        self._raw_calls_by_callee_raw: dict[str, list[dict[str, Any]]] = {}
        self._fan_in: dict[str, int] = {}
        self._build_index()
        self._classification: dict[str, Any] = _load_classifications(root)
        self._classification["_root"] = root
        self._resolve_inherited_methods()

    def _build_index(self) -> None:
        symbols = self.graph.symbols
        for sym in symbols:
            sym_name = sym.get("name", "")
            self._symbols_by_name.setdefault(sym_name, []).append(sym)
            sym_id = sym.get("id", "")
            if sym_id:
                self._symbols_by_id[sym_id] = sym
            recv = sym.get("receiver")
            if recv:
                self._methods_by_class.setdefault(recv, []).append(sym)
                self._own_methods_by_class.setdefault(recv, []).append(sym)
                self._class_by_method_name[sym_name] = recv

        calls = self.graph.calls
        unique_callers: dict[str, set[str]] = {}
        for call in calls:
            cid = call.get("caller_symbol_id", "")
            self._callees_of.setdefault(cid, []).append(call)

            callee_raw = call.get("callee_raw", "")
            normalized = self._normalize_callee_raw(callee_raw)
            call["_normalized_raw"] = normalized
            self._raw_calls_by_callee_raw.setdefault(normalized, []).append(call)

            resolved = self._resolve_callee(callee_raw)
            if resolved:
                resolved_name = resolved.get("name", "")
                resolved_id = resolved.get("id", "")
                call["_callee_resolved_id"] = resolved_id
                caller_sym = self._symbols_by_id.get(cid)
                caller_entry = caller_sym.get("entry_name", "") if caller_sym else ""
                self._callers_by_name.setdefault(resolved_name, []).append(
                    (caller_entry, call)
                )
                unique_callers.setdefault(resolved_name, set()).add(caller_entry)
                receiver = resolved.get("receiver")
                if receiver:
                    self._callers_by_name.setdefault(receiver, []).append(
                        (caller_entry, call)
                    )

        self._fan_in = {
            name: len(callers) for name, callers in unique_callers.items()
        }

    def _resolve_inherited_methods(self) -> None:
        self._methods_by_class = {
            k: list(v) for k, v in self._own_methods_by_class.items()
        }
        abstract = {
            name for name, info in self._classification.get("symbols", {}).items()
            if info.get("kind") == "abstract_resource"
        }
        class_syms: dict[str, dict[str, Any]] = {}
        for sym in self.graph.symbols:
            if sym.get("kind") == "class" and sym.get("name"):
                class_syms[sym["name"]] = sym
        for cls_name, cls_sym in class_syms.items():
            bases = cls_sym.get("bases", [])
            if not bases:
                continue
            visited: set[str] = set()
            stack = list(bases)
            while stack:
                raw = stack.pop()
                base_name = raw.split(".")[-1] if "." in raw else raw
                if base_name in visited or base_name not in class_syms:
                    continue
                visited.add(base_name)
                if base_name in abstract:
                    continue
                base_methods = self._methods_by_class.get(base_name, [])
                child_methods = self._methods_by_class.setdefault(cls_name, [])
                existing_ids = {m.get("id", "") for m in child_methods}
                for m in base_methods:
                    if m.get("id", "") not in existing_ids:
                        child_methods.append(m)
                        existing_ids.add(m.get("id", ""))
                for b in class_syms[base_name].get("bases", []):
                    resolved = b.split(".")[-1] if "." in b else b
                    if resolved not in visited:
                        stack.append(b)

    def _split_dotted_path(self, path: str) -> list[str]:
        parts: list[str] = []
        current: list[str] = []
        depth = 0
        for ch in path:
            if ch == "(":
                depth += 1
                current.append(ch)
            elif ch == ")":
                depth -= 1
                current.append(ch)
            elif ch == "." and depth == 0:
                parts.append("".join(current))
                current = []
            else:
                current.append(ch)
        parts.append("".join(current))
        return parts

    def _strip_call_args(self, segment: str) -> str:
        paren = segment.find("(")
        return segment[:paren] if paren != -1 else segment

    def _normalize_callee_raw(self, callee_raw: str) -> str:
        parts = self._split_dotted_path(callee_raw)
        cleaned = [self._strip_call_args(p) for p in parts]
        return ".".join(cleaned)

    def _resolve_callee(
        self, callee_raw: str
    ) -> dict[str, Any] | None:
        normalized = self._normalize_callee_raw(callee_raw)
        if normalized in self._symbols_by_name:
            return self._symbols_by_name[normalized][0]

        parts = normalized.split(".")
        if len(parts) >= 2:
            for i in range(len(parts) - 2, -1, -1):
                cls_name = parts[i]
                if cls_name in self._symbols_by_name:
                    for cls_sym in self._symbols_by_name[cls_name]:
                        if cls_sym.get("kind") == "class":
                            method_name = ".".join(parts[i + 1:])
                            for msym in self._symbols_by_name.get(cls_name, []):
                                recv = msym.get("receiver")
                                if recv == cls_name and msym.get("name") == method_name:
                                    return msym
                            candidates = self._get_methods_for_class(cls_name)
                            for cm in candidates:
                                if cm.get("name") == method_name:
                                    return cm

        for i in range(len(parts), 0, -1):
            candidate = ".".join(parts[:i])
            if candidate in self._symbols_by_name:
                return self._symbols_by_name[candidate][0]

        return None

    def _get_methods_for_class(self, class_name: str) -> list[dict[str, Any]]:
        return self._methods_by_class.get(class_name, [])

    # ── Classification helpers ──────────────────────────────

    def _sym_classification(self, name: str) -> str | None:
        entry: Any = self._classification.get("symbols", {}).get(name)
        if entry:
            val: Any = entry.get("kind")
            return str(val) if val else None
        return None

    def _entry_classification(self, name: str) -> str | None:
        entry: Any = self._classification.get("entries", {}).get(name)
        if entry:
            val: Any = entry.get("kind")
            return str(val) if val else None
        return None

    def classify_symbol(self, names: list[str], kind: str) -> dict[str, Any]:
        _classify_apply(self._classification, kind, names, "symbols")
        self._resolve_inherited_methods()
        return {"classified": len(names), "kind": kind, "names": names}

    def classify_entry(self, names: list[str], kind: str) -> dict[str, Any]:
        _classify_apply(self._classification, kind, names, "entries")
        self._resolve_inherited_methods()
        return {"classified": len(names), "kind": kind, "names": names}

    def unclassify_symbol(self, names: list[str]) -> dict[str, Any]:
        _unclassify_section(self._classification, names, "symbols")
        self._resolve_inherited_methods()
        return {"unclassified": len(names)}

    def unclassify_entry(self, names: list[str]) -> dict[str, Any]:
        _unclassify_section(self._classification, names, "entries")
        self._resolve_inherited_methods()
        return {"unclassified": len(names)}

    def list_classifications(self, kind: str | None = None) -> dict[str, Any]:
        symbols = self._classification.get("symbols", {})
        entries = self._classification.get("entries", {})
        if kind:
            symbols = {k: v for k, v in symbols.items() if v.get("kind") == kind}
            entries = {k: v for k, v in entries.items() if v.get("kind") == kind}
        return {"symbols": symbols, "entries": entries}

    def classify_discover(self, min_calls: int = 10) -> dict[str, Any]:
        candidates: list[dict[str, Any]] = []
        for name, fan_in in sorted(
            self._fan_in.items(), key=lambda x: -x[1]
        ):
            if fan_in >= min_calls and self._sym_classification(name) is None:
                candidates.append({
                    "name": name,
                    "unique_callers": fan_in,
                    "suggested_kind": "utility",
                })
        return {
            "candidates": candidates,
            "count": len(candidates),
            "hint": "Run classify_symbol(names=[...], kind='utility') to classify",
        }

    # ── Filter + summary helpers ────────────────────────────

    def _apply_filters(
        self,
        sym: dict[str, Any],
        kind: str | None = None,
        entry_kind: str | None = None,
        min_calls: int | None = None,
        max_calls: int | None = None,
    ) -> bool:
        if kind:
            sym_class = self._sym_classification(sym.get("name", ""))
            if kind.startswith("!"):
                if sym_class == kind[1:]:
                    return False
            elif sym_class != kind:
                return False
        if entry_kind:
            entry_class = self._entry_classification(sym.get("entry_name", ""))
            if entry_kind.startswith("!"):
                if entry_class == entry_kind[1:]:
                    return False
            elif entry_class != entry_kind:
                return False
        name = sym.get("name", "")
        fan_in = self._fan_in.get(name, 0)
        too_many = min_calls is not None and fan_in >= min_calls
        too_few = max_calls is not None and fan_in <= max_calls
        return not (too_many or too_few)

    def _summarize(
        self, items: list[dict[str, Any]], group_key: str
    ) -> list[dict[str, Any]]:
        groups: dict[str, dict[str, Any]] = {}
        for item in items:
            key = item.get(group_key, "")
            entry = item.get("entry_name", "")
            composite = f"{entry}::{key}"
            if composite not in groups:
                groups[composite] = {
                    group_key: key,
                    "entry_name": entry,
                    "call_count": 0,
                    "unique_files": set(),
                    "unique_callers": set(),
                    "samples": [],
                }
            groups[composite]["call_count"] += 1
            groups[composite]["unique_files"].add(item.get("file", ""))
            if "caller" in item:
                groups[composite]["unique_callers"].add(item.get("caller", ""))
            if len(groups[composite]["samples"]) < 3:
                groups[composite]["samples"].append(item)

        result = []
        for g in groups.values():
            g["unique_files"] = sorted(g["unique_files"])
            g["unique_callers"] = sorted(g["unique_callers"])
            result.append(g)
        result.sort(key=lambda x: -x["call_count"])
        return result

    def _truncate(
        self, items: list[Any], max_results: int | None
    ) -> tuple[list[Any], bool]:
        if max_results is not None and len(items) > max_results:
            return items[:max_results], True
        return items, False

    # ── Query methods ───────────────────────────────────────

    def find_symbols(
        self,
        pattern: str,
        kind: str | None = None,
        entry_kind: str | None = None,
        min_calls: int | None = None,
        max_calls: int | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        matched: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sym in self.graph.symbols:
            sym_id = sym.get("id", "")
            if sym_id and sym_id in seen:
                continue
            if not _match(sym.get("name", ""), pattern):
                continue
            if not self._apply_filters(sym, kind, entry_kind, min_calls, max_calls):
                continue
            # Build token-efficient snippet from full signature
            sig = sym.get("signature", "")
            snippet = _make_snippet(sig)
            if snippet:
                sym = dict(sym)
                sym["snippet"] = snippet
            matched.append(sym)
            seen.add(sym_id)
        items, truncated = self._truncate(matched, max_results)
        return {"items": items, "total": len(matched), "truncated": truncated}

    def _find_by_fqn(self, name: str) -> list[dict[str, Any]]:
        if "." not in name:
            return []
        parts = name.rsplit(".", 1)
        cls_part, method_part = parts[0], parts[1]
        result: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            if sym.get("receiver") == cls_part and sym.get("name") == method_part:
                result.append(sym)
            if sym.get("name") == name and sym.get("receiver") == "":
                result.append(sym)
        return result

    def get_symbol(self, name: str) -> dict[str, Any] | None:
        if "." in name:
            fqn = self._find_by_fqn(name)
            if fqn:
                return fqn[0]
        matches = self._symbols_by_name.get(name, [])
        if matches:
            return matches[0]
        return None

    def get_all_symbols(self, name: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = list(self._symbols_by_name.get(name, []))
        for sym in self.graph.symbols:
            receiver = sym.get("receiver")
            if receiver and sym.get("name") == name and sym not in result:
                result.append(sym)
        if "." in name:
            fqn = self._find_by_fqn(name)
            for s in fqn:
                if s not in result:
                    result.append(s)
        return result

    def get_callers(
        self,
        symbol_name: str,
        kind: str | None = None,
        entry_kind: str | None = None,
        min_calls: int | None = None,
        max_calls: int | None = None,
        max_results: int | None = None,
    ) -> dict[str, Any]:
        raw: list[tuple[dict[str, Any], dict[str, Any]]] = []
        target_ids: set[str] = set()
        for sym in self.get_all_symbols(symbol_name):
            sid = sym.get("id", "")
            if sid:
                target_ids.add(sid)

        for edge in self.graph.calls:
            callee = self._resolve_callee(edge.get("callee_raw", ""))
            if callee is None:
                continue
            callee_id = callee.get("id", "")
            callee_receiver = callee.get("receiver")
            if callee_id in target_ids or callee_receiver == symbol_name:
                caller_sym = self._symbols_by_id.get(edge.get("caller_symbol_id", ""))
                if caller_sym:
                    raw.append((caller_sym, edge))

        items = [
            {
                "caller": cs.get("name", ""),
                "file": ce.get("file", ""),
                "line": ce.get("line", 0),
                "callee_raw": ce.get("callee_raw", ""),
                "entry_name": ce.get("entry_name", ""),
            }
            for cs, ce in raw
            if self._apply_filters(cs, kind, entry_kind, min_calls, max_calls)
        ]

        total = len(items)
        items, truncated = self._truncate(items, max_results)
        return {"items": items, "total": total, "truncated": truncated}

    def _caller_class(self, caller_name: str) -> str | None:
        """Find the class that a method belongs to, if any."""
        lookup = caller_name.split(".")[-1] if "." in caller_name else caller_name
        direct = self._class_by_method_name.get(lookup)
        if direct:
            return direct
        for cls_name, methods in self._methods_by_class.items():
            for m in methods:
                if m.get("name") == lookup:
                    return cls_name
        return None

    def get_callees(
        self,
        symbol_name: str,
        kind: str | None = None,
        entry_kind: str | None = None,
        min_calls: int | None = None,
        max_calls: int | None = None,
        max_results: int | None = None,
        filter_builtins: bool = True,
        filter_self: bool = True,
        filter_dict_accessors: bool = True,
        filter_constructors: bool = True,
        filter_noise: bool = True,
        group_by_class: bool = True,
    ) -> dict[str, Any]:
        raw: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []
        seen: set[tuple[str, str, int]] = set()
        for sym in self.get_all_symbols(symbol_name):
            sym_id = sym.get("id", "")
            edges = self._callees_of.get(sym_id, [])
            for edge in edges:
                callee = self._resolve_callee(edge.get("callee_raw", ""))
                cid = edge.get("caller_symbol_id", "")
                craw = edge.get("callee_raw", "")
                lineno = edge.get("line", 0)
                k = (cid, craw, lineno)
                if k not in seen:
                    seen.add(k)
                    raw.append((callee, edge))

            if sym.get("kind") == "class":
                for method_sym in self.graph.symbols:
                    if method_sym.get("receiver") == sym.get("name"):
                        method_id = method_sym.get("id", "")
                        method_edges = self._callees_of.get(method_id, [])
                        for edge in method_edges:
                            callee = self._resolve_callee(edge.get("callee_raw", ""))
                            cid = edge.get("caller_symbol_id", "")
                            craw = edge.get("callee_raw", "")
                            lineno = edge.get("line", 0)
                            k = (cid, craw, lineno)
                            if k not in seen:
                                seen.add(k)
                                raw.append((callee, edge))

        items: list[dict[str, Any]] = []
        self_ref_count = 0
        builtin_count = 0
        dict_accessor_count = 0
        constructor_count = 0
        caller_class = self._caller_class(symbol_name)
        for cs, ce in raw:
            callee_name = cs.get("name", "") if cs else ce.get("callee_raw", "")
            callee_receiver = cs.get("receiver", "") if cs else ""

            if filter_self:
                if callee_receiver and callee_receiver == symbol_name:
                    self_ref_count += 1
                    continue
                if callee_receiver and caller_class and callee_receiver == caller_class:
                    self_ref_count += 1
                    continue
                if cs is None and ce.get("callee_raw", "").startswith(("self.", "cls.", "self[")):
                    self_ref_count += 1
                    continue
            if filter_builtins and callee_name in PYTHON_BUILTINS:
                builtin_count += 1
                continue
            if filter_dict_accessors:
                callee_raw = ce.get("callee_raw", "")
                is_dict_method = callee_name in DICT_LIKE_METHODS or any(
                    m in callee_raw for m in DICT_LIKE_METHODS
                )
                if is_dict_method:
                    dict_accessor_count += 1
                    continue
            if filter_constructors:
                is_ctor = callee_name in ("__init__", "__new__")
                if not is_ctor and callee_name in self._symbols_by_name:
                    for cand in self._symbols_by_name[callee_name]:
                        if cand.get("kind") == "class":
                            is_ctor = True
                            break
                if is_ctor:
                    constructor_count += 1
                    continue

            if filter_noise:
                noise_set = self._classification.get("symbols", {})
                is_noise = False
                check = callee_name
                while check:
                    info = noise_set.get(check)
                    if info and info.get("kind") == "noise":
                        is_noise = True
                        break
                    if "." in check:
                        check = check.rsplit(".", 1)[0]
                    else:
                        break
                if is_noise:
                    continue

            items.append({
                "callee": callee_name,
                "receiver": callee_receiver,
                "file": ce.get("file", ""),
                "line": ce.get("line", 0),
                "callee_raw": ce.get("callee_raw", ""),
                "entry_name": ce.get("entry_name", ""),
            })

        filtered = [
            it for it in items
            if self._apply_filters(
                {"name": it["callee"], "entry_name": it.get("entry_name", ""), "kind": ""},
                kind, entry_kind, min_calls, max_calls,
            )
        ]

        if group_by_class and filtered:
            classes: dict[str, dict[str, Any]] = {}
            standalone: list[dict[str, Any]] = []
            for item in filtered:
                receiver = item.get("receiver", "")
                if receiver:
                    cls_entry = classes.setdefault(receiver, {
                        "class": receiver,
                        "methods_called": {},
                        "total_calls": 0,
                        "unique_files": set(),
                    })
                    method_name = item["callee"]
                    cls_entry["methods_called"].setdefault(method_name, 0)
                    cls_entry["methods_called"][method_name] += 1
                    cls_entry["total_calls"] += 1
                    cls_entry["unique_files"].add(item.get("file", ""))
                else:
                    standalone.append(item)

            grouped_result = []
            for cls_data in classes.values():
                cls_data["unique_files"] = len(cls_data["unique_files"])
                grouped_result.append(cls_data)
            grouped_result.sort(key=lambda x: -x["total_calls"])
            standalone.sort(key=lambda x: -(x.get("line", 0)))

            result: dict[str, Any] = {
                "classes": grouped_result,
                "standalone": standalone,
                "total_classes": len(grouped_result),
                "total_standalone": len(standalone),
            }
            if self_ref_count:
                result["filtered_self_ref"] = self_ref_count
            if builtin_count:
                result["filtered_builtins"] = builtin_count
            if dict_accessor_count:
                result["filtered_dict_accessors"] = dict_accessor_count
            if constructor_count:
                result["filtered_constructors"] = constructor_count
            total = len(grouped_result) + len(standalone)
            return {"items": result, "total": total, "truncated": False}

        total = len(filtered)
        filtered, truncated = self._truncate(filtered, max_results)
        return {"items": filtered, "total": total, "truncated": truncated}

    def get_routes(self) -> list[dict[str, Any]]:
        return list(self.graph.routes)

    def get_orphans(
        self, include_public: bool = False, skip_underscore: bool = True,
    ) -> list[dict[str, Any]]:
        entry_names: set[str] = set()
        if self.graph.manifest:
            for entry in self.graph.manifest.entries:
                entry_names.add(entry.name)

        visited_ids: set[str] = set()
        queue: deque[str] = deque()

        for sym in self.graph.symbols:
            if sym.get("is_exported") or self._is_entry_point(sym):
                sid = sym.get("id", "")
                if sid and sid not in visited_ids:
                    visited_ids.add(sid)
                    queue.append(sym.get("name", ""))

        while queue:
            current = queue.popleft()
            for sym in self.get_all_symbols(current):
                sym_id = sym.get("id", "")
                edges = self._callees_of.get(sym_id, [])
                for edge in edges:
                    callee_id = edge.get("_callee_resolved_id", "")
                    if callee_id and callee_id not in visited_ids:
                        visited_ids.add(callee_id)
                        callee_sym = self._symbols_by_id.get(callee_id)
                        if callee_sym:
                            queue.append(callee_sym.get("name", ""))

        orphans: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            sym_id = sym.get("id", "")
            if not sym_id or sym_id in visited_ids:
                continue
            if not include_public and sym.get("is_exported"):
                continue
            if skip_underscore and sym.get("name", "").startswith("_"):
                continue
            orphans.append(sym)
        return orphans

    def _is_entry_point(self, sym: dict[str, Any]) -> bool:
        if sym.get("kind") in ("function", "method"):
            name = sym.get("name", "")
            for route in self.graph.routes:
                if route.get("handler") == name or route.get("handler", "").endswith(f"::{name}"):
                    return True
        return False

    def get_impact(
        self, symbol_name: str, max_depth: int | None = None
    ) -> list[dict[str, Any]]:
        visited_ids: set[str] = set()
        queue: deque[tuple[str, int]] = deque()
        result: list[dict[str, Any]] = []

        queue.append((symbol_name, 0))

        while queue:
            current, depth = queue.popleft()
            if max_depth is not None and depth >= max_depth:
                continue

            for sym in self.get_all_symbols(current):
                sym_id = sym.get("id", "")
                if sym_id in visited_ids:
                    continue
                visited_ids.add(sym_id)

                edges = self._callees_of.get(sym_id, [])
                for edge in edges:
                    callee = self._resolve_callee(edge.get("callee_raw", ""))
                    if callee is None:
                        continue
                    callee_id = callee.get("id", "")
                    result.append({
                        "caller": current,
                        "callee": callee.get("name", ""),
                        "file": edge.get("file", ""),
                        "line": edge.get("line", 0),
                        "entry_name": edge.get("entry_name", ""),
                    })
                    if callee_id and callee_id not in visited_ids:
                        queue.append((callee.get("name", ""), depth + 1))

                if sym.get("kind") == "class":
                    for method_sym in self.graph.symbols:
                        if method_sym.get("receiver") == sym.get("name"):
                            method_id = method_sym.get("id", "")
                            if method_id in visited_ids:
                                continue
                            visited_ids.add(method_id)
                            method_edges = self._callees_of.get(method_id, [])
                            for edge in method_edges:
                                callee = self._resolve_callee(edge.get("callee_raw", ""))
                                if callee is None:
                                    continue
                                callee_id = callee.get("id", "")
                                result.append({
                                    "caller": current,
                                    "callee": callee.get("name", ""),
                                    "file": edge.get("file", ""),
                                    "line": edge.get("line", 0),
                                    "entry_name": edge.get("entry_name", ""),
                                })
                                if callee_id and callee_id not in visited_ids:
                                    queue.append((callee.get("name", ""), depth + 1))

        return result

    def get_context(
        self,
        symbol_name: str,
        include_source: bool = True,
        kind: str | None = None,
        entry_kind: str | None = None,
        min_calls: int | None = None,
        max_calls: int | None = None,
        max_results: int | None = None,
        filter_builtins: bool = True,
        filter_self: bool = True,
        filter_dict_accessors: bool = True,
        filter_constructors: bool = True,
        filter_noise: bool = True,
    ) -> dict[str, Any]:
        symbol = self.get_symbol(symbol_name)
        source: str | None = None
        callers_list: list[dict[str, Any]] = []
        callees_list: list[dict[str, Any]] = []
        tests_list: list[dict[str, Any]] = []

        if symbol:
            caller_result = self.get_callers(
                symbol_name, kind=kind, entry_kind=entry_kind,
                min_calls=min_calls, max_calls=max_calls,
                max_results=max_results,
            )
            callers_list = caller_result["items"]

            callee_result = self.get_callees(
                symbol_name, kind=kind, entry_kind=entry_kind,
                min_calls=min_calls, max_calls=max_calls,
                max_results=max_results,
                filter_builtins=filter_builtins,
                filter_self=filter_self,
                filter_dict_accessors=filter_dict_accessors,
                filter_constructors=filter_constructors,
                filter_noise=filter_noise,
                group_by_class=False,
            )
            callees_list = callee_result["items"]
            if include_source and symbol.get("file"):
                source = self._load_source_snippet(
                    symbol.get("file", ""),
                    symbol.get("line", 0),
                    symbol.get("end_line", 0),
                )

            for te in self.graph.test_edges:
                if te.get("target") == symbol_name:
                    tests_list.append({
                        "test_func": te.get("test_func", ""),
                        "file": te.get("file", ""),
                        "line": te.get("line", 0),
                        "entry_name": te.get("entry_name", ""),
                    })

        return {
            "symbol": symbol,
            "callers": callers_list,
            "callees": callees_list,
            "tests": tests_list,
            "source": source,
        }

    def _load_source_snippet(
        self, file_path: str, start: int, end: int,
    ) -> str | None:
        candidates = [Path(self.root) / file_path]
        if self.graph.manifest:
            for entry in self.graph.manifest.entries:
                candidates.append(Path(self.root) / entry.path / file_path)
        for full in candidates:
            try:
                lines = full.read_text().splitlines()
                if end and end >= start and start > 0:
                    return "\n".join(lines[start - 1:end])
                if start > 0:
                    return "\n".join(lines[start - 1:start + 19])
                return None
            except OSError:
                continue
        return None

    def _load_source(self, file_path: str) -> str | None:
        candidates = [Path(self.root) / file_path]
        if self.graph.manifest:
            for entry in self.graph.manifest.entries:
                candidates.append(Path(self.root) / entry.path / file_path)
        for full in candidates:
            try:
                return full.read_text()
            except OSError:
                continue
        return None

    def _extract_call_args(
        self, file_path: str, line: int, callee_raw: str
    ) -> dict[str, Any]:
        source = self._load_source(file_path)
        if source is None:
            return {"args": [], "kwargs": {}}
        try:
            import ast
            tree = ast.parse(source)
        except SyntaxError:
            return {"args": [], "kwargs": {}}

        def _extract_arg_values(arg: ast.expr) -> list[str]:
            if isinstance(arg, ast.Constant) and isinstance(arg.value, str):
                return [arg.value]
            elif isinstance(arg, ast.Name):
                return [arg.id]
            elif isinstance(arg, (ast.List, ast.Tuple)):
                vals: list[str] = []
                for elt in arg.elts:
                    if isinstance(elt, ast.Constant) and isinstance(elt.value, str):
                        vals.append(elt.value)
                    elif isinstance(elt, ast.Name):
                        vals.append(elt.id)
                return vals
            return []

        for node in ast.walk(tree):
            if not isinstance(node, ast.Call) or getattr(node, "lineno", None) != line:
                continue
            parsed = ast.unparse(node.func)
            name_match = (
                callee_raw.startswith(parsed)
                or parsed.endswith(callee_raw)
                or callee_raw in parsed
                or parsed in callee_raw
            )
            if not name_match:
                continue
            args: list[str] = []
            for arg in node.args:
                args.extend(_extract_arg_values(arg))

            kwargs: dict[str, str] = {}
            for kw in node.keywords:
                if kw.arg is None:
                    continue
                if isinstance(kw.value, ast.Constant) and isinstance(kw.value.value, str):
                    kwargs[kw.arg] = kw.value.value
                elif isinstance(kw.value, ast.Name):
                    kwargs[kw.arg] = kw.value.id
            return {"args": args, "kwargs": kwargs}
        return {"args": [], "kwargs": {}}

    def get_trace(self, error_message: str) -> list[dict[str, Any]]:
        matching: list[dict[str, Any]] = []
        for err in self.graph.errors:
            msg = err.get("message", "")
            if error_message in msg or msg in error_message:
                matching.append({
                    "message": msg,
                    "function": err.get("function_name", ""),
                    "file": err.get("file", ""),
                    "line": err.get("line", 0),
                    "entry_name": err.get("entry_name", ""),
                })
        return matching

    def get_cross_service_edges(
        self,
        source_entry: str | None = None,
        target_entry: str | None = None,
    ) -> list[dict[str, Any]]:
        edges = list(self.graph.cross_service_edges)
        if source_entry:
            edges = [e for e in edges if e.get("source_entry") == source_entry]
        if target_entry:
            edges = [e for e in edges if e.get("target_entry") == target_entry]
        return edges

    def get_errorflow(self, error_message: str) -> list[dict[str, Any]]:
        matching_errors = [
            e for e in self.graph.errors
            if error_message in e.get("message", "") or e.get("message", "") in error_message
        ]

        result: list[dict[str, Any]] = []
        visited_funcs: set[str] = set()
        for err in matching_errors:
            fn_name = err.get("function_name", "")
            if fn_name in visited_funcs:
                continue
            visited_funcs.add(fn_name)

            trace: list[dict[str, Any]] = []
            queue: deque[tuple[str, int]] = deque([(fn_name, 0)])

            while queue:
                fn, _depth = queue.popleft()
                callers = self._callers_by_name.get(fn, [])
                for _caller_entry, edge in callers:
                    caller_sym = self._symbols_by_id.get(edge.get("caller_symbol_id", ""))
                    if caller_sym and caller_sym.get("name", "") not in visited_funcs:
                        visited_funcs.add(caller_sym.get("name", ""))
                        trace.append({
                            "from": caller_sym.get("name", ""),
                            "to": fn,
                            "file": edge.get("file", ""),
                            "line": edge.get("line", 0),
                            "entry_name": edge.get("entry_name", ""),
                        })
                        queue.append((caller_sym.get("name", ""), _depth + 1))

            result.append({
                "error": err,
                "trace": trace,
            })

        return result
