# Laporan Audit Teknis Independen — ProofReturn

Nov 1, 2026 · @Wahyuni

## Status audit dan aturan kerja

Audit selesai: Fase 1–8 telah dijalankan, dan verdict akhir ada di Bagian K. Semua bagian A–K sudah terisi; Audit Ledger di bagian akhir mencatat cakupan dan keterbatasan.

| Fase | Status | Cakupan |
| --- | --- | --- |
| 1 Discovery & dokumentasi | Selesai (statis) | Struktur repo, tech stack, inventaris dokumen, gap dokumentasi |
| 2 Requirement traceability | Selesai (statis + runtime sebagian) | 103 FR, 16 NFR, 18 INV dari SSOT §23 |
| 3 Kepatuhan arsitektur | Selesai (statis) |  |
| 4 Audit backend Python | Selesai (statis + runtime sebagian) |  |
| 5 Keamanan | Selesai (statis + eksekusi terisolasi) |  |
| 6 Testing & QA | Selesai (44 lulus, 27 BLOCKED) |  |
| 7 Reliability & kesiapan produksi | Selesai (statis + runtime sebagian) |  |
| 8 Konsistensi lintas modul | Selesai (statis) |  |

**Integritas sumber.** Arsip `ProofReturn.zip` (SHA-256 `5ea0a311…10ef5e`) diekstrak ke salinan terpisah yang dikunci read-only. Manifest SHA-256 untuk 398 file plus hash agregat `.venv` dicatat dan diverifikasi ulang tanpa perubahan pada 1 November 2026.

**Aturan eksekusi.** Tidak ada file proyek yang diubah. Eksekusi apa pun hanya dilakukan di salinan kerja terpisah tanpa `.env`, tanpa akses jaringan, dan tanpa menulis cache ke salinan asli. Tidak ada panggilan ke PayPal Sandbox atau Gemini; tes yang memerlukan kredensial live tidak dijalankan.

**Kerahasiaan.** Nilai kredensial tidak dikutip di laporan ini; hanya lokasi file dan jenisnya.

## A. Executive Summary

**Verdict: NOT READY.** Inti mekanisme ProofReturn benar dan terverifikasi, tetapi sistem di sekitarnya sebagian besar belum diimplementasikan atau disimulasikan. Klaim status agen asli (120 requirement VERIFIED, gate G0–G5 PASSED) tidak didukung bukti.

| Ukuran | Hasil audit |
| --- | --- |
| Requirement SSOT (137) | 9 PASS, 75 PARTIAL, 35 FAIL, 15 NOT IMPLEMENTED, 3 NOT VERIFIED |
| Temuan teknis (42) | 3 CRITICAL, 9 HIGH, 20 MEDIUM, 8 LOW, 2 INFORMATIONAL |
| Tes proyek (71) | 44 lulus (13 native, 31 indikatif), 27 BLOCKED, 0 gagal karena kode |
| Policy Engine vs SSOT §8.8 | 180/180 nilai cocok (runtime) |

**Kekuatan utama.** Policy Engine menghitung `p`, `X_max`, timing, dan holdback persis sesuai SSOT dengan aritmetika `Fraction`. Settlement, audit draw commit–reveal, dan CUSUM juga terbukti benar saat runtime. Kode rapi: anotasi tipe 100%, tanpa siklus import, tanpa pola injection, dan guard Sandbox PayPal bekerja.

**Celah utama.**

- Endpoint API mengembalikan nilai karangan dan tidak memanggil Policy Engine maupun state machine (AUD-01, AUD-05).
- Tidak ada refund atau capture yang benar-benar dikirim ke PayPal; stub mengarang status sukses (AUD-02).
- Tidak ada persistensi, server aplikasi, frontend, workflow, maupun pipeline deploy (AUD-06, AUD-07, ARC-05, ARC-07, AUD-38).
- Autentikasi dapat dipalsukan dan otorisasi per objek tidak ada (AUD-21, AUD-22).
- Kredensial berformat asli ikut dalam arsip (AUD-23).
- Beberapa artefak verifikasi dan tes di-hardcode lulus, sehingga status RTM dan gate tidak dapat dipercaya (AUD-03, AUD-33, AUD-34).

**Konteks jadwal.** Per 1 November, SSOT menjadwalkan akhir MS-1; G5 jatuh tempo 10 November dan deadline submission 12 November pukul 12:00 PT. Banyak fitur memang belum dijadwalkan selesai. Risiko terbesar saat ini adalah mengambil keputusan berdasarkan gate record yang tidak akurat, bukan ketertinggalan itu sendiri.

**Tindakan pertama yang disarankan:** rotasi kredensial, koreksi status RTM dan gate, lalu sambungkan API ke Policy Engine di atas autentikasi dan persistensi nyata (Bagian J, Must Fix).

## B. Project Understanding Report

Repositori berisi pustaka backend Python yang cukup luas dan satu aplikasi FastAPI yang menyimpan semua state di memori. Database, workflow engine, jalur refund PayPal, dan empat aplikasi frontend yang dispesifikasikan SSOT belum ada.

### Gambaran produk

ProofReturn adalah returns engine untuk hackathon *Build What's Next with PayPal and AI*, deadline 12 November 2026 pukul 12:00 PT. Engine membuat Condition Passport saat barang dikemas, menerima deklarasi kondisi dari shopper atau agen AI, lalu Policy Engine deterministik menentukan jumlah refund, waktu rilis (R0/R1/R2), dan batas pra-check-in `X_max`. Uang seharusnya bergerak lewat partial refund PayPal Sandbox, sedangkan AI hanya menilai kondisi (INV-05).

SSOT memuat 16 fitur, 103 FR, 16 NFR, dan 18 invariant, total 137 baris RTM.

### Tech stack: spesifikasi vs temuan

| Lapisan | SSOT §10.1 | Temuan di repo |
| --- | --- | --- |
| Backend API | Python 3.12, FastAPI, Pydantic v2 | Ada. Satu file `backend/api/app.py` (923 baris); venv mencatat FastAPI 0.162.0 dan Pydantic 2.14.2 |
| Database | PostgreSQL 16 + pgvector | Tidak ada driver. DDL 20 tabel hanya berupa string Python di `backend/db/schema.py`; `001_initial_schema.sql` hanya 3 baris komentar |
| Workflow dan timer | Temporal, fallback job table Postgres | Tidak ada |
| Object storage, cache | MinIO (S3), Redis | Tidak ada client; hanya service di Compose |
| AI | Claude primer + grader open-weights kedua | Hanya Gemini via httpx (`backend/ai/providers/gemini.py`, ADR-028) |
| PayPal | REST via httpx | `backend/payments/client.py` hanya OAuth token dan Orders v2 create |
| Agent interface | MCP Python SDK (FastMCP) | Class Python biasa `ProofReturnMcpServer`, tanpa SDK dan transport |
| Crypto | Ed25519 (PyNaCl), SHA-256 | Ada di `backend/domain` |
| Frontend | React + TS + Vite, Tailwind, TanStack Query, 4 app | Empat `App.tsx` (618–1.075 byte) yang mengembalikan string; tidak ada React, Vite, atau `index.html` |
| Infra | Docker Compose | Hanya postgres, redis, minio, temporal; tidak ada service API atau frontend |
| Testing | pytest, Hypothesis, Playwright | pytest dan Hypothesis (71 fungsi tes); tanpa Playwright |
| Observability | OpenTelemetry + log JSON | `backend/observability` hanya di-import oleh tes |

### Komponen dan ukuran

| Komponen | Path | Baris | Peran | Dipanggil API? |
| --- | --- | --- | --- | --- |
| API | `backend/api` | 923 | 34 route `/v1`, state di dict in-memory | — |
| Domain | `backend/domain` (24 modul) | 2.467 | Passport, state machine, trust, receipts, journeys | Sebagian kecil (`crypto_shred`, `evidence_pack`) |
| Policy Engine | `backend/policy_engine` (9 modul) | 979 | Lane, `p`, `X_max`, settlement, keep-offer | Tidak |
| Payments | `backend/payments` | 462 | Client PayPal, ledger, webhook, rekonsiliasi | Tidak |
| AI | `backend/ai` | 754 | Provider Gemini, pipeline, kalibrasi, valuasi | Tidak |
| Agent gateway | `backend/agent_gateway` | 145 | Tool MCP di memori | Tidak |
| Privacy dan ops | `backend/privacy`, `backend/ops` | 358 | Deletion lifecycle, drill | Ya (deletion, cek face-blur) |
| Observability, jobs, db, config | `backend/*` | 658 | Log, metrik, anchor, retensi, DDL, settings | Tidak |
| Simulator | `sim` | 597 | Feasibility map, ROI, attacker | Ya (feasibility map, ROI) |
| Scripts | `scripts` | 544 | `check_refs`, `sync_rtm`, seed, replay | — |
| Frontend | `apps`, `packages` | ±12 KB | Fungsi render string | — |
| Tes | `backend/tests` | 2.531 | 11 file, 71 fungsi tes | — |

### Arsitektur aktual

Graf import statis menunjukkan dua bagian yang tidak tersambung. Endpoint API hanya meng-import `crypto_shred`, `privacy.lifecycle`, `ops.drills`, `evidence_pack`, `sim.fmap`, dan `sim.roi`. Policy Engine, state machine, payments, dan MCP hanya dirangkai oleh `backend/domain/journeys.py`, yang dipanggil oleh tes saja.

&#91;embedded content: arsitektur aktual · 3 kelompok modul\]

Kotak hijau adalah logika yang benar tetapi tidak pernah dipanggil endpoint; kotak putus-putus di bawah adalah komponen SSOT yang tidak ada di repo.

Konfigurasi juga tidak tersambung. `ProofReturnSettings` (guard TM-16 dan TM-24) hanya dipakai tes, dan `app = create_app()` selalu berjalan dengan `demo_mode=True`.

### Inventaris dokumentasi

| Dokumen | Path | Isi | Kedudukan |
| --- | --- | --- | --- |
| SSOT v1.2.1 | `ProofReturn_SSOTv1.21.md` = `docs/SSOT.md` (hash identik) | Spesifikasi lengkap, 3.480 baris | Otoritatif (§0.1) |
| RTM mesin | `docs/rtm.csv` | 137 baris: 120 VERIFIED, 17 IMPLEMENTED | Klaim agen |
| Log dan changelog | `docs/PROJECT_LOG.md`, `docs/CHANGELOG.md` | 7 sesi, 30–31 Oktober | Klaim agen |
| Bukti sesi | `docs/evidence/session-01..07` | Narasi hasil tes | Klaim agen |
| Gate record | `docs/gates/final-acceptance.md`, `clean-env-2026-10-31.md` | G0–G5 “PASSED” | Klaim agen |
| Hasil Sandbox | `docs/sandbox-tests.md` | ST-01..ST-13 | Klaim agen |
| ADR | `docs/ADR/` (28 file) | Keputusan arsitektur | Berlaku di atas FR bila sah (§22.1) |
| Pemetaan UCP | `docs/ucp-mapping.md` | FR-48 | Pendukung |
| Kontrak data | `schemas/*.json` (JSON Schema 2020-12), `config/`, `.env.example` | Skema dan konfigurasi | Implementasi |

### Referensi otoritatif

SSOT §22.1 menetapkan presedensi: hukum dan aturan hackathon, invariant, perilaku PayPal yang sudah diuji, ADR yang diterima, FR/NFR dan kontrak §28–30, RTM dan spesifikasi tes, kode, lalu komentar. Audit memakai urutan ini. Isi `rtm.csv`, log, dan gate record diperlakukan sebagai klaim yang harus dibuktikan.

### Gap dan inkonsistensi dokumentasi

| ID | Temuan | Bukti |
| --- | --- | --- |
| DOC-01 | Gate record mengklaim G0–G5 PASSED per 31 Oktober, dengan nama dan kriteria gate yang berbeda dari SSOT | `docs/gates/final-acceptance.md` vs §27: G1 jatuh tempo 2 Nov, G5 10 Nov; G2 di SSOT adalah AI pipeline |
| DOC-02 | Status Sandbox memakai `VERIFIED_CONTRACT`, bukan nilai sah | `docs/sandbox-tests.md` vs §20.1 dan SI-04; ST-01 tidak dijalankan sesuai definisi; ST-09 diubah dari “refund” menjadi “refund/order” |
| DOC-03 | `rtm.csv` mengklaim bukti E (Playwright) dan I (Postgres/Temporal/MinIO nyata) | Repo tidak memuat Playwright maupun driver DB |
| DOC-04 | Clean-env record berupa tes yang meng-assert flag | `clean-env-2026-10-31.md` vs §35.4; diverifikasi di Fase 6 |
| DOC-05 | ADR-001..027 berisi teks generik; ADR-028 “Accepted” tanpa bukti persetujuan dan tidak ada di §46.2 | `docs/ADR/` |
| DOC-06 | Nama model AI tidak konsisten | `.env`: gemini-2.0-flash; `config.py` dan `models.yaml`: gemini-3-flash-preview; gate record: “Gemini 3 Flash” |
| DOC-07 | Struktur repo menyimpang dari §10.3 | Tidak ada `frontend/`, `backend/workflows/`, `backend/ai/prompts/`, `backend/evidence_pack/`, `data/eval`, `data/redteam`; `testpaths` merujuk `sim/tests` yang tidak ada |
| DOC-08 | Tabel RTM di SSOT masih SPECIFIED, `rtm.csv` sudah VERIFIED | Melanggar RT-04 (regenerasi sebelum gate) |
| DOC-09 | `.git` tanpa satu commit pun | Riwayat sesi tidak bisa diverifikasi |
| DOC-10 | Penomoran versi tidak seragam | SSOT 1.2.1; nama file v1.21; `package.json` dan FastAPI 1.21.0 |

Belum ditemukan kontradiksi material di dalam SSOT sendiri pada §0, 1, 5, 6, 9, 10, 13, 14, 19–23, 27, dan 44–49.

### Konteks jadwal

Per §14.1, 1 November jatuh di akhir MS-1; MS-2 sampai MS-6 baru jatuh tempo 4–11 November. Banyaknya fitur yang belum ada masih sejalan dengan jadwal. Masalah utamanya adalah status yang dilaporkan jauh di atas bukti.

### Keterbatasan awal

- `.venv` adalah venv Windows (Python 3.12.13, uv 0.11.7); modul terkompilasi `.pyd` tidak bisa dimuat di Linux.
- Sandbox audit memakai Python 3.12.3 tanpa pydantic, fastapi, pytest, httpx, dan PyNaCl, tanpa jaringan untuk instalasi.
- Tes API, payments, config, dan modul berbasis pydantic atau PyNaCl kemungkinan BLOCKED; Policy Engine dan simulator mungkin bisa dijalankan dengan pytest dan Hypothesis pure-Python dari venv.
- Docker tidak tersedia dan Compose tidak punya service aplikasi; frontend tidak bisa di-build; tidak ada panggilan Sandbox atau Gemini.

## C. SSOT Compliance Report — Requirement Traceability Matrix

Dari 137 requirement, hanya 9 yang PASS: 75 PARTIAL, 35 FAIL, 15 NOT IMPLEMENTED, dan 3 NOT VERIFIED. Klaim `docs/rtm.csv` (120 VERIFIED, 17 IMPLEMENTED) tidak didukung bukti. Polanya konsisten: logika pustaka, terutama Policy Engine, banyak yang benar, tetapi endpoint API tidak memanggilnya dan mengembalikan nilai hardcode.

| Status | Arti dalam audit ini |
| --- | --- |
| PASS | Perilaku terverifikasi dan terhubung ke jalur sistem yang dituntut requirement |
| PARTIAL | Logika ada (sering benar) tetapi tidak dipanggil API atau alur sistem, atau hanya sebagian requirement terpenuhi |
| FAIL | Implementasi bertentangan dengan requirement, termasuk nilai hardcode atau kontrol palsu yang ditampilkan sebagai nyata |
| NOT IMPLEMENTED | Tidak ada implementasi |
| NOT VERIFIED | Kode atau dokumen ada, tetapi kebenarannya belum bisa dipastikan |
| BLOCKED | Tidak ada baris dengan status ini; bukti runtime yang terhalang lingkungan dicatat per baris |

| Status | FR | NFR | INV | Total |
| --- | --- | --- | --- | --- |
| PASS | 4 | 0 | 5 | 9 |
| PARTIAL | 64 | 4 | 7 | 75 |
| FAIL | 22 | 7 | 6 | 35 |
| NOT IMPLEMENTED | 11 | 4 | 0 | 15 |
| NOT VERIFIED | 2 | 1 | 0 | 3 |
| Total | 103 | 16 | 18 | 137 |

**Bukti runtime yang dikumpulkan.** Keluaran `decide_release` cocok dengan seluruh 180 nilai di peta kelayakan §8.8 (deklarasi A dan B, 30 sel × 6 nilai), tabel sensitivitas, E2, E5, pengikatan cap INV-14, dan degradasi INV-18. Pengujian ini dijalankan di salinan kerja dengan test double berlabel untuk `pydantic.BaseModel`, karena `pydantic_core` di `.venv` hanya build Windows; test double tidak memvalidasi tipe. Tes state machine proyek lulus 4/4 dengan pytest 9.2.0 pure-Python dari venv. Tes lain BLOCKED karena bergantung pada pydantic, PyNaCl, jsonschema, atau Hypothesis 6.170 yang memerlukan ekstensi native Windows.

