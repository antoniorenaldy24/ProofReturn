# Laporan Audit Ulang — ProofReturn (Versi Revisi)

Nov 2, 2026 · @Wahyuni

## Status audit ulang dan aturan kerja

Audit ulang atas versi revisi selesai: Fase 1, R, dan 2–8 telah dijalankan, dan verdict akhir ada di Bagian K. Semua bagian sudah terisi; Audit Ledger mencatat cakupan dan keterbatasan.

| Fase | Status | Cakupan |
| --- | --- | --- |
| 1 Discovery dan perubahan | Selesai (statis) | Diff terhadap versi sebelumnya, tech stack, dokumen, bukti pengujian |
| R Verifikasi perbaikan | Selesai (statis + runtime) | AUD-01..AUD-42 dan klaim sesi 08–14 |
| 2 Requirement traceability | Selesai (statis + runtime) | 137 baris RTM |
| 3 Arsitektur | Selesai (statis + runtime) |  |
| 4 Backend | Selesai (statis + runtime) |  |
| 5 Keamanan | Selesai (statis + runtime) |  |
| 6 Testing dan bukti pengujian | Selesai (39 lulus, 58 BLOCKED, 0 gagal) | 98 tes dan log yang disediakan |
| 7 Reliability | Selesai (statis + runtime) |  |
| 8 Konsistensi lintas modul | Selesai (statis) |  |

**Integritas sumber.** Arsip `ProofReturnafterRevision.zip` (43.995.117 byte, 6.286 entri, SHA-256 `ad383fad…0c16368`) diperiksa bebas path traversal dan symlink, lalu diekstrak ke salinan terpisah yang dikunci read-only. Manifest SHA-256 untuk 494 file plus hash agregat `.venv` dicatat. Versi sebelumnya (SHA-256 `5ea0a311…10ef5e`) dipakai sebagai pembanding.

**Aturan eksekusi.** Tidak ada file proyek yang diubah. Eksekusi hanya di salinan kerja terpisah tanpa `.env`, tanpa jaringan, dan tanpa menulis ke salinan asli. Kredensial tidak pernah dipakai, dan database SQLite yang ikut dalam arsip hanya dibuka read-only.

**Kerahasiaan.** Nilai kredensial tidak dikutip; perbandingan antarversi dilakukan lewat kesamaan nilai tanpa menampilkannya.

## A. Executive Summary

**Verdict: NOT READY, tetapi membaik nyata.** Revisi menutup 11 temuan dan memperbaiki 17 lainnya sebagian, terutama di pustaka domain dan kejujuran dokumen. Jalur inti produk belum berubah: endpoint uang masih mengarang hasil, refund PayPal masih stub, dan token masih bisa dipalsukan lewat jalur fallback.

| Ukuran | Audit sebelumnya | Versi revisi |
| --- | --- | --- |
| Requirement SSOT (137) | 9 PASS, 75 PARTIAL, 35 FAIL, 15 NOT IMPLEMENTED, 3 NOT VERIFIED | 10 PASS, 82 PARTIAL, 27 FAIL, 15 NOT IMPLEMENTED, 3 NOT VERIFIED |
| Temuan terbuka | 42: 3 CRITICAL, 9 HIGH, 20 MEDIUM, 8 LOW, 2 info | 38: 3 CRITICAL, 7 HIGH, 16 MEDIUM, 12 LOW, 1 info |
| Status 42 temuan lama | — | 11 teratasi, 17 sebagian, 11 belum, 1 diterima pemilik, 2 info |
| Tes | 71: 44 lulus, 27 BLOCKED, 0 gagal | 98: 39 lulus, 58 BLOCKED, 1 deselected, 0 gagal |
| Mekanisme vs §8.8 | 180/180 | 180/180 |
| Klaim VERIFIED di `rtm.csv` | 120, tidak didukung | 27: 10 didukung, 12 PARTIAL, 5 bertentangan |

**Yang membaik.** Settlement kini meng-eskalasi gross mismatch dan memakai default protektif; ledger aman dari race; dedupe webhook atomik; promosi trust satu tingkat; kalibrasi konformal tersedia; crypto-shredding memakai AEAD; token bertanda tangan dengan scoping tenant di sebagian besar endpoint; ada middleware, readiness probe, Dockerfile, dan CI. Semua ini terverifikasi runtime atau statis.

**Tiga temuan CRITICAL.**

- AUD-01: endpoint uang tetap mengembalikan nilai karangan, termasuk tranche 22157 dan `via_policy_engine: True`.
- AUD-02: `payments/client.py` identik dengan versi sebelumnya; tidak ada refund ke PayPal.
- RV-01: kunci token gagal-terbuka ke konstanta di kode (terbukti runtime) dan terkopel dengan salt hash serial.

**Temuan baru penting lainnya.** Seed audit dapat diturunkan dari `return_id` (RV-02); guard state machine diisi literal `True` (RV-03); service `api` di Compose gagal start karena driver Postgres tidak ada (AUD-07); endpoint metrik terbuka tanpa autentikasi (RV-11).

**Konteks.** Per 2 November, tersisa 10 hari menuju deadline 12 November. `.env` sengaja disertakan dan akan dirotasi pemilik di akhir build (AUD-23, diterima).

**Tindakan pertama yang disarankan:** tutup RV-01 (hitungan jam), koreksi klaim status, buat Compose bisa start, lalu sambungkan endpoint ke repository dan Policy Engine (Bagian J).

## R. Verifikasi perbaikan atas temuan audit sebelumnya

Dari 42 temuan, 11 teratasi, 17 sebagian, 11 belum, 1 diterima pemilik sebagai risiko, dan 2 informasional tetap berlaku. Perbaikan paling kuat ada di pustaka (settlement, trust, ledger, webhook processor, cache) dan di kejujuran dokumen status. Ketiga temuan CRITICAL belum tertutup: endpoint API masih mengarang hasil, refund PayPal masih stub, dan token masih bisa dipalsukan lewat jalur fallback.

| Status | Arti |
| --- | --- |
| TERATASI | Perbaikan terverifikasi (runtime bila memungkinkan) dan tidak ditemukan sisa masalah |
| SEBAGIAN | Ada perbaikan nyata, tetapi bagian penting temuan masih terbuka |
| BELUM | Kondisi yang dilaporkan masih ada |
| DITERIMA | Pemilik sengaja menerima risiko dengan rencana penanganan |

| Severity awal | TERATASI | SEBAGIAN | BELUM | DITERIMA | Info tetap |
| --- | --- | --- | --- | --- | --- |
| CRITICAL (3) | 0 | 1 | 2 | 0 | — |
| HIGH (9) | 0 | 6 | 2 | 1 | — |
| MEDIUM (20) | 8 | 9 | 3 | 0 | — |
| LOW (8) | 3 | 1 | 4 | 0 | — |
| INFORMATIONAL (2) | — | — | — | — | 2 |
| Total (42) | 11 | 17 | 11 | 1 | 2 |

**Bukti runtime baru.** Harness mekanisme tetap 180/180 cocok dengan §8.8. Harness remediasi mengonfirmasi perbaikan pada AUD-08, 09, 11, 12, 13, 17, 18, dan 39, sekaligus membuktikan token palsu diterima lewat fallback `DEFAULT_AUTH_SECRET` (AUD-21). `create_engine` dengan URL Postgres dari Compose gagal karena driver tidak ada (AUD-07).

### Status per temuan

| ID | Temuan awal | Status | Bukti verifikasi |
| --- | --- | --- | --- |
| AUD-01 | API mengarang hasil, melewati Policy Engine | BELUM | `app.py`: `r0_tranche_minor: 22157` (baris 915), `via_policy_engine: True` (391), `ret_created_01` (586, 595), `NONCE-RET-DEMO-1` (343), ID evidence pack hardcode (1066), harga keep-offer 18000 di GET vs 5320 di respond. Hanya `/v1/simulate` yang kini memanggil `decide_release` |
| AUD-02 | Refund/capture PayPal stub | BELUM | `payments/client.py` identik byte-per-byte dengan versi lama; ST-01 masih IMPLEMENTED; sesi 14 hanya menjalankan OAuth dan order create |
| AUD-03 | Artefak verifikasi di-hardcode lulus | SEBAGIAN | Rekonsiliasi kini menghitung dari input, default `handled: True` FX hilang, latensi red-team diukur. Skenario CT tautologis tetap (`return_state.py` tidak berubah) dan masih dirujuk ST-11; RPO drill dan durasi bootstrap clean-env masih berupa parameter default |
| AUD-04 | Tanpa validasi input, default permisif | SEBAGIAN | Persetujuan `false` kini ditolak 400 dan scope token divalidasi. Tetap tanpa model Pydantic; persetujuan dianggap `true` bila kedua field tidak dikirim; `declared_grade` default B; `client_blur_applied` default `true` |
| AUD-05 | State diubah tanpa state machine | SEBAGIAN | Transisi kini lewat `ReturnStateMachine.apply`, tetapi guard diisi literal `True` (`exposure_cap_ok`, `evidence_complete`, `challenge_valid`, `eligible`, `not_expired`); lihat RV-03 |
| AUD-06 | State hanya di memori | BELUM | Model SQLModel dan SQLite ada, tetapi endpoint masih memakai dict; `db_repo` hanya dipakai untuk seed dan ping |
| AUD-07 | Tidak bisa dijalankan dengan dependensi terdeklarasi | SEBAGIAN | `uvicorn`, Dockerfile, dan service `api` ditambahkan. rt: URL `postgresql://` di Compose memicu `ModuleNotFoundError: psycopg`, sehingga `create_app()` gagal saat import dan container tidak bisa start |
| AUD-08 | Gross di-settle tanpa review | TERATASI | rt: deklarasi B, verifikasi D, bukti merchant ada, tanpa reviewer menghasilkan status ESCALATED tanpa tambahan refund |
| AUD-09 | Default tidak aman INV-10/FR-32 | TERATASI | rt: default kini `False`; F dan RESTRICTED hanya muncul dengan eksklusi konformal dan konfirmasi reviewer |
| AUD-10 | Curve tampil berbeda dari engine | TERATASI | API, MCP, dan storefront memakai 0,80/0,50; nilainya masih literal, belum dari snapshot order |
| AUD-11 | Ledger tidak atomik | TERATASI | `threading.RLock`; rt: dua thread × 30000 pada capture 40000 menghasilkan total 30000 dan satu penolakan |
| AUD-12 | Webhook ditandai sebelum berhasil | TERATASI | rt: order tak dikenal menghasilkan 404 tanpa dicatat; kiriman ulang setelah order terdaftar membekukan order |
| AUD-13 | Promosi NEW ke TRUSTED | TERATASI | rt: profil NEW yang memenuhi ambang TRUSTED naik ke ESTABLISHED |
| AUD-14 | Konfigurasi tidak tersambung | BELUM | `app = create_app(demo_mode=True, mode="judge")`; settings tidak disuntikkan; `DEMO_MODE` di Compose tidak dibaca |
| AUD-15 | Fallback degradasi tidak dipanggil | BELUM | Nol pemanggil `apply_fallback_degradation` di kode non-tes |
| AUD-16 | Konstanta terduplikasi | BELUM | Cap tier di `trust.py`, urutan grade di `misdeclaration.py`, dan himpunan {EU, ID} di `policy.py` masih ada |
| AUD-17 | Lane NO\_PASSPORT berlabel FAST | TERATASI | rt: order tanpa Passport dilaporkan NO\_PASSPORT |
| AUD-18 | Re-plan beda jumlah tidak ditolak | TERATASI | rt: `IdempotencyConflictError` |
| AUD-19 | Dependensi runtime hanya untuk tes | BELUM | `jsonschema` dan `pyyaml` tetap dideklarasikan runtime dan tidak di-import kode non-tes |
| AUD-20 | Kekuatan implementasi | Tetap berlaku | Mekanisme 180/180, tanpa siklus import |
| AUD-21 | Autentikasi dapat dipalsukan | SEBAGIAN | Token HS256 dengan `compare_digest` dan TTL untuk token yang di-mint. rt: bila settings gagal dimuat, token MERCHANT\_ADMIN yang ditandatangani `DEFAULT_AUTH_SECRET` dari kode diterima dengan `exp=0`. Kunci utama = `SERIAL_HASH_SALT`, yang nilainya sama dengan template publik versi lama (RV-01) |
| AUD-22 | BOLA | SEBAGIAN | Endpoint return, receipt, evidence pack, keep-offer, dan deklarasi kini memeriksa tenant atau order dari token terverifikasi. `POST /resale/listings/{id}/order` masih bisa dipanggil principal apa pun dan memindahkan Passport ke `new_owner_ref` dari body |
| AUD-23 | Kredensial dalam arsip | DITERIMA | Pemilik sengaja menyertakan `.env` dan akan merotasi kredensial di akhir fase build. Rotasi perlu mencakup `SERIAL_HASH_SALT`, karena nilai itu kini menjadi kunci tanda tangan token |
| AUD-24 | Verifikasi webhook lewat header klien | BELUM | Endpoint masih membaca `X-PayPal-Signature-Valid` dan hanya menolak bila bernilai `false`; tanpa header, event diterima; tidak ada panggilan verify-webhook-signature. RTM menandai NFR-04 VERIFIED |
| AUD-25 | Endpoint operasional tanpa autentikasi | SEBAGIAN | Demo clock, carrier events, dan demo reset kini mensyaratkan peran. `POST /privacy/deletion-requests` masih `required=False`; demo reset tetap mengembalikan `RESET_COMPLETE` tanpa melakukan apa pun |
| AUD-26 | Salt dan kunci di-hardcode | SEBAGIAN | Default salt di `config.py` kini acak; anchor dan fraud flag mensyaratkan parameter. Konstanta baru `DEFAULT_AUTH_SECRET` di `auth/tokens.py`; kunci literal `SerialRegistry` di `journeys.py` tetap |
| AUD-27 | Cipher buatan sendiri | TERATASI | `nacl.secret.SecretBox` menggantikan `_xor_stream` (statis; eksekusi BLOCKED karena PyNaCl Windows) |
| AUD-28 | Indikator kriptografi tanpa dasar | BELUM | Receipt ditandatangani kunci acak baru setiap request tanpa publikasi kunci publik, dengan `verified: true` tetap. “Signature” Passport adalah SHA-256(kunci acak + hash) berlabel `ed25519`. Seed audit diturunkan dari `return_id` (RV-02). Blur wajah tetap berdasarkan flag klien |
| AUD-29 | Independensi reviewer banding | SEBAGIAN | Pemutus banding kini diambil dari token; reviewer asal masih diambil dari body pengaju banding (default `rev_initial_01`) |
| AUD-30 | Tanpa rate limiting | BELUM | Tidak ada pembatas laju maupun batas ukuran body |
| AUD-31 | Kredensial default Compose | SEBAGIAN | Diparameterisasi `${VAR:-default}`, tetapi nilai default tetap tertulis |
| AUD-32 | Kontrol keamanan yang baik | Tetap berlaku | Tanpa injection, SSRF, atau logging secret |
| AUD-33 | Tes mengunci nilai hardcode | SEBAGIAN | Tes API tidak lagi meng-assert 22157; tes skema 20 tabel tidak berubah; tes baru tidak memeriksa keluaran endpoint terhadap engine |
| AUD-34 | Tanpa tes integrasi, E2E, konkurensi, AZ negatif | SEBAGIAN | Ditambah tes AZ negatif, tes repository SQLite, dan tes ledger multithread. Tetap tanpa Playwright, Postgres, maupun refund Sandbox; “E2E” berupa skrip in-process |
| AUD-35 | Tes live jalan otomatis | SEBAGIAN | `addopts` mengecualikan `live_model` dan `sandbox`; CI menjalankan `-m "not live"` yang menimpa `addopts`, sehingga tes live ikut terpilih (RV-06) |
| AUD-36 | Celah kasus batas | SEBAGIAN | Tes untuk AUD-08, 12, 13, dan 17 ditambahkan; RV-01 sampai RV-04 tidak tercakup |
| AUD-37 | Tanpa observability runtime | SEBAGIAN | `ObservabilityMiddleware` terpasang dengan request ID dan log terstruktur; `/v1/ready` mem-ping DB; alert dievaluasi saat request, tanpa scheduler |
| AUD-38 | Tanpa CI dan artefak deployment | SEBAGIAN | Workflow CI dan Dockerfile ada, tetapi repo tanpa commit sehingga CI belum pernah berjalan; `python:3.12-slim` dan `uv:latest` tidak di-pin digest |
| AUD-39 | State tanpa batas | TERATASI | rt: `BoundedTTLCache` menegakkan kapasitas dan TTL |
| AUD-40 | JSON Schema tidak cocok dengan API | SEBAGIAN | Deklarasi menerima nama field skema; GET keep-offer sesuai skema. Tidak ada validasi terhadap skema; respons keep-offer respond dan Passport masih menyimpang |
| AUD-41 | Scope agen tidak ditegakkan di REST | TERATASI | REST memeriksa `declare`, `read_policy`, dan `keep_offer`; MCP memakai `verify_token` |
| AUD-42 | Drift konfigurasi, enum, model | BELUM | `refund_actions` di model DB masih tanpa `merchant_id`, `capture_id`, `paypal_debug_id`, `attempt_count`; tier `ORIGIN_WITNESSED` masih dipakai seed API |

