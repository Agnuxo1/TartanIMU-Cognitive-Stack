"""Safe deterministic handlers that avoid LLM calls when possible."""
from __future__ import annotations

import ast
import operator
import re

_BINOPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul, ast.Div: operator.truediv, ast.FloorDiv: operator.floordiv, ast.Mod: operator.mod, ast.Pow: operator.pow}
_UNARY = {ast.UAdd: operator.pos, ast.USub: operator.neg}

def _eval(node: ast.AST):
    if isinstance(node, ast.Expression):
        return _eval(node.body)
    if isinstance(node, ast.Constant) and isinstance(node.value, (int, float)):
        return node.value
    if isinstance(node, ast.BinOp) and type(node.op) in _BINOPS:
        return _BINOPS[type(node.op)](_eval(node.left), _eval(node.right))
    if isinstance(node, ast.UnaryOp) and type(node.op) in _UNARY:
        return _UNARY[type(node.op)](_eval(node.operand))
    raise ValueError("Unsupported expression")

def try_exact_math(task: str) -> str | None:
    """Evaluate only a clearly arithmetic request with an explicit expression."""
    lowered = task.lower()
    arithmetic_signal = bool(re.search(r"\b(?:calculate|compute|evaluate|what is|solve)\b", lowered))
    stripped = task.strip()
    expression_only = bool(re.fullmatch(r"[\s\d.+\-*/%()]+", stripped))
    if not arithmetic_signal and not expression_only:
        return None
    candidates = re.findall(r"[+\-]?(?:\d+(?:\.\d+)?)(?:\s*(?:\*\*|[+\-*/%])\s*[+\-]?(?:\d+(?:\.\d+)?))+", task)
    if not candidates:
        return None
    expr = max(candidates, key=len).strip()
    try:
        return str(_eval(ast.parse(expr, mode="eval")))
    except Exception:
        return None

def deterministic_route(task: str) -> dict[str, object]:
    """Return a non-generative execution decision for the handlers we can prove safe."""
    exact = try_exact_math(task)
    return {
        "handled": exact is not None,
        "result": exact,
        "kind": "exact_math" if exact is not None else None,
        "confidence": 1.0 if exact is not None else 0.0,
    }

def compress_context(text: str, max_chars: int = 8000) -> str:
    text = text.strip()
    if len(text) <= max_chars:
        return text
    head = text[: int(max_chars * 0.65)]
    tail = text[-int(max_chars * 0.30):]
    return head + "\n...[context deterministically truncated]...\n" + tail