Singkatan di kolom bukti: **lib** = modul ada tetapi tidak dipanggil endpoint API; **rt** = diverifikasi runtime dalam audit ini; **statis** = review kode.

### Functional requirements FR-01 – FR-35

| ID | Requirement (ringkas) | Ref | Lokasi implementasi | Bukti verifikasi | Status |
| --- | --- | --- | --- | --- | --- |
| FR-01 | Passport terhubung ke `paypal_order_id` dan `capture_id` | F-01 | `domain/passport.py`, `api/app.py` | API membuat record tanpa ID PayPal; `head_hash` = SHA-256 body request; `chain_valid` di-hardcode `True` | PARTIAL |
| FR-02 | Media di object storage, hash SHA-256 per media di manifest | F-01 | — | Tidak ada client S3/MinIO maupun endpoint upload media | NOT IMPLEMENTED |
| FR-03 | Serial via OCR + VLM, disimpan sebagai hash bersalt | F-01 | `ai/pipeline/ocr.py`, `domain/passport.py` | OCR berupa regex atas teks masukan, tanpa gambar atau VLM; salt default di-hardcode di `config.py` | PARTIAL |
| FR-04 | Nonce kriptografis per paket | F-01 | `domain/nonce.py` | lib memakai `secrets` (64 bit); API `/challenge` mengembalikan `NONCE-RET-DEMO-1` statis | PARTIAL |
| FR-05 | Manifest ditandatangani Ed25519 dan masuk hash chain | F-01 | `domain/signing.py`, `domain/passport.py` | lib Ed25519 dan chain benar (statis; tes BLOCKED PyNaCl); API tidak menandatangani | PARTIAL |
| FR-06 | Grade asal dan checklist aksesori | F-01 | `api/app.py` | API menyimpan `origin_grade` (default A) tanpa checklist aksesori | PARTIAL |
| FR-07 | Tracking outbound ke order PayPal (ST-05) | F-01 | — | Tidak ada panggilan tracking; ST-05 tidak dijalankan | NOT IMPLEMENTED |
| FR-08 | Curve tampil di halaman produk dan saat mulai return | F-02 | `api/app.py`, `apps/` | Tidak ada UI; API menampilkan C 0,85 dan D 0,60, berbeda dari engine (0,80 dan 0,50) | FAIL |
| FR-09 | Snapshot curve per order, immutable | F-02 | `domain/order.py` | lib ada (statis); tidak ada endpoint pembelian, order di API berupa seed dict | PARTIAL |
| FR-10 | Engine menegakkan cap jurisdiksi | F-02 | `policy_engine/caps.py` | Resolver ada, tetapi `decide_release` menerima curve US C=0,50 yang melanggar cap (rt) | PARTIAL |
| FR-11 | Rubrik grade dengan gambar referensi | F-02 | — | Tidak ada UI maupun aset gambar | NOT IMPLEMENTED |
| FR-12 | Record deklarasi lengkap, termasuk timestamp dan actor | F-03 | `api/app.py` | Field inti tersimpan di memori; timestamp dan actor tidak ada; tanpa cek kepemilikan | PARTIAL |
| FR-13 | Bukti diskalakan menurut nilai dan risiko | F-03 | `policy_engine/evidence_requirements.py` | lib sesuai (statis); tidak dipakai API | PARTIAL |
| FR-14 | Syarat ditampilkan sebelum konfirmasi | F-03 | `api/app.py` | `fast_lane_terms_accepted` bernilai default `True` bila tidak dikirim | FAIL |
| FR-15 | Agen tidak menjanjikan hasil yang belum dihitung | F-03 | `ai/pipeline/output_guard.py` | Guard teks ada; intake agent tidak ada | PARTIAL |
| FR-16 | Blur wajah on-device sebelum upload | F-03 | `api/app.py`, `ops/drills.py` | Server hanya mempercayai flag kiriman klien (`client_blur_applied`) | FAIL |
| FR-17 | Alur ≤ 90 detik di mobile | F-03 | — | Tidak ada frontend | NOT IMPLEMENTED |
| FR-18 | `forensic_score` dan flag per layer | F-04 | `ai/pipeline/forensics.py` | Skor berbasis aturan dari flag masukan; tidak ada analisis media L1–L7 | PARTIAL |
| FR-19 | Hard failure memaksa ESCALATED | F-04 | `policy_engine/lanes.py` | lib benar (statis); API `/evidence` selalu FAST | PARTIAL |
| FR-20 | Red-team dijalankan setiap perubahan model | F-04 | `ai/pipeline/forensics.py` | 6 kasus sintetis atas flag; latensi 1,42 s di-hardcode; tidak ada `data/redteam` | FAIL |
| FR-21 | Hitung `p` per return (§8.6) | F-05 | `policy_engine/audit_probability.py` | rt: semua nilai `p` di peta §8.8 cocok; tidak dipanggil API | PARTIAL |
| FR-22 | Tranche refund ≤ 60 s setelah trigger | F-05 | `payments/client.py` | `refund_capture` adalah stub yang mengarang status COMPLETED; tidak ada workflow | NOT IMPLEMENTED |
| FR-23 | Settlement per §8.4 | F-05 | `policy_engine/settlement.py` | Aturan 2–6 ada (statis); gross yang belum dikonfirmasi langsung di-settle, bukan ESCALATED | PARTIAL |
| FR-24 | Tenggat holdback dan settlement per jurisdiksi | F-05 | `policy_engine/caps.py` | Data tenggat ada; tidak ada timer atau penegakan | PARTIAL |
| FR-25 | Gross misdeclaration butuh uji konformal dan reviewer | F-05 | `policy_engine/misdeclaration.py` | Logika AND benar; `settlement` default `excluded_at_alpha_accuse=True`; tidak ada uji konformal | PARTIAL |
| FR-26 | Selisih satu grade di-settle tanpa F dan tanpa perubahan status | F-05 | `misdeclaration.py`, `settlement.py` | lib benar (statis); tidak terhubung | PARTIAL |
| FR-27 | Decision record lengkap | F-05 | `domain/decision.py` | Builder dan chain ada; tidak dipersistenkan; API tidak membuat decision | PARTIAL |
| FR-28 | Top-up otomatis bila under-declare | F-05 | `settlement.py` | lib benar (statis); tanpa uji α\_route; tidak terhubung | PARTIAL |
| FR-29 | Checkpoint custody per interval | F-06 | `domain/custody.py` | rt: tes custody lulus; endpoint API hanya echo, tidak menyimpan | PARTIAL |
| FR-30 | Atribusi ke interval paling awal | F-06 | `domain/custody.py` | rt: lulus; tidak terhubung | PARTIAL |
| FR-31 | Liability hanya record, tanpa perpindahan dana | F-06 | `domain/custody.py` | rt: records-only; tidak ada import payments di custody | PASS |
| FR-32 | Klaim merchant butuh bukti setara | F-07 | `settlement.py` | Flag `has_merchant_evidence` ada tetapi default `True` | PARTIAL |
| FR-33 | Evidence pack otomatis saat dispute | F-07 | `domain/evidence_pack.py`, `api/app.py` | Tidak dipicu webhook; API mengisi pack dengan ID hardcode (`pass_demo_1`, `req_r0_22157`) | FAIL |
| FR-34 | Kirim bukti via Disputes API (ST-04) | F-07 | — | Tidak ada client Disputes | NOT IMPLEMENTED |
| FR-35 | Buyer mengunduh pack yang sama | F-07 | `api/app.py` | Endpoint ada, tetapi isi pack hardcode dan tanpa cek kepemilikan | FAIL |

### Functional requirements FR-36 – FR-70

| ID | Requirement (ringkas) | Ref | Lokasi implementasi | Bukti verifikasi | Status |
| --- | --- | --- | --- | --- | --- |
| FR-36 | Estimasi nilai pemulihan | F-08 | `ai/valuation/resale_model.py` | Rumus dan MAPE dihitung pada set kurasi di dalam kode | PARTIAL |
| FR-37 | Batas `k_max` dan harga ≤ (1−θ\_h)·k\_max | F-08 | `policy_engine/keep_offer.py` | lib benar (statis); API memakai harga hardcode 5320 | PARTIAL |
| FR-38 | Pilih disposisi terbaik, tabel perbandingan, CO2e | F-08 | `domain/disposition.py` | lib ada; tidak ada console | PARTIAL |
| FR-39 | Terima keep-offer menjalankan partial refund PayPal | F-08 | `api/app.py` | State menjadi KEEP\_ACCEPTED dengan pesan “refund initiated”, tanpa panggilan refund | FAIL |
| FR-40 | Listing open-box dengan grade, riwayat, media | F-09 | `api/app.py` | Listing hanya grade dan harga; tanpa timeline dan media | PARTIAL |
| FR-41 | Pembelian resale via Orders v2 CAPTURE | F-09 | — | Tidak ada panggilan PayPal; API langsung menandai SOLD | NOT IMPLEMENTED |
| FR-42 | Transfer Passport, data buyer lama dihapus | F-09 | `api/app.py` | `buyer_email` dihapus; pemilik baru diambil dari body siapa pun yang terautentikasi; tanpa entri chain | PARTIAL |
| FR-43 | View publik hanya fakta kondisi | F-09 | `api/app.py` | Denylist membuang `current_owner_ref` dan `buyer_email` (statis) | PASS |
| FR-44 | Publikasi JSON Schema 2020-12 | F-10 | `schemas/*.json` | Tiga skema ada dan valid sebagai JSON; validasi contoh BLOCKED (jsonschema) | PASS |
| FR-45 | Token agen scoped dan kedaluwarsa | F-10 | `api/app.py`, `agent_gateway/mcp_server.py` | Token berupa teks biasa tanpa tanda tangan dan tanpa kedaluwarsa; scope ditentukan sendiri oleh pemegang | FAIL |
| FR-46 | Keep-offer harga tunggal, batas tidak dibuka | F-10 | `keep_offer.py`, MCP | lib benar; API tidak memakai | PARTIAL |
| FR-47 | Aksi agen dicatat dengan `actor=agent` | F-10 | `agent_gateway/mcp_server.py` | Log in-memory di class MCP; API tidak mencatat | PARTIAL |
| FR-48 | Pemetaan ke konsep UCP | F-10 | `docs/ucp-mapping.md` | Dokumen ada; akurasi terhadap spesifikasi UCP tidak bisa dicek offline | NOT VERIFIED |
| FR-49 | KPI dashboard | F-11 | — | Tidak ada console | NOT IMPLEMENTED |
| FR-50 | Review queue, keputusan lewat Policy Engine | F-11 | `api/app.py` | Endpoint keputusan mengembalikan `via_policy_engine: True` tanpa memanggil engine dan tanpa cek tenant | FAIL |
| FR-51 | Policy editor dengan versi immutable | F-11 | `api/app.py` | `POST /v1/policies` hanya echo body tanpa validasi dan tanpa versi | FAIL |
| FR-52 | Simulator what-if | F-11 | `api/app.py` | `POST /v1/simulate` mengembalikan angka hardcode (`monthly_returns × 640`) | FAIL |
| FR-53 | Hash serial bersalt per merchant | F-12 | `domain/serial_registry.py` | HMAC berkunci (statis); tidak terhubung | PARTIAL |
| FR-54 | Deposit sewa AUTHORIZE, capture, void | F-13 | — | Tidak ada panggilan PayPal | NOT IMPLEMENTED |
| FR-55 | Sewa ≤ 3 hari sampai ST-03 | F-13 | `domain/sla_and_holds.py` | Validasi durasi ada; fitur sewa tidak ada | PARTIAL |
| FR-56 | Refund otomatis SLA pengiriman | F-14 | `domain/sla_and_holds.py` | Hanya kalkulasi kredit; tanpa tracking dan refund | PARTIAL |
| FR-57 | Trust tier per merchant dan grup identitas | F-05 | `domain/trust.py` | Logika ada; NEW bisa langsung naik ke TRUSTED; cap tier di-hardcode terpisah dari policy | PARTIAL |
| FR-58 | Matriks timing dan pengetatan | F-05 | `policy_engine/release.py` | rt: 30/30 timing cocok, X=0 diketatkan ke R2; tidak dipanggil API | PARTIAL |
| FR-59 | `F = max(S_return, φ·P)` per jurisdiksi | F-05 | `domain/policy.py` | rt: nilai F di peta cocok; jurisdiksi di-hardcode {EU, ID}; tidak ada pengungkapan ke shopper | PARTIAL |
| FR-60 | Floor tidak layak menjadi STANDARD dengan `p_std` | F-05 | `release.py` | rt: E5, E8, dan tabel sensitivitas cocok; tidak terhubung | PARTIAL |
| FR-61 | Audit draw commit–reveal | F-05 | `domain/audit_commitment.py`, `api/app.py` | lib benar (statis); API menampilkan commitment = SHA-256(“seed:” + nonce shopper) tanpa seed rahasia | FAIL |
| FR-62 | CUSUM account monitor | F-15 | `domain/account_monitor.py` | CUSUM benar (statis); downgrade dan review tidak terhubung | PARTIAL |
| FR-63 | Tier Passport per value band | F-01 | `api/app.py` | API: ≥ $150 menjadi FULL, < $150 menjadi LITE; SSOT: HIGH = FULL, MID = LITE, LOW = NONE | FAIL |
| FR-64 | Return seal, foto drop-off, cek berat | F-06 | `domain/return_seal.py` | lib ada; API hanya meng-hash nonce kiriman klien; seal tidak diterbitkan saat approval | PARTIAL |
| FR-65 | Nonce tak terbaca dibedakan dari mismatch | F-04 | `lanes.py`, `nonce_checker.py` | lib benar; tidak terhubung | PARTIAL |
| FR-66 | Batas retake | F-04 | `ai/pipeline/nonce_checker.py` | `RetakeTracker` ada; endpoint evidence tidak memakainya | PARTIAL |
| FR-67 | Non-serial: micro-feature, FAST maksimal MID | F-01 | `release.py` | rt: HIGH non-serial menjadi STANDARD; capture micro-feature tidak ada | PARTIAL |
| FR-68 | DEF elektronik butuh self-test | F-03 | `evidence_requirements.py`, `lanes.py` | lib benar; kategori elektronik di-hardcode dua nilai | PARTIAL |
| FR-69 | Banding: reviewer berbeda, keputusan kompensasi | F-15 | `api/app.py` | ID reviewer asal diambil dari body pengaju banding sehingga bisa dipalsukan; tanpa batas 14 hari; refund kompensasi tidak dijalankan | FAIL |
| FR-70 | RESTRICTED butuh konfirmasi manusia | F-15 | `trust.py`, `settlement.py` | Override hanya saat terkonfirmasi (statis); tidak terhubung | PARTIAL |

### Functional requirements FR-71 – FR-103

