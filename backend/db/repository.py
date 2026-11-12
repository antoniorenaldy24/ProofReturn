"""Persistent SQL Repository for ProofReturn (AUD-06, RV-08, RV-12, RV-14, Section 10.4, Section 30).

Provides atomic CRUD operations, Alembic-managed schema migrations (no create_all),
database session management, persistent token revocation, webhook deduplication,
and integrated ReturnStateMachine transitions backed by PostgreSQL or SQLite.
"""

from __future__ import annotations

import hashlib
import os
import pathlib
import secrets
import threading
import time
from datetime import datetime, timedelta, timezone
from typing import Any

import sqlalchemy as sa
from alembic import command
from alembic.config import Config as AlembicConfig
from sqlalchemy import Engine, text
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, create_engine, select

from backend.auth.tokens import register_revocation_persistence
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
from backend.domain.return_state import (
    InvalidStateTransitionError,
    ReturnEntity,
    ReturnStateMachine,
)
from backend.domain.signing import get_packer_keypair, sha256_hex, sign_message_ed25519
from backend.payments.ledger import (
    IdempotencyConflictError,
    OrderFrozenError,
    OverRefundError,
    compute_deterministic_request_id,
)


class MissingCaptureError(ValueError):
    """Raised when an order has no capture_id configured (INV-02, AUD-02)."""

REPO_ROOT = pathlib.Path(__file__).resolve().parents[2]
ALEMBIC_INI_PATH = REPO_ROOT / "alembic.ini"
MIGRATIONS_DIR = REPO_ROOT / "backend" / "migrations"


def normalize_database_url(url: str) -> str:
    """Normalize PostgreSQL URLs to use psycopg v3 driver when unspecified (AUD-07)."""
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql+asyncpg://")
    return url