### Status temuan dokumentasi

| ID | Status | Bukti |
| --- | --- | --- |
| DOC-01 Gate record | SEBAGIAN | Nama dan kriteria kini sesuai §27; G0 PASSED mencakup “CI green” dan “demo purchase captured” tanpa bukti run CI maupun capture |
| DOC-02 Status Sandbox | SEBAGIAN | Nilai status kini sah; deskripsi ST-09 masih “refund/order”; ST-11 masih merujuk tes CT tautologis |
| DOC-03 Klaim RTM | SEBAGIAN | 27 VERIFIED: 10 didukung penuh, 12 hanya PARTIAL, dan 5 bertentangan dengan kode (FR-61, FR-76, FR-80, NFR-04, INV-16); rincian di Bagian C |
| DOC-04 Clean-env | SEBAGIAN | Label jujur “UNIT VERIFIED”; fungsi pemeriksa masih memakai default durasi bootstrap 8,5 menit |
| DOC-05 ADR generik | BELUM | Tidak ada file ADR yang berubah |
| DOC-06 Nama model AI | BELUM | Lima nama berbeda: `.env` gemini-3.6-flash; `config.py` dan `models.yaml` gemini-3-flash-preview; `models.yaml` gemini-3.1-flash-lite-preview; ADR-028 gemini-1.5/2.0-flash |
| DOC-07 Struktur repo | SEBAGIAN | `testpaths` diperbaiki; struktur lain tidak berubah |
| DOC-08 Regenerasi RTM di SSOT | BELUM | SSOT tidak berubah |
| DOC-09 Repo tanpa commit | BELUM | `.git/objects` kosong |
| DOC-10 Penomoran versi | BELUM | Tidak berubah |

### Temuan baru dari verifikasi

Detail lengkap akan masuk Bagian E; ringkasnya:

- **RV-01 Kunci token fail-open dan dipakai ulang.** Fallback ke konstanta di kode bila settings gagal dimuat (terbukti runtime); kunci sama dengan salt hash serial; `exp` opsional.
- **RV-02 Seed audit dapat diturunkan publik.** `seed_platform = SHA-256("seed_platform_" + return_id)`, sehingga shopper bisa menghitung dan “menggiling” hasil audit draw; bertentangan dengan FR-95 dan INV-16 yang ditandai VERIFIED.
- **RV-03 Guard state machine diisi literal `True`.** Handler keep-offer menjalankan `SUBMIT_EVIDENCE` dan `FINISH_ASSESSMENT` atas nama token agen, sehingga larangan INV-12 terlewati secara efektif.
- **RV-04 Harga keep-offer tidak konsisten.** GET menawarkan 18000, sedangkan respond mencatat 5320; keduanya hardcode.
- **RV-05 Pemindai secret secara struktural buta.** `scan_secrets.py` mengecualikan `.env` dan memeriksa status tracking git di repo tanpa commit.
- **RV-06 CI menimpa pengecualian tes live.** `-m "not live"` menggantikan `addopts`.
- **RV-07 Gate AG-01 setara lempar koin.** rt: kalibrasi konformal yang benar menghasilkan cakupan sekitar target (0,886–0,922 untuk route; 0,979–0,986 untuk accuse), sehingga gate hanya lulus 2 dari 5 ulangan karena tidak ada margin.
- **RV-08 Skema DB dibuat ulang saat startup.** `SQLModel.metadata.create_all` di konstruktor repository melewati Alembic, dan file SQLite berisi data seed ikut disalin ke image.

## B. Project Understanding: perubahan sejak versi sebelumnya

Revisi menambahkan token bertanda tangan, model database dan migrasi Alembic, middleware observability, Dockerfile, workflow CI, dan 27 tes baru; dokumen status juga ditulis ulang jauh lebih jujur. Namun jalur inti, yaitu keputusan di endpoint API, refund ke PayPal, dan frontend, belum berubah secara substansial.

### Ringkasan perubahan

| Kategori | Jumlah | Isi utama |
| --- | --- | --- |
| File ditambahkan | 28 | `.github/workflows/ci.yml`, `alembic.ini`, `backend/auth/tokens.py`, `backend/api/middleware.py`, `backend/db/models.py`, `backend/db/repository.py`, `backend/migrations/`, `backend/ai/calibration/conformal.py`, `backend/domain/cache.py`, `infra/Dockerfile`, `scripts/scan_secrets.py`, 4 file tes remediasi, bukti sesi 08–14, `data/proofreturn.db`, salinan laporan audit sebelumnya |
| File diubah | 40 | `backend/api/app.py` (923 menjadi 1.449 baris), settlement, trust, ledger, webhook, rekonsiliasi, failure modes, drill, crypto-shred, config, MCP, `release.py`, Compose, `pyproject.toml`, `uv.lock`, `rtm.csv`, gate record, `sandbox-tests.md` |
| File dihapus | 0 | — |
| Tidak berubah tetapi relevan | — | `backend/payments/client.py` (stub refund), `backend/domain/return_state.py` (skenario CT), empat aplikasi frontend kecuali nilai curve storefront, SSOT |

### Tech stack: sebelum dan sesudah

| Lapisan | Versi sebelumnya | Versi revisi |
| --- | --- | --- |
| Server ASGI | Tidak ada | `uvicorn` dideklarasikan; service `api` di Compose; `infra/Dockerfile` |
| Persistensi | Tidak ada | SQLModel + SQLAlchemy, default SQLite `data/proofreturn.db`; Alembic `0001` dengan 20 tabel; API memakai repository hanya untuk seed dan ping |
| Autentikasi | Token teks biasa | Token HMAC-SHA256 di `backend/auth/tokens.py`; kunci diambil dari `SERIAL_HASH_SALT`, dengan fallback konstanta di kode |
| Observability | Hanya dipakai tes | `ObservabilityMiddleware`, `/v1/ready`, `/v1/metrics`, `/v1/ops/alerts` |
| CI | Tidak ada | Workflow GitHub Actions; repo tanpa commit sehingga belum ada riwayat run |
| Kalibrasi konformal | Tidak ada | `backend/ai/calibration/conformal.py` (210 baris) |
| PayPal | OAuth + order create live; refund stub | Tidak berubah |
| Frontend | Fungsi render string | Tidak berubah, kecuali curve storefront kini 0,80/0,50 |
| Venv | Windows | Masih Windows (Python 3.12.13); tambahan SQLAlchemy dengan modul Cython `.pyd` |

### Dokumentasi dan bukti pengujian yang disediakan

| Dokumen | Isi | Catatan awal |
| --- | --- | --- |
| `docs/rtm.csv` | 27 VERIFIED, 48 IMPLEMENTED, 62 SPECIFIED | Sebelumnya 120 VERIFIED; kini jauh lebih konservatif |
| `docs/gates/final-acceptance.md` | G0 PASSED, G1–G2 IN PROGRESS, G3–G6 PENDING | Nama dan kriteria kini sesuai §27; status G0 masih perlu diverifikasi |
| `docs/gates/clean-env-2026-10-31.md` | “UNIT VERIFIED” | Diakui belum berupa run di mesin bersih |
| `docs/sandbox-tests.md` | ST-09 VERIFIED; ST-01, 06, 10–13 IMPLEMENTED; sisanya SPECIFIED | Nilai status kini sah menurut §20.1; ST-11 masih merujuk tes CT lama |
| `docs/evidence/session-08..13` | Klaim remediasi R1–R6 per temuan AUD | Diverifikasi di Bagian R |
| `docs/evidence/session-14` | Gemini live (`gemini-3.6-flash`), OAuth dan order create di Sandbox, Alembic, readiness probe; 96 tes lulus offline | Tidak ada refund live |
| `data/proofreturn.db` | SQLite 22 tabel berisi data seed: 1 merchant, 2 order, 6 staff, 2 shopper | Ikut disalin ke image Docker |
| Laporan audit sebelumnya | Ditambahkan di root repo | — |

Inventaris tes kini 98 fungsi di 15 file (sebelumnya 71 di 11 file), dan `addopts` mengecualikan marker `live_model` serta `sandbox`.

### Perhatian awal

Poin di bawah sudah terkonfirmasi secara statis; dampak dan severity finalnya ditetapkan di Bagian R dan F.

- **Kredensial tidak dirotasi.** `.env` masih ikut dalam arsip, dan semua kredensial serta salt di dalamnya identik dengan versi sebelumnya (dibandingkan tanpa menampilkan nilai).
- **Kunci token sudah pernah terbuka.** Kunci HMAC token diambil dari `SERIAL_HASH_SALT`, yang nilainya sama dengan template publik `.env.example` versi sebelumnya; bila settings gagal dimuat, kodenya memakai konstanta `DEFAULT_AUTH_SECRET`.
- **Pemindai secret buta terhadap `.env`.** `scripts/scan_secrets.py` mengecualikan `.env`, sehingga klaim “0 credentials detected” tidak mencakup file rahasia yang sebenarnya.
- **Nilai karangan masih ada di API.** Antara lain `r0_tranche_minor: 22157`, `via_policy_engine: True`, `ret_created_01`, `NONCE-RET-DEMO-1`, dan harga keep-offer 5320.
- **Repo tanpa commit.** Klaim CI hijau belum bisa dibuktikan.