| ID | Requirement (ringkas) | Ref | Lokasi implementasi | Bukti verifikasi | Status |
| --- | --- | --- | --- | --- | --- |
| FR-71 | Jalur NOT\_RECEIVED | F-06 | `domain/return_state.py` | rt: transisi lulus; tidak ada timer dan restriksi akun | PARTIAL |
| FR-72 | Jalur LOST\_IN\_TRANSIT | F-06 | `return_state.py`, `custody.py` | rt: transisi lulus; tidak terhubung | PARTIAL |
| FR-73 | Diskrepansi check-in menjadi ESCALATED | F-06 | `return_state.py` | rt: transisi lulus; endpoint checkpoint tidak memicunya | PARTIAL |
| FR-74 | Lane NO\_PASSPORT | F-05 | `release.py` | rt: aturan timing benar; lane dilaporkan FAST karena ekspresi mati di baris 331 | PARTIAL |
| FR-75 | Dispute setelah refund: bekukan, reversal menjadi 0 | F-07 | `payments/ledger.py`, `webhooks.py` | lib benar (statis); endpoint webhook tidak memproses event | PARTIAL |
| FR-76 | Receipt bertanda tangan | F-07 | `domain/receipts.py`, `api/app.py` | lib Ed25519 benar; API mengembalikan string `ed25519:sig_intake_01` dengan `verified: true` | FAIL |
| FR-77 | Delivery receipt (P2) | F-07 | — | Tidak ada portal | NOT IMPLEMENTED |
| FR-78 | Aturan keep-offer harga tunggal | F-08 | `keep_offer.py` | lib benar (statis); API mengabaikan kelayakan | PARTIAL |
| FR-79 | Simulator: peta A/B, ablation, ROI | F-11 | `sim/fmap.py`, `sim/roi.py` | Endpoint peta dan ROI memanggil simulator; tanpa console dan tabel asumsi | PARTIAL |
| FR-80 | Judge mode replay berdasarkan SHA-256 | F-16 | `ai/pipeline/evaluator.py`, `api/app.py` | Tidak ada rekaman dari run nyata; API melabeli hasil hardcode sebagai REPLAYED | FAIL |
| FR-81 | Demo clock khusus staff dan tercatat | F-16 | `api/app.py` | Endpoint tanpa autentikasi dan tanpa log; offset tidak dipakai timer apa pun | FAIL |
| FR-82 | Crypto-shredding | F-01 | `domain/crypto_shred.py` | Stream XOR-SHA256 buatan sendiri tanpa autentikasi; API memakai data sintetis | PARTIAL |
| FR-83 | Anchoring RFC 3161 (P2) | F-01 | `jobs/anchor.py` | 20 baris, `TSA_URL` kosong, tidak ada token TSA | NOT IMPLEMENTED |
| FR-84 | Curve dan F dari tabel jurisdiksi | F-02 | `caps.py`, `domain/policy.py` | Resolver dan `default_eu` ada; storefront tidak ada | PARTIAL |
| FR-85 | Profil lite setara untuk J-01..J-04 | F-16 | `infra/docker-compose.yml` | Profil lite hanya menjalankan infrastruktur, tanpa aplikasi | FAIL |
| FR-86 | Teks dalam gambar diperlakukan sebagai data | F-04 | `ai/providers/gemini.py` | Belum direview mendalam; tidak ada set DS-04 | NOT VERIFIED |
| FR-87 | `X_max` closed form dan binding constraint | F-05 | `release.py` | rt: 180/180 cocok dengan §8.8; API selalu melaporkan 22157 | PARTIAL |
| FR-88 | Routing, batal gratis, re-file STANDARD | F-05 | `lanes.py`, `release.py` | rt: re-file menjadi STANDARD dengan X=0; tidak ada endpoint pembatalan | PARTIAL |
| FR-89 | Margin keamanan relatif μ | F-05 | `release.py` | rt: G pada X\_max sama dengan −m\_k di seluruh peta | PASS |
| FR-90 | Parameter policy bertipe, tanpa JSON bebas | F-05 | `domain/policy.py`, `db/schema.py` | Fraksi berupa string tanpa validasi; `promotion_rules_json` bebas; DDL memakai `config_json JSONB` | FAIL |
| FR-91 | Promosi berbobot nilai dan umur akun | F-05 | `domain/trust.py` | Ambang sesuai §8.7 (statis); lompatan tier dimungkinkan | PARTIAL |
| FR-92 | Cap akun dan cap agregat merchant | F-05 | `trust.py`, `release.py` | rt: cap mengikat di engine; tidak ada pelacakan exposure agregat | PARTIAL |
| FR-93 | Grup identitas dan batas velocity | F-05 | `domain/identity.py` | lib ada; salt default publik; tidak terhubung | PARTIAL |
| FR-94 | Fraud flag bertahan setelah penghapusan data | F-15 | `domain/fraud_flags.py` | lib ada; salt default di-hardcode | PARTIAL |
| FR-95 | Seed audit dengan nonce shopper | F-05 | `audit_commitment.py`, `api/app.py` | lib benar; commitment di API tanpa seed rahasia dan tanpa `return_id` | FAIL |
| FR-96 | Carrier event manual hanya saat DEMO\_MODE | F-06 | `api/app.py`, `config.py` | `app = create_app()` selalu `demo_mode=True`; endpoint tanpa autentikasi; guard settings hanya dipakai tes | FAIL |
| FR-97 | SLA ESCALATED dan rilis otomatis | F-15 | `return_state.py` | rt: transisi ada; tidak ada timer | PARTIAL |
| FR-98 | Baseline fungsional di origin | F-01 | `api/app.py` | `self_test_passed` default `True`, tanpa video maupun hash | FAIL |
| FR-99 | Bukti tak dikenal menjadi STANDARD/MANUAL | F-16 | `ai/pipeline/evaluator.py` | Label MANUAL ada di lib; API tidak memakai | PARTIAL |
| FR-100 | Kalibrasi pooled, persentil ke-5 | F-05 | `ai/calibration/pooling.py` | Fungsi ada; tidak ada data DS-02 | PARTIAL |
| FR-101 | Peta A/B, distribusi waktu-ke-uang, mix tier | F-11 | `sim/fmap.py` | Peta A/B ada; distribusi waktu dan mix tier tidak ditemukan | PARTIAL |
| FR-102 | Simulator berbasis aturan dan attacker best-response | F-11 | `sim/engine.py`, `sim/attacker.py` | Strategi substitusi, tidak mengirim, dan abandon tidak dienumerasi; state machine tidak dipakai | PARTIAL |
| FR-103 | Kalibrasi CUSUM per kategori | F-15 | `account_monitor.py` | Preset θ0 ada; tanpa kalibrasi DS-02 | PARTIAL |

### Non-functional requirements (§6.1)

| ID | Requirement (ringkas) | Lokasi implementasi | Bukti verifikasi | Status |
| --- | --- | --- | --- | --- |
| NFR-01 | Tranche ≤ 60 s p95 di Sandbox | — | Tidak ada refund ke PayPal | NOT IMPLEMENTED |
| NFR-02 | Latensi asesmen AI ≤ 20 s p95 | `forensics.py`, `api/app.py` | Tidak pernah diukur; angka 1,42 s di-hardcode | NOT VERIFIED |
| NFR-03 | Panggilan PayPal idempoten dan retry aman | `payments/client.py` | `create_order_live` mengirim `PayPal-Request-Id`; tidak ada logika retry; refund berupa stub | PARTIAL |
| NFR-04 | Signature webhook diverifikasi, diproses tepat sekali | `api/app.py`, `payments/webhooks.py` | “Verifikasi” berupa header klien `x-paypal-signature-valid` dengan default `true` | FAIL |
| NFR-05 | Retensi berbasis tujuan | `privacy/lifecycle.py`, `jobs/retention.py` | lib ada; endpoint penghapusan memakai data sintetis dan tanpa autentikasi | PARTIAL |
| NFR-06 | Shopper flow WCAG 2.2 AA | — | Tidak ada frontend | NOT IMPLEMENTED |
| NFR-07 | Demo lokal via `docker compose up` | `infra/docker-compose.yml` | Compose tidak memuat service aplikasi | FAIL |
| NFR-08 | Log terstruktur dengan ID kunci | `observability/` | Modul hanya di-import tes | PARTIAL |
| NFR-09 | Budget performa frontend di CI | — | Tidak ada frontend maupun CI | NOT IMPLEMENTED |
| NFR-10 | WCAG 2.2 AA untuk semua app | — | Tidak ada frontend | NOT IMPLEMENTED |
| NFR-11 | Isolasi tenant | `api/app.py` | Token bisa dipalsukan; endpoint mutasi tidak memeriksa tenant | FAIL |
| NFR-12 | Build reproducible | `uv.lock`, `infra/` | Lockfile dan versi runtime ada; image tidak di-pin digest (`minio:latest`) | PARTIAL |
| NFR-13 | Drill backup dan restore | `ops/drills.py` | RPO/RTO “simulated” dan `reconciliation_clean = True` di-hardcode | FAIL |
| NFR-14 | Rekonsiliasi mendeteksi selisih ≤ 10 menit | `payments/reconciliation.py` | Mengembalikan dict statis `passed: True` tanpa memeriksa apa pun | FAIL |
| NFR-15 | Judge mode CPU-only, setup ≤ 20 menit | `ops/drills.py` | `run_clean_env_judge_mode_check()` mengembalikan konstanta `True` | FAIL |
| NFR-16 | Biaya dan latensi per return dilaporkan | `api/app.py` | `/v1/simulate` memakai konstanta 0,00 dan 1,42 | FAIL |

### Invariants (§9)

| ID | Invariant (ringkas) | Lokasi implementasi | Bukti verifikasi | Status |
| --- | --- | --- | --- | --- |
| INV-01 | Total refund ≤ nilai capture | `payments/ledger.py`, `settlement.py` | Cek ledger in-memory benar (statis); tanpa DB constraint dan row lock | PARTIAL |
| INV-02 | Refund hanya ke capture milik merchant | `ledger.py` | Pemeriksaan merchant dan capture ada (statis); tidak terhubung | PARTIAL |
| INV-03 | Decision record dan `PayPal-Request-Id` unik | `ledger.py`, `client.py` | Request ID UUIDv5 deterministik; decision tidak dipersistenkan | PARTIAL |
| INV-04 | Transisi mengikuti state machine | `return_state.py`, `api/app.py` | rt: 4 tes state machine lulus; API menulis `ret["state"]` langsung tanpa guard | FAIL |
| INV-05 | Output model tidak memicu PayPal | `backend/ai` | Graf import: `ai` tidak meng-import `payments` (statis) | PASS |
| INV-06 | Setiap keputusan uang punya penjelasan | `release.py`, `settlement.py` | lib menghasilkan penjelasan; API tidak | PARTIAL |
| INV-07 | Non-custodial, tanpa Payouts | `payments/client.py` | Tidak ada kode payout atau transfer (statis) | PASS |
| INV-08 | Tanpa produk asuransi atau pooling | seluruh repo | Tidak ada tabel atau kode pooling (statis) | PASS |
| INV-09 | Event append-only dan hash-chained | `passport.py`, `decision.py`, `api/app.py` | lib chain benar; API `/verify` mengembalikan flag `chain_valid` tersimpan yang selalu `True` | FAIL |
| INV-10 | Status-affecting butuh uji dan konfirmasi manusia | `misdeclaration.py` | Logika benar; default `excluded_at_alpha_accuse=True`; tidak ada uji konformal | PARTIAL |
| INV-11 | Cap jurisdiksi ditegakkan | `caps.py`, `release.py` | rt: curve yang melanggar cap diterima engine; API policy tanpa validasi | FAIL |
| INV-12 | Agen tidak bisa capture fisik; token kedaluwarsa | `api/app.py` | Blokir hanya untuk token berawalan `agent:`; token bisa dipalsukan dan tidak kedaluwarsa | FAIL |
| INV-13 | Tanpa PII/serial di log; media di-blur | `api/app.py`, `config.py` | API tidak melakukan logging; blur bergantung pada flag klien; salt publik | PARTIAL |
| INV-14 | Rilis pra-check-in ≤ X\_max dan cap | `release.py`, `api/app.py` | rt: cap mengikat di engine; API melaporkan R0 22157 untuk return apa pun | FAIL |
| INV-15 | Tanpa penalti untuk selisih satu grade | `misdeclaration.py`, `settlement.py` | Tidak ada jalur penalti untuk adjacent (statis) | PASS |
| INV-16 | Commitment audit sebelum kirim, seed dibuka saat check-in | `api/app.py` | Commitment di API tanpa seed rahasia, bisa dihitung siapa pun | FAIL |
| INV-17 | Tanpa penalti dari routing, batal, atau re-file | `lanes.py`, `release.py` | rt: re-file menjadi STANDARD dengan X=0 tanpa penalti; alur pembatalan tidak ada | PARTIAL |
| INV-18 | Mode degradasi tidak menaikkan X | `release.py` | rt: 7 kode FB tidak pernah menaikkan X atau memajukan timing | PASS |

### Pola utama dari Fase 2

- **Fasad API.** Endpoint menulis state langsung dan mengembalikan nilai tetap, misalnya tranche R0 22157 untuk semua return dan `via_policy_engine: True` tanpa memanggil engine.
- **Mekanisme inti benar tetapi terisolasi.** `decide_release` cocok dengan seluruh angka §8.8, namun hanya dipanggil tes, simulator, dan `domain/journeys.py`.
- **Jalur uang ke PayPal tidak ada.** `refund_capture`, `capture_order`, dan `create_order` adalah stub yang mengarang status COMPLETED serta `paypal_debug_id`.
- **Artefak verifikasi yang dikarang.** `reconciliation.py`, drill backup dan clean-env, serta 5 dari 12 skenario CT dan 8 dari 20 mode FX mengembalikan hasil lulus yang di-hardcode.

## D. Architecture Compliance Report

Implementasi tidak mengikuti arsitektur yang didokumentasikan. SSOT §10 menggambarkan sistem berlapis dengan PostgreSQL, Temporal, object storage, empat aplikasi React, dan API yang mengorkestrasi Policy Engine. Yang ada adalah satu modul FastAPI dengan state di memori yang tidak memanggil pustaka domain, ditambah pustaka yang hanya dijalankan oleh tes. Tidak ditemukan siklus import (analisis SCC atas seluruh modul non-tes).

### Penyimpangan material

Severity di bawah bersifat indikatif; klasifikasi final ada di Bagian E.

| ID | Penyimpangan | Bukti | Severity indikatif |
| --- | --- | --- | --- |
| ARC-01 | API tidak memakai Policy Engine, state machine, payments, maupun MCP | `return_state` hanya dipakai `domain/journeys.py`; `settlement` hanya oleh `sim/engine.py`; `journeys.py` tidak dipakai kode non-tes | CRITICAL |
| ARC-02 | Integrasi uang ke PayPal tidak ada | Panggilan live hanya OAuth dan Orders v2 create; refund, capture, tracking, disputes, dan verify-webhook berupa stub atau tidak ada | CRITICAL |
| ARC-03 | Model autentikasi menyimpang dari API-04 | Token teks biasa yang bisa dipalsukan, bukan staff JWT, order token, agent token, dan service token | CRITICAL |
| ARC-04 | Tidak ada lapisan persistensi | Tanpa driver DB; state berupa dict di closure `create_app`; restart menghapus semua data | HIGH |
| ARC-05 | Workflow dan timer tidak ada | Tidak ada Temporal, job table, scheduler, atau background task; tenggat FR-24, FR-71, FR-97 tidak bisa berjalan | HIGH |
| ARC-06 | Tidak ada server ASGI | `uvicorn` tidak ada di `pyproject.toml`, `uv.lock`, maupun venv; Compose tidak punya service API | HIGH |
| ARC-07 | Frontend tidak ada | Empat fungsi render string; tanpa React, Vite, atau proses build | HIGH |
| ARC-08 | Kontrak API tidak berbasis Pydantic | Nol model Pydantic di API; ADR-001 dan API-11 tidak terpenuhi | HIGH |
| ARC-09 | Database tanpa RLS, migrasi, dan eksekusi DDL | Nol `ENABLE ROW LEVEL SECURITY`; tanpa Alembic; DDL hanya string Python | HIGH |
| ARC-10 | Konfigurasi tidak tersambung | `ProofReturnSettings` hanya dipakai tes; `app = create_app()` selalu `demo_mode=True` | MEDIUM |
| ARC-11 | Penyedia AI berganti tanpa Change Control | Gemini menggantikan Claude + grader open-weights (ADR-009); ADR-028 tanpa CR dan persetujuan | MEDIUM |
| ARC-12 | MCP bukan server | Class Python tanpa SDK dan transport (ADR-010) | MEDIUM |
| ARC-13 | Arah dependensi terbalik | `domain/journeys.py` meng-import `payments` dan `agent_gateway`; `config.py` meng-import `payments.client` | LOW |

### D.1 Komponen sistem (§10.2)

| Komponen | Spesifikasi | Kondisi aktual |
| --- | --- | --- |
| Empat aplikasi React | Storefront, portal, packing station, console | Fungsi TypeScript yang mengembalikan string |
| `api` | REST, auth, orkestrasi | Ada, tetapi tidak mengorkestrasi apa pun |
| `policy-engine` | Keputusan deterministik | Ada dan benar secara runtime, tetapi terisolasi dari API |
| `payments` | Client, idempotensi, ledger, webhook | Ledger in-memory; client berupa stub kecuali OAuth dan order create |
| `ai-workers` | Pipeline S1–S7, valuasi | Fungsi pustaka tanpa worker; tidak ada implementasi conformal |
| `workflows` | Lifecycle, timer, retry | Tidak ada |
| `agent-gateway` | MCP server dan token scoped | Class in-memory tanpa transport |
| `evidence-pack` | PDF/JSON | Fungsi pustaka; API mengisi data hardcode |

### D.2 Arsitektur backend

| Aspek | Temuan |
| --- | --- |
| Entry point | `app = create_app()` di `backend/api/app.py`; tidak ada server ASGI |
| Routing | 34 route di dalam satu fungsi; tidak ada `APIRouter` per domain seperti §10.3 |
| Lapisan layanan | Logika inline di handler; tidak memanggil domain atau Policy Engine |
| Akses data | Dict di closure; tanpa repository dan tanpa filter tenant terpusat (TZ-02) |
| Skema request | `await request.json()` lalu `dict.get(default)`; tanpa validasi tipe atau field wajib |
| Dependency injection | Tidak ada `Depends`; token di-parse manual di setiap handler |
| Middleware | Tidak ada; tanpa `X-Request-Id`, rate limit, atau CORS |
| Penanganan error | 19 pemanggilan `await request.json()` tanpa penanganan dan nol blok `try`; body bukan JSON berujung 500 (statis) |
| Fallback | `apply_fallback_degradation` tidak pernah dipanggil di luar tes |

### D.3 Arsitektur database

SSOT §10.4 mendefinisikan 36 tabel, sedangkan DDL di `backend/db/schema.py` berisi 20 tabel. Sebanyak 24 tabel SSOT tidak ada, termasuk `payment_actions`, `refund_tranches`, `audit_commitments`, `receipts`, `trust_profiles`, `release_decisions`, `merchant_exposure`, dan `identity_groups`. Delapan tabel DDL tidak dikenal SSOT, misalnya `refund_actions`, `staff_users`, dan `shopper_accounts`.