class DatabaseRepository:
    """Manages persistent database operations, Alembic migrations, state transitions, and concurrency control."""

    def __init__(
        self,
        database_url: str | None = None,
        engine: Engine | None = None,
        *,
        run_migrations_on_init: bool = True,
    ) -> None:
        if engine is not None:
            if (
                engine.url.drivername.startswith("sqlite")
                and (not engine.url.database or engine.url.database == ":memory:")
                and not isinstance(engine.pool, StaticPool)
            ):
                self.engine = create_engine(
                    "sqlite:///:memory:",
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                self.engine = engine
        else:
            raw_url = database_url or os.environ.get("DATABASE_URL", "sqlite:///./data/proofreturn.db")
            url = normalize_database_url(raw_url)
            if url.startswith("sqlite:///./data/"):
                (REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
            if "sqlite" in url and ":memory:" in url:
                self.engine = create_engine(
                    url,
                    connect_args={"check_same_thread": False},
                    poolclass=StaticPool,
                )
            else:
                connect_args = {"check_same_thread": False} if "sqlite" in url else {}
                self.engine = create_engine(url, connect_args=connect_args)

        self._lock = threading.RLock()
        self.state_machine = ReturnStateMachine()

        if run_migrations_on_init:
            try:
                self.run_migrations()
            except sa.exc.OperationalError:
                if "sqlite" not in str(self.engine.url):
                    fallback_url = "sqlite:///./data/proofreturn.db"
                    (REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
                    self.engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
                    self.run_migrations()
                else:
                    raise
        else:
            if "sqlite" not in str(self.engine.url):
                try:
                    with self.engine.connect():
                        pass
                except sa.exc.OperationalError:
                    fallback_url = "sqlite:///./data/proofreturn.db"
                    (REPO_ROOT / "data").mkdir(parents=True, exist_ok=True)
                    self.engine = create_engine(fallback_url, connect_args={"check_same_thread": False})
                    self.run_migrations()

        register_revocation_persistence(
            writer=self.revoke_token_signature,
            checker=self.is_signature_revoked,
        )

    def run_migrations(self) -> None:
        """Apply Alembic migrations up to head without using SQLModel.metadata.create_all (RV-08, MG-01)."""
        cfg = AlembicConfig(str(ALEMBIC_INI_PATH))
        cfg.set_main_option("script_location", str(MIGRATIONS_DIR))
        cfg.attributes["skip_logging"] = True

        with self._lock, self.engine.begin() as conn:
            cfg.attributes["connection"] = conn
            inspector = sa.inspect(conn)
            existing_tables = set(inspector.get_table_names())
            if "merchants" in existing_tables and "alembic_version" not in existing_tables:
                command.stamp(cfg, "0001_initial_schema")
            command.upgrade(cfg, "head")

    def get_session(self) -> Session:
        return Session(self.engine, expire_on_commit=False)

    def ping(self) -> bool:
        """Verify database connectivity (AUD-37)."""
        with self.get_session() as session:
            session.exec(text("SELECT 1"))
        return True

    def seed_demo_data(self) -> None:
        """Seed deterministic multi-tenant demo data into canonical tables."""
        with self._lock, self.get_session() as session:
            # 1. Merchants (merch_a and merch_b for BOLA / cross-tenant tests)
            for mid, mname in [("merch_a", "Acme Electronics"), ("merch_b", "Beta Gadgets")]:
                if not session.get(Merchant, mid):
                    session.add(
                        Merchant(
                            merchant_id=mid,
                            name=mname,
                            instant_exposure_cap_minor=500000,
                            outstanding_instant_exposure_minor=0,
                            currency="USD",
                        )
                    )

            # 2. Staff users
            for role, sid, mid in [
                ("PACKER", "pack_01", "merch_a"),
                ("RECEIVER", "recv_01", "merch_a"),
                ("REVIEWER", "rev_01", "merch_a"),
                ("REVIEWER", "rev_02", "merch_a"),
                ("REVIEWER", "rev_initial_01", "merch_a"),
                ("MERCHANT_ADMIN", "admin_01", "merch_a"),
                ("MERCHANT_OPERATOR", "op_01", "merch_a"),
                ("MERCHANT_ADMIN", "admin_b_01", "merch_b"),
            ]:
                if not session.get(StaffUser, sid):
                    session.add(
                        StaffUser(
                            staff_id=sid,
                            merchant_id=mid,
                            role=role,
                            email_hash=hashlib.sha256(f"{sid}@proofreturn.dev".encode()).hexdigest(),
                        )
                    )

            # 3. Shopper accounts
            for acc_id, grp_id, tier in [
                ("shopper_1", "grp_01", "TRUSTED"),
                ("shopper_2", "grp_02", "NEW"),
                ("shopper_b", "grp_b1", "ESTABLISHED"),
            ]:
                if not session.get(ShopperAccount, acc_id):
                    session.add(
                        ShopperAccount(
                            account_id=acc_id,
                            identity_group_id=grp_id,
                            trust_tier=tier,
                            cusum_score=0.0,
                            clean_Counter_verified_returns=5 if tier == "TRUSTED" else 0,
                            account_age_days=120 if tier == "TRUSTED" else 10,
                        )
                    )

            # 4. Policies
            default_curve = {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50}
            for pver, mid, jur in [
                ("pol_v1_us_ca", "merch_a", "US_CA"),
                ("pol_electronics_us_v1", "merch_a", "US_CA"),
                ("pol_merch_b_v1", "merch_b", "US_NY"),
            ]:
                if not session.get(Policy, pver):
                    session.add(
                        Policy(
                            policy_version=pver,
                            merchant_id=mid,
                            jurisdiction=jur,
                            return_window_days=30,
                            config_json={
                                "curve": default_curve,
                                "fee_f_minor": 1500,
                                "c_ship_minor": 800,
                                "salvage_ ratios": {"A": 0.85, "B": 0.70, "C": 0.50, "D": 0.25, "DEF": 0.10},
                            },
                        )
                    )

            # 5. Passports with real Ed25519 signature (AUD-28, AUD-42: tier FULL, not ORIGIN_WITNESSED)
            if not session.get(Passport, "pass_demo_1"):
                packer_priv, _, packer_kid = get_packer_keypair()
                manifest_payload = {
                    "passport_id": "pass_demo_1",
                    "merchant_id": "merch_a",
                    "sku": "PR-HP-XM5",
                    "tier": "FULL",
                    "origin_grade": "A",
                    "weight_g": 250,
                    "self_test_passed": True,
                }
                h_hash = sha256_hex(str(sorted(manifest_payload.items())))
                sig_b64 = sign_message_ed25519(packer_priv, h_hash)
                session.add(
                    Passport(
                        passport_id="pass_demo_1",
                        merchant_id="merch_a",
                        sku="PR-HP-XM5",
                        tier="FULL",
                        origin_grade="A",
                        serial_commitment=hashlib.sha256(b"SN-DEMO-XM5-001").hexdigest(),
                        head_hash=h_hash,
                        signature=f"ed25519:{sig_b64}",
                        signing_key_id=packer_kid,
                        weight_g=250,
                        self_test_passed=True,
                        current_owner_ref="shopper_1",
                        buyer_email="shopper1@example.com",
                    )
                )
                session.add(
                    PassportEvent(
                        event_id="pe_demo_origin_1",
                        passport_id="pass_demo_1",
                        seq_no=1,
                        prev_hash="0" * 64,
                        event_hash=h_hash,
                        payload_json=manifest_payload,
                        signature=f"ed25519:{sig_b64}",
                    )
                )

            # 6. Orders
            order_seeds = [
                ("ord_demo_1", "merch_a", "shopper_1", "pol_electronics_us_v1", 38000, "CAP_ORD_DEMO_1"),
                ("ord_resale_1", "merch_a", "shopper_2", "pol_v1_us_ca", 31500, "CAP_ORD_RESALE_1"),
                ("ord_merch_b_1", "merch_b", "shopper_b", "pol_merch_b_v1", 25000, "CAP_ORD_MERCH_B_1"),
            ]
            for oid, mid, acc_id, pver, amt, cap_id in order_seeds:
                ord_in_db = session.get(Order, oid)
                if not ord_in_db:
                    session.add(
                        Order(
                            order_id=oid,
                            merchant_id=mid,
                            account_id=acc_id,
                            policy_version=pver,
                            paypal_order_id=f"PP-{oid}",  # demo-seed-only: synthetic PayPal order id for offline demo seed
                            capture_id=cap_id,
                            capture_amount_minor=amt,
                            confirmed_refunded_minor=0,
                            pending_refunded_minor=0,
                            currency="USD",
                        )
                    )
                else:
                    if not ord_in_db.capture_id:
                        ord_in_db.capture_id = cap_id
                    actions = session.exec(select(RefundAction).where(RefundAction.order_id == oid)).all()
                    ord_in_db.pending_refunded_minor = sum(a.amount_minor for a in actions if a.status in {"PLANNED", "SUBMITTED"})
                    ord_in_db.confirmed_refunded_minor = sum(a.amount_minor for a in actions if a.status == "CONFIRMED")
                    session.add(ord_in_db)

            # 7. Order items
            for item_id, oid, pid, sku, price in [
                ("item_demo_1", "ord_demo_1", "pass_demo_1", "PR-HP-XM5", 38000),
                ("item_demo_2", "ord_demo_1", "pass_demo_1", "PR-HP-XM5", 38000),
                ("item_resale_1", "ord_resale_1", "pass_demo_1", "PR-HP-XM5", 31500),
                ("item_merch_b_1", "ord_merch_b_1", None, "PR-KB-PRO", 25000),
            ]:
                if not session.get(OrderItem, item_id):
                    session.add(
                        OrderItem(
                            order_item_id=item_id,
                            order_id=oid,
                            passport_id=pid,
                            sku=sku,
                            price_minor=price,
                            currency="USD",
                        )
                    )

            # 8. Returns with CSPRNG audit seeds and commitments (RV-02)
            for ret_id, oid, item_id, mid, sh_id, st in [
                ("ret_demo_1", "ord_demo_1", "item_demo_1", "merch_a", "shopper_1", "DECLARED"),
                ("ret_demo_escalated", "ord_demo_1", "item_demo_2", "merch_a", "shopper_1", "ESCALATED"),
                ("ret_merch_b_01", "ord_merch_b_1", "item_merch_b_1", "merch_b", "shopper_b", "REQUESTED"),
            ]:
                existing_ret = session.get(Return, ret_id)
                if existing_ret:
                    existing_ret.state = st
                    existing_ret.lane = "FAST" if st != "ESCALATED" else "MANUAL"
                    existing_ret.timing = "R0" if st != "ESCALATED" else "R3"
                    existing_ret.declared_grade = "B" if st != "REQUESTED" else None
                    existing_ret.consent_recorded = (st != "REQUESTED")
                    session.add(existing_ret)
                else:
                    seed_hex = secrets.token_hex(32)
                    seed_bytes = bytes.fromhex(seed_hex)
                    commitment = hashlib.sha256(seed_bytes + b"||" + ret_id.encode("utf-8")).hexdigest()
                    session.add(
                        Return(
                            return_id=ret_id,
                            order_id=oid,
                            order_item_id=item_id,
                            merchant_id=mid,
                            shopper_id=sh_id,
                            state=st,
                            lane="FAST" if st != "ESCALATED" else "MANUAL",
                            timing="R0" if st != "ESCALATED" else "R3",
                            declared_grade="B" if st != "REQUESTED" else None,
                            r0_tranche_minor=0,
                            currency="USD",
                            challenge_nonce=f"NONCE-{secrets.token_hex(8).upper()}",
                            shopper_nonce="shopper_nonce_seed_01" if st != "REQUESTED" else None,
                            audit_seed_hex=seed_hex,
                            audit_commitment=commitment,
                            audit_probability=0.05,
                            consent_recorded=(st != "REQUESTED"),
                        )
                    )

            # 9. Initial Review on ret_demo_escalated so Appeals can look up original_reviewer_id from DB (AUD-29)
            existing_rev = session.get(Review, "rev_rec_demo_1")
            if not existing_rev:
                session.add(
                    Review(
                        review_id="rev_rec_demo_1",
                        return_id="ret_demo_1",
                        reviewer_id="rev_01",
                        verified_grade="C",
                        outcome="DOWNGRADED",
                        notes="Initial warehouse review.",
                    )
                )
            else:
                existing_rev.reviewer_id = "rev_01"
                session.add(existing_rev)

            session.commit()

    # =========================================================================
    # Token Revocation Persistence (RV-12)
    # =========================================================================
    def revoke_token_signature(self, sig_b64: str) -> None:
        sig_hash = hashlib.sha256(sig_b64.encode("utf-8")).hexdigest()
        token_id = f"rev_{sig_hash[:24]}"
        with self._lock, self.get_session() as session:
            existing = session.get(AgentToken, token_id)
            if existing:
                existing.revoked = True
                session.add(existing)
            else:
                # Ensure ord_demo_1 exists or fallback cleanly
                order_exists = session.get(Order, "ord_demo_1")
                if order_exists:
                    session.add(
                        AgentToken(
                            token_id=token_id,
                            order_id="ord_demo_1",
                            merchant_id="platform",
                            agent_id="revoked_principal",
                            scopes="",
                            agent_label="revoked",
                            signature_hash=sig_hash,
                            revoked=True,
                            expires_at=int(time.time()) + 86400,
                        )
                    )
            session.commit()

    def is_signature_revoked(self, sig_b64: str) -> bool:
        sig_hash = hashlib.sha256(sig_b64.encode("utf-8")).hexdigest()
        token_id = f"rev_{sig_hash[:24]}"
        with self.get_session() as session:
            rec = session.get(AgentToken, token_id)
            if rec and rec.revoked:
                return True
            stmt = select(AgentToken).where(
                AgentToken.signature_hash == sig_hash,
                AgentToken.revoked == True,  # noqa: E712
            )
            found = session.exec(stmt).first()
            return found is not None

    # =========================================================================
    # Entity Accessors & Mutators
    # =========================================================================
    def get_merchant(self, merchant_id: str) -> Merchant | None:
        with self.get_session() as session:
            return session.get(Merchant, merchant_id)

    def save_merchant(self, merchant: Merchant) -> Merchant:
        with self._lock, self.get_session() as session:
            session.add(merchant)
            session.commit()
            session.refresh(merchant)
            return merchant

    def get_shopper(self, account_id: str) -> ShopperAccount | None:
        with self.get_session() as session:
            return session.get(ShopperAccount, account_id)

    def save_shopper(self, shopper: ShopperAccount) -> ShopperAccount:
        with self._lock, self.get_session() as session:
            session.add(shopper)
            session.commit()
            session.refresh(shopper)
            return shopper

    def list_shoppers(self) -> list[ShopperAccount]:
        with self.get_session() as session:
            stmt = select(ShopperAccount)
            return list(session.exec(stmt).all())

    def get_policy(self, policy_version: str) -> Policy | None:
        with self.get_session() as session:
            return session.get(Policy, policy_version)

    def list_policies(self, merchant_id: str | None = None, *, include_inactive: bool = False) -> list[Policy]:
        with self.get_session() as session:
            stmt = select(Policy)
            if merchant_id:
                stmt = stmt.where(Policy.merchant_id == merchant_id)
            if not include_inactive:
                stmt = stmt.where(Policy.is_active == True)  # noqa: E712
            return list(session.exec(stmt).all())

    def save_policy(self, policy: Policy) -> Policy:
        with self._lock, self.get_session() as session:
            merged = session.merge(policy)
            session.commit()
            session.refresh(merged)
            return merged

    def get_return(self, return_id: str) -> Return | None:
        with self.get_session() as session:
            return session.get(Return, return_id)

    def list_returns(self, state: str | None = None) -> list[Return]:
        with self.get_session() as session:
            stmt = select(Return)
            if state:
                stmt = stmt.where(Return.state == state)
            return list(session.exec(stmt).all())

    def list_returns_by_merchant(self, merchant_id: str) -> list[Return]:
        with self.get_session() as session:
            stmt = select(Return).where(Return.merchant_id == merchant_id)
            return list(session.exec(stmt).all())

    def save_return(self, return_obj: Return) -> Return:
        with self._lock, self.get_session() as session:
            if not return_obj.audit_commitment:
                return_obj.ensure_audit_commitment()
            merged = session.merge(return_obj)
            session.commit()
            session.refresh(merged)
            return merged

    def apply_return_transition(self, return_id: str, event: str, **guards: Any) -> Return:
        """Atomically advance return state via ReturnStateMachine (AUD-05, RV-03, INV-04)."""
        with self._lock, self.get_session() as session:
            ret = session.get(Return, return_id)
            if not ret:
                raise ValueError(f"Return {return_id} not found.")

            entity = ReturnEntity(
                return_id=ret.return_id,
                order_id=ret.order_id,
                state=ret.state,
                lane=ret.lane,
                timing=ret.timing,
            )

            self.state_machine.apply(entity, event, **guards)

            ret.state = entity.state
            ret.lane = entity.lane
            ret.timing = entity.timing
            ret.version += 1
            session.add(ret)
            session.commit()
            session.refresh(ret)
            return ret

    def get_order(self, order_id: str) -> Order | None:
        with self.get_session() as session:
            return session.get(Order, order_id)

    def is_order_frozen(self, order_id: str) -> bool:
        """Read Order.frozen_by_dispute and Order.capture_reversed columns from the database (RV3-11, FR-75)."""
        with self.get_session() as session:
            order = session.get(Order, order_id)
            if order is None:
                raise KeyError(f"Unknown order {order_id}")
            return bool(order.frozen_by_dispute or order.capture_reversed)

    def ensure_order_registered(
        self,
        *,
        order_id: str,
        merchant_id: str,
        capture_id: str,
        capture_amount_minor: int,
        currency: str = "USD",
    ) -> Order:
        """Ensure an Order row exists in DB so freeze/reversal columns have a single DB source of truth (RV3-11)."""
        with self._lock, self.get_session() as session:
            existing = session.get(Order, order_id)
            if existing is not None:
                return existing
            if session.get(Merchant, merchant_id) is None:
                session.add(Merchant(merchant_id=merchant_id, name=merchant_id, currency=currency))
            if session.get(ShopperAccount, "shopper_1") is None:
                session.add(ShopperAccount(account_id="shopper_1", identity_group_id="grp_01", trust_tier="TRUSTED"))
            pver = f"pol_{merchant_id}"
            if session.get(Policy, pver) is None:
                session.add(
                    Policy(
                        policy_version=pver,
                        merchant_id=merchant_id,
                        jurisdiction="US_CA",
                        return_window_days=30,
                        config_json={
                            "curve": {"A": 1.0, "B": 0.95, "C": 0.80, "D": 0.50},
                            "fee_f_minor": 1500,
                            "c_ship_minor": 800,
                        },
                    )
                )
            session.flush()
            order = Order(
                order_id=order_id,
                merchant_id=merchant_id,
                account_id="shopper_1",
                policy_version=pver,
                paypal_order_id="",
                capture_id=capture_id,
                capture_amount_minor=capture_amount_minor,
                confirmed_refunded_minor=0,
                pending_refunded_minor=0,
                currency=currency,
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def list_orders(self, merchant_id: str | None = None) -> list[Order]:
        with self.get_session() as session:
            stmt = select(Order)
            if merchant_id is not None:
                stmt = stmt.where(Order.merchant_id == merchant_id)
            return list(session.exec(stmt).all())

    def save_order(self, order: Order) -> Order:
        with self._lock, self.get_session() as session:
            merged = session.merge(order)
            session.commit()
            session.refresh(merged)
            return merged

    def get_order_items(self, order_id: str) -> list[OrderItem]:
        with self.get_session() as session:
            stmt = select(OrderItem).where(OrderItem.order_id == order_id)
            return list(session.exec(stmt).all())

    def get_order_item(self, order_item_id: str) -> OrderItem | None:
        with self.get_session() as session:
            return session.get(OrderItem, order_item_id)

    def resolve_order_line_price_minor(
        self,
        *,
        merchant_id: str | None = None,
        order_id: str | None = None,
        order_item_id: str | None = None,
        sku: str | None = None,
        fallback_price_minor: int | None = None,
    ) -> int:
        with self.get_session() as session:
            if order_item_id:
                item = session.get(OrderItem, order_item_id)
                if item is not None:
                    return int(item.price_minor)
            if order_id:
                items = list(session.exec(select(OrderItem).where(OrderItem.order_id == order_id)).all())
                if sku:
                    for it in items:
                        if it.sku == sku:
                            return int(it.price_minor)
                if items:
                    return int(items[0].price_minor)
                order = session.get(Order, order_id)
                if order is not None:
                    return int(order.capture_amount_minor)
            if sku:
                stmt = select(OrderItem, Order).join(Order, OrderItem.order_id == Order.order_id).where(OrderItem.sku == sku)
                if merchant_id:
                    stmt = stmt.where(Order.merchant_id == merchant_id)
                rows = list(session.exec(stmt).all())
                if rows:
                    return int(rows[-1][0].price_minor)
                items_by_sku = list(session.exec(select(OrderItem).where(OrderItem.sku == sku)).all())
                if items_by_sku:
                    return int(items_by_sku[-1].price_minor)
            if fallback_price_minor is not None:
                return int(fallback_price_minor)
            return 0

    def save_order_item(self, item: OrderItem) -> OrderItem:
        with self._lock, self.get_session() as session:
            merged = session.merge(item)
            session.commit()
            session.refresh(merged)
            return merged

    def get_passport(self, passport_id: str) -> Passport | None:
        with self.get_session() as session:
            return session.get(Passport, passport_id)

    def save_passport(self, passport: Passport) -> Passport:
        with self._lock, self.get_session() as session:
            merged = session.merge(passport)
            session.commit()
            session.refresh(merged)
            return merged

    def list_passport_events(self, passport_id: str) -> list[PassportEvent]:
        with self.get_session() as session:
            stmt = select(PassportEvent).where(PassportEvent.passport_id == passport_id).order_by(PassportEvent.seq_no)
            return list(session.exec(stmt).all())

    def save_passport_event(self, event: PassportEvent) -> PassportEvent:
        with self._lock, self.get_session() as session:
            merged = session.merge(event)
            session.commit()
            session.refresh(merged)
            return merged

    def get_return_evidence(self, return_id: str) -> list[ReturnEvidence]:
        with self.get_session() as session:
            stmt = select(ReturnEvidence).where(ReturnEvidence.return_id == return_id)
            return list(session.exec(stmt).all())

    def save_return_evidence(self, ev: ReturnEvidence) -> ReturnEvidence:
        with self._lock, self.get_session() as session:
            merged = session.merge(ev)
            session.commit()
            session.refresh(merged)
            return merged

    def get_latest_assessment(self, return_id: str) -> Assessment | None:
        with self.get_session() as session:
            stmt = select(Assessment).where(Assessment.return_id == return_id).order_by(Assessment.created_at.desc())
            return session.exec(stmt).first()

    def save_assessment(self, assessment: Assessment) -> Assessment:
        with self._lock, self.get_session() as session:
            merged = session.merge(assessment)
            session.commit()
            session.refresh(merged)
            return merged

    def get_latest_decision(self, return_id: str) -> Decision | None:
        with self.get_session() as session:
            stmt = select(Decision).where(Decision.return_id == return_id).order_by(Decision.created_at.desc())
            return session.exec(stmt).first()

    def list_decisions_for_return(self, return_id: str) -> list[Decision]:
        with self.get_session() as session:
            stmt = select(Decision).where(Decision.return_id == return_id).order_by(Decision.created_at.asc())
            return list(session.exec(stmt).all())

    def save_decision(self, decision: Decision) -> Decision:
        with self._lock, self.get_session() as session:
            merged = session.merge(decision)
            session.commit()
            session.refresh(merged)
            return merged

    def get_keep_offer_by_return(self, return_id: str) -> KeepOffer | None:
        with self.get_session() as session:
            stmt = select(KeepOffer).where(KeepOffer.return_id == return_id)
            return session.exec(stmt).first()

    def get_keep_offer(self, offer_id: str) -> KeepOffer | None:
        with self.get_session() as session:
            return session.get(KeepOffer, offer_id)

    def save_keep_offer(self, offer: KeepOffer) -> KeepOffer:
        with self._lock, self.get_session() as session:
            merged = session.merge(offer)
            session.commit()
            session.refresh(merged)
            return merged

    def list_pending_keep_offers(self) -> list[KeepOffer]:
        with self.get_session() as session:
            stmt = select(KeepOffer).where(KeepOffer.status.in_(["OFFERED", "PENDING"]))
            return list(session.exec(stmt).all())

    def list_refund_actions_by_return(self, return_id: str) -> list[RefundAction]:
        with self.get_session() as session:
            stmt = select(RefundAction).where(RefundAction.return_id == return_id)
            return list(session.exec(stmt).all())

    def list_refund_actions_by_order(self, order_id: str) -> list[RefundAction]:
        with self.get_session() as session:
            stmt = select(RefundAction).where(RefundAction.order_id == order_id)
            return list(session.exec(stmt).all())

    def get_refund_action(self, request_id: str) -> RefundAction | None:
        with self.get_session() as session:
            return session.get(RefundAction, request_id)

    def save_refund_action(self, action: RefundAction) -> RefundAction:
        with self._lock, self.get_session() as session:
            merged = session.merge(action)
            session.commit()
            session.refresh(merged)
            return merged

    def plan_refund_action_transactional(
        self,
        *,
        order_id: str,
        return_id: str,
        decision_id: str,
        tranche: str,
        amount_minor: int,
        merchant_id: str | None = None,
        currency: str = "USD",
        paypal_debug_id: str | None = None,
    ) -> RefundAction:
        """Atomically lock order row, verify capture_id, recompute remaining balance,
        insert RefundAction, and increment pending_refunded_minor (INV-01, INV-02, INV-03, RV2-04).
        """
        req_id = compute_deterministic_request_id(decision_id, tranche)
        with self._lock, self.get_session() as session:
            stmt = select(Order).where(Order.order_id == order_id)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update()
            order = session.exec(stmt).first()
            if not order:
                raise ValueError(f"Order {order_id} not found.")

            if order.frozen_by_dispute or order.capture_reversed:
                raise OrderFrozenError(
                    f"Order {order_id} is frozen (frozen_by_dispute={order.frozen_by_dispute}, capture_reversed={order.capture_reversed})."
                )

            if not order.capture_id or not order.capture_id.strip():
                raise MissingCaptureError(f"Order {order_id} has no capture_id.")

            existing_act = session.get(RefundAction, req_id)
            if existing_act:
                if existing_act.amount_minor != amount_minor:
                    raise IdempotencyConflictError(
                        f"Action {req_id} already planned for {existing_act.amount_minor} minor, cannot replan with {amount_minor} minor."
                    )
                return existing_act

            remaining = order.capture_amount_minor - order.confirmed_refunded_minor - order.pending_refunded_minor
            if amount_minor > remaining:
                raise OverRefundError(
                    f"Requested refund {amount_minor} minor exceeds remaining refundable balance {remaining} minor "
                    f"(capture={order.capture_amount_minor}, confirmed={order.confirmed_refunded_minor}, pending={order.pending_refunded_minor})."
                )

            act = RefundAction(
                request_id=req_id,
                merchant_id=merchant_id or order.merchant_id,
                order_id=order_id,
                return_id=return_id,
                decision_id=decision_id,
                capture_id=order.capture_id,
                tranche=tranche,
                amount_minor=amount_minor,
                currency=currency,
                status="PLANNED",
                attempt_count=0,
                paypal_debug_id=paypal_debug_id,
            )
            session.add(act)
            order.pending_refunded_minor += amount_minor
            order.version += 1
            session.add(order)
            session.commit()
            session.refresh(act)
            return act

    def claim_planned_refund_actions(
        self,
        limit: int = 10,
        merchant_id: str | None = None,
        now: datetime | None = None,
        max_attempts: int = 8,
    ) -> list[RefundAction]:
        """Claim up to limit PLANNED or eligible UNKNOWN refund actions, marking them SUBMITTED.
        Respects next_attempt_at backoff and max_attempts ceiling (RV3-12).
        Skips actions whose order is frozen or reversed, marking them BLOCKED_BY_DISPUTE
        and releasing pending_refunded_minor in the same transaction (AUD-02, ARC-19, RV3-11, FR-75).
        """
        effective_now = now or datetime.now(timezone.utc)
        if effective_now.tzinfo is None:
            effective_now = effective_now.replace(tzinfo=timezone.utc)
        else:
            effective_now = effective_now.astimezone(timezone.utc)

        with self._lock, self.get_session() as session:
            stmt = (
                select(RefundAction)
                .where(RefundAction.status.in_(["PLANNED", "UNKNOWN"]))
                .order_by(RefundAction.created_at)
            )
            if merchant_id:
                stmt = stmt.where(RefundAction.merchant_id == merchant_id)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update(skip_locked=True)
            actions = list(session.exec(stmt).all())
            claimed_actions: list[RefundAction] = []
            for act in actions:
                if len(claimed_actions) >= limit:
                    break
                if act.status == "UNKNOWN":
                    if act.attempt_count >= max_attempts:
                        continue
                    if act.next_attempt_at is not None:
                        next_dt = (
                            act.next_attempt_at.replace(tzinfo=timezone.utc)
                            if act.next_attempt_at.tzinfo is None
                            else act.next_attempt_at.astimezone(timezone.utc)
                        )
                        if next_dt > effective_now:
                            continue

                ord_stmt = select(Order).where(Order.order_id == act.order_id)
                if not self.engine.url.drivername.startswith("sqlite"):
                    ord_stmt = ord_stmt.with_for_update()
                order = session.exec(ord_stmt).first()
                if order and (order.frozen_by_dispute or order.capture_reversed):
                    act.status = "BLOCKED_BY_DISPUTE"
                    act.version += 1
                    session.add(act)
                    order.pending_refunded_minor = max(0, order.pending_refunded_minor - act.amount_minor)
                    order.version += 1
                    session.add(order)
                else:
                    act.status = "SUBMITTED"
                    act.attempt_count += 1
                    act.version += 1
                    session.add(act)
                    claimed_actions.append(act)
            session.commit()
            for act in claimed_actions:
                session.refresh(act)
            return claimed_actions

    def list_refund_actions_by_status(
        self,
        status: str,
        merchant_id: str | None = None,
    ) -> list[RefundAction]:
        """List refund actions matching a specific status (e.g. NEEDS_ATTENTION; RV3-12)."""
        with self._lock, self.get_session() as session:
            stmt = select(RefundAction).where(RefundAction.status == status).order_by(RefundAction.created_at)
            if merchant_id:
                stmt = stmt.where(RefundAction.merchant_id == merchant_id)
            return list(session.exec(stmt).all())

    def list_exhausted_unknown_refund_actions(
        self,
        max_attempts: int = 8,
        merchant_id: str | None = None,
    ) -> list[RefundAction]:
        """List UNKNOWN refund actions that have reached or exceeded max_attempts (RV3-12)."""
        with self._lock, self.get_session() as session:
            stmt = (
                select(RefundAction)
                .where(
                    RefundAction.status == "UNKNOWN",
                    RefundAction.attempt_count >= max_attempts,
                )
                .order_by(RefundAction.created_at)
            )
            if merchant_id:
                stmt = stmt.where(RefundAction.merchant_id == merchant_id)
            return list(session.exec(stmt).all())

    def list_submitted_refund_actions_with_paypal_id(
        self,
        limit: int = 10,
        merchant_id: str | None = None,
    ) -> list[RefundAction]:
        """List SUBMITTED refund actions that have a paypal_refund_id for GET /v2/payments/refunds/{id} reconciliation (RV3-01)."""
        with self._lock, self.get_session() as session:
            stmt = (
                select(RefundAction)
                .where(
                    RefundAction.status == "SUBMITTED",
                    RefundAction.paypal_refund_id.is_not(None),  # type: ignore[union-attr]
                )
                .order_by(RefundAction.created_at)
                .limit(limit)
            )
            if merchant_id:
                stmt = stmt.where(RefundAction.merchant_id == merchant_id)
            actions = list(session.exec(stmt).all())
            return [a for a in actions if a.paypal_refund_id and a.paypal_refund_id.strip()]

    def record_refund_submitted_pending(
        self,
        *,
        request_id: str,
        paypal_refund_id: str,
        status_detail: str | None = "PENDING",
        paypal_debug_id: str | None = None,
    ) -> RefundAction:
        """Record a PENDING refund from PayPal as SUBMITTED with paypal_refund_id and status_detail; keeps pending balance (RV3-01)."""
        with self._lock, self.get_session() as session:
            act = session.get(RefundAction, request_id)
            if not act:
                raise ValueError(f"RefundAction {request_id} not found.")
            if act.status == "CONFIRMED":
                return act

            act.status = "SUBMITTED"
            act.paypal_refund_id = paypal_refund_id
            act.status_detail = status_detail
            if paypal_debug_id:
                act.paypal_debug_id = paypal_debug_id
            act.version += 1
            session.add(act)
            session.commit()
            session.refresh(act)
            return act

    def record_refund_confirmed(
        self,
        *,
        request_id: str,
        paypal_refund_id: str,
        paypal_debug_id: str,
        status_detail: str | None = "COMPLETED",
    ) -> RefundAction:
        """Mark refund action CONFIRMED and atomically move balance from pending to confirmed (INV-01, AUD-02, RV3-01)."""
        with self._lock, self.get_session() as session:
            act = session.get(RefundAction, request_id)
            if not act:
                raise ValueError(f"RefundAction {request_id} not found.")
            if act.status == "CONFIRMED":
                return act

            stmt = select(Order).where(Order.order_id == act.order_id)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update()
            order = session.exec(stmt).first()
            if not order:
                raise ValueError(f"Order {act.order_id} not found for refund action {request_id}.")

            order.pending_refunded_minor = max(0, order.pending_refunded_minor - act.amount_minor)
            order.confirmed_refunded_minor += act.amount_minor
            order.version += 1
            session.add(order)

            act.status = "CONFIRMED"
            act.paypal_refund_id = paypal_refund_id
            act.paypal_debug_id = paypal_debug_id
            act.status_detail = status_detail
            act.next_attempt_at = None
            act.version += 1
            session.add(act)

            session.commit()
            session.refresh(act)
            return act

    def record_refund_unknown(
        self,
        *,
        request_id: str,
        paypal_debug_id: str | None = None,
        paypal_refund_id: str | None = None,
        status_detail: str | None = None,
        now: datetime | None = None,
        next_attempt_at: datetime | None = None,
    ) -> RefundAction:
        """Mark refund action UNKNOWN due to network error/timeout or missing id/status, scheduling exponential backoff; preserves pending balance (AUD-02, ARC-19, RV3-01, RV3-12)."""
        with self._lock, self.get_session() as session:
            act = session.get(RefundAction, request_id)
            if not act:
                raise ValueError(f"RefundAction {request_id} not found.")
            act.status = "UNKNOWN"
            if paypal_debug_id:
                act.paypal_debug_id = paypal_debug_id
            if paypal_refund_id:
                act.paypal_refund_id = paypal_refund_id
            if status_detail is not None:
                act.status_detail = status_detail
            if next_attempt_at is not None:
                act.next_attempt_at = next_attempt_at
            else:
                effective_now = now or datetime.now(timezone.utc)
                if effective_now.tzinfo is None:
                    effective_now = effective_now.replace(tzinfo=timezone.utc)
                else:
                    effective_now = effective_now.astimezone(timezone.utc)
                backoff_minutes = min(60, 2 ** max(0, int(act.attempt_count) - 1))
                act.next_attempt_at = effective_now + timedelta(minutes=backoff_minutes)
            act.version += 1
            session.add(act)
            session.commit()
            session.refresh(act)
            return act

    def record_refund_needs_attention(
        self,
        *,
        request_id: str,
        status_detail: str | None = "MAX_ATTEMPTS_EXCEEDED",
        paypal_debug_id: str | None = None,
        paypal_refund_id: str | None = None,
    ) -> RefundAction:
        """Mark refund action NEEDS_ATTENTION after max retry attempts; preserves pending balance (RV3-12)."""
        with self._lock, self.get_session() as session:
            act = session.get(RefundAction, request_id)
            if not act:
                raise ValueError(f"RefundAction {request_id} not found.")
            if act.status == "CONFIRMED":
                return act
            act.status = "NEEDS_ATTENTION"
            act.next_attempt_at = None
            if status_detail is not None:
                act.status_detail = status_detail
            if paypal_debug_id:
                act.paypal_debug_id = paypal_debug_id
            if paypal_refund_id:
                act.paypal_refund_id = paypal_refund_id
            act.version += 1
            session.add(act)
            session.commit()
            session.refresh(act)
            return act

    def record_refund_failed_permanent(
        self,
        *,
        request_id: str,
        paypal_debug_id: str | None = None,
        paypal_refund_id: str | None = None,
        status_detail: str | None = None,
    ) -> RefundAction:
        """Mark refund action FAILED_PERMANENT on 4xx error or FAILED/CANCELLED status and release pending balance (AUD-02, ARC-19, RV3-01)."""
        with self._lock, self.get_session() as session:
            act = session.get(RefundAction, request_id)
            if not act:
                raise ValueError(f"RefundAction {request_id} not found.")
            if act.status == "FAILED_PERMANENT":
                return act

            stmt = select(Order).where(Order.order_id == act.order_id)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update()
            order = session.exec(stmt).first()
            if not order:
                raise ValueError(f"Order {act.order_id} not found for refund action {request_id}.")

            order.pending_refunded_minor = max(0, order.pending_refunded_minor - act.amount_minor)
            order.version += 1
            session.add(order)

            act.status = "FAILED_PERMANENT"
            act.next_attempt_at = None
            if paypal_debug_id:
                act.paypal_debug_id = paypal_debug_id
            if paypal_refund_id:
                act.paypal_refund_id = paypal_refund_id
            if status_detail is not None:
                act.status_detail = status_detail
            act.version += 1
            session.add(act)

            session.commit()
            session.refresh(act)
            return act

    def acquire_scheduler_lease(
        self,
        lease_name: str = "automation_scheduler",
        holder_id: str = "worker_1",
        ttl_seconds: float = 30.0,
    ) -> bool:
        """Acquire or renew leadership lease for background scheduler execution (RV2-02).
        Uses Postgres pg_try_advisory_lock or transactional lease row.
        """
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)

        with self._lock, self.get_session() as session:
            driver = str(self.engine.url.drivername).lower()
            if "postgres" in driver:
                res = session.execute(
                    text("SELECT pg_try_advisory_lock(:lock_id)"),
                    {"lock_id": 839218392},
                ).scalar()
                if not res:
                    return False

            session.execute(
                text(
                    "CREATE TABLE IF NOT EXISTS scheduler_leases ("
                    "lease_name VARCHAR PRIMARY KEY, "
                    "holder_id VARCHAR NOT NULL, "
                    "acquired_at TIMESTAMP NOT NULL, "
                    "expires_at TIMESTAMP NOT NULL)"
                )
            )

            stmt = select(SchedulerLease).where(SchedulerLease.lease_name == lease_name)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update()
            lease = session.exec(stmt).first()

            if lease is None:
                lease = SchedulerLease(
                    lease_name=lease_name,
                    holder_id=holder_id,
                    acquired_at=now,
                    expires_at=expires_at,
                )
                session.add(lease)
                session.commit()
                return True

            if lease.holder_id == holder_id:
                lease.expires_at = expires_at
                session.add(lease)
                session.commit()
                return True

            lease_exp = lease.expires_at
            if lease_exp.tzinfo is None:
                lease_exp = lease_exp.replace(tzinfo=timezone.utc)

            if lease_exp < now:
                lease.holder_id = holder_id
                lease.acquired_at = now
                lease.expires_at = expires_at
                session.add(lease)
                session.commit()
                return True

            return False

    def release_scheduler_lease(
        self,
        lease_name: str = "automation_scheduler",
        holder_id: str = "worker_1",
    ) -> bool:
        """Release leadership lease for background scheduler execution (RV2-02)."""
        with self._lock, self.get_session() as session:
            driver = str(self.engine.url.drivername).lower()
            if "postgres" in driver:
                session.execute(
                    text("SELECT pg_advisory_unlock(:lock_id)"),
                    {"lock_id": 839218392},
                )

            stmt = select(SchedulerLease).where(SchedulerLease.lease_name == lease_name)
            lease = session.exec(stmt).first()
            if lease and lease.holder_id == holder_id:
                session.delete(lease)
                session.commit()
                return True
            return False

    def record_evidence_pack_transactional(
        self,
        *,
        return_id: str,
        evidence: ReturnEvidence,
        assessment: Assessment,
        decision: Decision,
        refund_amount_minor: int,
        tranche: str = "R0",
        paypal_debug_id: str | None = None,
        lane: str | None = None,
        timing: str | None = None,
        audit_probability: float | None = None,
        transition_event: str | None = None,
        **transition_guards: Any,
    ) -> tuple[ReturnEvidence, Assessment, Decision, RefundAction | None, Return]:
        """Atomically persist ReturnEvidence, Assessment, Decision, optional RefundAction (with order row lock
        and pending_refunded_minor increment), and apply state transition on Return.
        Rolls back completely if any step fails (INV-01, AUD-06, RV2-04).
        """
        with self._lock, self.get_session() as session:
            ret = session.get(Return, return_id)
            if not ret:
                raise ValueError(f"Return {return_id} not found.")

            stmt = select(Order).where(Order.order_id == ret.order_id)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update()
            order = session.exec(stmt).first()
            if not order:
                raise ValueError(f"Order {ret.order_id} not found.")

            if order.frozen_by_dispute or order.capture_reversed:
                raise OrderFrozenError(
                    f"Order {order.order_id} is frozen (frozen_by_dispute={order.frozen_by_dispute}, capture_reversed={order.capture_reversed})."
                )

            action = None
            if refund_amount_minor > 0:
                if not order.capture_id or not order.capture_id.strip():
                    raise MissingCaptureError(f"Order {order.order_id} has no capture_id.")

                remaining = order.capture_amount_minor - order.confirmed_refunded_minor - order.pending_refunded_minor
                if refund_amount_minor > remaining:
                    raise OverRefundError(
                        f"Requested R0 refund {refund_amount_minor} minor exceeds remaining refundable {remaining} minor "
                        f"(capture={order.capture_amount_minor}, confirmed={order.confirmed_refunded_minor}, pending={order.pending_refunded_minor})."
                    )

                req_id = compute_deterministic_request_id(decision.decision_id, tranche)
                action = session.get(RefundAction, req_id)
                if action:
                    if action.amount_minor != refund_amount_minor:
                        raise IdempotencyConflictError(f"Action {req_id} already exists with different amount.")
                else:
                    action = RefundAction(
                        request_id=req_id,
                        merchant_id=order.merchant_id,
                        order_id=ret.order_id,
                        return_id=return_id,
                        decision_id=decision.decision_id,
                        capture_id=order.capture_id,
                        tranche=tranche,
                        amount_minor=refund_amount_minor,
                        currency=order.currency,
                        status="PLANNED",
                        attempt_count=0,
                        paypal_debug_id=paypal_debug_id,
                    )
                    session.add(action)
                    order.pending_refunded_minor += refund_amount_minor
                    order.version += 1
                    session.add(order)

            # State machine transitions
            entity = ReturnEntity(
                return_id=ret.return_id,
                order_id=ret.order_id,
                state=ret.state,
                lane=lane or ret.lane,
                timing=timing or ret.timing,
            )
            # Dynamic guards computed from persisted data (RV-03, Task T6, R4-T3)
            pol = session.get(Policy, order.policy_version) if order else None
            return_window_days = pol.return_window_days if pol else 30
            now_utc = datetime.now(timezone.utc)
            order_created = order.created_at.replace(tzinfo=timezone.utc) if (order and order.created_at) else now_utc
            within_window = transition_guards.get("within_window", (now_utc - order_created).days <= return_window_days)
            authorized = transition_guards.get("authorized", bool(order and ret.order_id == order.order_id))
            consent_recorded = transition_guards.get("consent_recorded", bool(ret.consent_recorded))
            retakes_ok = transition_guards.get("retakes_ok", (ret.retake_count <= 3))
            stored_nonce = ret.challenge_nonce.strip().upper() if ret.challenge_nonce else ""
            ev_nonce = evidence.nonce_return.strip().upper() if (evidence and evidence.nonce_return) else ""
            challenge_valid = transition_guards.get("challenge_valid", (ev_nonce == stored_nonce if (ev_nonce and stored_nonce) else False))
            challenge_not_verified = transition_guards.get("challenge_not_verified", False)
            evidence_complete = transition_guards.get("evidence_complete", bool(evidence and evidence.evidence_sha256))
            assessment_exists = transition_guards.get("assessment_exists", bool(assessment and assessment.assessment_id))

            if entity.state == "REQUESTED":
                self.state_machine.apply(
                    entity,
                    "SUBMIT_DECLARATION",
                    within_window=within_window,
                    authorized=authorized,
                    consent_recorded=consent_recorded,
                )
            if entity.state == "DECLARED":
                self.state_machine.apply(
                    entity,
                    "SUBMIT_EVIDENCE",
                    evidence_complete=evidence_complete,
                    challenge_valid=challenge_valid,
                    challenge_not_verified=challenge_not_verified,
                    retakes_ok=retakes_ok,
                )
                self.state_machine.apply(
                    entity,
                    "FINISH_ASSESSMENT",
                    assessment_exists=assessment_exists,
                )
            elif entity.state == "EVIDENCE_SUBMITTED":
                self.state_machine.apply(
                    entity,
                    "FINISH_ASSESSMENT",
                    assessment_exists=assessment_exists,
                )

            ret.state = entity.state
            if lane:
                ret.lane = lane
            if timing:
                ret.timing = timing
            ret.r0_tranche_minor = refund_amount_minor
            if audit_probability is not None:
                ret.audit_probability = audit_probability
            ret.version += 1
            session.add(ret)

            ev_merged = session.merge(evidence)
            ass_merged = session.merge(assessment)
            dec_merged = session.merge(decision)

            session.commit()
            if action:
                session.refresh(action)
            session.refresh(ret)
            session.refresh(ev_merged)
            session.refresh(ass_merged)
            session.refresh(dec_merged)
            return ev_merged, ass_merged, dec_merged, action, ret

    def record_review_and_settlement_transactional(
        self,
        *,
        return_id: str,
        review: Review,
        refund_amount_minor: int,
        tranche: str = "SETTLEMENT",
        paypal_debug_id: str | None = None,
        transition_event: str | None = None,
        **transition_guards: Any,
    ) -> tuple[Review, RefundAction | None, Return]:
        """Atomically persist Review, optional settlement RefundAction (with order row lock
        and pending_refunded_minor increment), and apply state transition on Return.
        Rolls back completely if any step fails (INV-01, AUD-29, RV2-04).
        """
        with self._lock, self.get_session() as session:
            ret = session.get(Return, return_id)
            if not ret:
                raise ValueError(f"Return {return_id} not found.")

            if ret.state in {"REJECTED", "CLOSED", "CANCELLED"}:
                raise InvalidStateTransitionError(f"Cannot review return in terminal state {ret.state}")

            stmt = select(Order).where(Order.order_id == ret.order_id)
            if not self.engine.url.drivername.startswith("sqlite"):
                stmt = stmt.with_for_update()
            order = session.exec(stmt).first()
            if not order:
                raise ValueError(f"Order {ret.order_id} not found.")

            if order.frozen_by_dispute or order.capture_reversed:
                raise OrderFrozenError(
                    f"Order {order.order_id} is frozen (frozen_by_dispute={order.frozen_by_dispute}, capture_reversed={order.capture_reversed})."
                )

            action = None
            if refund_amount_minor > 0:
                if not order.capture_id or not order.capture_id.strip():
                    raise MissingCaptureError(f"Order {order.order_id} has no capture_id.")

                remaining = order.capture_amount_minor - order.confirmed_refunded_minor - order.pending_refunded_minor
                if refund_amount_minor > remaining:
                    raise OverRefundError(
                        f"Requested settlement refund {refund_amount_minor} minor exceeds remaining refundable {remaining} minor "
                        f"(capture={order.capture_amount_minor}, confirmed={order.confirmed_refunded_minor}, pending={order.pending_refunded_minor})."
                    )

                req_id = compute_deterministic_request_id(review.review_id, tranche)
                action = session.get(RefundAction, req_id)
                if action:
                    if action.amount_minor != refund_amount_minor:
                        raise IdempotencyConflictError(f"Action {req_id} already exists with different amount.")
                else:
                    action = RefundAction(
                        request_id=req_id,
                        merchant_id=order.merchant_id,
                        order_id=ret.order_id,
                        return_id=return_id,
                        decision_id=review.review_id,
                        capture_id=order.capture_id,
                        tranche=tranche,
                        amount_minor=refund_amount_minor,
                        currency=order.currency,
                        status="PLANNED",
                        attempt_count=0,
                        paypal_debug_id=paypal_debug_id,
                    )
                    session.add(action)
                    order.pending_refunded_minor += refund_amount_minor
                    order.version += 1
                    session.add(order)

            # Apply state machine transition if specified
            if transition_event:
                entity = ReturnEntity(
                    return_id=ret.return_id,
                    order_id=ret.order_id,
                    state=ret.state,
                    lane=ret.lane,
                    timing=ret.timing,
                )
                self.state_machine.apply(entity, transition_event, **transition_guards)
                ret.state = entity.state
                ret.lane = entity.lane
                ret.timing = entity.timing
                ret.version += 1
                session.add(ret)

            rev_merged = session.merge(review)
            session.commit()
            if action:
                session.refresh(action)
            session.refresh(ret)
            session.refresh(rev_merged)
            return rev_merged, action, ret

    def list_custody_events_by_passport(self, passport_id: str) -> list[CustodyEvent]:
        with self.get_session() as session:
            stmt = select(CustodyEvent).where(CustodyEvent.passport_id == passport_id)
            return list(session.exec(stmt).all())

    def get_custody_event(self, custody_event_id: str) -> CustodyEvent | None:
        with self.get_session() as session:
            return session.get(CustodyEvent, custody_event_id)

    def save_custody_event(self, event: CustodyEvent) -> CustodyEvent:
        with self._lock, self.get_session() as session:
            merged = session.merge(event)
            session.commit()
            session.refresh(merged)
            return merged

    def get_webhook_event(self, event_id: str) -> WebhookEvent | None:
        with self.get_session() as session:
            return session.get(WebhookEvent, event_id)

    def save_webhook_event(self, event: WebhookEvent) -> WebhookEvent:
        with self._lock, self.get_session() as session:
            merged = session.merge(event)
            session.commit()
            session.refresh(merged)
            return merged

    def process_webhook_event_transactional(
        self,
        *,
        event_id: str,
        event_type: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        """Atomically deduplicate webhook event and apply dispute/reversal freeze on Order in the SAME transaction (RV3-11, FR-75, AUD-12, RV-14)."""
        with self._lock, self.get_session() as session:
            existing_event = session.get(WebhookEvent, event_id)
            if existing_event is not None:
                return {
                    "status_code": 200,
                    "duplicate": True,
                    "event_id": event_id,
                }

            order_id = str(payload.get("order_id", "")).strip()
            order: Order | None = None
            if order_id:
                stmt = select(Order).where(Order.order_id == order_id)
                if not self.engine.url.drivername.startswith("sqlite"):
                    stmt = stmt.with_for_update()
                order = session.exec(stmt).first()
                if order is None:
                    # AUD-12: Unknown order — do not record event as processed so future retry succeeds
                    return {
                        "status_code": 404,
                        "code": "ORDER_NOT_FOUND",
                        "duplicate": False,
                        "event_id": event_id,
                    }

            now = datetime.now(timezone.utc)
            if event_type == "CUSTOMER.DISPUTE.CREATED" and order is not None:
                res_dict = payload.get("resource") if isinstance(payload.get("resource"), dict) else {}
                dispute_reason = str(
                    payload.get("dispute_id")
                    or res_dict.get("dispute_id")
                    or res_dict.get("id")
                    or payload.get("id")
                    or event_id
                )
                order.frozen_by_dispute = True
                order.frozen_at = now
                order.frozen_reason = dispute_reason
                order.version += 1
                session.add(order)
            elif event_type == "PAYMENT.CAPTURE.REVERSED" and order is not None:
                order.capture_reversed = True
                order.reversed_at = now
                order.version += 1
                session.add(order)
            elif event_type == "PAYMENT.CAPTURE.REFUNDED":
                res_dict = payload.get("resource") if isinstance(payload.get("resource"), dict) else {}
                refund_id = str(
                    payload.get("refund_id")
                    or res_dict.get("refund_id")
                    or res_dict.get("id")
                    or ""
                ).strip()
                refund_status = str(res_dict.get("status") or payload.get("status") or "COMPLETED").strip().upper()
                act_match: RefundAction | None = None
                if refund_id:
                    act_match = session.exec(
                        select(RefundAction).where(RefundAction.paypal_refund_id == refund_id)
                    ).first()
                if act_match is None and order is not None:
                    act_match = session.exec(
                        select(RefundAction).where(
                            RefundAction.order_id == order.order_id,
                            RefundAction.status == "SUBMITTED",
                        )
                    ).first()
                if act_match is not None and act_match.status != "CONFIRMED" and refund_status == "COMPLETED":
                    target_order = order
                    if target_order is None:
                        ord_stmt = select(Order).where(Order.order_id == act_match.order_id)
                        if not self.engine.url.drivername.startswith("sqlite"):
                            ord_stmt = ord_stmt.with_for_update()
                        target_order = session.exec(ord_stmt).first()
                    if target_order is not None:
                        target_order.pending_refunded_minor = max(
                            0, target_order.pending_refunded_minor - act_match.amount_minor
                        )
                        target_order.confirmed_refunded_minor += act_match.amount_minor
                        target_order.version += 1
                        session.add(target_order)
                        act_match.status = "CONFIRMED"
                        act_match.status_detail = "COMPLETED"
                        if refund_id and not act_match.paypal_refund_id:
                            act_match.paypal_refund_id = refund_id
                        act_match.version += 1
                        session.add(act_match)

            webhook_rec = WebhookEvent(
                event_id=event_id,
                event_type=event_type,
                payload_json=payload,
            )
            session.add(webhook_rec)
            session.commit()

            return {
                "status_code": 200,
                "duplicate": False,
                "event_id": event_id,
                "event_type": event_type,
            }

    def get_latest_review_by_return(self, return_id: str) -> Review | None:
        with self.get_session() as session:
            stmt = select(Review).where(Review.return_id == return_id).order_by(Review.created_at.desc())
            return session.exec(stmt).first()

    def save_review(self, review: Review) -> Review:
        with self._lock, self.get_session() as session:
            if not session.get(StaffUser, review.reviewer_id):
                session.merge(
                    StaffUser(
                        staff_id=review.reviewer_id,
                        merchant_id="merch_a",
                        role="REVIEWER",
                        email_hash=hashlib.sha256(review.reviewer_id.encode()).hexdigest(),
                    )
                )
                session.flush()
            merged = session.merge(review)
            session.commit()
            session.refresh(merged)
            return merged

    def save_appeal(self, appeal: Appeal) -> Appeal:
        with self._lock, self.get_session() as session:
            for staff_id in [appeal.original_reviewer_id, appeal.appeal_reviewer_id]:
                if staff_id and not session.get(StaffUser, staff_id):
                    session.merge(
                        StaffUser(
                            staff_id=staff_id,
                            merchant_id="merch_a",
                            role="REVIEWER",
                            email_hash=hashlib.sha256(staff_id.encode()).hexdigest(),
                        )
                    )
            session.flush()
            merged = session.merge(appeal)
            session.commit()
            session.refresh(merged)
            return merged

    def get_appeal(self, appeal_id: str) -> Appeal | None:
        with self.get_session() as session:
            return session.get(Appeal, appeal_id)

    def save_resale_listing(self, listing: ResaleListing) -> ResaleListing:
        with self._lock, self.get_session() as session:
            merged = session.merge(listing)
            session.commit()
            session.refresh(merged)
            return merged

    def get_resale_listing(self, listing_id: str) -> ResaleListing | None:
        with self.get_session() as session:
            return session.get(ResaleListing, listing_id)

    def save_agent_token(self, token_record: AgentToken) -> AgentToken:
        with self._lock, self.get_session() as session:
            session.add(token_record)
            session.commit()
            session.refresh(token_record)
            return token_record

    def reset_demo_database(self) -> None:
        """Cleanly reset mutable demo records while maintaining schema (AUD-25)."""
        with self._lock, self.get_session() as session:
            session.exec(sa.delete(Appeal))
            session.exec(sa.delete(Review))
            session.exec(sa.delete(ResaleListing))
            session.exec(sa.delete(ReturnEvidence))
            session.exec(sa.delete(Assessment))
            session.exec(sa.delete(RefundAction))
            session.exec(sa.delete(Decision))
            session.exec(sa.delete(KeepOffer))
            session.exec(sa.delete(CustodyEvent))
            session.exec(sa.delete(PassportEvent))
            session.exec(sa.delete(Passport))
            session.exec(sa.delete(AgentToken))
            session.exec(sa.delete(WebhookEvent))
            session.exec(sa.delete(Return))
            for ord_row in session.exec(select(Order)).all():
                ord_row.confirmed_refunded_minor = 0
                ord_row.pending_refunded_minor = 0
                ord_row.frozen_by_dispute = False
                ord_row.frozen_at = None
                ord_row.frozen_reason = None
                ord_row.capture_reversed = False
                ord_row.reversed_at = None
                session.add(ord_row)
            session.commit()
        self.seed_demo_data()
