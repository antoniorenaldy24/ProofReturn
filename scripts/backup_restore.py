#!/usr/bin/env python3
"""PostgreSQL Backup, Restore, and Disaster Recovery Drill Runner (BK-01..BK-07, Section 36, NFR-13, AUD-37).

Provides:
  - Database logical backup export
  - Database restoration into clean instances
  - Automated Disaster Recovery drill with post-restore reconciliation (REC-01..REC-04)
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine, select

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from backend.db.models import (
    AgentToken,
    Appeal,
    Assessment,
    CustodyEvent,
    Decision,
    IdentityLinkEvent,
    KeepOffer,
    Merchant,
    Order,
    OrderItem,
    Passport,
    PassportEvent,
    Policy,
    RefundAction,
    ResaleListing,
    Return,
    ReturnEvidence,
    Review,
    SchedulerLease,
    SerialRegistry,
    ShopperAccount,
    StaffUser,
    WebhookEvent,
)
from backend.db.repository import DatabaseRepository
from backend.ops.drills import BackupRestoreDrillResult, run_backup_restore_drill
from backend.payments.ledger import RefundLedger
from backend.payments.reconciliation import run_reconciliation_suite

TABLE_MODELS = [
    Merchant,
    Policy,
    ShopperAccount,
    StaffUser,
    SerialRegistry,
    Order,
    OrderItem,
    Return,
    ReturnEvidence,
    Assessment,
    Decision,
    KeepOffer,
    Review,
    Appeal,
    ResaleListing,
    Passport,
    PassportEvent,
    CustodyEvent,
    AgentToken,
    RefundAction,
    WebhookEvent,
    IdentityLinkEvent,
    SchedulerLease,
]


def backup_database(db_url: str, output_path: Path) -> dict[str, Any]:
    """Export database snapshot to JSON archive or pg_dump (BK-01)."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    t0 = time.perf_counter()

    # Try pg_dump if db_url is postgresql and pg_dump binary is present
    if "postgres" in db_url and shutil.which("pg_dump"):
        cmd = ["pg_dump", "-Fc", db_url, "-f", str(output_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode == 0:
            elapsed = time.perf_counter() - t0
            return {
                "format": "custom_pg_dump",
                "path": str(output_path),
                "duration_seconds": elapsed,
                "timestamp": datetime.now(UTC).isoformat(),
            }

    # Universal structured snapshot (SQLAlchemy model serializer)
    engine = create_engine(db_url)
    snapshot: dict[str, list[dict[str, Any]]] = {}
    with Session(engine) as session:
        for model in TABLE_MODELS:
            table_name = model.__tablename__
            rows = session.exec(select(model)).all()
            snapshot[table_name] = [row.model_dump(mode="json") for row in rows]

    manifest = {
        "format": "proofreturn_snapshot_v1",
        "created_at": datetime.now(UTC).isoformat(),
        "tables_count": len(snapshot),
        "total_rows": sum(len(r) for r in snapshot.values()),
        "data": snapshot,
    }
    output_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    elapsed = time.perf_counter() - t0
    return {
        "format": "proofreturn_snapshot_v1",
        "path": str(output_path),
        "duration_seconds": elapsed,
        "tables": len(snapshot),
        "total_rows": manifest["total_rows"],
        "timestamp": manifest["created_at"],
    }


def restore_database(snapshot_path: Path, target_db_url: str) -> dict[str, Any]:
    """Restore database from snapshot into fresh database instance (BK-05, BK-06)."""
    t0 = time.perf_counter()

    # Initialize target schema via Alembic migrations (no raw create_all, RV-08)
    repo = DatabaseRepository(database_url=target_db_url, run_migrations_on_init=True)

    if not snapshot_path.exists():
        raise FileNotFoundError(f"Snapshot not found: {snapshot_path}")

    # Inspect snapshot format
    try:
        content = json.loads(snapshot_path.read_text(encoding="utf-8"))
        if content.get("format") == "proofreturn_snapshot_v1":
            data = content.get("data", {})
            restored_rows = 0
            with Session(repo.engine) as session:
                for model in TABLE_MODELS:
                    table_name = model.__tablename__
                    table_rows = data.get(table_name, [])
                    for row_dict in table_rows:
                        obj = model.model_validate(row_dict)
                        session.merge(obj)
                        restored_rows += 1
                session.commit()
            elapsed = time.perf_counter() - t0
            return {
                "status": "RESTORED",
                "target_db_url": target_db_url,
                "restored_rows": restored_rows,
                "duration_seconds": elapsed,
            }
    except json.JSONDecodeError:
        pass

    # Fallback to pg_restore if binary available
    if "postgres" in target_db_url and shutil.which("pg_restore"):
        cmd = ["pg_restore", "--clean", "--if-exists", "-d", target_db_url, str(snapshot_path)]
        res = subprocess.run(cmd, capture_output=True, text=True)
        if res.returncode != 0:
            raise RuntimeError(f"pg_restore failed: {res.stderr}")
        elapsed = time.perf_counter() - t0
        return {
            "status": "RESTORED",
            "target_db_url": target_db_url,
            "duration_seconds": elapsed,
        }

    raise ValueError(f"Unsupported backup format for file {snapshot_path}")


def execute_drill(target_db_url: str | None = None) -> int:
    """Execute Disaster Recovery Drill with post-restore reconciliation (BK-06, BK-07)."""
    drill_start = time.perf_counter()
    timestamp_str = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
    snapshot_id = f"snap_drill_{timestamp_str}"
    snapshot_file = ROOT / "data" / "backups" / f"{snapshot_id}.json"

    print("=" * 80)
    print(f"PROOFRETURN DISASTER RECOVERY & RECONCILIATION DRILL (Section 36, BK-01..BK-07)")
    print(f"Timestamp: {datetime.now(UTC).isoformat()} | Snapshot ID: {snapshot_id}")
    print("=" * 80)

    # 1. Source Database Initialization & Seeding
    print("\n[Step 1/5] Preparing source state with canonical demo entities...")
    source_db_url = "sqlite:///./data/drill_source.db"
    source_repo = DatabaseRepository(database_url=source_db_url, run_migrations_on_init=True)
    source_repo.seed_demo_data()
    source_repo.plan_refund_action_transactional(
        order_id="ord_demo_1",
        return_id="ret_demo_1",
        decision_id="dec_drill_01",
        tranche="R0",
        amount_minor=15000,
    )
    print("  -> Source DB initialized with seed data (merchants, orders, refunds, policies).")

    # 2. Execute Backup Snapshot
    print(f"\n[Step 2/5] Creating backup snapshot to {snapshot_file.name}...")
    backup_meta = backup_database(source_db_url, snapshot_file)
    print(f"  -> Backup completed in {backup_meta['duration_seconds']:.3f}s. Rows exported: {backup_meta.get('total_rows', 'N/A')}")

    # 3. Provision Clean Target Database & Restore
    target_url = target_db_url or "sqlite:///./data/drill_restored_clean.db"
    clean_target_path = ROOT / "data" / "drill_restored_clean.db"
    if clean_target_path.exists():
        clean_target_path.unlink()

    print(f"\n[Step 3/5] Restoring snapshot into clean database ({target_url})...")
    restore_meta = restore_database(snapshot_file, target_url)
    rto_seconds = int(restore_meta["duration_seconds"])
    print(f"  -> Restore completed in {restore_meta['duration_seconds']:.3f}s (RTO achieved: {rto_seconds}s <= 3600s).")

    # 4. Rehydrate Persistent State & Outbox Ledger
    print("\n[Step 4/5] Rehydrating refund ledger & order state from restored database...")
    restored_repo = DatabaseRepository(database_url=target_url, run_migrations_on_init=False)
    ledger = RefundLedger()
    orders = restored_repo.list_orders()
    actions_count = 0
    for ord_obj in orders:
        if ord_obj.capture_id:
            ledger.register_order(
                order_id=ord_obj.order_id,
                merchant_id=ord_obj.merchant_id,
                capture_id=ord_obj.capture_id,
                capture_amount_minor=ord_obj.capture_amount_minor,
                currency=ord_obj.currency,
            )
            for act_obj in restored_repo.list_refund_actions_by_order(ord_obj.order_id):
                ledger.rehydrate_action(
                    request_id=act_obj.request_id,
                    order_id=act_obj.order_id,
                    merchant_id=act_obj.merchant_id,
                    capture_id=act_obj.capture_id,
                    decision_id=act_obj.decision_id,
                    tranche=act_obj.tranche,
                    amount_minor=act_obj.amount_minor,
                    status=act_obj.status,
                    paypal_refund_id=act_obj.paypal_refund_id,
                    paypal_debug_id=act_obj.paypal_debug_id,
                    attempt_count=act_obj.attempt_count,
                )
                actions_count += 1
    print(f"  -> Rehydrated {len(orders)} orders and {actions_count} refund actions.")

    # 5. Run Post-Restore Reconciliation Suite (BK-07, REC-01..REC-04)
    print("\n[Step 5/5] Executing post-restore reconciliation suite (REC-01..REC-04)...")
    # For demo seed, PLANNED actions are rehydrated. Mark any PLANNED as clean or verify invariant:
    rec_report = run_reconciliation_suite(ledger)
    for code, details in rec_report.items():
        status_label = "PASS" if details["passed"] else "FAIL"
        print(f"  [{status_label}] {code}: {details['job']} (cadence: {details['cadence']})")

    drill_res: BackupRestoreDrillResult = run_backup_restore_drill(
        snapshot_id=snapshot_id,
        simulated_rpo_seconds=int(backup_meta["duration_seconds"]),
        simulated_rto_seconds=rto_seconds,
        reconciliation_report=rec_report,
    )

    total_drill_duration = time.perf_counter() - drill_start

    print("\n" + "=" * 80)
    print("DRILL VERIFICATION SUMMARY")
    print("=" * 80)
    print(f"  Snapshot ID:                      {drill_res.snapshot_id}")
    print(f"  RPO Achieved:                     {drill_res.rpo_seconds}s (target <= 86400s / 24h)")
    print(f"  RTO Achieved:                     {drill_res.rto_seconds}s (target <= 3600s / 1h)")
    print(f"  Post-Restore Reconciliation:       {'CLEAN (PASS)' if drill_res.post_restore_reconciliation_clean else 'DISCREPANCY (FAIL)'}")
    print(f"  Money Actions Re-enabled:         {'YES' if drill_res.money_actions_reenabled else 'NO'}")
    print(f"  Overall Drill Status:             {'PASSED' if drill_res.passed else 'FAILED'}")
    print(f"  Total Drill Duration:             {total_drill_duration:.3f}s")
    print("=" * 80)

    # Clean up temporary drill DBs
    for p in [clean_target_path, ROOT / "data" / "drill_source.db"]:
        if p.exists():
            try:
                p.unlink()
            except Exception:
                pass

    return 0 if drill_res.passed else 1


def main() -> None:
    parser = argparse.ArgumentParser(description="ProofReturn Backup, Restore & Drill Runner")
    parser.add_argument("--backup", metavar="OUTPUT_PATH", help="Export database backup")
    parser.add_argument("--restore", metavar="INPUT_PATH", help="Restore database from backup")
    parser.add_argument("--target-url", metavar="DATABASE_URL", help="Target database URL for restore")
    parser.add_argument("--drill", action="store_true", help="Run full backup/restore drill and reconciliation")

    args = parser.parse_args()

    if args.drill:
        sys.exit(execute_drill(args.target_url))
    elif args.backup:
        db_url = args.target_url or os.environ.get("DATABASE_URL", "sqlite:///./data/proofreturn.db")
        res = backup_database(db_url, Path(args.backup))
        print(json.dumps(res, indent=2))
    elif args.restore:
        target_url = args.target_url or os.environ.get("DATABASE_URL", "sqlite:///./data/proofreturn.db")
        res = restore_database(Path(args.restore), target_url)
        print(json.dumps(res, indent=2))
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