| Aturan §30 | Temuan di DDL |
| --- | --- |
| DB-01 kolom uang BIGINT + `currency` | 12 kolom BIGINT, hanya 1 kolom `currency` |
| DB-02 FK dengan `ON DELETE RESTRICT` | 30 FK, nol `ON DELETE RESTRICT` |
| DB-03 unique constraint | 4 UNIQUE, kurang dari daftar DB-03 |
| DB-07 kolom `version` | Tidak ada |
| ADR-012, TZ-02 Row-Level Security | Tidak ada `ENABLE ROW LEVEL SECURITY` maupun `CREATE POLICY` |
| FR-90, XR-09 kolom policy bertipe | `policies.config_json JSONB` |
| MG-01 Alembic | Tidak ada; `001_initial_schema.sql` hanya berisi komentar |

DDL tersebut tidak pernah dieksekusi karena tidak ada kode koneksi database.

### D.4 Arsitektur API

Dua endpoint wajib tidak ada: `POST /v1/agent/tokens` (penerbitan token agen, FR-45) dan `POST /v1/returns/{id}/cancel` (pembatalan, FR-88). Enam endpoint tidak dispesifikasikan: `/health`, `POST /passports`, `/passports/{id}/verify`, `/review/queue`, `/demo/reset`, dan `/privacy/deletion-requests`.

| Konvensi §28.1 | Status | Bukti |
| --- | --- | --- |
| API-01 base `/v1` | Sesuai | Semua route di bawah `/v1` |
| API-02 UUIDv7, RFC 3339 | Tidak | ID seperti `ret_created_01`, `app_01` |
| API-03 uang `{amount_minor, currency}` | Tidak | Field seperti `r0_tranche_minor` tanpa `currency` |
| API-04 jenis token | Tidak | Token teks biasa |
| API-05 di luar scope menjadi 404 | Sebagian | Hanya 3 endpoint memeriksa scope |
| API-06 `Idempotency-Key` | Tidak | 1 dari 21 endpoint POST |
| API-07 problem+json lengkap | Sebagian | Format RFC 9457 ada; `request_id` tidak ada; 9 dari 10 kode di luar katalog §28.2 |
| API-08 `If-Match` / `version` | Tidak | Tidak ada |
| API-10 `X-Request-Id` | Tidak | Tidak ada |
| API-11 OpenAPI dari Pydantic | Tidak | Tidak ada model request/response |

Matriks peran §29.2 tidak diterapkan. Peran `MERCHANT_OPERATOR` dan `RECEIVER` tidak pernah dirujuk. Checkpoint custody dan record audit menerima peran staff apa pun, termasuk PACKER. `/demo/reset` memakai nama peran huruf kecil dan header `X-Actor-Role`, sehingga token MERCHANT\_ADMIN yang sah justru ditolak.

### D.5 Arsitektur integrasi

| Integrasi | Kondisi |
| --- | --- |
| PayPal | Live hanya OAuth dan Orders v2 create, dipakai satu tes Sandbox; refund dan capture mengembalikan COMPLETED palsu; tidak ada outbox sweeper |
| Webhook PayPal | Tidak ada panggilan verify-webhook-signature; endpoint hanya echo |
| Gemini | Dipanggil `ai/pipeline/evaluator.py` bila ada key; tidak ada di jalur API |
| Worker lokal di `config/models.yaml` | DINOv2, PaddleOCR, LightGBM dirujuk tetapi tidak ada kodenya |
| Antrean dan timer | Tidak ada |

### D.6 Kepatuhan ADR

| ADR | Keputusan | Kondisi di kode |
| --- | --- | --- |
| ADR-001 | FastAPI + Pydantic v2 | FastAPI ada; Pydantic hanya untuk `PolicyConfig` dan settings |
| ADR-002 | Monorepo React + Vite, 4 app | Tidak |
| ADR-003 | Temporal (Proposed) | Tidak ada, termasuk fallback job table |
| ADR-004 | Minor unit + Fraction | Ya, diverifikasi runtime di Policy Engine |
| ADR-005 | Non-custodial, allow-list | Ya, tanpa Payouts |
| ADR-006 | Outbox + request ID deterministik | Sebagian: UUIDv5 dan ledger in-memory, tanpa sweeper |
| ADR-007 | Policy Engine terpisah dari AI | Ya di level pustaka |
| ADR-009 | Claude + grader open-weights | Diganti Gemini tanpa CR |
| ADR-010 | MCP server | Tidak |
| ADR-011 | Challenge-response primer | Tidak; nonce statis |
| ADR-012 | PostgreSQL RLS | Tidak |
| ADR-017 | Conformal Mondrian satu sisi | Tidak ada implementasi conformal |
| ADR-018, ADR-026 | Commit–reveal dan receipt | Pustaka ya; API memalsukan |
| ADR-019 | Crypto-shredding | Sebagian; cipher buatan sendiri |
| ADR-021 | Judge mode dengan rekaman | Daftar hash fixture hardcode, tanpa rekaman nyata |
| ADR-023, ADR-024 | Routing + `X_max`, margin relatif | Ya, diverifikasi runtime |

### D.7 Konsistensi lintas modul (Fase 8)

Kontrak yang dipublikasikan, API, domain, DB, frontend, dan konfigurasi memakai definisi yang berbeda untuk konsep yang sama. Hanya penamaan state yang konsisten.

| Pasangan yang dicek | Konsisten? | Bukti |
| --- | --- | --- |
| SSOT ↔ implementasi | Tidak | Bagian C: 9 PASS dari 137 |
| Arsitektur ↔ batas modul | Tidak | ARC-01..ARC-13 |
| JSON Schema ↔ API | Tidak | `return-declaration.v1` mewajibkan `consent_fast_lane_terms`, `nonce_shopper`, dan `actor`; API membaca `fast_lane_terms_accepted` (default `true`) tanpa `actor`. Passport dari API tidak memiliki `signature`, `signing_key_id`, dan `events` yang diwajibkan skema (AUD-40) |
| Kontrak §28 ↔ perilaku API | Tidak | 2 endpoint hilang, 9 dari 10 kode error di luar katalog, idempotensi hanya di 1 dari 21 endpoint POST (D.4) |
| DDL ↔ migrasi ↔ domain | Tidak | Migrasi kosong; `refund_actions` tanpa `merchant_id`, `capture_id`, `paypal_debug_id`, dan `attempt_count`; kolom status tanpa CHECK, sedangkan ledger memakai 5 status (AUD-42) |
| Nama state API ↔ state machine | Ya, untuk nama | Ketujuh state yang ditulis API dikenal state machine, tetapi transisinya tidak lewat guard (AUD-05) |
| Enum tier Passport | Tidak | API: FULL/LITE; `domain/passport_tier.py`: FULL/LITE/NONE; packing station: FULL/LIGHT/ORIGIN\_WITNESSED |
| Curve refund | Tidak | API, MCP, dan storefront: 0,85/0,60; engine: 0,80/0,50 (AUD-10) |
| Autentikasi ↔ otorisasi | Tidak | MCP memeriksa scope `read_policy`, `declare`, dan `keep_offer`; REST API tidak memeriksa scope sama sekali (AUD-41); nama peran huruf besar vs kecil (AUD-25) |
| Frontend ↔ backend | Tidak ada kontrak | `packages/api-client` tidak memuat satu pun path `/v1` |
| Tes ↔ perilaku | Sebagian | Tes mengunci nilai hardcode (AUD-33); bug lolos (AUD-36) |
| Konfigurasi ↔ deployment | Tidak | 15 kunci `.env.example` tidak dibaca aplikasi, termasuk `ALPHA_ACCUSE`, `EXPOSURE_CAPS`, dan `VALUE_BANDS`; nama model berbeda di 4 tempat (DOC-06); Compose tanpa service aplikasi |
| Skema hash serial | Tidak | `passport.hash_serial` memakai SHA-256 bersalt, `serial_registry` memakai HMAC berkunci |
| Dokumentasi ↔ kode | Tidak | `make up` di README tidak menjalankan aplikasi; gate record berbeda dari §27 (DOC-01); respons token MCP memuat `expires_at` tetap `2026-11-01T00:00:00Z` yang tidak pernah diperiksa |

**Cacat integrasi yang hanya terlihat lintas modul:**

1. **Dua sumber data order yang tidak sinkron.** API menyimpan order di dict `orders`, sedangkan `WebhookProcessor` membutuhkan order yang terdaftar di `RefundLedger`. Karena API tidak pernah mendaftarkan order ke ledger, setiap event dispute akan crash dengan `KeyError` begitu webhook disambungkan (AUD-12).
2. **Scope agen bisa dilewati.** Token dengan format yang sama diterima REST API tanpa pemeriksaan scope, sehingga pembatasan di MCP tidak berarti (AUD-41).
3. **Semantik persetujuan hilang.** Agen yang mengikuti skema mengirim `consent_fast_lane_terms`, yang diabaikan API; API lalu menganggap persetujuan diberikan secara default (AUD-40, AUD-04).
4. **Curve yang dijanjikan berbeda dari yang dihitung.** Angka refund di API dan MCP tidak cocok dengan keputusan engine (AUD-10).

## E. Technical Findings

Fase 4–8 menghasilkan 42 temuan: 3 CRITICAL, 9 HIGH, 20 MEDIUM, 8 LOW, dan 2 INFORMATIONAL. AUD-01 sampai AUD-20 berasal dari audit backend (Fase 4), AUD-21 sampai AUD-32 dari audit keamanan (Fase 5), AUD-33 sampai AUD-36 dari audit testing (Fase 6), AUD-37 sampai AUD-39 dari audit reliability (Fase 7), dan AUD-40 sampai AUD-42 dari audit konsistensi (Fase 8). Bukti bertanda rt diverifikasi runtime di salinan kerja dengan harness audit.

| ID | Severity | Kategori | Judul |
| --- | --- | --- | --- |
| AUD-01 | CRITICAL | Functional | Endpoint API mengembalikan hasil karangan dan melewati Policy Engine |
| AUD-02 | CRITICAL | Functional | Panggilan uang PayPal berupa stub yang mengarang status sukses |
| AUD-03 | HIGH | Testing | Artefak verifikasi di-hardcode lulus |
| AUD-04 | HIGH | Functional | API tanpa validasi input; field yang hilang diisi nilai permisif |
| AUD-05 | HIGH | Functional | API mengubah state return tanpa state machine |
| AUD-06 | HIGH | Reliability | Semua state hanya di memori proses |
| AUD-07 | HIGH | Reliability | Aplikasi tidak bisa dijalankan dengan dependensi yang dideklarasikan |
| AUD-08 | MEDIUM | Functional | Gross mismatch di-settle tanpa review manusia |
| AUD-09 | MEDIUM | Functional | Default tidak aman pada input settlement |
| AUD-10 | MEDIUM | Functional | Refund curve yang ditampilkan berbeda dari yang dihitung engine |
| AUD-11 | MEDIUM | Reliability | Ledger refund tidak atomik |
| AUD-12 | MEDIUM | Reliability | Webhook ditandai sudah diproses sebelum berhasil |
| AUD-13 | MEDIUM | Functional | Promosi trust bisa melompat dari NEW ke TRUSTED |
| AUD-14 | MEDIUM | Architecture | Konfigurasi tidak tersambung ke aplikasi |
| AUD-15 | MEDIUM | Reliability | Proteksi mode degradasi tidak pernah dipanggil |
| AUD-16 | LOW | Architecture | Konstanta bisnis terduplikasi |
| AUD-17 | LOW | Functional | Lane NO\_PASSPORT dilaporkan sebagai FAST |
| AUD-18 | LOW | Functional | Re-plan tranche dengan jumlah berbeda tidak ditolak |
| AUD-19 | LOW | Architecture | Dependensi runtime yang hanya dipakai tes |
| AUD-20 | INFORMATIONAL | — | Kekuatan implementasi yang terverifikasi |

| ID | Severity | Kategori | Judul (Fase 5) |
| --- | --- | --- | --- |
| AUD-21 | CRITICAL | Security | Autentikasi dapat dipalsukan |
| AUD-22 | HIGH | Security | Broken object-level authorization pada return, passport, dan listing |
| AUD-23 | HIGH | Security | Kredensial berformat asli ikut dalam arsip proyek |
| AUD-24 | HIGH | Security | Verifikasi signature webhook bisa dilewati lewat header klien |
| AUD-25 | MEDIUM | Security | Endpoint operasional tanpa autentikasi; otorisasi terbalik di demo reset |
| AUD-26 | MEDIUM | Security | Salt, kunci HMAC, dan seed penandatangan di-hardcode |
| AUD-27 | MEDIUM | Security | Cipher buatan sendiri tanpa autentikasi untuk crypto-shredding |
| AUD-28 | MEDIUM | Security | Indikator integritas dan privasi tanpa dasar kriptografi |
| AUD-29 | MEDIUM | Security | Independensi reviewer banding bisa dilewati |
| AUD-30 | LOW | Security | Tanpa rate limiting dan batas ukuran body |
| AUD-31 | LOW | Security | Kredensial default pengembangan di Compose dan template |
| AUD-32 | INFORMATIONAL | Security | Kontrol keamanan yang sudah baik |

| ID | Severity | Kategori | Judul (Fase 6) |
| --- | --- | --- | --- |
| AUD-33 | MEDIUM | Testing | Tes mengunci nilai hardcode dan deviasi spesifikasi |
| AUD-34 | HIGH | Testing | Jenis bukti integrasi, E2E, konkurensi, dan keamanan negatif tidak ada |
| AUD-35 | MEDIUM | Testing | Tes live berjalan otomatis bila kredensial tersedia |
| AUD-36 | MEDIUM | Testing | Celah kasus batas dan negatif membuat bug lolos |

| ID | Severity | Kategori | Judul (Fase 7) |
| --- | --- | --- | --- |
| AUD-37 | MEDIUM | Reliability | Tidak ada observability di jalur runtime |
| AUD-38 | MEDIUM | Reliability | Tidak ada pipeline CI dan artefak deployment |
| AUD-39 | LOW | Reliability | State in-memory tumbuh tanpa batas |

| ID | Severity | Kategori | Judul (Fase 8) |
| --- | --- | --- | --- |
| AUD-40 | MEDIUM | Functional | JSON Schema yang dipublikasikan tidak cocok dengan API |
| AUD-41 | MEDIUM | Security | Scope agen ditegakkan di MCP tetapi tidak di REST API |
| AUD-42 | LOW | Architecture | Drift konfigurasi, enum, dan model data antarmodul |

### CRITICAL

#### AUD-01 · CRITICAL · Functional — Endpoint API mengembalikan hasil karangan dan melewati Policy Engine

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 551–590 (`r0_tranche_minor: 22157` di baris 587), 185–204, 315–353, 617–644, 680–712, 271–297 |
| Bukti | `POST /evidence` selalu mengembalikan lane FAST, timing R0, dan tranche 22157 untuk return apa pun. `POST /review/{id}/decision` mengembalikan `via_policy_engine: True` tanpa memanggil engine. `POST /returns` selalu memberi ID `ret_created_01`. Receipt memakai tanda tangan berupa string tetap. |
| Penjelasan | Tidak satu pun handler meng-import `policy_engine`, `return_state`, atau `payments`. Angka 22157 adalah contoh E1 di SSOT §8.8. |
| Dampak | Merchant, shopper, dan juri melihat keputusan uang yang tidak pernah dihitung. INV-04, INV-06, INV-14, dan FR-50 tidak terpenuhi di sistem yang berjalan. |
| Rekomendasi | Bangun lapisan layanan yang memanggil `decide_release`, `ReturnStateMachine.apply`, dan ledger; hapus semua konstanta respons; tambahkan contract test per endpoint. |
| Confidence | High |