### Keterbatasan

Venv masih berupa build Windows, sehingga tes yang membutuhkan pydantic, FastAPI, SQLModel, PyNaCl, atau Hypothesis kemungkinan tetap BLOCKED. Pendekatannya sama seperti audit sebelumnya: modul pure-Python dijalankan langsung, fungsi tertentu diekstrak via AST, dan test double berlabel dipakai bila perlu; tidak ada panggilan jaringan.

## C. SSOT Compliance Report — Requirement Traceability Matrix versi revisi

Dari 137 requirement, 10 kini PASS, 82 PARTIAL, 27 FAIL, 15 NOT IMPLEMENTED, dan 3 NOT VERIFIED. Sembilan baris membaik dibanding audit sebelumnya, terutama di autentikasi, isolasi tenant, dan guard state machine, tetapi tidak ada baris yang naik dari NOT IMPLEMENTED. Dari 27 klaim VERIFIED di `rtm.csv`, 10 didukung penuh, 12 hanya PARTIAL, dan 5 bertentangan dengan kode.

Rubrik status sama dengan audit sebelumnya: PASS berarti perilaku terverifikasi dan tersambung ke jalur sistem yang dituntut requirement; PARTIAL berarti logika ada tetapi tidak tersambung atau hanya sebagian terpenuhi; FAIL berarti implementasi bertentangan dengan requirement, termasuk nilai hardcode atau kontrol palsu. Singkatan **rt** berarti diverifikasi runtime dalam audit ini.

| Status | Audit sebelumnya | Audit ulang | Perubahan |
| --- | --- | --- | --- |
| PASS | 9 | 10 | +1 |
| PARTIAL | 75 | 82 | +7 |
| FAIL | 35 | 27 | −8 |
| NOT IMPLEMENTED | 15 | 15 | 0 |
| NOT VERIFIED | 3 | 3 | 0 |

### Baris yang berubah status

| ID | Sebelumnya | Sekarang | Alasan |
| --- | --- | --- | --- |
| FR-08 | FAIL | PARTIAL | API dan MCP kini menampilkan curve 0,80/0,50 yang sama dengan engine; UI nyata belum ada |
| FR-45 | FAIL | PARTIAL | Token HS256 ber-TTL dan `POST /v1/agent/tokens` ada; jalur fallback kunci publik (RV-01) |
| FR-52 | FAIL | PARTIAL | `/v1/simulate` memanggil `decide_release`, tetapi dengan policy default dan metrik biaya/latensi hardcode |
| FR-81 | FAIL | PARTIAL | Demo clock kini butuh MERCHANT\_ADMIN dan tercatat di log; offset belum dipakai timer |
| NFR-11 | FAIL | PARTIAL | Scoping tenant/order di sebagian besar endpoint; endpoint resale masih terbuka |
| NFR-14 | FAIL | PARTIAL | Rekonsiliasi kini menghitung dari input; belum dijadwalkan maupun tersambung ke data |
| INV-04 | FAIL | PARTIAL | Transisi lewat state machine, tetapi guard diisi literal `True` (RV-03) |
| INV-10 | PARTIAL | PASS | rt: default protektif; F dan RESTRICTED hanya dengan eksklusi konformal dan konfirmasi reviewer; tidak ada jalur yang melanggar |
| INV-12 | FAIL | PARTIAL | Agen diblokir di challenge dan evidence; handler keep-offer menjalankan `SUBMIT_EVIDENCE` atas nama agen |

### Klaim VERIFIED di rtm.csv

| Penilaian audit | Jumlah | Requirement |
| --- | --- | --- |
| Didukung (PASS) | 10 | FR-31, FR-43, FR-44, FR-89, INV-05, INV-07, INV-08, INV-10, INV-15, INV-18 |
| Hanya PARTIAL | 12 | FR-09, FR-37, FR-45, FR-72, FR-74, FR-82, FR-91, NFR-08, NFR-11, INV-01, INV-04, INV-12 |
| Bertentangan (FAIL) | 5 | FR-61, FR-76, FR-80, NFR-04, INV-16 |

**Bukti eksekusi tes untuk matriks ini.** 39 tes lulus (14 native, 25 indikatif dengan test double `pydantic` dan stub Hypothesis), 58 BLOCKED karena FastAPI, SQLModel, PyNaCl, jsonschema, atau Hypothesis native tidak tersedia, 1 tes Sandbox di-deselect oleh `addopts`, dan tidak ada yang gagal. Rincian di Bagian G.

### Matriks lengkap: FR-01 – FR-52

| ID | Sebelumnya | Sekarang | Bukti |
| --- | --- | --- | --- |
| FR-01 | PARTIAL | PARTIAL | Passport API kini punya field `signature` dan `events`, tetapi tanpa capture PayPal dan signature-nya palsu |
| FR-02 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada object storage |
| FR-03 | PARTIAL | PARTIAL | OCR tetap regex atas teks |
| FR-04 | PARTIAL | PARTIAL | Challenge API masih `NONCE-RET-DEMO-1` |
| FR-05 | PARTIAL | PARTIAL | Pustaka Ed25519 benar; API memakai hash berlabel ed25519 |
| FR-06 | PARTIAL | PARTIAL | Tidak berubah |
| FR-07 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada tracking |
| FR-08 | FAIL | PARTIAL | Curve benar di API dan MCP; tanpa UI nyata |
| FR-09 | PARTIAL | PARTIAL | Curve literal, bukan snapshot order; diklaim VERIFIED |
| FR-10 | PARTIAL | PARTIAL | rt: engine masih menerima curve yang melanggar cap |
| FR-11 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada UI |
| FR-12 | PARTIAL | PARTIAL | Actor dan persetujuan kini dicatat; tanpa timestamp; di memori |
| FR-13 | PARTIAL | PARTIAL | Tidak berubah |
| FR-14 | FAIL | FAIL | Persetujuan dianggap `true` bila field tidak dikirim |
| FR-15 | PARTIAL | PARTIAL | Tidak berubah |
| FR-16 | FAIL | FAIL | Blur tetap berdasarkan flag klien (default `true`) |
| FR-17 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada frontend |
| FR-18 | PARTIAL | PARTIAL | Tidak berubah |
| FR-19 | PARTIAL | PARTIAL | Endpoint evidence tetap mengembalikan FAST |
| FR-20 | FAIL | FAIL | Latensi kini diukur, tetapi kasus red-team tetap sintetis |
| FR-21 | PARTIAL | PARTIAL | rt 180/180; tidak dipanggil endpoint return |
| FR-22 | NOT IMPLEMENTED | NOT IMPLEMENTED | Refund tetap stub |
| FR-23 | PARTIAL | PARTIAL | rt: eskalasi gross diperbaiki; tidak tersambung ke API |
| FR-24 | PARTIAL | PARTIAL | Tanpa timer |
| FR-25 | PARTIAL | PARTIAL | Konformal dan guard ada di pustaka; endpoint audit masih echo |
| FR-26 | PARTIAL | PARTIAL | Tidak berubah |
| FR-27 | PARTIAL | PARTIAL | Tabel `decisions` ada tetapi tidak dipakai |
| FR-28 | PARTIAL | PARTIAL | Tidak berubah |
| FR-29 | PARTIAL | PARTIAL | Peran kini diperiksa; endpoint masih echo |
| FR-30 | PARTIAL | PARTIAL | Tidak berubah |
| FR-31 | PASS | PASS | Tidak berubah |
| FR-32 | PARTIAL | PARTIAL | Default kini protektif; tidak tersambung |
| FR-33 | FAIL | FAIL | ID evidence pack tetap hardcode |
| FR-34 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada client Disputes |
| FR-35 | FAIL | FAIL | Isi pack hardcode |
| FR-36 | PARTIAL | PARTIAL | Tidak berubah |
| FR-37 | PARTIAL | PARTIAL | Pustaka benar; API menawarkan 18000 lalu mencatat 5320; diklaim VERIFIED |
| FR-38 | PARTIAL | PARTIAL | Tidak berubah |
| FR-39 | FAIL | FAIL | Tetap “partial refund initiated” tanpa refund |
| FR-40 | PARTIAL | PARTIAL | Tidak berubah |
| FR-41 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada capture PayPal |
| FR-42 | PARTIAL | PARTIAL | Pemilik baru diambil dari body principal mana pun |
| FR-43 | PASS | PASS | Denylist PII tetap berlaku |
| FR-44 | PASS | PASS | Tidak berubah |
| FR-45 | FAIL | PARTIAL | Token ber-TTL dan endpoint penerbitan ada; fallback kunci publik (RV-01) |
| FR-46 | PARTIAL | PARTIAL | Harga keep-offer hardcode |
| FR-47 | PARTIAL | PARTIAL | Log request terstruktur; tanpa field khusus aksi agen |
| FR-48 | NOT VERIFIED | NOT VERIFIED | Tidak bisa dicek offline |
| FR-49 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada console |
| FR-50 | FAIL | FAIL | `via_policy_engine: True` tanpa memanggil engine |
| FR-51 | FAIL | FAIL | `POST /policies` masih echo |
| FR-52 | FAIL | PARTIAL | `decide_release` dipanggil dengan policy default; metrik biaya dan latensi hardcode |

### Matriks lengkap: FR-53 – FR-103

| ID | Sebelumnya | Sekarang | Bukti |
| --- | --- | --- | --- |
| FR-53 | PARTIAL | PARTIAL | Tidak berubah |
| FR-54 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada |
| FR-55 | PARTIAL | PARTIAL | Tidak berubah |
| FR-56 | PARTIAL | PARTIAL | Tidak berubah |
| FR-57 | PARTIAL | PARTIAL | Promosi diperbaiki di pustaka; tidak tersambung |
| FR-58 | PARTIAL | PARTIAL | rt 30/30 timing; tidak tersambung |
| FR-59 | PARTIAL | PARTIAL | Tidak berubah |
| FR-60 | PARTIAL | PARTIAL | rt cocok; tidak tersambung |
| FR-61 | FAIL | FAIL | Seed audit diturunkan dari `return_id` (RV-02); diklaim VERIFIED |
| FR-62 | PARTIAL | PARTIAL | Tidak berubah |
| FR-63 | FAIL | FAIL | Tier Passport kini diambil dari body (default FULL), bukan dari value band |
| FR-64 | PARTIAL | PARTIAL | Seal tetap berupa hash nonce kiriman klien |
| FR-65 | PARTIAL | PARTIAL | Tidak berubah |
| FR-66 | PARTIAL | PARTIAL | Guard retake diisi literal `True` |
| FR-67 | PARTIAL | PARTIAL | Tidak berubah |
| FR-68 | PARTIAL | PARTIAL | Tidak berubah |
| FR-69 | FAIL | FAIL | Reviewer asal tetap dari body; tanpa batas 14 hari maupun refund kompensasi |
| FR-70 | PARTIAL | PARTIAL | Tidak berubah |
| FR-71 | PARTIAL | PARTIAL | Tanpa timer |
| FR-72 | PARTIAL | PARTIAL | Hanya di pustaka state machine; diklaim VERIFIED |
| FR-73 | PARTIAL | PARTIAL | Tidak berubah |
| FR-74 | PARTIAL | PARTIAL | rt: label lane benar; tidak tersambung; diklaim VERIFIED |
| FR-75 | PARTIAL | PARTIAL | rt: processor diperbaiki; endpoint webhook tidak memanggilnya |
| FR-76 | FAIL | FAIL | Kunci acak per request, `verified: true` tetap; diklaim VERIFIED |
| FR-77 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada portal |
| FR-78 | PARTIAL | PARTIAL | Kelayakan tidak diperiksa API |
| FR-79 | PARTIAL | PARTIAL | Tidak berubah |
| FR-80 | FAIL | FAIL | Badge REPLAYED pada hasil hardcode; diklaim VERIFIED |
| FR-81 | FAIL | PARTIAL | Kini butuh MERCHANT\_ADMIN dan tercatat di log; offset belum dipakai timer |
| FR-82 | PARTIAL | PARTIAL | AEAD SecretBox; endpoint penghapusan tanpa autentikasi wajib; diklaim VERIFIED |
| FR-83 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tetap tanpa TSA |
| FR-84 | PARTIAL | PARTIAL | Tidak berubah |
| FR-85 | FAIL | FAIL | Service `api` di Compose gagal start (driver psycopg) |
| FR-86 | NOT VERIFIED | NOT VERIFIED | Provider Gemini tidak berubah |
| FR-87 | PARTIAL | PARTIAL | rt 180/180; endpoint evidence tetap 22157 |
| FR-88 | PARTIAL | PARTIAL | Endpoint pembatalan masih tidak ada |
| FR-89 | PASS | PASS | rt tetap |
| FR-90 | FAIL | FAIL | Tidak berubah |
| FR-91 | PARTIAL | PARTIAL | rt: tanpa lompatan tier; tidak tersambung; diklaim VERIFIED |
| FR-92 | PARTIAL | PARTIAL | Tidak berubah |
| FR-93 | PARTIAL | PARTIAL | Tidak berubah |
| FR-94 | PARTIAL | PARTIAL | Salt kini wajib sebagai parameter |
| FR-95 | FAIL | FAIL | Seed dapat diturunkan publik (RV-02) |
| FR-96 | FAIL | FAIL | Kini terautentikasi, tetapi `demo_mode=True` di-hardcode pada objek `app` |
| FR-97 | PARTIAL | PARTIAL | Tanpa timer |
| FR-98 | FAIL | FAIL | `self_test_passed` default `true` |
| FR-99 | PARTIAL | PARTIAL | Tidak berubah |
| FR-100 | PARTIAL | PARTIAL | Tidak berubah |
| FR-101 | PARTIAL | PARTIAL | Tidak berubah |
| FR-102 | PARTIAL | PARTIAL | Tidak berubah |
| FR-103 | PARTIAL | PARTIAL | Tidak berubah |

