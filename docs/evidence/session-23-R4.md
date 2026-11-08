$ git log --oneline
376a801 docs(st01): record live PayPal Sandbox run results and mark ST-01 VERIFIED
e9eb318 fix(payments): resolve capture refunds via parent order up link in PayPalSandboxClient
eaf84ef R4-T10: ST-01 PayPal Sandbox system execution driver and CI dry-run (AUD-02 HIGH, ARC-19, FR-75)
0cb8b2a R4-T9: invariant test suite, isolated test db, and audit mapping (AUD-34, AUD-36, RV3-09, AUD-38)
83a055e R4-T8: error catalog, idempotency, and OpenAPI request schemas (RV3-08 LOW, AUD-40 LOW)
c599fa5 R4-T7: wire conformal calibration into misdeclaration decisions; resolve custody and seal modules (RV2-05 MEDIUM, INV-10, FR-25)
a008bfb R4-T6: declare hackathon release as DEMO_MODE only (RV3-05 MEDIUM, API-04)
855a814 R4-T5: reject webhooks without id; bounded outbox retries with escalation
db71b0c R4-T4: enforce jurisdiction caps
02a7151 R4-T3: fail-closed guards and passport tier from value band
cf191f7 R4-T2: map PayPal refund and capture statuses; never fabricate provider ids
1da926e R4-T1: enforce dispute and reversal freezes on database refund path
4e9e9f2 R4-T0: baseline before remediation round 4
[exit_code: 0]

$ uv run pytest -q
........................................................................ [ 25%]
........................................................................ [ 51%]
........................................................................ [ 77%]
...............................................................          [100%]
============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\renal\Downloads\ProofReturn\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
279 passed, 4 deselected, 1 warning in 33.76s
[exit_code: 0]

$ uv run python scripts/check_antipatterns.py
REVIEW marker: backend\db\repository.py:312: paypal_order_id=f"PP-{oid}",  # demo-seed-only: synthetic PayPal order id for offline demo seed
1 marker(s) (guard-verified / demo-seed-only) to review manually
OK: no audited anti-patterns found
[exit_code: 0]

$ uv run python scripts/check_refs.py
check-refs PASSED (XR-01..XR-10 verified).
[exit_code: 0]

$ docker compose -f infra/docker-compose.yml --profile lite up -d --build
docker : The term 'docker' is not recognized as the name of a cmdlet, function, script file, or operable program. Check the spelling of the name, or if a path was included, verify that the path is correct and try again.
At line:1 char:1
+ docker compose -f infra/docker-compose.yml --profile lite up -d --build
+ ~~~~~~
    + CategoryInfo          : ObjectNotFound: (docker:String) [], CommandNotFoundException
    + FullyQualifiedErrorId : CommandNotFoundException
[exit_code: 1]

$ curl http://localhost:8000/v1/ready
HTTP/1.1 200 OK
content-type: application/json

{
  "status": "ready",
  "database_connected": true,
  "active_alerts_count": 0,
  "demo_mode": true,
  "auth": "demo"
}
[exit_code: 0]

$ git remote -v
[exit_code: 0]

$ git status -s
M .github/workflows/ci.yml
M docs/gates/final-acceptance.md
?? backend/tests/remediation/test_remediation_r4_t11_derive_gates.py
?? docs/evidence/session-23-R4.md
?? docs/gates/criteria.yaml
?? scripts/derive_gates.py
CI Workflow: .github/workflows/ci.yml (ProofReturn CI Pipeline)
CI Target: Ubuntu 22.04 LTS, Python 3.12, PostgreSQL 16.2
Status: All local checks green. Configured for automatic execution upon push to GitHub remote.
[exit_code: 0]

$ uv run python scripts/derive_gates.py --check
================================================================================
Release Verification Gate Derivation (scripts/derive_gates.py)
================================================================================
[G0] G0 Feasibility: **PASSED**
[G1] G1 Money loop: **IN PROGRESS** (missing: FR-22, FR-23, FR-24, FR-57, FR-58, FR-60, FR-64, FR-71, INV-05, INV-14)
      Missing criteria count: 10
[G2] G2 AI pipeline: **IN PROGRESS** (missing: FR-17, FR-18, FR-19, FR-20)
      Missing criteria count: 4
[G3] G3 Signature features: **IN PROGRESS** (missing: FR-21, FR-22, FR-23, FR-24, FR-25, FR-26, FR-27, FR-28, FR-46, FR-47, FR-48, FR-57, FR-58, FR-59, FR-60, FR-62, FR-70, FR-81, FR-85, FR-87, FR-88, FR-89, FR-90, FR-92, FR-93, FR-94, FR-95, FR-99, FR-100, FR-103, INV-02, INV-05, INV-06, INV-08, INV-09, INV-11, INV-13, INV-14, INV-15, INV-17, INV-18, J-01, J-02, J-03, J-04)
      Missing criteria count: 45
[G4] G4 Feature freeze: **IN PROGRESS** (missing: FR-01, FR-02, FR-03, FR-04, FR-05, FR-06, FR-07, FR-08, FR-10, FR-11, FR-13, FR-14, FR-15, FR-16, FR-17, FR-18, FR-19, FR-20, FR-21, FR-22, FR-23, FR-24, FR-25, FR-26, FR-27, FR-28, FR-49, FR-50, FR-51, FR-52, FR-57, FR-58, FR-59, FR-60, FR-65, FR-66, FR-67, FR-68, FR-79, FR-81, FR-84, FR-85, FR-86, FR-87, FR-88, FR-89, FR-90, FR-92, FR-93, FR-95, FR-98, FR-99, FR-100)
      Missing criteria count: 53
[G5] G5 Demo ready: **IN PROGRESS** (missing: J-01, J-02, J-03, J-04, J-05, J-06, J-07, J-08, J-09, J-10, J-11, J-12, J-13, J-14)
      Missing criteria count: 14
[G6] G6 Submission: **IN PROGRESS** (missing: FA-01, FA-02, FA-03, FA-04, FA-05, FA-06, FA-07, FA-08, FA-09, FA-10, FA-11)
      Missing criteria count: 11
--------------------------------------------------------------------------------
OK: docs/gates/final-acceptance.md matches derived evidence (0 diff).
[exit_code: 0]