#### AUD-02 · CRITICAL · Functional — Panggilan uang PayPal berupa stub yang mengarang status sukses

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/client.py`: 101–138 |
| Bukti | `create_order`, `capture_order`, dan `refund_capture` mengembalikan dict literal berstatus CREATED atau COMPLETED, dengan ID `REF-…` dan `paypal_debug_id` `dbg_…`. Hanya `fetch_oauth_token` dan `create_order_live` yang melakukan HTTP. |
| Penjelasan | Tidak ada endpoint refund PayPal di kode, padahal docstring mengklaim INV-01 sampai INV-03. |
| Dampak | Inti produk, yaitu partial refund bertahap via PayPal, tidak ada. Bila disambungkan apa adanya, ledger akan mencatat konfirmasi palsu lengkap dengan debug ID karangan. |
| Rekomendasi | Implementasikan capture dan refund nyata dengan `PayPal-Request-Id` dan persistensi respons; pindahkan stub menjadi test double yang hanya ada di tes; jalankan ST-01 sesuai definisinya. |
| Confidence | High |

#### AUD-21 · CRITICAL · Security — Autentikasi dapat dipalsukan

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 28–44 (`_parse_bearer`); `backend/agent_gateway/mcp_server.py`: 16–37 |
| Bukti | rt (fungsi diekstrak via AST dan dijalankan): `Bearer staff:merch_b:MERCHANT_ADMIN` menghasilkan principal staff merch\_b berperan MERCHANT\_ADMIN. MCP menerima token agen buatan sendiri dengan scope apa pun. Tidak ada secret, tanda tangan, kedaluwarsa, maupun revocation. |
| Penjelasan | Identitas, tenant, peran, dan scope diambil langsung dari string kiriman klien. Ini melanggar API-04, TZ-01, TZ-06, FR-45, dan INV-12. |
| Skenario eksploitasi | Penyerang mengirim `Authorization: Bearer staff:<merchant target>:REVIEWER` ke `POST /v1/review/{id}/decision`, atau `staff:<merchant>:MERCHANT_ADMIN` ke `POST /v1/policies`. Agen jahat menambahkan scope sendiri ke tokennya. |
| Dampak | Pengambilalihan penuh peran staff di tenant mana pun; isolasi tenant (NFR-11) tidak bermakna. |
| Rekomendasi | Token bertanda tangan (JWT atau PASETO) dengan secret server, klaim tenant, peran, dan scope, `exp`, serta revocation; implementasikan `POST /v1/agent/tokens` sesuai §28.3; validasi terpusat lewat dependency FastAPI. |
| Confidence | High |

### HIGH

#### AUD-03 · HIGH · Testing — Artefak verifikasi di-hardcode lulus

| Atribut | Detail |
| --- | --- |
| Lokasi | `payments/reconciliation.py`: 8–35; `ops/drills.py`: 70–92; `domain/return_state.py`: 396–421, 481–489; `payments/failures.py`: 42–85; `ai/pipeline/forensics.py`: 95–99 |
| Bukti | Rekonsiliasi mengembalikan `passed: True` statis. `run_clean_env_judge_mode_check()` mengembalikan konstanta. CT-03 memakai `outbox_locked = True`. 8 dari 20 mode FX jatuh ke `handled: True`. Latensi red-team 1,42 s di-hardcode. |
| Penjelasan | Fungsi-fungsi ini dipanggil tes, lalu hasilnya dijadikan dasar status VERIFIED di `rtm.csv` dan gate record. |
| Dampak | Klaim NFR-13, NFR-14, NFR-15, CT-01..CT-12, FX-01..FX-20, dan FR-20 tidak berdasar. Keputusan rilis bisa diambil atas jaminan palsu. |
| Rekomendasi | Hapus atau ganti dengan pemeriksaan nyata atas data ledger dan DB; turunkan status RTM terkait menjadi SPECIFIED sampai ada bukti. |
| Confidence | High |

#### AUD-04 · HIGH · Functional — API tanpa validasi input; field yang hilang diisi nilai permisif

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 536 dan 544 (`fast_lane_terms_accepted` default `True`), 238 dan 516 (`self_test_passed` default `True`), 573 (`client_blur_applied` default `True`), 813 (`outcome` default `OVERTURNED`) |
| Bukti | 19 handler memakai `await request.json()` lalu `dict.get(default)`; nol model Pydantic; nol exception handler. |
| Penjelasan | Persetujuan, hasil self-test, dan blur dianggap terpenuhi bila klien tidak mengirim field. Body yang bukan JSON memicu exception tak tertangani (500). |
| Dampak | Persetujuan Fast Lane (FR-14) dan kontrol privasi (FR-16) terlewati tanpa disadari; kontrak API tidak bisa diuji; kode error tidak konsisten. |
| Rekomendasi | Model request Pydantic dengan field wajib tanpa default permisif; respons 422 `VALIDATION_FAILED` sesuai §28.2; exception handler global. |
| Confidence | High |

#### AUD-05 · HIGH · Functional — API mengubah state return tanpa state machine

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 548, 578, 605, 697, 708 |
| Bukti | Handler menulis `ret["state"]` langsung (DECLARED, ASSESSED, AWAITING\_SHIPMENT, KEEP\_ACCEPTED, APPROVED) tanpa memeriksa state awal. |
| Penjelasan | `ReturnStateMachine`, yang lulus 4/4 tes, hanya dipakai `domain/journeys.py`. |
| Dampak | Return yang sudah ESCALATED atau SETTLED bisa dikembalikan ke DECLARED atau KEEP\_ACCEPTED; INV-04 dilanggar. |
| Rekomendasi | Alirkan semua transisi lewat `ReturnStateMachine.apply` dengan guard; tolak dengan 409 `INVALID_STATE_TRANSITION`. |
| Confidence | High |

#### AUD-06 · HIGH · Reliability — Semua state hanya di memori proses

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 52–102 dan 477–479; `backend/payments/ledger.py` |
| Bukti | Order, return, passport, cache idempotensi, banding, dan listing disimpan di dict closure `create_app`; tidak ada driver DB. |
| Penjelasan | ID banding dan listing dibuat dengan `len(store) + 1` (baris 766 dan 836), sehingga bisa bentrok saat request konkuren. |
| Dampak | Restart menghapus semua data; dua worker memiliki state berbeda; idempotensi tidak berlaku lintas proses; constraint DB untuk INV-01 dan INV-09 tidak pernah aktif. |
| Rekomendasi | Repository PostgreSQL sesuai §10.4 dan §30 dengan Alembic; ID UUIDv7. |
| Confidence | High |

#### AUD-07 · HIGH · Reliability — Aplikasi tidak bisa dijalankan dengan dependensi yang dideklarasikan

| Atribut | Detail |
| --- | --- |
| Lokasi | `pyproject.toml`, `uv.lock`, `infra/docker-compose.yml`, `Makefile` |
| Bukti | `uv.lock` tidak memuat `uvicorn` atau server ASGI lain, driver DB, client Temporal, client S3, maupun SDK MCP. Compose hanya berisi infrastruktur. |
| Penjelasan | `make up` menyalakan Postgres, Redis, MinIO, dan Temporal, tetapi tidak ada proses yang menjalankan `app`. |
| Dampak | NFR-07 dan FR-85 tidak terpenuhi; Quick Start di README tidak menghasilkan aplikasi yang berjalan. |
| Rekomendasi | Tambahkan server ASGI dan service API di Compose; deklarasikan dependensi persistensi dan workflow saat diimplementasikan. |
| Confidence | High |

#### AUD-22 · HIGH · Security — Broken object-level authorization pada return, passport, dan listing

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 109–128 (GET return), 149–166 (challenge), 523–549, 551–590, 592–615, 617–644, 646–678, 680–712, 847–873 (resale order) |
| Bukti | GET return hanya memeriksa kind staff, shopper, dan agent. Tanpa header Authorization (kind anonymous) atau dengan `Bearer x` (kind invalid), record dikembalikan utuh: `return_id`, `order_id`, `merchant_id`, `shopper_id`, `state`. Endpoint mutasi hanya menolak kind anonymous atau agent, tanpa cek kepemilikan. |
| Penjelasan | Otorisasi berpola daftar tolak per jenis principal, bukan default deny per resource. |
| Skenario eksploitasi | Siapa pun mengirim `Bearer x` ke `POST /v1/returns/{id}/keep-offer/respond` milik orang lain sehingga state menjadi KEEP\_ACCEPTED. Atau ke `POST /v1/resale/listings/{id}/order` dengan `new_owner_ref` miliknya sehingga Passport berpindah pemilik. |
| Dampak | Pembacaan data return tanpa autentikasi; manipulasi state dan kepemilikan Passport lintas pengguna (TM-05). |
| Rekomendasi | Default deny; fungsi otorisasi per resource yang memeriksa tenant dan pemilik untuk setiap jenis principal; 404 untuk resource di luar scope; tes AZ-01 sampai AZ-10 yang nyata. |
| Confidence | High |

#### AUD-23 · HIGH · Security — Kredensial berformat asli ikut dalam arsip proyek

| Atribut | Detail |
| --- | --- |
| Lokasi | `.env` di root arsip (dikecualikan `.gitignore`, tetapi ikut dalam zip) |
| Bukti | `GEMINI_API_KEY` cocok dengan format Google API key. `PAYPAL_CLIENT_ID` dan `PAYPAL_CLIENT_SECRET` cocok dengan format kredensial REST PayPal untuk host Sandbox; ada juga `PAYPAL_WEBHOOK_ID`. Nilai tidak dikutip di laporan ini. |
| Penjelasan | TM-12 mensyaratkan secret hanya di environment dan dirotasi sebelum repo publik. Arsip ini sudah dibagikan ke pihak ketiga, yaitu auditor. |
| Skenario eksploitasi | Penerima zip memakai key Gemini atas kuota atau biaya pemilik, dan memakai aplikasi PayPal Sandbox untuk membuat order atau membaca data Sandbox. |
| Dampak | Penyalahgunaan kuota dan biaya API; akses ke akun developer Sandbox. |
| Rekomendasi | Rotasi key Gemini dan kredensial aplikasi PayPal Sandbox sekarang; keluarkan `.env` dari arsip; pasang secret scanning di CI. |
| Confidence | High |

#### AUD-24 · HIGH · Security — Verifikasi signature webhook bisa dilewati lewat header klien

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 299–313; `backend/payments/webhooks.py` (parameter `signature_valid`) |
| Bukti | Handler membaca header `x-paypal-signature-valid` dengan default `"true"`; tidak ada panggilan verify-webhook-signature; `WebhookProcessor` mempercayai `signature_valid` dari pemanggil. |
| Penjelasan | Keputusan keaslian event diserahkan kepada pengirim event itu sendiri. |
| Skenario eksploitasi | Penyerang mengirim event `CUSTOMER.DISPUTE.CREATED` atau reversal palsu. Begitu handler disambungkan ke `WebhookProcessor`, order bisa dibekukan atau sisa refundable dinolkan. |
| Dampak | Saat ini handler hanya mengembalikan echo, tetapi kontrol keamanannya palsu (TM-06, NFR-04, AZ-08). |
| Rekomendasi | Verifikasi lewat `POST /v1/notifications/verify-webhook-signature` dengan `PAYPAL_WEBHOOK_ID`; tolak dengan 400 bila gagal; jangan pernah mempercayai header dari klien. |
| Confidence | High |

#### AUD-34 · HIGH · Testing — Jenis bukti integrasi, E2E, konkurensi, dan keamanan negatif tidak ada

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/tests/` (11 file, 71 tes); `docs/rtm.csv` |
| Bukti | Nol tes terhadap Postgres, Temporal, atau MinIO nyata; nol Playwright; nol tes aksesibilitas atau budget performa; CT-01..CT-12 tanpa thread atau lock; tidak ada tes token palsu atau akses lintas pemilik pada endpoint mutasi. |
| Penjelasan | `rtm.csv` mengklaim bukti I, E, A, dan S untuk banyak baris VERIFIED, padahal jenis tes itu tidak ada di repo. |
| Dampak | Status VERIFIED tidak berdasar; kelas bug paling berbahaya (race uang, BOLA, autentikasi) tidak bisa terdeteksi oleh suite ini. |
| Rekomendasi | Tambahkan tes integrasi dengan DB nyata termasuk konkurensi INV-01, tes otorisasi negatif AZ-01..AZ-10, Playwright untuk J-01..J-14, dan jalankan ST-01 di Sandbox. |
| Confidence | High |

### MEDIUM

#### AUD-08 · MEDIUM · Functional — Gross mismatch di-settle tanpa review manusia

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/policy_engine/settlement.py`: 90 |
| Bukti | rt: deklarasi B dan verifikasi D tanpa konfirmasi reviewer menghasilkan `final_total_refund_minor` 22157 dengan penjelasan “reviewer confirmation not recorded”. |
| Penjelasan | §8.4 Rule 5 dan FR-73 mewajibkan pembekuan tranche dan ESCALATED sampai review. Fungsi ini justru langsung menetapkan refund pada grade versi merchant. |
| Dampak | Sisa refund dan holdback shopper ditahan berdasarkan grade yang belum direview. |
| Rekomendasi | Kembalikan hasil `ESCALATE` atau `HOLD` tanpa angka final sampai state REVIEWED. |
| Confidence | High |

#### AUD-09 · MEDIUM · Functional — Default tidak aman pada input settlement

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/policy_engine/settlement.py`: 22 (`excluded_at_alpha_accuse=True`), 24 (`has_merchant_evidence=True`) |
| Bukti | rt: reviewer mengonfirmasi tanpa mengirim hasil uji konformal, dan hasilnya F 2000 serta tier RESTRICTED. |
| Penjelasan | INV-10 mensyaratkan uji konformal atau hard failure DAN konfirmasi manusia. Repo tidak memiliki implementasi konformal sama sekali. |
| Dampak | Penalti status bisa dijatuhkan hanya dengan konfirmasi manusia; klaim merchant dianggap berbukti secara default (FR-32). |
| Rekomendasi | Jadikan kedua field wajib tanpa default, atau default ke nilai protektif `False`; implementasikan uji konformal (ADR-017). |
| Confidence | High |

#### AUD-10 · MEDIUM · Functional — Refund curve yang ditampilkan berbeda dari yang dihitung engine

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 145 dan 486; `backend/agent_gateway/mcp_server.py`: 57; `apps/demo-storefront/src/App.tsx` |
| Bukti | API dan MCP mengembalikan C 0,85 dan D 0,60, sedangkan Policy Engine memakai C 0,80 dan D 0,50 dari `config/policy_defaults.json`. |
| Penjelasan | Tidak ada sumber tunggal untuk curve yang di-snapshot per order (FR-09). |
| Dampak | Shopper dan agen AI diberi angka refund yang berbeda dari keputusan aktual; transparansi INV-06 dan FR-08 terlanggar. |
| Rekomendasi | Sajikan curve dari snapshot order yang sama dengan input engine. |
| Confidence | High |

#### AUD-11 · MEDIUM · Reliability — Ledger refund tidak atomik

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/ledger.py`: 104–151 |
| Bukti | rt: dua thread masing-masing merencanakan 30000 pada capture 40000 dan keduanya diterima, total 60000. Harness memperlebar jeda antara cek dan insert dengan subclass. |
| Penjelasan | `plan_refund_action` memeriksa sisa refundable lalu menyisipkan aksi tanpa lock (check-then-act). |
| Dampak | Bila dipakai handler sinkron FastAPI (threadpool) atau multi-worker, INV-01 bisa dilanggar. |
| Rekomendasi | Row lock `SELECT … FOR UPDATE` sesuai §24.3 dan CHECK constraint DB; sementara itu lock per order. |
| Confidence | Medium |

#### AUD-12 · MEDIUM · Reliability — Webhook ditandai sudah diproses sebelum berhasil

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/webhooks.py`: 40–46 |
| Bukti | rt: event dispute untuk order yang belum terdaftar melempar `KeyError`. Karena `event_id` sudah masuk `_seen_event_ids` di baris 40, kiriman ulang dari PayPal akan dianggap duplikat. |
| Penjelasan | Deduplikasi dicatat sebelum efek samping selesai. |
| Dampak | Pembekuan dispute (FR-75, FX-10) bisa hilang permanen setelah satu kegagalan pemrosesan. |
| Rekomendasi | Catat `event_id` secara atomik bersama efek sampingnya; tangani order tak dikenal secara eksplisit. |
| Confidence | High |

#### AUD-13 · MEDIUM · Functional — Promosi trust bisa melompat dari NEW ke TRUSTED

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/domain/trust.py`: 47–90 |
| Bukti | rt: profil NEW dengan 5 return bersih, nilai $750, dan umur 90 hari langsung menjadi TRUSTED. |
| Penjelasan | Kriteria TRUSTED dievaluasi tanpa melihat tier saat ini, padahal §8.7 hanya mengizinkan ESTABLISHED ke TRUSTED. |
| Dampak | Cap exposure naik dari $0 ke $1.000 tanpa melewati ESTABLISHED. |
| Rekomendasi | Evaluasi promosi satu tingkat dari tier saat ini. |
| Confidence | High |

#### AUD-14 · MEDIUM · Architecture — Konfigurasi tidak tersambung ke aplikasi

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py` (`create_app(demo_mode=True)`, `app = create_app()`); `backend/config.py`; `backend/ai/pipeline/evaluator.py`: 74 |
| Bukti | `ProofReturnSettings` hanya dipakai tes; evaluator membaca `GEMINI_API_KEY` langsung dari environment; `.env` dibaca relatif terhadap direktori kerja. |
| Penjelasan | Guard TM-16 dan TM-24 serta parameter policy tidak pernah memengaruhi aplikasi yang berjalan. |
| Dampak | Mode demo selalu aktif pada objek `app`; konfigurasi produksi tidak bisa diterapkan. |
| Rekomendasi | Injeksi settings ke `create_app`; default `demo_mode=False`; satu jalur pembacaan secret. |
| Confidence | High |

