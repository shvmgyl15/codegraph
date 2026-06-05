from __future__ import annotations

import re
from collections import deque
from pathlib import Path
from typing import Any

from codegraph.graph.types import UnifiedGraph


def _match(name: str, pattern: str) -> bool:
    try:
        return re.search(pattern, name) is not None
    except re.error:
        return pattern in name


class WorkspaceQuery:
    def __init__(self, graph: UnifiedGraph, root: str = ".") -> None:
        self.graph = graph
        self.root = root
        self._symbols_by_name: dict[str, list[dict[str, Any]]] = {}
        self._symbols_by_id: dict[str, dict[str, Any]] = {}
        self._callees_of: dict[str, list[dict[str, Any]]] = {}
        self._callers_by_name: dict[str, list[tuple[str, dict[str, Any]]]] = {}
        self._build_index()

    def _build_index(self) -> None:
        for sym in self.graph.symbols:
            sym_name = sym.get("name", "")
            self._symbols_by_name.setdefault(sym_name, []).append(sym)
            sym_id = sym.get("id", "")
            if sym_id:
                self._symbols_by_id[sym_id] = sym

        for call in self.graph.calls:
            cid = call.get("caller_symbol_id", "")
            self._callees_of.setdefault(cid, []).append(call)

            callee_raw = call.get("callee_raw", "")
            resolved = self._resolve_callee(callee_raw)
            if resolved:
                resolved_name = resolved.get("name", "")
                caller_sym = self._symbols_by_id.get(cid)
                caller_entry = caller_sym.get("entry_name", "") if caller_sym else ""
                self._callers_by_name.setdefault(resolved_name, []).append(
                    (caller_entry, call)
                )
                receiver = resolved.get("receiver")
                if receiver:
                    self._callers_by_name.setdefault(receiver, []).append(
                        (caller_entry, call)
                    )

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
        result: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            if sym.get("receiver") == class_name:
                result.append(sym)
        return result

    def find_symbols(self, pattern: str) -> list[dict[str, Any]]:
        matched: list[dict[str, Any]] = []
        seen: set[str] = set()
        for sym in self.graph.symbols:
            sym_id = sym.get("id", "")
            if sym_id not in seen and _match(sym.get("name", ""), pattern):
                matched.append(sym)
                seen.add(sym_id)
        return matched

    def get_symbol(self, name: str) -> dict[str, Any] | None:
        matches = self._symbols_by_name.get(name, [])
        if matches:
            return matches[0]
        return None

    def get_all_symbols(self, name: str) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = list(self._symbols_by_name.get(name, []))
        for sym in self.graph.symbols:
            receiver = sym.get("receiver")
            if receiver and sym.get("name") == name:
                qualified = f"{receiver}.{name}"
                if qualified == name and sym not in result:
                    result.append(sym)
        return result

    def get_callers(
        self, symbol_name: str
    ) -> list[tuple[dict[str, Any], dict[str, Any]]]:
        result: list[tuple[dict[str, Any], dict[str, Any]]] = []
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
                    result.append((caller_sym, edge))
        return result

    def get_callees(
        self, symbol_name: str
    ) -> list[tuple[dict[str, Any] | None, dict[str, Any]]]:
        result: list[tuple[dict[str, Any] | None, dict[str, Any]]] = []
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
                    result.append((callee, edge))

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
                                result.append((callee, edge))
        return result

    def get_routes(self) -> list[dict[str, Any]]:
        return list(self.graph.routes)

    def get_orphans(self, include_public: bool = False) -> list[dict[str, Any]]:
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
                    callee = self._resolve_callee(edge.get("callee_raw", ""))
                    if callee:
                        callee_id = callee.get("id", "")
                        if callee_id and callee_id not in visited_ids:
                            visited_ids.add(callee_id)
                            queue.append(callee.get("name", ""))

        orphans: list[dict[str, Any]] = []
        for sym in self.graph.symbols:
            sym_id = sym.get("id", "")
            if sym_id and sym_id not in visited_ids and (
                include_public or not sym.get("is_exported")
            ):
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
        self, symbol_name: str, include_source: bool = True
    ) -> dict[str, Any]:
        symbol = self.get_symbol(symbol_name)
        source: str | None = None
        callers_list: list[dict[str, Any]] = []
        callees_list: list[dict[str, Any]] = []
        tests_list: list[dict[str, Any]] = []

        if symbol:
            for caller_sym, edge in self.get_callers(symbol_name):
                callers_list.append({
                    "caller": caller_sym.get("name", ""),
                    "file": caller_sym.get("file", ""),
                    "line": edge.get("line", 0),
                    "callee_raw": edge.get("callee_raw", ""),
                    "entry_name": edge.get("entry_name", ""),
                })
            for callee_sym, edge in self.get_callees(symbol_name):
                if callee_sym:
                    callee_name = callee_sym.get("name", "")
                else:
                    callee_name = edge.get("callee_raw", "")
                callee_file = callee_sym.get("file", "") if callee_sym else ""
                callees_list.append({
                    "callee": callee_name,
                    "file": callee_file,
                    "line": edge.get("line", 0),
                    "callee_raw": edge.get("callee_raw", ""),
                    "entry_name": edge.get("entry_name", ""),
                })
            if include_source and symbol.get("file"):
                source = self._load_source(symbol.get("file", ""))

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

    def _load_source(self, file_path: str) -> str | None:
        full = Path(self.root) / file_path
        try:
            return full.read_text()
        except OSError:
            return None

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