### Matriks lengkap: NFR dan INV

| ID | Sebelumnya | Sekarang | Bukti |
| --- | --- | --- | --- |
| NFR-01 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada refund |
| NFR-02 | NOT VERIFIED | NOT VERIFIED | Tidak diukur live |
| NFR-03 | PARTIAL | PARTIAL | Tidak berubah |
| NFR-04 | FAIL | FAIL | Endpoint masih membaca header klien; diklaim VERIFIED |
| NFR-05 | PARTIAL | PARTIAL | Penghapusan tanpa autentikasi wajib |
| NFR-06 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada frontend |
| NFR-07 | FAIL | FAIL | Service `api` di Compose gagal start |
| NFR-08 | PARTIAL | PARTIAL | Log terstruktur dengan request ID dan trace ID; tanpa `return_id`, `decision_id`, `paypal_debug_id`; diklaim VERIFIED |
| NFR-09 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada frontend |
| NFR-10 | NOT IMPLEMENTED | NOT IMPLEMENTED | Tidak ada frontend |
| NFR-11 | FAIL | PARTIAL | Scoping tenant di sebagian besar endpoint; resale terbuka; fallback kunci token; diklaim VERIFIED |
| NFR-12 | PARTIAL | PARTIAL | Image Docker tidak di-pin digest |
| NFR-13 | FAIL | FAIL | RPO tetap parameter simulasi |
| NFR-14 | FAIL | PARTIAL | Logika rekonsiliasi nyata atas input; belum dijadwalkan |
| NFR-15 | FAIL | FAIL | Durasi bootstrap tetap parameter default |
| NFR-16 | FAIL | FAIL | `/simulate` memakai konstanta 1,2 s dan 0,05 sen |
| INV-01 | PARTIAL | PARTIAL | rt: lock ledger mencegah race; constraint DB tidak terpakai; diklaim VERIFIED |
| INV-02 | PARTIAL | PARTIAL | Tidak berubah |
| INV-03 | PARTIAL | PARTIAL | Tidak berubah |
| INV-04 | FAIL | PARTIAL | Transisi lewat state machine dengan guard literal `True` (RV-03); diklaim VERIFIED |
| INV-05 | PASS | PASS | Tidak berubah |
| INV-06 | PARTIAL | PARTIAL | Tidak berubah |
| INV-07 | PASS | PASS | Tidak berubah |
| INV-08 | PASS | PASS | Tidak berubah |
| INV-09 | FAIL | FAIL | `chain_valid: True` dan signature palsu di API |
| INV-10 | PARTIAL | PASS | rt: default protektif dan uji konformal; tidak ada jalur yang melanggar |
| INV-11 | FAIL | FAIL | rt: curve yang melanggar cap tetap diterima |
| INV-12 | FAIL | PARTIAL | Agen diblokir di challenge dan evidence; keep-offer menjalankan `SUBMIT_EVIDENCE` atas nama agen; diklaim VERIFIED |
| INV-13 | PARTIAL | PARTIAL | Blur tetap berdasarkan flag klien |
| INV-14 | FAIL | FAIL | Tranche 22157 untuk return apa pun; `exposure_cap_ok=True` literal |
| INV-15 | PASS | PASS | Tidak berubah |
| INV-16 | FAIL | FAIL | Seed dapat diturunkan (RV-02); diklaim VERIFIED |
| INV-17 | PARTIAL | PARTIAL | Tidak berubah |
| INV-18 | PASS | PASS | rt tetap |

## D. Architecture Compliance Report

Arsitektur bergerak ke arah yang benar: kini ada lapisan auth, middleware, model DB, migrasi, dan server ASGI. Namun lapisan baru itu belum berada di jalur runtime keputusan uang. Settlement, trust, kalibrasi konformal, ledger, webhook processor, dan MCP tidak terjangkau dari endpoint mana pun.

&#91;embedded content: arsitektur aktual versi revisi\]

Kotak hijau adalah pustaka yang terbukti benar saat runtime tetapi tidak dipanggil endpoint; kotak putus-putus di bawah adalah komponen SSOT yang belum ada atau belum bisa berjalan.

### Status penyimpangan sebelumnya

| ID | Penyimpangan | Status | Bukti |
| --- | --- | --- | --- |
| ARC-01 | API tidak memakai engine, state machine, payments, MCP | SEBAGIAN | State machine kini dipakai dengan guard literal `True`; `release.py` hanya di `/v1/simulate`; modul lain tidak terjangkau dari API |
| ARC-02 | Integrasi uang PayPal | BELUM | `payments/client.py` identik dengan versi lama |
| ARC-03 | Model autentikasi API-04 | SEBAGIAN | Token HS256 untuk staff, shopper, agen, dan service; tanpa penerbitan identitas; kunci terikat ke salt serial dengan fallback konstanta (RV-01) |
| ARC-04 | Tidak ada persistensi | SEBAGIAN | Model, repository 15 metode, dan migrasi ada; API hanya memanggil `ping` dan `seed_demo_data` |
| ARC-05 | Workflow dan timer | BELUM | Tidak ada scheduler maupun job runner |
| ARC-06 | Server ASGI | SEBAGIAN | `uvicorn`, Dockerfile, dan service `api` ada; start di Compose gagal karena driver psycopg |
| ARC-07 | Frontend | BELUM | Masih fungsi render string |
| ARC-08 | Kontrak API berbasis Pydantic | BELUM | Nol `BaseModel` di API; 20 pemanggilan `await request.json()` |
| ARC-09 | DB tanpa RLS dan migrasi | SEBAGIAN | Alembic dan SQL 20 tabel kini ada; nol RLS; drift model–migrasi (ARC-15) |
| ARC-10 | Konfigurasi tidak tersambung | BELUM | `create_app(demo_mode=True, mode="judge")`; settings hanya dipakai `auth/tokens.py` untuk kunci |
| ARC-11 | Penyedia AI tanpa Change Control | BELUM | Tetap Gemini; kini lima nama model berbeda |
| ARC-12 | MCP bukan server | BELUM | Tetap class Python tanpa SDK dan transport |
| ARC-13 | Arah dependensi terbalik | BELUM | `domain/journeys.py` meng-import payments dan agent gateway; `config.py` meng-import `payments.client` |

### Penyimpangan baru

| ID | Penyimpangan | Bukti | Severity indikatif |
| --- | --- | --- | --- |
| ARC-14 | Dua sumber state | DB di-seed saat startup tetapi tidak pernah diperbarui endpoint; `/v1/ready` melaporkan DB sehat sementara data operasional hanya ada di dict | HIGH |
| ARC-15 | Skema tidak dikelola migrasi | `SQLModel.metadata.create_all` di konstruktor repository; model berisi 22 tabel, migrasi hanya 20 (tanpa `agent_tokens` dan `resale_listings`) | MEDIUM |
| ARC-16 | SQLite sebagai default, bukan PostgreSQL 16 | Default `sqlite:///data/proofreturn.db`; URL Postgres di Compose tanpa driver; RLS tidak tersedia di SQLite | MEDIUM |
| ARC-17 | Tidak ada penerbitan identitas | `mint_staff_token` dan `mint_shopper_token` hanya dipanggil dari kode dan tes; tidak ada endpoint login maupun magic link | MEDIUM |

### Database (§30)

| Aturan | Temuan |
| --- | --- |
| DB-01 BIGINT + `currency` | Nol `BigInteger`; hanya 1 kolom `currency` |
| DB-02 `ON DELETE RESTRICT` | Tidak ada |
| DB-03 dan INV-01 | CHECK `confirmed_refunded_minor + pending_refunded_minor <= capture_amount_minor` dan `appeal_reviewer_id <> original_reviewer_id` ada di migrasi, tetapi tidak berlaku karena API tidak menulis ke DB |
| DB-07 kolom `version` | Tidak ada |
| ADR-012 RLS | Tidak ada |
| MG-01 Alembic | Ada, tetapi tidak sinkron dengan model |

### Konvensi API (§28.1)

| Konvensi | Status | Bukti |
| --- | --- | --- |
| API-01 base `/v1` | Sesuai | 39 route |
| API-02 UUIDv7 | Tidak | ID demo seperti `ret_created_01` |
| API-03 uang `{amount_minor, currency}` | Sebagian | Hanya GET keep-offer |
| API-04 jenis token | Sebagian | Lihat ARC-03 dan ARC-17 |
| API-05 di luar scope menjadi 404 | Sebagian | Sebagian besar endpoint; resale terbuka |
| API-06 `Idempotency-Key` | Tidak | 1 dari 22 endpoint POST |
| API-07 problem+json | Sebagian | 9 dari 14 kode error di luar katalog §28.2 |
| API-08 `If-Match` | Tidak | Tidak ada |
| API-10 `X-Request-Id` | Sesuai | Ditambahkan middleware |
| API-11 OpenAPI dari Pydantic | Tidak | Tanpa model request dan response |

Endpoint `POST /v1/returns/{id}/cancel` (FR-88) masih tidak ada, dan seluruh route tetap berada di satu file tanpa `APIRouter`.

### Perubahan kepatuhan ADR

| ADR | Sebelumnya | Sekarang |
| --- | --- | --- |
| ADR-006 Outbox dan request ID | Ledger in-memory | Ledger dengan lock, tetap in-memory dan tidak dipanggil endpoint |
| ADR-017 Konformal | Tidak ada | Diimplementasikan; rt: cakupan sekitar target; tidak tersambung |
| ADR-018, ADR-026 Commit–reveal dan receipt | API palsu | API memakai pustaka, tetapi seed dapat diturunkan dan kunci receipt efemeral (RV-02, AUD-28) |
| ADR-019 Crypto-shredding | Cipher kustom | AEAD SecretBox |
| ADR-001, 003, 010, 012, 021 | Tidak dipenuhi | Tidak berubah |

## E. Technical Findings versi revisi

Versi revisi memiliki 38 temuan terbuka ditambah 1 catatan informasional: 3 CRITICAL, 7 HIGH, 16 MEDIUM, dan 12 LOW. Tiga belas di antaranya baru (RV-01 sampai RV-09 dari Fase 4, RV-11 sampai RV-13 dari Fase 5, RV-14 dari Fase 7); sisanya adalah temuan lama yang masih terbuka dengan severity yang dinilai ulang. Temuan yang sudah teratasi dan risiko yang diterima pemilik tidak dihitung (lihat Bagian R).

| Severity | Audit sebelumnya | Versi revisi |
| --- | --- | --- |
| CRITICAL | 3 | 3 |
| HIGH | 9 | 7 |
| MEDIUM | 20 | 16 |
| LOW | 8 | 12 |
| INFORMATIONAL | 2 | 1 |

### Temuan baru