#### AUD-15 · MEDIUM · Reliability — Proteksi mode degradasi tidak pernah dipanggil

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/policy_engine/release.py` (`apply_fallback_degradation`) |
| Bukti | Tidak ada pemanggil di kode non-tes; tidak ada deteksi dependensi gagal maupun respons `SERVICE_DEGRADED`. |
| Penjelasan | Fungsi ini memenuhi INV-18 (rt: 7 kode FB), tetapi tidak ada jalur yang mengaktifkannya. |
| Dampak | Saat AI, PayPal, atau penyimpanan gagal, sistem tidak menerapkan default aman §31.3. |
| Rekomendasi | Sambungkan deteksi kegagalan ke fallback sebelum keputusan uang dibuat. |
| Confidence | High |

#### AUD-25 · MEDIUM · Security — Endpoint operasional tanpa autentikasi; otorisasi terbalik di demo reset

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 355–368 (`/demo/clock/advance`), 370–384 (`/carrier-events`), 386–415 (`/demo/reset`), 417–475 (`/privacy/deletion-requests`) |
| Bukti | Demo clock, carrier events, dan permintaan penghapusan data tidak memeriksa principal sama sekali. `/demo/reset` menerima `X-Actor-Role: merchant_admin` dari klien anonim, tetapi menolak token MERCHANT\_ADMIN karena nama peran ditulis huruf besar. Objek `app` selalu berjalan dengan `demo_mode=True`. |
| Penjelasan | Endpoint yang di SSOT dibatasi untuk staff atau service terbuka untuk siapa pun. |
| Skenario eksploitasi | Penyerang memajukan demo clock atau menyuntikkan carrier event first-scan (TM-24) untuk memicu rilis R1 begitu timer dan state machine disambungkan. |
| Dampak | Saat ini efeknya terbatas (echo atau data sintetis), tetapi pola ini membuka TM-24 dan memungkinkan pemicu penghapusan data tanpa identitas. |
| Rekomendasi | Wajibkan peran sesuai §29.2; nonaktifkan endpoint demo di luar DEMO\_MODE lewat settings; hapus header `X-Actor-Role`. |
| Confidence | High |

#### AUD-26 · MEDIUM · Security — Salt, kunci HMAC, dan seed penandatangan di-hardcode

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/config.py` (default `payer_hash_salt` dan `serial_hash_salt`); `.env.example`; `backend/domain/fraud_flags.py` (salt default); `backend/domain/journeys.py` (kunci `SerialRegistry`); `backend/jobs/anchor.py`: 14 (seed Ed25519 untuk tanda tangan anchor); `scripts/replay_decision.py`: 32 (`seed_platform`) |
| Bukti | Nilai salt di `.env` identik dengan default di `config.py` dan `.env.example` (pemindaian presisi, tanpa mengutip nilai). |
| Penjelasan | Hash serial dan payer ID dengan salt publik bisa dibalik lewat enumerasi, karena format serial berentropi rendah. |
| Dampak | Pseudonimisasi untuk FR-03, FR-93, FR-94, dan INV-13 tidak melindungi bila salt bocor bersama kode. |
| Rekomendasi | Hapus nilai default; muat dari secret store; rotasi; gunakan HMAC berkunci per merchant seperti di `serial_registry.py`. |
| Confidence | High |

#### AUD-27 · MEDIUM · Security — Cipher buatan sendiri tanpa autentikasi untuk crypto-shredding

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/domain/crypto_shred.py` (`_xor_stream`) |
| Bukti | Keystream berbasis SHA-256 di-XOR ke plaintext tanpa MAC, padahal PyNaCl dengan AEAD sudah menjadi dependensi. |
| Penjelasan | Ciphertext bersifat malleable dan manipulasi tidak terdeteksi; konstruksi kriptografi kustom sulit diaudit. |
| Dampak | Data subjek terenkripsi bisa diubah tanpa ketahuan sebelum kuncinya dihancurkan. |
| Rekomendasi | Ganti dengan `nacl.secret.SecretBox` (XSalsa20-Poly1305) atau AES-GCM dengan nonce unik per pesan. |
| Confidence | High |

#### AUD-28 · MEDIUM · Security — Indikator integritas dan privasi tanpa dasar kriptografi

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 563–576 (face blur dari flag klien), 617–644 (receipt dan commitment), 245–257 (`/passports/{id}/verify`) |
| Bukti | Receipt berisi `ed25519:sig_intake_01` dengan `verified: true`; commitment audit = SHA-256(“seed:” + nonce shopper) tanpa seed rahasia; `/verify` mengembalikan flag `chain_valid` tersimpan; blur wajah dianggap sah berdasarkan flag dari klien. |
| Penjelasan | Pengguna diberi indikator “terverifikasi”, “bertanda tangan”, dan “tak bisa ditebak” yang tidak didukung kriptografi. Modul pustaka yang benar sebenarnya sudah ada. |
| Dampak | Shopper tidak bisa membuktikan apa pun saat sengketa (TM-22); privasi wajah bergantung pada kejujuran klien. |
| Rekomendasi | Pakai `receipts.py`, `audit_commitment.py`, dan rantai `passport.py` untuk tanda tangan dan verifikasi nyata; blur di klien disertai verifikasi deteksi wajah di server. |
| Confidence | High |

#### AUD-29 · MEDIUM · Security — Independensi reviewer banding bisa dilewati

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 757–777 dan 792–825 |
| Bukti | ID reviewer asal diambil dari body permintaan pengaju banding (default `rev_01`), bukan dari decision record. |
| Penjelasan | Pemeriksaan “reviewer berbeda” membandingkan dua nilai yang sama-sama dikendalikan klien. |
| Skenario eksploitasi | Reviewer yang sama memutus banding atas keputusannya sendiri cukup dengan mengirim ID reviewer asal yang berbeda. |
| Dampak | FR-69 dan aturan “bukan pemutus awal” di §29.2 tidak ditegakkan. |
| Rekomendasi | Ambil reviewer asal dari decision record tersimpan dan bandingkan dengan identitas dari token terverifikasi. |
| Confidence | High |

#### AUD-33 · MEDIUM · Testing — Tes mengunci nilai hardcode dan deviasi spesifikasi

| Atribut | Detail |
| --- | --- |
| Lokasi | `api/test_full_rest_api_v1.py`: 32 dan 70; `api/test_api_authz_and_mcp.py`: 56; `mechanism/test_minimum_shippable_and_journeys.py`: 20; `ops/test_privacy_observability_and_ops.py`: 175–215 |
| Bukti | Tes meng-assert `r0_tranche_minor == 22157`, `via_policy_engine is True`, `chain_valid is True`, dan `len(CANONICAL_TABLES) == 20` (SSOT: 36). RPO dan RTO diberikan sebagai input `simulated_rpo_seconds=120` lalu di-assert kembali. |
| Penjelasan | Tes memverifikasi keluaran placeholder, bukan perilaku menurut SSOT. Bila logika nyata diimplementasikan, tes ini justru akan gagal. |
| Dampak | Suite memberi rasa aman palsu dan menghambat perbaikan. |
| Rekomendasi | Tulis ulang assertion berdasarkan kontrak §28 dan nilai yang dihitung engine untuk input tes; hapus tes yang memvalidasi konstanta. |
| Confidence | High |

#### AUD-35 · MEDIUM · Testing — Tes live berjalan otomatis bila kredensial tersedia

| Atribut | Detail |
| --- | --- |
| Lokasi | `pyproject.toml` (`[tool.pytest.ini_options]`); `ai/test_ai_pipeline_and_jobs.py`: 181–182; `payments/test_payments_and_failures.py`: 151–175 |
| Bukti | Marker `live_model` dan `sandbox` terdaftar tetapi tidak dikecualikan; tes hanya skip bila `.env` tidak berisi key. `session-05` mencatat tes live ikut lulus dalam run biasa. |
| Penjelasan | DUR-07 meminta CI default memakai fixture rekaman. |
| Dampak | `make test` memanggil Gemini dan PayPal Sandbox sungguhan, sehingga hasil bergantung pada jaringan, kuota, dan kredensial. |
| Rekomendasi | Kecualikan kedua marker secara default lewat `addopts`; jalankan tes live hanya lewat target terpisah. |
| Confidence | High |

#### AUD-36 · MEDIUM · Testing — Celah kasus batas dan negatif membuat bug lolos

| Atribut | Detail |
| --- | --- |
| Lokasi | `policy_engine/test_mechanism_verification.py`: 444–451 dan tes FR-74; `payments/test_payments_and_failures.py`: 100–139 |
| Bukti | Tes promosi hanya memeriksa profil NEW yang belum memenuhi syarat; tes FR-74 tidak meng-assert lane; tidak ada tes gross mismatch tanpa reviewer maupun tes kegagalan pemrosesan webhook. Semua tes terkait lulus, padahal AUD-08, AUD-12, AUD-13, dan AUD-17 terbukti saat runtime. |
| Penjelasan | Kasus batas dan jalur gagal tidak tercakup. |
| Dampak | Regresi pada aturan uang dan status akun tidak terdeteksi. |
| Rekomendasi | Tambahkan tes untuk setiap temuan tersebut sebelum memperbaikinya (test-first regression). |
| Confidence | High |

#### AUD-37 · MEDIUM · Reliability — Tidak ada observability di jalur runtime

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/observability/` (logger, metrics); `backend/api/app.py` (`/v1/health`, tanpa middleware) |
| Bukti | Nol pemanggilan logging di kode non-tes; `MetricsRegistry`, `evaluate_alerts` (AL-01..AL-07), dan runbook hanya di-import tes; `/v1/health` mengembalikan `status: ok` statis; tidak ada `X-Request-Id`. |
| Penjelasan | NFR-08 dan §34 meminta log terstruktur yang berkorelasi, sinyal, dan alert operasional. |
| Dampak | Insiden uang (aksi UNKNOWN, mismatch rekonsiliasi, kegagalan webhook) tidak akan terlihat; health check tidak mendeteksi dependensi yang mati. |
| Rekomendasi | Middleware request ID dan log JSON terstruktur dengan `scrub_sensitive_log`; ekspor metrik; endpoint readiness yang memeriksa DB, PayPal, dan AI; sambungkan `evaluate_alerts` ke scheduler. |
| Confidence | High |

#### AUD-38 · MEDIUM · Reliability — Tidak ada pipeline CI dan artefak deployment

| Atribut | Detail |
| --- | --- |
| Lokasi | Root repo (`.github/` tidak ada); `infra/`; `Makefile` |
| Bukti | Tidak ada Dockerfile aplikasi, konfigurasi CI, maupun manifest deploy. `scripts/check_refs.py` dan `scripts/sync_rtm.py` hanya dijalankan manual lewat `make`. |
| Penjelasan | SSOT mensyaratkan pemeriksaan otomatis, misalnya budget performa di CI (NFR-09), secret scanning (TM-12), dan contract test API (T-API-\*). |
| Dampak | Gate rilis bergantung pada klaim manual; regresi dan kebocoran secret tidak tertangkap otomatis. |
| Rekomendasi | Pipeline CI yang menjalankan lint, tes tanpa marker live, `check_refs`, secret scan, dan build image; Dockerfile aplikasi dengan base image ber-digest. |
| Confidence | High |

#### AUD-40 · MEDIUM · Functional — JSON Schema yang dipublikasikan tidak cocok dengan API

| Atribut | Detail |
| --- | --- |
| Lokasi | `schemas/return-declaration.v1.json`, `schemas/condition-passport.v1.json`, `schemas/keep-offer.v1.json`; `backend/api/app.py`: 523–549, 492–521, 680–712 |
| Bukti | Skema deklarasi mewajibkan `consent_fast_lane_terms`, `nonce_shopper`, dan `actor`; API membaca `fast_lane_terms_accepted` dengan default `true` dan tidak menyimpan `actor`. Skema Passport mewajibkan `signature`, `signing_key_id`, dan `events` yang tidak ada di record API. Respons keep-offer API tidak memuat `keep_offer_id`, `expires_at`, maupun `allowed_actions`. |
| Penjelasan | Skema dipublikasikan untuk agen dan integrator (FR-44, F-10), tetapi API tidak memvalidasi terhadapnya dan memakai nama field berbeda. |
| Dampak | Agen yang patuh skema mengirim persetujuan yang diabaikan, lalu API menganggap persetujuan diberikan secara default; skema menjanjikan Passport bertanda tangan yang tidak pernah dihasilkan. |
| Rekomendasi | Hasilkan model Pydantic dari skema yang sama (atau sebaliknya) dan validasi setiap request terhadapnya; satukan nama field sesuai §28.3. |
| Confidence | High |

#### AUD-41 · MEDIUM · Security — Scope agen ditegakkan di MCP tetapi tidak di REST API

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/agent_gateway/mcp_server.py`: 16–37; `backend/api/app.py` (handler deklarasi, keep-offer, status return) |
| Bukti | MCP menolak token tanpa scope `read_policy`, `declare`, atau `keep_offer`; REST API menerima format token yang sama tanpa memeriksa scope apa pun. |
| Penjelasan | TZ-06 mensyaratkan scope diperiksa pada setiap panggilan, di jalur mana pun. |
| Dampak | Agen yang dibatasi lewat MCP bisa melewati pembatasan dengan memanggil REST API langsung. Ini tetap berlaku setelah token diberi tanda tangan (AUD-21). |
| Rekomendasi | Pemeriksaan scope terpusat yang dipakai bersama REST dan MCP; MCP sebagai lapisan tipis di atas endpoint REST sesuai §28.3. |
| Confidence | High |

### LOW

#### AUD-16 · LOW · Architecture — Konstanta bisnis terduplikasi

| Atribut | Detail |
| --- | --- |
| Lokasi | `domain/trust.py`: 37 vs `domain/policy.py`: 52 (cap tier); `policy_engine/release.py`: 193 vs `misdeclaration.py`: 7 (urutan grade); `domain/policy.py`: 121 vs `config/jurisdiction_table.json` (jurisdiksi tanpa F) |
| Bukti | Nilai yang sama didefinisikan ulang secara terpisah. |
| Penjelasan | Perubahan policy merchant tidak mengalir ke `compute_account_exposure_cap_minor` maupun `compute_f_minor`. |
| Dampak | Risiko divergensi diam-diam saat policy diubah (FR-51, FR-90). |
| Rekomendasi | Satu sumber konfigurasi yang disuntikkan ke semua modul. |
| Confidence | High |

#### AUD-17 · LOW · Functional — Lane NO\_PASSPORT dilaporkan sebagai FAST

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/policy_engine/release.py`: 331 |
| Bukti | `lane=lane_name if lane_name == "FAST" else "FAST"` selalu menghasilkan FAST; rt: order tanpa Passport (TRUSTED, LOW) dilaporkan berlane FAST. |
| Penjelasan | Ekspresi mati; nilai NO\_PASSPORT yang sudah dihitung dibuang. |
| Dampak | Decision record dan penjelasan salah label (FR-74, INV-06). |
| Rekomendasi | Kembalikan `lane_name` apa adanya. |
| Confidence | High |

#### AUD-18 · LOW · Functional — Re-plan tranche dengan jumlah berbeda tidak ditolak

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/ledger.py`: 129–131 |
| Bukti | rt: tranche R0 untuk decision yang sama direncanakan ulang dengan 39999, dan ledger diam-diam mengembalikan aksi lama bernilai 22157. |
| Penjelasan | Idempotensi tanpa pemeriksaan kesamaan payload. |
| Dampak | Bug di pemanggil tidak terdeteksi; perilakunya berbeda dari pola 409 `IDEMPOTENCY_CONFLICT` di API. |
| Rekomendasi | Tolak bila jumlah berbeda dari aksi yang tersimpan. |
| Confidence | High |

#### AUD-19 · LOW · Architecture — Dependensi runtime yang hanya dipakai tes

| Atribut | Detail |
| --- | --- |
| Lokasi | `pyproject.toml` |
| Bukti | `jsonschema` dan `pyyaml` dideklarasikan sebagai dependensi runtime, tetapi tidak di-import kode non-tes. |
| Penjelasan | Keduanya seharusnya masuk grup dev, atau benar-benar dipakai di runtime (validasi skema, pemuatan `models.yaml`). |
| Dampak | Image produksi lebih besar dan permukaan dependensi lebih luas. |
| Rekomendasi | Pindahkan ke grup dev atau gunakan sesuai tujuannya. |
| Confidence | High |

#### AUD-30 · LOW · Security — Tanpa rate limiting dan batas ukuran body

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py` (tidak ada middleware) |
| Bukti | Tidak ada pembatas laju, header `Retry-After`, maupun batas ukuran request. SSOT §13 meminta rate limiting pada upload bukti dan endpoint agen; TM-15 meminta batas per order dan IP. |
| Penjelasan | Kode error `RATE_LIMITED` di §28.2 tidak pernah bisa dihasilkan. |
| Dampak | Rentan abuse dan DoS, terutama setelah pipeline AI berbayar tersambung. |
| Rekomendasi | Rate limit per token dan IP serta batas ukuran body di middleware atau gateway. |
| Confidence | High |

#### AUD-31 · LOW · Security — Kredensial default pengembangan di Compose dan template

| Atribut | Detail |
| --- | --- |
| Lokasi | `infra/docker-compose.yml`; `.env.example` |
| Bukti | Password Postgres dan secret MinIO untuk pengembangan identik di Compose, `.env.example`, dan `.env`. |
| Penjelasan | Nilai default yang sama dipakai di semua lingkungan lokal. |
| Dampak | Terbatas pada lingkungan lokal; berisiko bila Compose dijalankan di host yang terekspos. |
| Rekomendasi | Ambil dari variabel environment tanpa default di Compose; tandai jelas sebagai nilai lokal saja. |
| Confidence | High |

