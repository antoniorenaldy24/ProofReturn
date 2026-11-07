$ git status
On branch main

No commits yet

Untracked files:
  (use "git add <file>..." to include in what will be committed)
	.env.example
	.github/
	.gitignore
	.nvmrc
	.python-version
	LICENSE
	"Laporan Audit Teknis Independen \342\200\224 ProofReturn.md"
	"Laporan Audit Ulang ke-2 \342\200\224 ProofReturn (Revisi ke-2).md"
	"Laporan Audit Ulang \342\200\224 ProofReturn (Versi Revisi).md"
	Makefile
	ProofReturn_SSOTv1.21.md
	README.md
	alembic.ini
	apps/
	backend/
	config/
	data/
	docs/
	infra/
	package.json
	packages/
	pyproject.toml
	schemas/
	scripts/
	sim/
	uv.lock

nothing added to commit but untracked files present (use "git add" to track)
[exit_code: 0]

$ git rev-parse HEAD
HEAD
fatal: ambiguous argument 'HEAD': unknown revision or path not in the working tree.
Use '--' to separate paths from revisions, like this:
'git <command> [<revision>...] -- [<file>...]'
[exit_code: 128]

$ uv run python scripts/check_antipatterns.py
0 guard-verified marker(s) to review manually
OK: no audited anti-patterns found
[exit_code: 0]

$ uv run python scripts/scan_secrets.py
============================================================
Running ProofReturn Secret & Credential Scanner (AUD-38, TM-12)
============================================================
Scanned 246 files across repository.
[OK] Secret scan passed: 0 credentials or leaked keys detected.
[exit_code: 0]

$ uv run python scripts/check_refs.py
check-refs PASSED (XR-01..XR-10 verified).
[exit_code: 0]

$ uv run python scripts/sync_rtm.py
Synchronized 137 RTM rows in C:\Users\renal\Downloads\ProofReturn\docs\rtm.csv.
[exit_code: 0]

$ npm test
> proofreturn-monorepo@1.21.0 test
> node --test --experimental-strip-types packages/ui/tests/frontend.test.ts

TAP version 13
# (node:29880) ExperimentalWarning: Type Stripping is an experimental feature and might change at any time
# (Use `node --trace-warnings ...` to show where the warning was created)
# Subtest: Design System: formatUsd handles zero, typical, and large minor amounts
ok 1 - Design System: formatUsd handles zero, typical, and large minor amounts
  ---
  duration_ms: 0.5209
  ...
# Subtest: Design System: Shared Components render accessible markup with design tokens
ok 2 - Design System: Shared Components render accessible markup with design tokens
  ---
  duration_ms: 0.2302
  ...
# Subtest: App 1: DemoStorefrontController manages catalog, checkout with card, and order flow
ok 3 - App 1: DemoStorefrontController manages catalog, checkout with card, and order flow
  ---
  duration_ms: 0.3172
  ...
# Subtest: App 2: PackingStationController manages minting passport and receiving dock check-in
ok 4 - App 2: PackingStationController manages minting passport and receiving dock check-in
  ---
  duration_ms: 0.2007
  ...
# Subtest: App 3: ShopperPortalController handles declaration, keep-offer, decision, and free cancel
ok 5 - App 3: ShopperPortalController handles declaration, keep-offer, decision, and free cancel
  ---
  duration_ms: 1.1653
  ...
# Subtest: App 4: MerchantConsoleController manages dashboard KPIs, reviewer queue, policy, and simulator
ok 6 - App 4: MerchantConsoleController manages dashboard KPIs, reviewer queue, policy, and simulator
  ---
  duration_ms: 0.3914
  ...
1..6
# tests 6
# suites 0
# pass 6
# fail 0
# cancelled 0
# skipped 0
# todo 0
# duration_ms 103.5759
[exit_code: 0]

$ uv run pytest -m "not sandbox and not live_model"
============================= test session starts =============================
platform win32 -- Python 3.12.13, pytest-9.2.0, pluggy-1.7.0
rootdir: C:\Users\renal\Downloads\ProofReturn
configfile: pyproject.toml
testpaths: backend/tests
plugins: anyio-4.15.1, hypothesis-6.170.13
collected 193 items / 4 deselected / 189 selected

