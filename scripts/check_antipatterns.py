#!/usr/bin/env python3
"""Audit gate v2: exits 1 when known audit anti-patterns exist in non-test backend code."""
import ast, pathlib, re, sys

ROOT = pathlib.Path(sys.argv[1]).resolve() if len(sys.argv) > 1 else pathlib.Path(__file__).resolve().parents[1]
SRC = [p for p in (ROOT / "backend").rglob("*.py") if "tests" not in p.parts and "migrations" not in p.parts]
GUARDS = {"within_window", "consent_recorded", "authorized", "evidence_complete", "challenge_valid", "retakes_ok",
          "assessment_exists", "eligible", "not_expired", "seal_nonce_matches", "source_authentic", "exposure_cap_ok",
          "reviewer_authorized", "sla_exceeded", "within_extended_grace", "within_appeal_window"}
problems, markers = [], []

def rel(p): return p.relative_to(ROOT)

for path in SRC:
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    marked = lambda ln: "guard-verified:" in lines[ln - 1]
    for node in ast.walk(ast.parse(text)):
        # 1. Broad exception swallowed
        if isinstance(node, ast.ExceptHandler):
            broad = node.type is None or (isinstance(node.type, ast.Name) and node.type.id in {"Exception", "BaseException"})
            if broad and all(isinstance(s, ast.Pass) for s in node.body):
                problems.append(f"{rel(path)}:{node.lineno}: broad exception swallowed with pass")
        # 2. Literal True guards, and `x or True` anywhere in a transition call
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute) and node.func.attr in {"apply_return_transition", "apply"}:
            for kw in node.keywords:
                v = kw.value
                if isinstance(v, ast.Constant) and v.value is True:
                    if marked(v.lineno):
                        markers.append(f"{rel(path)}:{v.lineno}: {lines[v.lineno - 1].strip()}")
                        continue
                    problems.append(f"{rel(path)}:{node.lineno}: guard '{kw.arg}' passed as literal True")
                if isinstance(v, ast.BoolOp) and isinstance(v.op, ast.Or) and any(isinstance(x, ast.Constant) and x.value is True for x in v.values):
                    problems.append(f"{rel(path)}:{node.lineno}: guard '{kw.arg}' uses `or True`")
        # 3. Guard variables initialised to True (fail-open default)
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            value = node.value
            if isinstance(value, ast.Constant) and value.value is True:
                for t in targets:
                    if isinstance(t, ast.Name) and t.id in GUARDS and not marked(node.lineno):
                        problems.append(f"{rel(path)}:{node.lineno}: guard variable '{t.id}' defaults to True (fail-open)")
        # 4. Hardcoded success/verification flags
        if isinstance(node, ast.Dict):
            for k, v in zip(node.keys, node.values):
                if not (isinstance(k, ast.Constant) and isinstance(v, ast.Constant)):
                    continue
                if k.value in {"verified", "chain_valid"} and v.value is True:
                    problems.append(f"{rel(path)}:{node.lineno}: '{k.value}' hardcoded to True")
                if k.value == "status" and v.value == "COMPLETED" and "payments" in path.parts:
                    problems.append(f"{rel(path)}:{node.lineno}: payment status 'COMPLETED' fabricated")
    for i, line in enumerate(lines, 1):
        if re.search(r"(?i)x-paypal-signature-valid", line):
            problems.append(f"{rel(path)}:{i}: client-controlled webhook signature header")
        if re.search(r'f["\'](CAP|PP|PAYPAL|REF|ORD|PP-REF)[-_]\{', line) or re.search(r'f["\']PP-REF-\{', line):
            if "demo-seed-only:" in line:
                markers.append(f"{rel(path)}:{i}: {line.strip()}")
            else:
                problems.append(f"{rel(path)}:{i}: fabricated provider id")
        if re.search(r"create_app\([^)]*demo_mode\s*=\s*True", line):
            problems.append(f"{rel(path)}:{i}: demo mode forced at module level")
        if re.search(r"posted_price_minor\s+or\s+\d+", line):
            problems.append(f"{rel(path)}:{i}: hardcoded keep-offer fallback price")
        if re.search(r'"p95_eval_seconds"\s*:\s*[0-9.]+', line):
            problems.append(f"{rel(path)}:{i}: hardcoded latency metric")
        if re.search(r"(event_id|webhook_event_id)\s*=.*\bor\b.*(uuid|token_hex|random)", line) or re.search(r"get\(\s*[\"']id[\"']\s*,.*(uuid|token_hex|random)", line):
            problems.append(f"{rel(path)}:{i}: random fallback for provider event id")

for p in problems:
    print("FAIL", p)
for m in markers:
    print("REVIEW marker:", m)
print(f"{len(markers)} marker(s) (guard-verified / demo-seed-only) to review manually")
print(f"{len(problems)} anti-pattern(s) found" if problems else "OK: no audited anti-patterns found")
sys.exit(1 if problems else 0)