#### RV-01 · CRITICAL · Security — Kunci tanda tangan token fail-open dan dipakai ulang

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/auth/tokens.py`: 36–52 (`_get_signing_secret`), 113–182 (`verify_token`) |
| Bukti | rt: saat settings gagal dimuat, token MERCHANT\_ADMIN yang ditandatangani `DEFAULT_AUTH_SECRET` (konstanta di kode) diterima dengan `exp=0`. `except Exception: pass` di baris 49–50 menelan error lalu jatuh ke konstanta. Dalam konfigurasi normal, kunci adalah `SERIAL_HASH_SALT`, yang nilainya sama dengan template publik `.env.example` versi sebelumnya. |
| Penjelasan | Autentikasi gagal-terbuka ke kunci publik; satu nilai dipakai untuk dua tujuan (salt hash serial dan MAC token); `exp` opsional sehingga token tanpa `exp` tidak pernah kedaluwarsa. |
| Skenario eksploitasi | Konfigurasi apa pun yang membuat `ProofReturnSettings()` melempar error membuat server menerima token yang dibuat siapa pun dari kode sumber. Dengan konfigurasi saat ini, pemegang template lama juga bisa membuat token sah. |
| Dampak | Pengambilalihan peran staff lintas tenant, sama seperti AUD-21 sebelumnya. |
| Rekomendasi | Gagal-tertutup (aplikasi menolak start tanpa kunci); kunci token terpisah, misalnya `AUTH_SIGNING_KEY` minimal 32 byte dari secret store; wajibkan `exp`; rotasi bersama kredensial lain di akhir build. |
| Confidence | High |

#### RV-02 · HIGH · Security — Seed audit dapat diturunkan dari return\_id

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 968–1040 (handler receipts) |
| Bukti | `seed_platform = SHA-256("seed_platform_" + return_id)`; `nonce_shopper` default `shopper_nonce_default`. |
| Penjelasan | FR-95 dan INV-16 mensyaratkan seed rahasia yang dikomit sebelum nonce shopper diterima. Seed yang bisa dihitung siapa pun membuat hasil draw dapat diprediksi. |
| Skenario eksploitasi | Shopper menghitung nilai draw untuk banyak kandidat nonce dan memilih nonce yang menghindari audit sebelum mengirim barang. |
| Dampak | Audit acak, yang menjadi dasar keamanan `X_max`, bisa dihindari. `rtm.csv` menandai FR-61 dan INV-16 VERIFIED. |
| Rekomendasi | Seed acak 32 byte per return dari `secrets`, disimpan terenkripsi, dikomit sebelum nonce diterima, dan dibuka hanya saat check-in. |
| Confidence | High |

#### RV-03 · HIGH · Functional — Guard state machine diisi literal True

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 778–850 (deklarasi), 851–919 (evidence), 920–967 (dropoff), 1116–1195 (keep-offer respond) |
| Bukti | `within_window=True`, `consent_recorded=True`, `evidence_complete=True`, `challenge_valid=True`, `exposure_cap_ok=True`, `eligible=True`, dan `not_expired=True` dikirim sebagai literal ke `ReturnStateMachine.apply`. Handler keep-offer menjalankan `SUBMIT_EVIDENCE` dan `FINISH_ASSESSMENT` untuk return berstatus DECLARED, termasuk untuk token agen. |
| Penjelasan | Guard hanya bermakna bila nilainya dihitung dari data; literal `True` membuat state machine hanya memeriksa urutan state. Temuan ini melanjutkan AUD-05. |
| Dampak | INV-04 dan INV-14 tidak ditegakkan, karena cap exposure tidak dicek sebelum approval. Agen bisa memajukan return melewati tahap bukti, berlawanan dengan maksud INV-12. |
| Rekomendasi | Hitung setiap guard dari data nyata: cap exposure dari ledger, kelengkapan bukti dari evidence store, kelayakan keep-offer dari `keep_offer.py`; larang token agen memicu transisi bukti. |
| Confidence | High |

#### RV-04 · MEDIUM · Functional — Harga keep-offer berbeda antara tawaran dan pencatatan

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 1108 (GET, 18000), 1180 dan 1191 (respond, 5320) |
| Bukti | GET menawarkan `posted_price.amount_minor` 18000 dengan `expires_at` tetap; respond mencatat `posted_price_minor` 5320 dan pesan “partial refund initiated” tanpa refund. |
| Penjelasan | Kedua angka hardcode dan tidak dihitung dari `keep_offer.py`. |
| Dampak | Shopper atau agen menerima tawaran yang berbeda dari yang dicatat; untuk barang murah, harga tawaran bisa melampaui refund yang terutang. Ini bertentangan dengan klaim FR-37 VERIFIED. |
| Rekomendasi | Hitung tawaran dengan `compute_keep_offer`, simpan, lalu pakai angka yang sama saat respons. |
| Confidence | High |

#### RV-05 · MEDIUM · Security — Pemindai secret secara struktural tidak bisa menemukan secret yang dikirim

| Atribut | Detail |
| --- | --- |
| Lokasi | `scripts/scan_secrets.py` |
| Bukti | `.env` dikecualikan dari pemindaian; pemeriksaan “tidak di-track git” berjalan di repo tanpa commit; `except Exception: pass` di baris 57–58. |
| Penjelasan | Laporan “0 credentials detected” di sesi 08 tidak mencakup file yang benar-benar berisi secret maupun artefak yang dibagikan (zip, image Docker). |
| Dampak | Rasa aman palsu; kebocoran saat arsip atau image dibagikan tidak akan tertangkap. |
| Rekomendasi | Pindai artefak rilis serta `.env*` kecuali template; gunakan alat teruji seperti gitleaks atau trufflehog di CI. |
| Confidence | High |

#### RV-06 · MEDIUM · Testing — CI menimpa pengecualian tes live

| Atribut | Detail |
| --- | --- |
| Lokasi | `.github/workflows/ci.yml` (langkah pytest); `pyproject.toml` (`addopts`) |
| Bukti | CI menjalankan `pytest -v -m "not live"`. Opsi `-m` di baris perintah menggantikan `-m "not live_model and not sandbox"` dari `addopts`, padahal tidak ada marker bernama `live`. |
| Penjelasan | Perbaikan AUD-35 di `addopts` dibatalkan oleh perintah CI. Temuan ini melanjutkan AUD-35. |
| Dampak | Bila secret tersedia di CI, tes `live_model` dan `sandbox` ikut berjalan dan memanggil layanan sungguhan. |
| Rekomendasi | Hapus `-m` dari perintah CI, atau gunakan `-m "not live_model and not sandbox"`. |
| Confidence | High |

#### RV-07 · LOW · Testing — Gate AG-01 tanpa margin statistik

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/ai/calibration/conformal.py` (`verify_gate_ag01`) |
| Bukti | rt: kalibrasi konformal yang benar pada data sintetis menghasilkan cakupan 0,886–0,922 (route) dan 0,979–0,986 (accuse); gate lulus 2 dari 5 ulangan. |
| Penjelasan | Konformal menjamin cakupan minimal 1−α secara rata-rata, sehingga uji empiris yang tepat di target gagal sekitar separuh waktu. |
| Dampak | Gate tidak informatif: bisa gagal untuk model yang benar dan lulus karena kebetulan. |
| Rekomendasi | Gunakan batas bawah interval kepercayaan (misalnya Clopper–Pearson), atau kalibrasi pada α sedikit lebih ketat dari target. |
| Confidence | High |

#### RV-08 · MEDIUM · Reliability — Skema DB dibuat saat startup dan tidak sinkron dengan migrasi

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/db/repository.py`: 40–60; `backend/db/models.py`; `backend/migrations/versions/0001_initial_schema.py`; `infra/Dockerfile` (`COPY data/`) |
| Bukti | `SQLModel.metadata.create_all` dijalankan di konstruktor repository. Model berisi 22 tabel, migrasi 20 (tanpa `agent_tokens` dan `resale_listings`). Default SQLite `data/proofreturn.db` berisi data seed ikut disalin ke image. rt: URL Postgres di Compose gagal karena driver psycopg tidak ada. `alembic.ini` men-hardcode `sqlalchemy.url = sqlite:///./data/proofreturn.db`. |
| Penjelasan | Alembic bukan sumber kebenaran skema (MG-01). SQLite menggantikan PostgreSQL 16 tanpa ADR atau CR, sehingga RLS tidak mungkin diterapkan. |
| Dampak | Migrasi di Postgres akan menghasilkan skema yang berbeda dari yang dipakai lokal; image produksi membawa database demo. |
| Rekomendasi | Hapus `create_all`; buat migrasi 0002 untuk dua tabel yang hilang; tambahkan driver psycopg; jangan salin file DB ke image. |
| Confidence | High |

#### RV-09 · MEDIUM · Security — Tidak ada penerbitan identitas untuk staff dan shopper

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/auth/tokens.py` (`mint_staff_token`, `mint_shopper_token`); `backend/api/app.py` |
| Bukti | Tidak ada endpoint login, SSO, maupun magic link; token staff dan shopper hanya dibuat oleh kode dan tes. |
| Penjelasan | API-04 mensyaratkan staff JWT dari penyedia autentikasi dan order token shopper lewat magic link. |
| Dampak | Pengguna nyata tidak bisa mendapatkan token tanpa jalur di luar API, sehingga mendorong praktik berbagi token demo. |
| Rekomendasi | Magic link per order untuk shopper; login staff lewat penyedia identitas, atau minimal endpoint admin yang diaudit. |
| Confidence | High |

#### RV-11 · MEDIUM · Security — Endpoint metrik dan alert tanpa autentikasi, label memakai path mentah

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 183–186 (`/v1/metrics`), 188–196 (`/v1/ops/alerts`); `backend/api/middleware.py` (label `path`) |
| Bukti | Kedua handler tidak memanggil `_resolve_principal`. Middleware mencatat metrik dengan label `request.url.path`, yang memuat ID return dan order. Aplikasi mendengarkan di `0.0.0.0:8000`. |
| Penjelasan | Path mentah sebagai label menghasilkan kardinalitas tak terbatas dan membocorkan identifier resource ke siapa pun yang membaca metrik. |
| Skenario eksploitasi | Pihak luar membaca `/v1/metrics` untuk mengenumerasi ID return yang aktif dan pola trafik, atau membanjiri path unik untuk membengkakkan memori registry. |
| Dampak | Paparan data operasional dan vektor DoS memori (TM-15). |
| Rekomendasi | Batasi kedua endpoint ke jaringan internal atau peran operator; gunakan template route (misalnya `/v1/returns/{return_id}`) sebagai label. |
| Confidence | High |

#### RV-12 · LOW · Security — Token tanpa audience dan issuer, revocation hanya di memori

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/auth/tokens.py`: 94–110 (revocation), 184–290 (fungsi `mint_*`); `backend/api/app.py`: 268–285 (GET return) |
| Bukti | Token tidak memuat `aud` maupun `iss`; daftar revocation disimpan di memori proses; principal bertipe service tidak diperiksa tenant di GET return. |
| Penjelasan | Token yang sah di satu lingkungan juga sah di lingkungan lain berkunci sama; revocation hilang saat restart dan tidak berlaku lintas worker. |
| Dampak | Pencabutan token tidak andal; token service bisa membaca return milik tenant mana pun. |
| Rekomendasi | Tambahkan dan verifikasi `aud` dan `iss`; simpan revocation di DB; batasi principal service ke endpoint yang membutuhkannya. |
| Confidence | High |

#### RV-13 · LOW · Security — Hardening container dan jaringan pengembangan

| Atribut | Detail |
| --- | --- |
| Lokasi | `infra/Dockerfile`; `infra/docker-compose.yml` |
| Bukti | Dockerfile tanpa direktif `USER`, sehingga proses berjalan sebagai root, dan `uv:latest` tidak dipin. Compose mengekspos Postgres (5432), Redis (6379), MinIO (9000/9001), dan Temporal (7233) ke semua interface host dengan kredensial default. |
| Penjelasan | Konfigurasi ini wajar untuk laptop pengembang, tetapi berbahaya bila Compose yang sama dipakai di host yang terekspos. |
| Dampak | Akses langsung ke infrastruktur data dari jaringan; eskalasi lebih mudah bila container disusupi. |
| Rekomendasi | Jalankan sebagai user non-root; pin digest image; bind port infrastruktur ke `127.0.0.1` atau jaringan internal Compose. |
| Confidence | High |