backend\tests\ai\test_ai_pipeline_and_jobs.py .....                      [  2%]
backend\tests\ai\test_gemini_provider.py .....                           [  5%]
backend\tests\api\test_api_authz_and_mcp.py .....                        [  7%]
backend\tests\api\test_full_rest_api_v1.py ...                           [  9%]
backend\tests\api\test_remediation_fase3_persistence_and_concurrency.py . [ 10%]
....                                                                     [ 12%]
backend\tests\domain\test_domain_and_schemas.py ....                     [ 14%]
backend\tests\golden\test_golden_examples.py ..........                  [ 19%]
backend\tests\mechanism\test_minimum_shippable_and_journeys.py ......    [ 22%]
backend\tests\ops\test_privacy_observability_and_ops.py .......          [ 26%]
backend\tests\payments\test_payments_and_failures.py .....               [ 29%]
backend\tests\policy_engine\test_mechanism_verification.py ............. [ 35%]
.....                                                                    [ 38%]
backend\tests\remediation\test_remediation_fase4_ai_and_calibration.py . [ 39%]
......                                                                   [ 42%]
backend\tests\remediation\test_remediation_fase5_observability_and_security.py . [ 42%]
.....                                                                    [ 45%]
backend\tests\remediation\test_remediation_fase6_e2e_release_gates.py .. [ 46%]
....                                                                     [ 48%]
backend\tests\remediation\test_remediation_tahap10_transactional_money_path.py . [ 49%]
.......                                                                  [ 52%]
backend\tests\remediation\test_remediation_tahap11_outbox_executor.py .. [ 53%]
....                                                                     [ 56%]
backend\tests\remediation\test_remediation_tahap12_schedulers.py ....    [ 58%]
backend\tests\remediation\test_remediation_tahap13_guards_and_caps.py .. [ 59%]
.........                                                                [ 64%]
backend\tests\remediation\test_remediation_tahap1_security_and_infra.py . [ 64%]
...                                                                      [ 66%]
backend\tests\remediation\test_remediation_tahap2_api_and_engine.py .... [ 68%]
.......                                                                  [ 71%]
backend\tests\remediation\test_remediation_tahap3_payments_and_webhooks.py . [ 72%]
.....                                                                    [ 75%]
backend\tests\remediation\test_remediation_tahap4_contracts_and_hardening.py . [ 75%]
............                                                             [ 82%]
backend\tests\remediation\test_remediation_tahap5_clean_architecture_and_ops.py . [ 82%]
.....                                                                    [ 85%]
backend\tests\remediation\test_remediation_tahap6_automation_and_pipeline.py . [ 85%]
.......                                                                  [ 89%]
backend\tests\remediation\test_remediation_tahap7_frontend_and_e2e.py .. [ 90%]
..                                                                       [ 91%]
backend\tests\remediation\test_remediation_tahap8_token_issuance_and_demo_mode.py . [ 92%]
.....                                                                    [ 94%]
backend\tests\remediation\test_remediation_tahap9_webhook_fail_closed.py . [ 95%]
.....                                                                    [ 97%]
backend\tests\state_machine\test_return_state_machine.py ....            [100%]

============================== warnings summary ===============================
.venv\Lib\site-packages\fastapi\testclient.py:1
  C:\Users\renal\Downloads\ProofReturn\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
    from starlette.testclient import TestClient as TestClient  # noqa

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
================ 189 passed, 4 deselected, 1 warning in 25.87s ================
[exit_code: 0]

$ curl http://localhost:8000/v1/ready
{'status': 'ready', 'database_connected': True, 'active_alerts_count': 0, 'demo_mode': True}
C:\Users\renal\Downloads\ProofReturn\.venv\Lib\site-packages\fastapi\testclient.py:1: StarletteDeprecationWarning: Using `httpx` with `starlette.testclient` is deprecated; install `httpx2` instead.
  from starlette.testclient import TestClient as TestClient  # noqa
[exit_code: 0]