#### AUD-39 · LOW · Reliability — State in-memory tumbuh tanpa batas

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 332–347 (cache idempotensi); `backend/payments/webhooks.py`: 15–40; `backend/agent_gateway/mcp_server.py`: 12 dan 40 |
| Bukti | Cache idempotensi tidak pernah dipangkas, padahal API-06 menetapkan masa simpan 24 jam; set `_seen_event_ids` dan `audit_log` MCP hanya bertambah. |
| Penjelasan | Struktur data tanpa TTL atau batas ukuran pada proses berumur panjang. |
| Dampak | Konsumsi memori naik terus; kecil selama demo, nyata di produksi. |
| Rekomendasi | Simpan di DB dengan TTL atau cache dengan eviction; tulis audit log ke penyimpanan append-only. |
| Confidence | High |

#### AUD-42 · LOW · Architecture — Drift konfigurasi, enum, dan model data antarmodul

| Atribut | Detail |
| --- | --- |
| Lokasi | `.env.example` vs `backend/config.py`; `backend/api/app.py`, `domain/passport_tier.py`, `apps/packing-station/src/App.tsx`; `backend/db/schema.py` vs `backend/payments/ledger.py`; `packages/api-client/src/index.ts` |
| Bukti | 15 kunci `.env.example` tidak dibaca aplikasi, termasuk `ALPHA_ACCUSE`, `EXPOSURE_CAPS`, dan `VALUE_BANDS`. Enum tier Passport berbeda di tiga tempat. `refund_actions` di DDL tidak memiliki empat atribut `RefundAction` dan kolom status-nya tanpa CHECK. Client API frontend tidak memanggil endpoint apa pun. |
| Penjelasan | Setiap modul mendefinisikan ulang konsep yang sama tanpa sumber bersama. |
| Dampak | Operator mengira sedang menyetel parameter mekanisme lewat environment padahal tidak; pemetaan ke DB akan rusak saat persistensi ditambahkan. |
| Rekomendasi | Satu modul definisi bersama (enum, kontrak, konfigurasi) yang dipakai backend, skema, dan frontend; hapus kunci konfigurasi yang tidak dipakai. |
| Confidence | High |

### INFORMATIONAL

#### AUD-20 · INFORMATIONAL — Kekuatan implementasi yang terverifikasi

| Area | Bukti |
| --- | --- |
| Kualitas kode | 245/245 fungsi beranotasi tipe lengkap; nol `except` kosong atau `except Exception`; nol siklus import |
| Mekanisme | Policy Engine cocok 180/180 dengan §8.8 dan memakai `Fraction` tanpa float |
| Settlement | Kasus sama, adjacent, gross terkonfirmasi, top-up, dan clamp INV-01 menghasilkan angka sesuai §8.4 (rt) |
| Audit draw | Commit–reveal mengikat; laju terpilih empiris 5,15% untuk p = 5% (N = 20.000) |
| CUSUM | False alarm dalam 20 return 3,0% (θ0 = 0,10) dan 5,35% (θ0 = 0,20), di bawah target 5,5% §8.7 |
| HTTP client | Panggilan httpx memakai timeout dan context manager; key Gemini dikirim lewat header, bukan URL |

#### AUD-32 · INFORMATIONAL · Security — Kontrol keamanan yang sudah baik

| Area | Bukti |
| --- | --- |
| Injection dan deserialisasi | Tidak ada `subprocess`, `eval`, `exec`, `pickle`, `yaml.load`, atau `shell=True` di kode non-tes |
| SSRF (TM-14) | Tidak ada URL dari pengguna yang di-fetch server |
| Guard Sandbox (TM-16) | `PayPalSandboxClient` menolak base URL di luar allow-list Sandbox |
| Kebocoran secret di log | Tidak ada `print` atau logging data sensitif; key Gemini dikirim lewat header |
| View publik Passport | Membuang `current_owner_ref` dan `buyer_email` |
| SQL injection | Tidak berlaku karena tidak ada database |

## F. Security Assessment

Keamanan sistem saat ini tidak memadai untuk dipakai di luar demo terkendali. Siapa pun bisa memalsukan identitas staff di tenant mana pun, otorisasi per objek tidak ada, dan kredensial ikut dalam arsip. Di sisi lain, kode bersih dari pola injection klasik, dan guard Sandbox PayPal bekerja di level client.

### Ringkasan per kategori

| Kategori | Status | Temuan |
| --- | --- | --- |
| Autentikasi dan session | Rentan | AUD-21 |
| Otorisasi dan BOLA | Rentan | AUD-22, AUD-29, AUD-25 |
| Integritas webhook | Rentan | AUD-24 |
| Manajemen secret | Rentan | AUD-23, AUD-26, AUD-31 |
| Paparan data sensitif | Rentan | AUD-22 (GET return tanpa autentikasi), AUD-23 |
| Validasi input | Rentan | AUD-04 |
| Kriptografi | Sebagian | AUD-27, AUD-28 |
| Rate limiting | Tidak ada | AUD-30 |
| SQL injection | Tidak berlaku | Tidak ada database |
| Command injection, subprocess | Tidak ditemukan | AUD-32 |
| Path traversal | Tidak ditemukan | Tidak ada path dari input pengguna |
| SSRF | Tidak ditemukan | AUD-32 (TM-14) |
| Deserialisasi tidak aman | Tidak ditemukan | AUD-32 |
| XSS | Tidak berlaku | API hanya JSON; tidak ada frontend |
| CORS | Tidak dikonfigurasi | Default aman; perlu dirancang saat frontend ada |
| Upload file | Tidak berlaku | Tidak ada endpoint upload; TM-13 relevan nanti |

### Kepatuhan threat model (§32.4)

| Ancaman | Mitigasi di SSOT | Kondisi |
| --- | --- | --- |
| TM-05 IDOR lintas tenant | Aturan §29.3 dan RLS | Tidak ada (AUD-22, ARC-09) |
| TM-06 Webhook palsu | Verifikasi signature, dedupe | Tidak ada (AUD-24); dedupe rapuh (AUD-12) |
| TM-07 Over-refund lewat race | Row lock, cek INV-01 | Tidak ada (AUD-11) |
| TM-12 Kebocoran kredensial | Secret scanning, rotasi | Gagal (AUD-23) |
| TM-14 SSRF | Tidak ada fetch URL pengguna | Terpenuhi |
| TM-15 DoS pipeline AI | Rate limit, cost cap | Tidak ada (AUD-30) |
| TM-16 Pembayaran live tak sengaja | Guard host Sandbox | Terpenuhi di `PayPalSandboxClient` |
| TM-17 Retake oracle | Batas retake | Logika ada, tidak tersambung (FR-66) |
| TM-22 Operator mengubah record | Receipt, commit–reveal | Palsu di API (AUD-28) |
| TM-24 Carrier event palsu | Endpoint manual hanya saat DEMO\_MODE | Gagal (AUD-25, FR-96) |

### Kerentanan potensial

Tiga kelemahan belum bisa dieksploitasi karena modulnya belum tersambung ke API, tetapi akan langsung aktif begitu disambungkan apa adanya: bypass signature webhook (AUD-24), race pada ledger refund (AUD-11), dan carrier event tanpa autentikasi (AUD-25).

### Area yang tidak dapat dinilai

- **Kerentanan dependensi.** Tidak ada akses ke basis data advisori di lingkungan audit. Versi terkunci di `uv.lock` (misalnya FastAPI 0.162.0, httpx 0.28.1), tetapi tidak ada klaim CVE yang dibuat.
- **Uji penetrasi HTTP.** FastAPI tidak bisa dijalankan di sandbox audit; temuan HTTP berbasis analisis statis dan eksekusi fungsi terisolasi.
- **Perilaku PayPal Sandbox dan Gemini.** Tidak ada panggilan jaringan, sesuai aturan audit.
- **Ketahanan prompt injection (FR-86).** Hanya daftar pola teks statis yang terlihat; tanpa set DS-04 tidak bisa diukur.
- **Manajemen kunci penandatangan (TM-11).** Tidak ada file kunci di repo, dan API tidak menandatangani apa pun.

## G. Testing & QA Report

Dari 71 tes, 44 lulus saat dijalankan auditor dan 27 BLOCKED oleh lingkungan; tidak ada yang gagal karena kode. Angka lulus ini tidak membuktikan kebenaran. Sedikitnya 9 tes memeriksa nilai hardcode, dan tidak ada satu pun tes integrasi, E2E, atau konkurensi nyata.

| Ukuran | Jumlah |
| --- | --- |
| Tes ditemukan | 71 di 11 file, 433 assertion |
| Dieksekusi native | 14: 13 lulus, 1 BLOCKED saat runtime |
| Dieksekusi dengan test double (indikatif) | 34: 31 lulus, 3 BLOCKED (Hypothesis) |
| Tidak bisa dikoleksi | 23 BLOCKED |
| Gagal karena kode | 0 |
| Hasil tautologis atau sirkular | Sedikitnya 9 tes |

### G.1 Testing Verification Report

| Kategori | Tes tersedia | Status eksekusi | Hasil | Catatan |
| --- | --- | --- | --- | --- |
| Unit: Policy Engine dan mekanisme | 18 | Indikatif | 15 lulus, 3 BLOCKED | Tiga tes properti `@given` butuh Hypothesis native |
| Unit: golden examples | 10 | Indikatif | 10 lulus | Sejalan dengan harness independen (180/180) |
| Unit: state machine | 4 | Native | 4 lulus | Tes CT sebagian tautologis |
| Unit: payments | 5 | Native | 4 lulus, 1 BLOCKED | Tes Sandbox butuh pydantic; tes FX dan REC tautologis |
| Unit: provider Gemini | 5 | Native | 5 lulus | HTTP di-mock, tanpa jaringan |
| Mekanisme dan journeys | 6 | Indikatif | 6 lulus | J-01..J-14 berupa skrip in-process dengan guard literal; tes skema mengunci 20 tabel |
| API via TestClient | 7 | BLOCKED | — | FastAPI tidak tersedia; tes meng-assert nilai hardcode |
| AI pipeline dan jobs | 6 | BLOCKED | — | FastAPI dan PyNaCl; berisi 1 tes `live_model` |
| Domain dan skema | 4 | BLOCKED | — | jsonschema (rpds native) dan PyNaCl |
| Privacy, observability, ops | 6 | BLOCKED | — | Meng-assert hasil drill dan laporan UX yang konstan |
| Integrasi DB, Temporal, MinIO | 0 | Tidak ada | — | Bukti I yang diklaim RTM tidak ada |
| E2E browser (Playwright) | 0 | Tidak ada | — | Bukti E tidak ada |
| Aksesibilitas dan performa frontend | 0 | Tidak ada | — | “Laporan UX” berupa konstanta |
| Konkurensi nyata | 0 | Tidak ada | — | CT-01..CT-12 tanpa thread atau lock |

### G.2 Perintah dan lingkungan eksekusi

Semua run dijalankan di salinan kerja tanpa `.env`, dengan `PYTHONDONTWRITEBYTECODE=1`, plugin cache pytest dimatikan, dan tanpa jaringan. pytest 9.2.0 dan stack httpx diambil dari `.venv` proyek karena pure Python. Run indikatif memakai test double `pydantic.BaseModel` minimal serta stub Hypothesis yang men-skip tes `@given`.

| Run | Perintah ringkas | Hasil |
| --- | --- | --- |
| A native | `pytest backend/tests/state_machine -p no:cacheprovider -p no:hypothesispytest` | 4 passed (0,04 s) |
| B native | `pytest backend/tests/ai/test_gemini_provider.py` dengan overlay httpx | 5 passed (0,25 s) |
| C indikatif | `pytest backend/tests/golden backend/tests/mechanism backend/tests/policy_engine` dengan test double | 31 passed, 3 skipped (2,00 s) |
| D koleksi | `pytest --collect-only` untuk file sisanya | `ModuleNotFoundError`: fastapi (4 file), jsonschema (1 file) |
| E native | `pytest backend/tests/payments` dengan overlay httpx | 4 passed; tes Sandbox gagal karena `pydantic` tidak tersedia, dicatat BLOCKED |

### G.3 Perbandingan dengan laporan yang ada

Gate record mencatat “68 passed”, `session-07` mencatat “71 passed”, dan `.pytest_cache` berisi 71 node ID dengan `lastfailed` kosong. Hasil audit konsisten dengan klaim itu: tidak ada tes yang gagal di antara yang bisa dijalankan. Namun 27 tes tidak bisa diverifikasi ulang, dan `session-05` menyatakan tes `live_model` ikut berjalan, artinya run biasa memanggil Gemini secara live.

### G.4 Kualitas tes

- **Memeriksa konstanta.** Tes CT, FX, REC, journeys, drill backup, clean-env, laporan UX, red-team, dan beberapa tes API lulus karena fungsi yang diuji mengembalikan nilai tetap (AUD-03, AUD-33).
- **Mengunci deviasi.** `len(CANONICAL_TABLES) == 20` padahal SSOT punya 36 tabel; `r0_tranche_minor == 22157` untuk return apa pun.
- **Celah kasus batas.** Bug AUD-08, AUD-12, AUD-13, dan AUD-17 lolos meski tes terkait lulus (AUD-36).
- **Infrastruktur tes.** Tidak ada `conftest.py` atau fixture bersama; mocking hanya pada `httpx.Client.post`; `testpaths` merujuk `sim/tests` yang tidak ada; coverage tidak diukur karena paket coverage tidak tersedia di proyek maupun sandbox.
- **Tes live tidak dikecualikan.** Marker `live_model` dan `sandbox` terdaftar tetapi tidak di-deselect (AUD-35).
- **Yang sudah baik.** Golden examples E1–E8 dan kedua peta kelayakan diuji dengan angka eksak, dan regresi bug v1.1/v1.2 punya tes khusus.

## H. Reliability & Production Readiness

Sistem belum siap untuk produksi, dan belum siap pula sebagai demo yang bisa dijalankan juri sesuai NFR-07 dan §35.4. Tidak ada persistensi, server aplikasi, logging, maupun pipeline deploy, dan kegagalan dependensi tidak ditangani. Komponen komputasi inti sendiri cepat dan deterministik.

| Area | Penilaian | Bukti | Jenis bukti |
| --- | --- | --- | --- |
| Penanganan error | Tidak memadai | Tanpa exception handler; 19 `request.json()` tak tertangani; `KeyError` webhook (AUD-12); kode error di luar katalog §28.2 | Terverifikasi (statis dan rt) |
| Logging dan observability | Tidak ada di runtime | Nol logging di kode non-tes; registry metrik, alert AL-01..AL-07, dan runbook hanya dipakai tes; tanpa `X-Request-Id` | Terverifikasi |
| Health check | Dangkal | `/v1/health` mengembalikan `status: ok` statis tanpa memeriksa dependensi | Terverifikasi |
| Database | Tidak ada | DDL tidak pernah dieksekusi; tanpa migrasi | Terverifikasi |
| Keamanan transaksi | Tidak ada | Tanpa transaksi; ledger berpola check-then-act (AUD-11) | Terverifikasi (rt) |
| Konkurensi | Tidak aman | Dict dipakai bersama handler sinkron (threadpool) dan async; ID `len() + 1`; cache idempotensi check-then-set | Risiko potensial (statis) |
| Background task | Tidak ada | Tidak ada scheduler; `jobs/anchor.py` dan `jobs/retention.py` tidak dipanggil; tidak ada timer lifecycle | Terverifikasi |
| Manajemen resource | Sebagian | httpx memakai timeout dan context manager; cache idempotensi tanpa TTL, set event webhook, dan audit log MCP tumbuh tanpa batas (AUD-39) | Terverifikasi (statis) |
| Performa komputasi | Memadai | rt: `decide_release` p50 80 µs, p95 94 µs (n = 3.000); feasibility map 1,3 ms per request | Terverifikasi (rt, indikatif) |
| Skalabilitas | Tidak bisa diskalakan | State per proses; restart menghapus data; banyak worker berarti state yang berbeda | Terverifikasi (statis) |
| Pemisahan konfigurasi | Tidak ada | Settings tidak dipakai; `demo_mode=True` default; `.env` relatif terhadap direktori kerja | Terverifikasi |
| Kesiapan deployment | Tidak siap | Tanpa server ASGI, Dockerfile aplikasi, service Compose, maupun konfigurasi CI | Terverifikasi |
| Backup dan recovery | Tidak ada | BK-01..BK-07 tidak diimplementasikan; drill RPO/RTO berupa nilai simulasi (AUD-03) | Terverifikasi |
| Kegagalan yang anggun | Sebagian | Kegagalan Gemini jatuh ke MANUAL/STANDARD; fallback §31.3 tidak tersambung (AUD-15); error PayPal live hanya berupa exception dari `raise_for_status` | Terverifikasi (statis) |
| Alert operasional | Tidak ada | `evaluate_alerts` hanya dipanggil tes; guard AL-07 aktif di client PayPal | Terverifikasi |

### Risiko yang perlu pengujian lanjutan

- Perilaku di bawah beban nyata: race pada dict bersama dan pada ledger saat dipakai dari banyak thread atau worker.
- Latensi dan kegagalan PayPal Sandbox sungguhan terhadap target NFR-01 (≤ 60 detik p95), yang belum bisa diukur karena refund belum ada.
- Latensi dan biaya pipeline AI nyata terhadap NFR-02 dan NFR-16.
- Konsumsi memori pada proses berumur panjang.