#### RV-14 · LOW · Reliability — Dedupe webhook hilang saat restart

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/webhooks.py`: 17 |
| Bukti | `_seen_event_ids` adalah `BoundedTTLCache(max_size=10000, ttl_seconds=86400 * 30)` di memori proses. |
| Penjelasan | NFR-04 mensyaratkan setiap event diproses tepat sekali. Cache di memori hilang saat restart dan membuang event lama setelah 10.000 entri. |
| Dampak | Event yang dikirim ulang PayPal setelah restart, misalnya dispute atau reversal, akan diproses dua kali. |
| Rekomendasi | Simpan ID event yang sudah diproses di DB dengan unique constraint, dalam transaksi yang sama dengan efek sampingnya. |
| Confidence | High |

#### RV-10 · INFORMATIONAL — Perbaikan dan kekuatan yang terverifikasi

| Area | Bukti |
| --- | --- |
| Mekanisme | 180/180 nilai §8.8 tetap cocok; label NO\_PASSPORT kini benar (rt) |
| Settlement dan INV-10 | Eskalasi gross dan default protektif (rt) |
| Ledger dan webhook processor | Lock mencegah race; dedupe atomik; konflik re-plan ditolak (rt) |
| Trust | Promosi satu tingkat (rt) |
| Konformal | Cakupan empiris sekitar target (rt) |
| Kriptografi | AEAD SecretBox untuk crypto-shredding |
| Operasional | Middleware request ID dan log terstruktur; readiness memeriksa DB; TTL cache (rt) |
| Kualitas kode | 310/310 fungsi beranotasi tipe lengkap; tanpa `except` kosong; skenario FX kini menjalankan ledger dan webhook processor |
| Dokumen | RTM dan gate record jauh lebih konservatif dan memakai nilai status §20.1 |

### Temuan lama yang masih terbuka

Severity dinilai ulang sesuai kondisi versi revisi. Bukti lengkap dan kartu atribut asli ada di laporan audit sebelumnya; tabel ini mencatat sisa masalah dan lokasinya sekarang.

| ID | Severity | Kategori | Sisa masalah dan lokasi | Rekomendasi | Confidence |
| --- | --- | --- | --- | --- | --- |
| AUD-01 | CRITICAL | Functional | Nilai karangan di endpoint uang: tranche 22157 (`app.py`: 915), `via_policy_engine: True` (391), `ret_created_01` (586), `NONCE-RET-DEMO-1` (343), ID evidence pack (1066), harga keep-offer (RV-04) | Sambungkan endpoint ke `decide_release`, ledger, dan `keep_offer.py`; hapus konstanta | High |
| AUD-02 | CRITICAL | Functional | `payments/client.py` tidak berubah: refund dan capture stub berstatus COMPLETED | Implementasikan refund dan capture nyata; jalankan ST-01 | High |
| AUD-04 | HIGH | Functional | Tanpa model Pydantic; persetujuan, blur, dan self-test default `true`; body bukan JSON berujung 500 | Model request dengan field wajib; 422 sesuai §28.2 | High |
| AUD-06 | HIGH | Reliability | Endpoint tetap memakai dict; DB hanya di-seed (ARC-14) | Pakai 15 metode repository yang sudah ada di semua endpoint | High |
| AUD-07 | HIGH | Reliability | Service `api` di Compose gagal start karena driver psycopg tidak dideklarasikan (rt) | Tambahkan driver atau samakan URL; uji `docker compose up` di mesin bersih | High |
| AUD-24 | HIGH | Security | Webhook dipercaya dari header `X-PayPal-Signature-Valid`; tanpa header diterima | Verifikasi lewat API PayPal; sambungkan `WebhookProcessor` | High |
| AUD-34 | HIGH | Testing | Tanpa Playwright, Postgres, maupun refund Sandbox; tidak ada tes yang membandingkan keluaran endpoint dengan engine | Contract test endpoint vs engine; integrasi Postgres; ST-01 | High |
| AUD-03 | MEDIUM | Testing | Skenario CT tautologis tetap dan dirujuk ST-11; RPO drill dan durasi bootstrap dari parameter default | Uji konkurensi dan drill sungguhan | High |
| AUD-14 | MEDIUM | Architecture | `create_app(demo_mode=True, mode="judge")` | Injeksi settings; default non-demo | High |
| AUD-15 | MEDIUM | Reliability | `apply_fallback_degradation` tanpa pemanggil | Sambungkan deteksi kegagalan | High |
| AUD-22 | MEDIUM | Security | Resale order dapat dipanggil principal apa pun dan memindahkan Passport ke `new_owner_ref` dari body | Batasi ke pembeli terverifikasi setelah capture | High |
| AUD-25 | MEDIUM | Security | Penghapusan data `required=False`; demo reset mengembalikan `RESET_COMPLETE` tanpa aksi | Autentikasi wajib; reset nyata atau hapus endpoint | High |
| AUD-28 | MEDIUM | Security | Receipt dengan kunci efemeral dan `verified: true` tetap; signature Passport berupa SHA-256; blur dari flag klien | Kunci penandatangan persisten dengan kunci publik terbit; verifikasi nyata | High |
| AUD-29 | MEDIUM | Security | Reviewer asal diambil dari body pengaju banding (default `rev_initial_01`) | Ambil dari decision record | High |
| AUD-33 | MEDIUM | Testing | Tes skema mengunci 20 tabel; tes baru mengunci perilaku keliru: `verified is True` dan panjang signature (`test_aud28`), exit code 0 pemindai buta (`test_aud38`), ID keep-offer literal (`test_aud40`), jalur keep-offer otomatis (`test_aud05`) | Assertion berbasis kontrak dan engine | High |
| AUD-36 | MEDIUM | Testing | RV-01 sampai RV-04 tidak tercakup tes | Tes regresi untuk setiap temuan | High |
| AUD-40 | MEDIUM | Functional | Tanpa validasi JSON Schema; respons keep-offer respond dan Passport menyimpang | Validasi terhadap skema | High |
| AUD-16 | LOW | Architecture | Konstanta tier, urutan grade, dan jurisdiksi masih terduplikasi | Sumber konfigurasi tunggal | High |
| AUD-19 | LOW | Architecture | `jsonschema` dan `pyyaml` runtime tanpa pemakaian | Pindahkan ke grup dev | High |
| AUD-26 | LOW | Security | Kunci literal `SerialRegistry` di `journeys.py`; konstanta token kini tercakup RV-01 | Hapus kunci literal | High |
| AUD-30 | LOW | Security | Tanpa rate limiting dan batas ukuran body | Rate limit per token dan IP | High |
| AUD-31 | LOW | Security | Nilai default kredensial tetap tertulis di Compose | Tanpa default | High |
| AUD-37 | LOW | Reliability | Log tanpa `return_id`, `decision_id`, `paypal_debug_id`; alert tanpa scheduler | Tambahkan field domain; jadwalkan alert | High |
| AUD-38 | LOW | Reliability | CI belum pernah berjalan; image tidak di-pin digest | Jalankan CI; pin digest | High |
| AUD-42 | LOW | Architecture | Model `refund_actions` berbeda dari `RefundActionRecord`; tier `ORIGIN_WITNESSED` di seed API | Satukan definisi | High |

AUD-05, AUD-21, dan AUD-35 dilanjutkan sebagai RV-03, RV-01, dan RV-06.

## F. Security Assessment versi revisi

Postur keamanan membaik nyata. Token kini bertanda tangan, sebagian besar endpoint memeriksa tenant atau order dari token terverifikasi, endpoint operasional terautentikasi, dan crypto-shredding memakai AEAD. Tiga celah serius masih ada: kunci token fail-open (RV-01), seed audit yang dapat diturunkan (RV-02), dan verifikasi webhook lewat header klien (AUD-24).

### Ringkasan per kategori

| Kategori | Audit sebelumnya | Versi revisi | Temuan terkait |
| --- | --- | --- | --- |
| Autentikasi dan session | Rentan | Rentan, cakupan lebih sempit | RV-01, RV-09, RV-12 |
| Otorisasi dan BOLA | Rentan | Sebagian | AUD-22 (resale), AUD-29, AUD-25 (penghapusan data) |
| Integritas webhook | Rentan | Rentan | AUD-24 |
| Manajemen secret | Rentan | Sebagian | RV-01, RV-05, AUD-26, AUD-31; `.env` diterima pemilik (AUD-23) |
| Paparan data | Rentan | Sebagian | RV-11 (metrik tanpa autentikasi) |
| Validasi input | Rentan | Rentan | AUD-04 |
| Kriptografi | Sebagian | Sebagian | RV-02, AUD-28; crypto-shredding kini AEAD |
| Rate limiting | Tidak ada | Tidak ada | AUD-30 |
| SQL injection | Tidak berlaku | Tidak ditemukan | ORM SQLModel; satu-satunya SQL mentah adalah `SELECT 1` |
| Command injection, path traversal, deserialisasi, SSRF | Tidak ditemukan | Tidak ditemukan | — |
| Logging data sensitif | Baik | Baik | Middleware hanya mencatat method, path, status, dan durasi melalui `scrub_sensitive_log` |
| CORS | Tidak dikonfigurasi | Tidak dikonfigurasi | Default aman selama belum ada frontend |
| Container dan jaringan dev | — | Lemah | RV-13 |

### Kepatuhan threat model (§32.4)

| Ancaman | Audit sebelumnya | Versi revisi |
| --- | --- | --- |
| TM-05 IDOR lintas tenant | Tidak ada mitigasi | Sebagian: scoping per endpoint, tanpa RLS, resale terbuka |
| TM-06 Webhook palsu | Tidak ada mitigasi | Tidak ada di endpoint (AUD-24); dedupe di processor kini atomik |
| TM-07 Over-refund lewat race | Tidak ada mitigasi | Lock di ledger; CHECK constraint ada di migrasi tetapi DB tidak dipakai |
| TM-12 Kebocoran kredensial | Gagal | Diterima pemilik dengan rencana rotasi; pemindai secret buta (RV-05) |
| TM-14 SSRF | Terpenuhi | Terpenuhi |
| TM-15 DoS dan biaya | Tidak ada mitigasi | Tidak ada rate limit; kardinalitas metrik tak terbatas (RV-11) |
| TM-16 Pembayaran live tak sengaja | Terpenuhi di client | Terpenuhi di client |
| TM-17 Retake oracle | Tidak tersambung | Guard retake diisi literal `True` (RV-03) |
| TM-22 Operator mengubah record | Palsu | Tetap tidak dapat diverifikasi (AUD-28, RV-02) |
| TM-24 Carrier event palsu | Gagal | Sebagian: endpoint terautentikasi, `DEMO_MODE` tetap hardcode |

### Rantai serangan paling realistis

Penyerang yang memegang template `.env.example` versi lama, atau yang bisa memicu kegagalan pemuatan settings, membuat token MERCHANT\_ADMIN untuk merchant mana pun (RV-01). Dengan token itu ia membaca return tenant lain, mencatat keputusan review, dan memanggil endpoint resale untuk memindahkan Passport ke dirinya sendiri (AUD-22). Secara terpisah, shopper mana pun bisa menghitung hasil audit draw sebelum mengirim barang (RV-02). Dampak uang langsung saat ini terbatas karena refund ke PayPal belum ada, tetapi rantai yang sama akan memindahkan uang begitu jalur pembayaran disambungkan.

### Area yang tidak dapat dinilai

- **Kerentanan dependensi.** Tanpa akses ke basis data advisori; tidak ada klaim CVE.
- **Uji penetrasi HTTP.** FastAPI tidak bisa dijalankan di sandbox audit; temuan HTTP berbasis analisis statis dan eksekusi fungsi terisolasi.
- **PayPal Sandbox dan Gemini.** Tidak ada panggilan jaringan, sesuai aturan audit.
- **Ketahanan prompt injection (FR-86).** Provider Gemini tidak berubah dan set DS-04 tidak tersedia.
- **Manajemen kunci di lingkungan deploy.** Bergantung pada rotasi yang direncanakan pemilik di akhir fase build.

## G. Testing & QA Report versi revisi

Dari 98 tes, 39 lulus saat dijalankan auditor (14 native, 25 indikatif), 58 BLOCKED oleh lingkungan, 1 di-deselect, dan tidak ada yang gagal. Hasil ini konsisten dengan klaim “96 passed, 2 deselected”. Tes baru menambah cakupan nyata untuk perbaikan pustaka, tetapi beberapa tes justru mengunci perilaku yang keliru: indikator kriptografi, pemindai secret, dan alur keep-offer.

| Ukuran | Audit sebelumnya | Versi revisi |
| --- | --- | --- |
| Tes ditemukan | 71 di 11 file, 433 assertion | 98 di 15 file, 662 assertion |
| Dieksekusi native | 14: 13 lulus, 1 BLOCKED saat runtime | 14 lulus; 1 tes Sandbox di-deselect `addopts` |
| Dieksekusi indikatif | 34: 31 lulus, 3 BLOCKED | 28: 25 lulus, 3 BLOCKED |
| Tidak bisa dikoleksi | 23 | 55 |
| Gagal karena kode | 0 | 0 |

### G.1 Testing Verification Report

| Kategori | Tes | Status eksekusi | Hasil | Catatan |
| --- | --- | --- | --- | --- |
| Unit: state machine | 4 | Native | 4 lulus | Skenario CT masih tautologis |
| Unit: provider Gemini | 5 | Native | 5 lulus | HTTP di-mock |
| Unit: payments, FX, rekonsiliasi | 6 | Native | 5 lulus, 1 deselected | Skenario FX kini menjalankan ledger dan webhook processor |
| Unit: golden examples | 10 | Indikatif | 10 lulus | — |
| Unit: Policy Engine | 18 | Indikatif | 15 lulus, 3 BLOCKED | Tes properti butuh Hypothesis native |
| Mekanisme dan journeys | 6 | BLOCKED | — | pydantic |
| Remediasi R3: persistensi dan konkurensi | 5 | BLOCKED | — | FastAPI dan SQLModel |
| Remediasi R4: settlement, trust, konformal | 7 | BLOCKED | — | FastAPI; perilakunya diverifikasi ulang lewat harness di Bagian R |
| Remediasi R5: observability dan keamanan | 6 | BLOCKED | — | FastAPI |
| Remediasi R6: E2E, AZ, gate | 6 | BLOCKED | — | FastAPI |
| API via TestClient (lama) | 8 | BLOCKED | — | FastAPI |
| AI pipeline, ops, domain | 17 | BLOCKED | — | FastAPI, PyNaCl, jsonschema |
| E2E browser (Playwright) | 0 | Tidak ada | — | — |
| Integrasi Postgres | 0 | Tidak ada | — | Tes DB memakai SQLite dan `create_all` |
| Refund di Sandbox | 0 | Tidak ada | — | — |

Semua run dijalankan di salinan kerja tanpa `.env` dan tanpa jaringan; perintah dan lingkungannya sama dengan Fase 2 (dicatat di Audit Ledger).

### G.2 Kualitas tes baru

**Menambah jaminan nyata.** Matriks otorisasi negatif (AZ), kasus batas settlement dengan angka eksak, ledger multithread, retry webhook setelah kegagalan, kuantil konformal, TTL cache, promosi trust satu tingkat, konflik re-plan, dan penolakan transisi ilegal dengan 409.

**Mengunci perilaku yang keliru.**

- `test_aud28_cryptographic_receipts_commitment_and_passport_chain` hanya memeriksa `verified is True`, panjang signature, dan `chain_valid is True`. Tidak ada verifikasi signature dengan kunci publik maupun commitment terhadap seed, sehingga AUD-28 dan RV-02 lolos.
- `test_aud38_secret_scanner_execution` meng-assert exit code 0 dari pemindai yang mengecualikan `.env` (RV-05).
- `test_aud40_declaration_and_keep_offer_schema_alignment` mengunci ID keep-offer literal `koff_ret_demo_1`; ketidakcocokan harga dengan respond tidak diuji (RV-04).
- `test_aud05_api_enforces_return_state_machine_guard` meng-assert jalur keep-offer otomatis sampai KEEP\_ACCEPTED sebagai perilaku benar (RV-03).
- Journey E2E meng-assert `state == "ASSESSED"` dan `seal_recorded is True`, keduanya respons hardcode; tidak ada pemeriksaan jumlah refund terhadap engine.
- Tes DB memanggil `DatabaseRepository` dan `create_all` langsung di SQLite, sehingga persistensi di endpoint (AUD-06) dan drift migrasi (RV-08) tidak teruji.

**Belum tercakup.** Fallback kunci token (RV-01), seed audit (RV-02), endpoint metrik tanpa autentikasi (RV-11), dan start service di Compose (AUD-07).

### G.3 Verifikasi bukti pengujian yang disediakan

| Klaim | Sumber | Hasil verifikasi |
| --- | --- | --- |
| 96 passed, 2 deselected | Sesi 13 dan 14 | Konsisten: 98 tes; semua subset yang bisa dijalankan auditor lulus |
| NFR-04 dan FR-80 VERIFIED | Sesi 10 | Bertentangan: endpoint webhook membaca header klien; badge REPLAYED dipasang pada hasil hardcode |
| Receipt dan commitment Ed25519 nyata (FR-61, FR-76, INV-16) | Sesi 12 | Sebagian: Ed25519 dari pustaka, tetapi kunci efemeral tanpa publikasi dan seed dapat diturunkan |
| Persistensi database (AUD-06) | Sesi 10 | Sebagian: repository dan model ada, endpoint tidak memakainya |
| `alembic upgrade head` atas 22 tabel | Sesi 14 | Tidak cocok: migrasi 0001 membuat 20 tabel (21 dengan `alembic_version`); angka 22 sesuai dengan DB hasil `create_all` |
| J-01 rotasi kunci dan `.env` dihapus: COMPLETED | Sesi 13 | Tidak sesuai isi arsip; pemilik merencanakan rotasi di akhir build, sehingga status yang tepat adalah DEFERRED |
| Gemini live dan OAuth/order di Sandbox | Sesi 14 | Tidak diverifikasi ulang karena tanpa jaringan; tidak ada refund live |
| CI hijau (bagian dari G0) | Gate record | Tidak dapat dibuktikan: repo tanpa commit dan tanpa riwayat run |
| `docker compose up` di mesin bersih | — | Tidak ada bukti; rt menunjukkan service `api` gagal start |

### G.4 Infrastruktur tes

`addopts` kini mengecualikan marker live, tetapi perintah CI menimpanya (RV-06). Coverage tetap tidak diukur, dan tidak ada tes yang dijalankan terhadap Postgres, browser, atau Sandbox.

## H. Reliability & Production Readiness versi revisi

Kesiapan membaik untuk demo lokal: `uvicorn backend.api.app:app` dengan SQLite default kemungkinan besar bisa berjalan, dan ada readiness probe serta log terstruktur. Namun jalur yang disyaratkan SSOT untuk juri, yaitu `docker compose up` (NFR-07), tetap gagal, dan sistem belum siap produksi karena persistensi, jalur uang, dan proses latar belakang belum tersambung.

| Area | Audit sebelumnya | Versi revisi | Bukti |
| --- | --- | --- | --- |
| Penanganan error | Tidak memadai | Sebagian | Middleware menangkap dan mencatat exception; body bukan JSON tetap berujung 500, bukan 422; 9 dari 14 kode error di luar katalog |
| Logging dan observability | Tidak ada di runtime | Sebagian | Log JSON dengan request ID dan trace ID; metrik Prometheus per proses; label path mentah (RV-11); tanpa field domain |
| Health dan readiness | Dangkal | Membaik | `/v1/ready` mem-ping DB dan menyertakan alert, tetapi DB itu tidak menyimpan data operasional (ARC-14) |
| Database | Tidak ada | Ada, tidak dipakai | SQLite default; `create_all` saat startup; `alembic.ini` men-hardcode URL SQLite; driver Postgres tidak ada |
| Transaksi | Tidak ada | Hanya di pustaka | Repository melakukan commit per metode, tetapi tidak dipanggil endpoint |
| Konkurensi | Tidak aman | Sebagian | Ledger memakai RLock (rt); ID banding dan listing kini UUID4 8 heksadesimal; dict API tetap dibagi handler sinkron dan async |
| Background task | Tidak ada | Tidak ada | Alert hanya dievaluasi saat request; tanpa scheduler, timer lifecycle, maupun sweeper outbox |
| Manajemen resource | Sebagian | Membaik | TTL cache untuk idempotensi dan dedupe webhook (rt); registry metrik tumbuh tanpa batas karena label path (RV-11) |
| Exactly-once webhook | — | Rapuh | Dedupe disimpan di memori (maksimal 10.000 event, 30 hari) dan hilang saat restart (RV-14) |
| Performa komputasi | Memadai | Memadai | rt: `decide_release` p50 80 µs, p95 90 µs (n = 3.000); feasibility map 1,3 ms per request |
| Skalabilitas | Tidak bisa diskalakan | Tidak bisa diskalakan | State, revocation token, dan metrik per proses; SQLite hanya satu penulis |
| Pemisahan konfigurasi | Tidak ada | Tidak ada | `demo_mode=True` hardcode; `DEMO_MODE` dan `MODE` di Compose tidak dibaca aplikasi |
| Kesiapan deployment | Tidak siap | Sebagian | Dockerfile dan service `api` ada, tetapi service gagal start (psycopg); image berjalan sebagai root, tidak dipin, dan membawa SQLite seed; CI belum pernah berjalan |
| Backup dan recovery | Tidak ada | Tidak ada | RPO drill tetap parameter; tidak ada strategi backup DB |
| Kegagalan yang anggun | Sebagian | Memburuk di satu titik | Kegagalan memuat settings membuat autentikasi gagal-terbuka (RV-01); fallback §31.3 tetap tidak tersambung (AUD-15) |
| Alert operasional | Tidak ada | Sebagian | `evaluate_alerts` dipanggil `/v1/ops/alerts`, tanpa scheduler dan tanpa autentikasi |

### Risiko yang perlu pengujian lanjutan

- Race pada dict bersama saat beban nyata, karena handler sinkron berjalan di threadpool.
- Migrasi Alembic terhadap Postgres sungguhan, setelah driver ditambahkan dan URL tidak lagi di-hardcode.
- Perilaku webhook setelah restart, ketika PayPal mengirim ulang event yang sudah pernah diproses.
- Latensi dan kegagalan PayPal sungguhan terhadap NFR-01, yang belum bisa diukur karena refund belum ada.

### Kesimpulan kesiapan

Perbaikan reliability di pustaka sudah nyata dan terukur. Penentu kesiapan tetap tiga hal yang sama seperti audit sebelumnya: persistensi yang dipakai endpoint, jalur uang ke PayPal, dan cara menjalankan aplikasi yang bisa direproduksi lewat Compose.

## I. Missing Implementation & Technical Debt

Utang terbesar kini bukan kode yang belum ditulis, melainkan kode yang sudah benar tetapi belum disambungkan. Repository dengan 15 metode, settlement, trust, ledger, webhook processor, dan kalibrasi konformal sudah siap dipakai endpoint.

### I.1 Konsistensi lintas modul (Fase 8)

| Pasangan yang dicek | Audit sebelumnya | Versi revisi | Bukti |
| --- | --- | --- | --- |
| SSOT ↔ implementasi | Tidak | Tidak | 10 PASS dari 137 (Bagian C) |
| Arsitektur ↔ batas modul | Tidak | Sebagian | Lapisan baru ada tetapi di luar jalur keputusan uang (Bagian D) |
| JSON Schema ↔ API | Tidak | Sebagian | Deklarasi menerima nama field skema dan GET keep-offer sesuai skema; respond keep-offer dan Passport menyimpang; tanpa validasi skema |
| Kontrak §28 ↔ API | Tidak | Tidak | Endpoint cancel tidak ada; idempotensi 1 dari 22 POST; 9 dari 14 kode error di luar katalog |
| Model DB ↔ migrasi ↔ domain | Tidak | Tidak | Model 22 tabel vs migrasi 20; `refund_actions` berbeda dari `RefundActionRecord` |
| Target database | — | Tidak | Compose memakai URL Postgres, sedangkan `alembic.ini` dan default repository memakai SQLite |
| Nama state API ↔ state machine | Ya | Ya, guard tidak | Nama konsisten; guard diisi literal `True` (RV-03) |
| Curve refund | Tidak | Ya | API, MCP, dan storefront memakai 0,80/0,50 |
| Enum tier Passport | Tidak | Tidak | API: FULL, LITE, ORIGIN\_WITNESSED; domain: FULL/LITE/NONE; packing station: FULL/LIGHT/ORIGIN\_WITNESSED |
| Scope agen REST ↔ MCP | Tidak | Ya | Keduanya memeriksa `declare`, `read_policy`, `keep_offer` |
| Order API ↔ ledger | Tidak | Tidak | API tidak pernah memanggil `register_order`, sehingga webhook dispute akan selalu 404 bila disambungkan |
| Keep-offer GET ↔ respond | — | Tidak | 18000 vs 5320 (RV-04) |
| Kunci token ↔ salt hash serial | — | Terkopel | Merotasi salt pseudonimisasi membatalkan semua token, dan sebaliknya (RV-01) |
| `key_id` receipt ↔ kunci aktual | — | Tidak | `platform_key_v1` dan `key_packer_origin_01` tetap, sementara kunci dibuat acak per request (AUD-28) |
| Dokumentasi ↔ kode | Tidak | Sebagian | README masih menyuruh `make up` yang gagal untuk service `api`; klaim “22 tabel”, J-01 COMPLETED, dan NFR-04 VERIFIED tidak sesuai kode (Bagian G.3) |

### I.2 Implementasi yang belum ada

| Area | Yang belum ada | Referensi |
| --- | --- | --- |
| Jalur uang | Capture dan refund PayPal, tracking, Disputes API, verifikasi webhook, outbox sweeper | AUD-02, AUD-24 |
| Frontend | Empat aplikasi React | ARC-07, NFR-06, NFR-09, NFR-10 |
| Workflow | Scheduler, timer lifecycle, retry | ARC-05, FR-24, FR-71, FR-97 |
| Media dan bukti | Object storage, upload, blur on-device yang terverifikasi | FR-02, FR-16 |
| Pipeline AI | Forensik media nyata, OCR/VLM, grader kedua, rekaman judge mode | FR-18, FR-20, FR-80 |
| Identitas | Login staff dan magic link shopper | RV-09 |
| Agen | Server MCP dengan transport | ARC-12 |
| Endpoint | `POST /v1/returns/{id}/cancel` | FR-88 |
| Operasional | Backup dan restore, Compose yang bisa start | NFR-13, AUD-07 |
| P2 | Anchoring RFC 3161, deposit sewa, delivery receipt | FR-83, FR-54, FR-77 |

### I.3 Placeholder yang masih tampil sebagai implementasi

| Placeholder | Lokasi | Temuan |
| --- | --- | --- |
| Tranche 22157, `via_policy_engine: True`, `ret_created_01`, nonce challenge tetap, ID evidence pack, harga keep-offer | `backend/api/app.py` | AUD-01, RV-04 |
| Refund dan capture dengan status COMPLETED palsu | `backend/payments/client.py` | AUD-02 |
| Guard state machine literal `True` | `backend/api/app.py` | RV-03 |
| Signature Passport berupa SHA-256 dan `verified: true` pada receipt | `backend/api/app.py` | AUD-28 |
| Demo reset tanpa aksi, metrik biaya dan latensi di `/v1/simulate` | `backend/api/app.py` | AUD-25, NFR-16 |
| Skenario CT tautologis, RPO drill dan durasi bootstrap dari parameter | `domain/return_state.py`, `ops/drills.py` | AUD-03 |

### I.4 Technical debt

- **Pustaka yang belum disambungkan:** repository, settlement, trust, kalibrasi konformal, ledger, webhook processor, fallback degradasi (AUD-06, AUD-15, ARC-01).
- **Dua sumber state:** dict di memori dan DB yang hanya di-seed (ARC-14).
- **Skema tidak dikelola migrasi:** `create_all` dan drift model–migrasi (RV-08).
- **Definisi terduplikasi:** cap tier, urutan grade, jurisdiksi, enum tier Passport (AUD-16, AUD-42).
- **Tes mengunci perilaku keliru:** tes kriptografi, pemindai, dan keep-offer perlu ditulis ulang ketika logikanya diperbaiki (AUD-33).
- **Dokumen bukti belum akurat:** klaim di sesi 10, 12, 13, dan 14 perlu dikoreksi; ADR tetap generik; repo tanpa commit (DOC-03, DOC-05, DOC-09).

## J. Remediation Roadmap

Urutan mengikuti dependensi teknis, dengan sisa 10 hari menuju deadline 12 November. Sebagian besar item Must Fix adalah pekerjaan menyambungkan pustaka yang sudah benar, bukan menulis ulang. Bila waktu tidak cukup, ikuti cut order SSOT §14.4 dan tandai fitur yang dipotong sebagai DEFERRED atau DEGRADED secara terbuka.

### J.1 Must Fix Before Release

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-01 | Kunci token gagal-tertutup: `AUTH_SIGNING_KEY` terpisah, hapus `DEFAULT_AUTH_SECRET` dan `except: pass`, wajibkan `exp` | RV-01 | Satu-satunya CRITICAL yang bisa ditutup dalam hitungan jam | — |
| J-02 | Koreksi `rtm.csv` (5 klaim FAIL, 12 PARTIAL), klaim sesi 10–14, dan status G0; J-01 di dokumen menjadi DEFERRED | DOC-01, DOC-03, G.3 | Keputusan gate harus bersandar pada status yang benar | — |
| J-03 | Compose bisa start: tambah driver psycopg, satukan URL DB (Compose, `alembic.ini`, repository), hapus `create_all`, migrasi 0002, jangan salin DB ke image | AUD-07, RV-08 | NFR-07 adalah jalur juri | — |
| J-04 | Sambungkan endpoint ke repository (hapus dict), ke `decide_release`, ledger, dan `keep_offer.py`; hitung guard dari data | AUD-01, AUD-06, RV-03, RV-04 | Inti produk belum berjalan di sistem | J-03 |
| J-05 | Seed audit acak yang dikomit dan disimpan; kunci penandatangan persisten dengan kunci publik terbit | RV-02, AUD-28 | Audit acak adalah dasar keamanan `X_max` | J-04 |
| J-06 | Capture dan refund nyata; verifikasi signature webhook; daftarkan order ke ledger; dedupe di DB; jalankan ST-01 | AUD-02, AUD-24, RV-14 | Nilai utama produk adalah refund PayPal bertahap | J-04 |
| J-07 | Frontend minimal untuk J-01..J-04 | ARC-07 | Juri perlu melihat alur shopper dan merchant | J-04 |

### J.2 Should Fix Before Production

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-08 | Model Pydantic dari JSON Schema; persetujuan, blur, dan self-test tanpa default permisif; 422 sesuai §28.2 | AUD-04, AUD-40 | Persetujuan Fast Lane (FR-14) dan privasi (FR-16) | J-04 |
| J-09 | Metrik dan alert di balik autentikasi dengan label template route; `aud`/`iss` dan revocation di DB; otorisasi resale, penghapusan data, dan reviewer banding; penerbitan identitas; rate limiting | RV-11, RV-12, AUD-22, AUD-25, AUD-29, RV-09, AUD-30 | Menutup sisa celah otorisasi | J-01, J-04 |
| J-10 | Contract test endpoint vs engine; tes verifikasi kriptografi; integrasi Postgres; Playwright; tes regresi RV-01..RV-04; perbaiki marker CI, tes pemindai, margin AG-01, dan skenario CT | AUD-03, AUD-33, AUD-34, AUD-36, RV-05, RV-06, RV-07 | Agar status VERIFIED bermakna | J-03, J-04 |
| J-11 | Settings disuntikkan dengan default non-demo; fallback §31.3 tersambung; scheduler untuk alert dan timer | AUD-14, AUD-15, AUD-37, ARC-05 | Perilaku aman saat dependensi gagal | J-04 |
| J-12 | Container non-root dengan image ber-digest; port infrastruktur hanya lokal; jalankan CI sungguhan | RV-13, AUD-31, AUD-38 | Kebersihan rilis | J-03 |

### J.3 Recommended Improvements

| ID | Tindakan | Temuan | Bergantung pada |
| --- | --- | --- | --- |
| J-13 | Definisi bersama untuk enum dan konstanta; bersihkan dependensi runtime; hapus kunci literal di `journeys.py`; satukan nama model AI dan lengkapi ADR | AUD-16, AUD-42, AUD-19, AUD-26, DOC-05, DOC-06 | J-04 |

### J.4 Optional Optimizations

| ID | Tindakan | Alasan |
| --- | --- | --- |
| J-14 | Tracing OpenTelemetry end-to-end | Berguna setelah log berisi field domain |
| J-15 | Verifikasi pemetaan UCP | Butuh akses ke spesifikasi UCP terbaru |

### Rencana pemilik di akhir build

Rotasi seluruh kredensial di penyedia API sesuai rencana (AUD-23). Sertakan kedua salt; bila J-01 sudah selesai, kunci token yang baru harus terpisah dari salt pseudonimisasi.

## K. Final Verdict

**NOT READY, dengan arah perbaikan yang jelas.** Masalah fundamental pada implementasi, keamanan, dan reliability masih ada, tetapi versi revisi menutup sebagian besar cacat di level pustaka dan membuat dokumen status jauh lebih jujur.

| Dimensi | Dasar verdict |
| --- | --- |
| Implementasi | Endpoint uang masih mengembalikan nilai karangan; refund PayPal masih stub; frontend dan persistensi di endpoint belum ada; 10 dari 137 requirement PASS |
| Keamanan | Kunci token gagal-terbuka ke konstanta publik (CRITICAL); seed audit dapat diturunkan; verifikasi webhook lewat header klien |
| Reliability | Service `api` di Compose tidak bisa start; dua sumber state; tanpa proses latar belakang |
| Integritas bukti | 5 dari 27 klaim VERIFIED bertentangan dengan kode dan 12 lainnya hanya PARTIAL; beberapa tes baru mengunci perilaku keliru |

**Mengapa bukan REQUIRES REMEDIATION.** Kategori itu mengandaikan sistem yang sebagian besar sudah terbangun. Di sini jalur uang, persistensi yang dipakai endpoint, antarmuka pengguna, dan cara menjalankan aplikasi lewat Compose belum ada.

**Mengapa bukan INCONCLUSIVE.** Cacat penentu terverifikasi langsung di kode dan sebagian lewat eksekusi runtime: token palsu diterima, URL Compose gagal tanpa driver, dan nilai hardcode terlihat di handler. Keterbatasan lingkungan (58 tes BLOCKED, tanpa jaringan) tidak mengubah kesimpulan.

**Kemajuan yang terverifikasi.** Sebelas temuan lama teratasi dan 17 sebagian; FAIL di RTM turun dari 35 ke 27; tiga perbaikan pustaka yang paling berisiko bagi uang dan keadilan (race ledger, dedupe webhook, default INV-10) kini benar saat runtime; mekanisme inti tetap 180/180.

**Yang siap menjadi fondasi.** Policy Engine, settlement, trust, ledger, webhook processor, kalibrasi konformal, TTL cache, crypto-shredding AEAD, state machine, middleware, dan repository. Semuanya layak dipertahankan dan tinggal disambungkan.

**Keyakinan dan batas cakupan.** Keyakinan atas verdict: High. Tidak ada panggilan ke PayPal maupun Gemini; lapisan HTTP dinilai secara statis dan lewat fungsi terisolasi; kerentanan dependensi tidak dinilai. File yang belum dibaca rinci tercatat di Audit Ledger dan kecil kemungkinannya mengubah verdict.

**Kriteria audit ulang berikutnya.** J-01 sampai J-07 selesai, `docker compose up` berhasil di mesin bersih, ST-01 dijalankan di Sandbox sesuai definisinya, dan RTM diregenerasi hanya dari bukti nyata.

Seluruh file versi revisi tetap tidak berubah selama audit (manifest SHA-256 diverifikasi setiap fase), dan kredensial di `.env` tidak pernah dipakai.

## Audit Ledger

Posisi per 2 November 2026, setelah Fase 8. Semua bagian sudah diisi.

### Eksekusi

| Eksekusi | Perintah ringkas | Hasil |
| --- | --- | --- |
| Harness mekanisme (ulang) | `harness/mechanism_check.py` dengan test double `pydantic` berlabel | 180/180 cocok dengan §8.8; tanpa regresi |
| Harness remediasi | `harness/remediation_check.py` | AUD-08, 09, 11, 12, 13, 17, 18, 39 terkonfirmasi; token palsu diterima lewat fallback; cakupan konformal sekitar target |
| Uji driver Compose | `create_engine("postgresql://…")` memakai SQLAlchemy 2.1.6 dari venv | `ModuleNotFoundError: psycopg` |
| Database SQLite dalam arsip | Dibuka read-only via `sqlite3` | 22 tabel termasuk `alembic_version`, berisi data seed |

**Fase 2.** Suite tes proyek dijalankan sejauh lingkungan memungkinkan: state machine dan provider Gemini (9 lulus, native), payments (5 lulus, 1 tes Sandbox di-deselect `addopts`, native), golden dan policy engine (25 lulus, 3 tes `@given` di-skip, indikatif dengan test double). Sepuluh file lain tidak bisa dikoleksi karena FastAPI, pydantic, atau jsonschema tidak tersedia. RTM 137 baris dinilai ulang memakai bukti Fase R dan inspeksi tambahan atas `/v1/simulate`, pembuatan Passport, view publik Passport, endpoint audit dan checkpoint, serta field log middleware.

**Fase 3.** Graf import non-tes termasuk import lazy di dalam fungsi, keterjangkauan modul dari `backend.api.app`, metode repository yang dipanggil API, perbandingan tabel model SQLModel dengan migrasi Alembic, constraint integritas di migrasi, konvensi API §28.1, dan jenis token. Bukti runtime driver Compose dari Fase R dipakai ulang.

**Fase 4.** Metrik statis versi revisi (anotasi tipe, pola exception, literal hardcode), pemeriksaan jalur fail-open di `auth/tokens.py`, struktur skenario FX di `payments/failures.py`, penanganan exception di middleware, dan sumber data metrik. Temuan disusun di Bagian E: 9 temuan baru dan 25 temuan lama yang masih terbuka.

**Fase 5.** Pemeriksaan revocation dan klaim token, field log middleware dan scrubbing, CORS, SQL mentah, path dari input pengguna, autentikasi endpoint metrik dan alert, perlakuan principal service, Dockerfile (COPY selektif, tanpa `USER`), serta port Compose. Hasilnya tiga temuan baru (RV-11 sampai RV-13) dan Bagian F.

**Fase 6.** Inventaris AST atas 98 tes, pembacaan assertion pada tes remediasi kunci, dan pencocokan klaim di bukti sesi 08–14 terhadap kode (jumlah tes, status VERIFIED, persistensi, jumlah tabel Alembic, status J-01, CI, Compose). Hasil eksekusi tes memakai run Fase 2.

**Fase 7.** Pemeriksaan pembuatan ID, struktur dedupe webhook, pola transaksi repository, URL Alembic, serta micro-benchmark `decide_release` (n = 3.000) dan `generate_feasibility_map` (n = 20) di salinan kerja dengan test double pydantic. Hasilnya Bagian H dan temuan RV-14.

**Fase 8.** Penelusuran konsistensi lintas modul atas skema, kontrak API, model dan target database, enum, scope, ledger, keep-offer, kunci token, `key_id` receipt, dan README. Hasilnya dirangkum di Bagian I.1; laporan final A, I, J, dan K disusun dari seluruh fase.

Semua eksekusi berjalan di salinan kerja tanpa `.env` dan tanpa jaringan. Manifest SHA-256 salinan asli diverifikasi tanpa perubahan setelah fase ini.

### Cakupan inspeksi

- **Dibaca rinci:** handler `app.py` untuk token agen, return, policy, challenge, policies, review, webhook, create return, demo, deklarasi, evidence, dropoff, receipt, evidence pack, keep-offer, banding, resale, penghapusan data, Passport, simulate, dan readiness; `auth/tokens.py`; ledger dan webhook processor; inisialisasi repository; Compose, Dockerfile, CI, `scan_secrets.py`; gate record, `sandbox-tests.md`, dan klaim utama sesi 08–14.
- **Diverifikasi lewat runtime:** settlement, trust, ledger, webhook processor, kalibrasi konformal, TTL cache, jalur fallback token, mekanisme §8.8.
- **Belum dibaca rinci:** `db/models.py` (sebagian), migrasi `0001` (hanya hitungan), `api/middleware.py`, `observability/metrics.py`, `ops/drills.py` dan `payments/failures.py` (sebagian), isi tes remediasi, CHANGELOG dan PROJECT\_LOG.

### Catatan pemilik

`.env` sengaja disertakan dalam arsip, dan kredensial akan dirotasi di penyedia API pada akhir fase build. AUD-23 dicatat sebagai DITERIMA.