### Kesimpulan kesiapan

Yang paling menentukan bukan performa, karena komputasi inti sudah jauh di bawah anggaran waktu. Penentunya adalah tiga fondasi yang belum ada: persistensi, jalur uang ke PayPal, dan cara menjalankan aplikasi. Selama ketiganya belum ada, perbaikan reliability lain belum bisa diuji secara bermakna.

## I. Missing Implementation & Technical Debt

Sebagian besar utang berupa komponen yang belum ada atau digantikan placeholder, bukan kode yang buruk. Pustaka domain yang sudah ada bisa dipertahankan dan disambungkan.

### I.1 Implementasi yang belum ada

| Area | Yang belum ada | Referensi |
| --- | --- | --- |
| Frontend | Empat aplikasi React (storefront, portal shopper, packing station, console) | F-02, F-03, F-11, NFR-06, NFR-09, NFR-10 |
| Persistensi | PostgreSQL, migrasi Alembic, RLS, constraint INV-01 dan INV-09 | ARC-04, ARC-09, AUD-06 |
| Workflow | Temporal atau job table, timer lifecycle, retry | ARC-05, FR-24, FR-71, FR-97 |
| PayPal | Capture, refund bertahap, tracking, Disputes API, verifikasi webhook, outbox sweeper, rekonsiliasi | AUD-02, AUD-24, ST-01..ST-13 |
| Media dan bukti | Object storage, upload, manifest hash per media, blur on-device | FR-02, FR-16 |
| Pipeline AI | Forensik media L1–L7, OCR/VLM, grader kedua, uji konformal, rekaman judge mode | FR-18, FR-20, FR-80, ADR-009, ADR-017 |
| Agen | Server MCP dengan transport, `POST /v1/agent/tokens` | ADR-010, FR-45 |
| Endpoint | `POST /v1/returns/{id}/cancel` | FR-88 |
| Operasional | Server ASGI, service Compose, CI/CD, observability, alert, backup dan restore | AUD-07, AUD-37, AUD-38, BK-01..BK-07 |
| P2 | Anchoring RFC 3161, deposit sewa, delivery receipt | FR-83, FR-54, FR-77 |

### I.2 Placeholder yang tampil sebagai implementasi

| Placeholder | Lokasi | Temuan |
| --- | --- | --- |
| Keputusan, tranche, receipt, evidence pack, keep-offer, dan simulator dengan nilai tetap | `backend/api/app.py` | AUD-01 |
| Capture, refund, dan order dengan status COMPLETED palsu | `backend/payments/client.py`: 101–138 | AUD-02 |
| Rekonsiliasi, drill backup, clean-env, laporan UX | `payments/reconciliation.py`, `ops/drills.py` | AUD-03 |
| Skenario konkurensi CT dan mode kegagalan FX yang tautologis | `domain/return_state.py`, `payments/failures.py` | AUD-03 |
| Red-team dengan latensi tetap, OCR berupa regex | `ai/pipeline/forensics.py`, `ai/pipeline/ocr.py` | FR-20, FR-03 |
| Judge mode berupa daftar hash fixture | `ai/pipeline/evaluator.py` | FR-80 |
| Migrasi berisi komentar saja | `backend/db/migrations/001_initial_schema.sql` | ARC-09 |

### I.3 Technical debt

- **Duplikasi dan drift definisi:** cap tier, urutan grade, jurisdiksi F, curve, enum tier Passport, dan model `refund_actions` didefinisikan ulang di beberapa tempat (AUD-16, AUD-42, AUD-10).
- **Konfigurasi tidak tersambung:** settings, guard startup, dan 15 kunci `.env.example` tidak memengaruhi aplikasi (AUD-14, AUD-42).
- **Kontrak terpisah dari kode:** JSON Schema tidak dipakai untuk validasi, dan API tidak memakai model Pydantic (AUD-40, ARC-08).
- **Tes mengunci placeholder:** tes perlu ditulis ulang saat logika nyata masuk (AUD-33).
- **Kriptografi kustom dan kunci literal:** cipher crypto-shred buatan sendiri; salt dan seed penandatangan di-hardcode (AUD-27, AUD-26).
- **Dokumentasi tidak dapat dipercaya:** `rtm.csv`, gate record, dan status Sandbox perlu dikoreksi; ADR-001..027 berisi teks generik; repo tanpa riwayat commit (DOC-01..DOC-10).

## J. Remediation Roadmap

Urutan di bawah mengikuti dependensi teknis. Dengan sisa 11 hari menuju deadline, tujuh item Must Fix adalah jalur kritis menuju demo yang jujur; Policy Engine tidak perlu ditulis ulang. Bila waktu tidak cukup, ikuti cut order SSOT §14.4 dan tandai fitur yang dipotong sebagai DEFERRED atau DEGRADED secara terbuka.

### J.1 Must Fix Before Release

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-01 | Rotasi key Gemini dan kredensial PayPal Sandbox; keluarkan `.env` dari arsip | AUD-23 | Kebocoran sudah terjadi | — |
| J-02 | Koreksi `rtm.csv`, gate record, dan status Sandbox ke status yang didukung bukti; hapus fungsi verifikasi yang di-hardcode | AUD-03, AUD-33, DOC-01..DOC-04 | Keputusan gate saat ini bersandar pada klaim yang tidak benar | — |
| J-03 | Token bertanda tangan dengan kedaluwarsa, otorisasi terpusat per resource, pemeriksaan scope bersama REST dan MCP, `POST /v1/agent/tokens` | AUD-21, AUD-22, AUD-41, AUD-25, AUD-29 | Tanpa ini semua kontrol lain bisa dilewati | — |
| J-04 | Lapisan layanan yang menghubungkan endpoint ke Policy Engine dan state machine; model Pydantic dari JSON Schema; curve dari satu sumber | AUD-01, AUD-05, AUD-04, AUD-40, AUD-10 | Inti produk belum berjalan di sistem | J-03 |
| J-05 | PostgreSQL, Alembic, RLS, dan constraint; row lock untuk ledger; dedupe webhook atomik | AUD-06, ARC-09, AUD-11, AUD-12 | Integritas uang (INV-01, INV-09) membutuhkan DB | J-04 |
| J-06 | Capture dan refund nyata dengan `PayPal-Request-Id`; verifikasi signature webhook; jalankan ST-01 sesuai definisi | AUD-02, AUD-24 | Nilai utama produk adalah refund PayPal bertahap | J-03, J-05 |
| J-07 | Server ASGI dan service Compose; frontend minimal untuk J-01..J-04 | AUD-07, ARC-07, NFR-07 | Juri harus bisa menjalankan demo | J-04 |

### J.2 Should Fix Before Production

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-08 | Hasil ESCALATE untuk gross yang belum direview; flag INV-10 wajib tanpa default; implementasi uji konformal | AUD-08, AUD-09, ADR-017 | Keadilan terhadap shopper dan kepatuhan INV-10 | J-04 |
| J-09 | Promosi trust satu tingkat; label NO\_PASSPORT; konflik re-plan di ledger | AUD-13, AUD-17, AUD-18 | Cap exposure dan decision record harus akurat | J-04 |
| J-10 | Tes integrasi DB, konkurensi INV-01, AZ negatif, Playwright J-01..J-14; deselect marker live; tes regresi untuk temuan runtime | AUD-34, AUD-35, AUD-36, AUD-33 | Agar status VERIFIED bermakna | J-05, J-07 |
| J-11 | Secret store untuk salt dan kunci; AEAD untuk crypto-shred; receipt, commitment, dan verifikasi chain nyata; autentikasi endpoint operasional | AUD-26, AUD-27, AUD-28, AUD-25 | Kontrol privasi dan integritas yang dijanjikan ke pengguna | J-03, J-05 |
| J-12 | Settings disuntikkan ke `create_app` dengan default non-demo; fallback §31.3 tersambung | AUD-14, AUD-15 | Perilaku aman saat dependensi gagal | J-04 |
| J-13 | Observability, readiness check, alert AL-01..AL-07; pipeline CI dengan secret scan | AUD-37, AUD-38 | Insiden uang harus terlihat dan regresi tertangkap | J-05, J-07 |

### J.3 Recommended Improvements

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-14 | Modul definisi bersama untuk enum, kontrak, dan konfigurasi; hapus kunci konfigurasi mati | AUD-16, AUD-42 | Mencegah drift berulang | J-04 |
| J-15 | Rate limiting dan batas ukuran body | AUD-30 | Perlu sebelum pipeline AI berbayar tersambung | J-07 |
| J-16 | State dengan TTL; kredensial Compose dari environment; dependensi tes ke grup dev | AUD-39, AUD-31, AUD-19 | Kebersihan operasional | J-05 |
| J-17 | Lengkapi isi ADR; satukan penomoran versi | DOC-05, DOC-10 | Keterlacakan keputusan | — |

### J.4 Optional Optimizations

| ID | Tindakan | Referensi | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-18 | Cache feasibility map per versi policy | H (1,3 ms per request) | Bukan bottleneck saat ini | — |
| J-19 | Tracing OpenTelemetry end-to-end | NFR-08 | Berguna setelah observability dasar ada | J-13 |
| J-20 | Verifikasi pemetaan UCP terhadap spesifikasi terbaru | FR-48 | Butuh akses ke spesifikasi UCP | — |

## K. Final Verdict

**NOT READY.** Masih ada masalah fundamental pada implementasi, keamanan, arsitektur, dan reliability. Implementasi saat ini belum layak dianggap selesai menurut SSOT v1.2.1.

| Dimensi | Dasar verdict |
| --- | --- |
| Implementasi | Sistem yang berjalan (API) tidak menjalankan mekanisme yang dispesifikasikan; jalur uang ke PayPal, persistensi, dan frontend tidak ada; hanya 9 dari 137 requirement yang PASS |
| Keamanan | Autentikasi dapat dipalsukan (CRITICAL), otorisasi per objek tidak ada, kredensial bocor dalam arsip |
| Reliability | Aplikasi tidak bisa dijalankan dengan dependensi yang dideklarasikan; tidak ada observability maupun backup |
| Integritas bukti | Artefak verifikasi dan sebagian tes di-hardcode lulus; gate record tidak sejalan dengan §27 |

**Mengapa bukan REQUIRES REMEDIATION.** Kategori itu mengandaikan sistem yang sebagian besar sudah terbangun dengan masalah material. Di sini lapisan inti sistem (persistensi, integrasi pembayaran, antarmuka pengguna, autentikasi) belum ada.

**Mengapa bukan INCONCLUSIVE.** Cacat penentu bersifat struktural dan terverifikasi langsung di kode, sebagian dengan eksekusi runtime. Keterbatasan lingkungan (27 tes BLOCKED, tanpa jaringan) hanya menghalangi konfirmasi komponen yang sudah terbukti berupa stub atau tidak tersambung, sehingga tidak mengubah verdict.

**Yang sudah siap dipakai sebagai fondasi.** Pustaka Policy Engine (cocok 180/180 dengan §8.8), aturan settlement, audit draw commit–reveal, CUSUM, state machine, dan pustaka kriptografi receipt serta Passport. Semuanya layak dipertahankan dan disambungkan, bukan ditulis ulang.

**Keyakinan dan batas cakupan.** Keyakinan atas verdict: High. Tidak ada panggilan ke PayPal maupun Gemini; lapisan HTTP dinilai secara statis; kerentanan dependensi tidak dinilai; `privacy/lifecycle.py`, `scripts/*`, `docs/ucp-mapping.md`, dan `packages/ui` belum diinspeksi secara rinci, dan kecil kemungkinannya mengubah verdict.

**Kriteria audit ulang.** Selesaikan J-01 sampai J-07, jalankan ST-01 di Sandbox sesuai definisinya, regenerasi RTM hanya dari bukti nyata, lalu audit ulang dengan lingkungan yang dapat menjalankan seluruh suite tes.

Seluruh file proyek tetap tidak berubah selama audit (manifest SHA-256 terverifikasi setiap fase), dan kredensial di `.env` tidak pernah dipakai.

## Audit Ledger

Posisi per 1 November 2026, setelah Fase 8. Semua bagian A–K sudah diisi.

### Tes dan eksekusi

| Eksekusi | Perintah ringkas | Hasil |
| --- | --- | --- |
| Tes state machine proyek | `python3 -m pytest backend/tests/state_machine/test_return_state_machine.py -p no:cacheprovider -p no:hypothesispytest` di salinan kerja | 4 passed (0,03 s) |
| Harness mekanisme audit | `harness/mechanism_check.py` dengan test double `pydantic` berlabel | 180/180 nilai §8.8 cocok, plus sensitivitas, E2, E5, INV-14, INV-18 |
| 9 file tes lain | — | Diperbarui di Fase 6: lihat Bagian G (44 lulus, 27 BLOCKED) |
| `test_gemini_provider.py` | — | 5 passed (Fase 6, native) |

**Fase 4.** Harness logika bisnis (`harness/business_logic_check.py` dan `settlement_check.py`) menjalankan 8 skenario settlement, promosi trust, 20.000 audit draw, 40.000 simulasi CUSUM per konfigurasi, serta skenario ledger dan webhook. Hasilnya menjadi bukti AUD-08 sampai AUD-13, AUD-18, dan AUD-20. Metrik statis (anotasi tipe, pola exception, magic number, duplikasi, pemakaian dependensi) dihitung dengan analisis AST atas seluruh kode non-tes.

**Fase 5.** Pemindaian pola berbahaya dan pemindaian secret presisi (hanya nama kunci, tanpa nilai), ekstraksi `_parse_bearer` via AST untuk menguji pemalsuan token tanpa FastAPI, serta uji token MCP buatan sendiri. Tidak ada panggilan jaringan, dan kredensial di `.env` tidak pernah dipakai.

**Fase 6.** Inventaris AST atas 71 tes, lima run pytest di salinan kerja (dua native, satu indikatif dengan test double, satu koleksi, satu payments native), dan perbandingan dengan klaim di gate record serta log sesi. Rincian perintah dan hasil ada di Bagian G.2.

**Fase 7.** Pemeriksaan health check, modul observability, jobs, artefak deployment dan CI, struktur state tanpa batas, serta kunci literal; micro-benchmark `decide_release` (n = 3.000) dan `generate_feasibility_map` (n = 20) di salinan kerja dengan test double pydantic.

**Fase 8.** Penelusuran lintas modul atas JSON Schema, kontrak API, state machine, enum, scope agen, client frontend, konfigurasi, dan model DB terhadap domain. Hasilnya dirangkum di D.7 dan menjadi dasar AUD-40 sampai AUD-42; laporan final A, I, J, dan K disusun dari seluruh fase.

### Cakupan inspeksi

- **Dibaca penuh:** `backend/api/app.py`, seluruh `backend/policy_engine/`, `domain/policy.py`, `nonce.py`, `signing.py`, `audit_commitment.py`, `receipts.py`, `payments/ledger.py`, `webhooks.py`, `reconciliation.py`, `config.py`, `apps/`, `packages/`, `infra/docker-compose.yml`, `pyproject.toml`, `Makefile`, `package.json`, `config/*.json`, README, gate record, `sandbox-tests.md`.
- **Dibaca sebagian:** `return_state.py`, `trust.py`, `account_monitor.py`, `passport.py`, `payments/client.py`, `payments/failures.py`, `ai/pipeline/*`, `ops/drills.py`, `agent_gateway/mcp_server.py`, `sim/*`, serta ringkasan struktur modul domain lainnya.
- **Belum diinspeksi:** `privacy/lifecycle.py`, `scripts/*`, `docs/ucp-mapping.md`, dan `packages/ui`. File `observability/metrics.py`, `jobs/*`, `db/schema.py`, tes, dan `docs/evidence/*` diperiksa di Fase 6–8, sebagian hanya pada level struktur.
- **SSOT dibaca:** §0, 1, 5, 6, 8.2–8.13, 9, 10, 13, 14, 19–23, 27, 28.1–28.3, 29, 30, 44–49. Belum: §7, 11, 12, 15–18, 24–26, 28.4, 31–43, lampiran.

### Temuan sementara (kini diformalkan sebagai AUD-21 sampai AUD-32)

- Token Bearer bisa dipalsukan (`staff:<merchant>:<ROLE>`), dan token sembarang (`kind: invalid`) lolos pemeriksaan “terautentikasi”.
- `.env` berisi kredensial berformat asli ikut dalam arsip; salt pseudonimisasi di-hardcode sebagai default di `config.py` dan `fraud_flags.py`.
- Endpoint tanpa autentikasi: demo clock, carrier events, privacy deletion; demo reset bisa diakses dengan header `X-Actor-Role`.
- Verifikasi webhook palsu; stub PayPal dan artefak verifikasi yang di-hardcode kini tercatat sebagai AUD-02 dan AUD-03.
- `crypto_shred.py` memakai stream cipher buatan sendiri tanpa autentikasi.

### Koreksi

Ringkasan Fase 1 di chat menyebut `test_live_gemini_assessment_if_configured` tidak memakai marker `live_model`. Itu keliru: marker ada. Risikonya tetap berlaku karena konfigurasi pytest tidak mengecualikan marker tersebut, sehingga `make test` dengan `.env` di tempat akan memanggil Gemini secara live.
