# Laporan Audit Ulang ke-2 — ProofReturn (Revisi ke-2)

Nov 3, 2026 · @Wahyuni

## Status audit ulang ke-2 dan aturan kerja

Audit ulang ke-2 selesai: Fase 1, R, dan 2–8 telah dijalankan, dan verdict akhir ada di Bagian K. Semua bagian sudah terisi; Audit Ledger mencatat cakupan dan keterbatasan.

| Fase | Status | Cakupan |
| --- | --- | --- |
| 1 Discovery dan perubahan | Selesai (statis) | Diff terhadap revisi pertama, tech stack, dokumen, bukti pengujian |
| R Verifikasi perbaikan | Selesai (statis + runtime) | 38 temuan terbuka, status DOC, klaim sesi 15–21 |
| 2 Requirement traceability | Selesai (statis + runtime) | 137 baris RTM |
| 3 Arsitektur | Selesai (statis) |  |
| 4 Backend | Selesai (statis) |  |
| 5 Keamanan | Selesai (statis + runtime) |  |
| 6 Testing dan bukti pengujian | Selesai (45 lulus, mutasi 6/11) | 151 tes backend, 6 tes frontend |
| 7 Reliability | Selesai (statis) |  |
| 8 Konsistensi lintas modul | Selesai (statis) |  |

**Integritas sumber.** Arsip `ProofReturnRevisiKe2.zip` (49.061.229 byte, 7.225 entri, SHA-256 `6ce29863…4e5f10a`) diperiksa bebas path traversal dan symlink, lalu diekstrak ke salinan terpisah yang dikunci read-only. Manifest SHA-256 untuk 568 file plus hash agregat `.venv` dicatat. Revisi pertama (SHA-256 `ad383fad…0c16368`) dipakai sebagai pembanding.

**Aturan eksekusi.** Tidak ada file proyek yang diubah. Eksekusi hanya di salinan kerja terpisah tanpa `.env`, tanpa jaringan, dan tanpa menulis ke salinan asli; kredensial tidak pernah dipakai. Sesuai permintaan pemilik, `.env` di folder proyek tidak dinilai sebagai temuan.

## A. Executive Summary

**Verdict: NOT READY, dekat ke REQUIRES REMEDIATION.** Revisi ke-2 adalah lompatan terbesar sejauh ini: endpoint uang kini memakai Policy Engine dan settlement, state tersimpan di database, token gagal-tertutup, dan seed audit rahasia. Dua masalah fundamental tersisa: siapa pun bisa meminta token staff atau shopper, dan refund tidak pernah dieksekusi ke PayPal.

| Ukuran | Audit awal | Revisi pertama | Revisi ke-2 |
| --- | --- | --- | --- |
| Requirement (PASS / PARTIAL / FAIL / NOT IMPL. / NOT VERIF.) | 9 / 75 / 35 / 15 / 3 | 10 / 82 / 27 / 15 / 3 | 21 / 90 / 10 / 12 / 4 |
| Temuan terbuka (CRITICAL / HIGH / MEDIUM / LOW) | 40 (3 / 9 / 20 / 8) | 38 (3 / 7 / 16 / 12) | 26 (2 / 4 / 10 / 10) |
| Status temuan versi sebelumnya | — | 11 teratasi, 17 sebagian, 11 belum | 16 teratasi, 19 sebagian, 2 belum, 1 tidak dinilai |
| Tes lulus / BLOCKED / gagal | 44 / 27 / 0 | 39 / 58 / 0 | 45 / 111 / 0 |
| Skor mutasi subset | — | — | 6 dari 11 |
| Mekanisme vs §8.8 | 180/180 | 180/180 | 180/180 |

**Yang membaik.** Orkestrasi engine di endpoint, persistensi penuh lewat repository, migrasi sinkron dengan constraint lengkap, token gagal-tertutup dengan kunci terpisah (terbukti runtime), seed audit acak, kunci penandatangan persisten, validasi Pydantic, rate limiting, container non-root, dan driver Postgres di Compose.

**Dua temuan CRITICAL.**

- RV2-01: `POST /v1/auth/staff-token` dan `/v1/auth/shopper-magic-link` menerbitkan token tanpa memeriksa kredensial apa pun.
- AUD-02: aksi refund berhenti di status PLANNED tanpa eksekutor, dan ID capture yang dipakai adalah karangan.

**Temuan penting lainnya.** Webhook masih menerima header uji dan prefiks `cert-url` palsu (AUD-24); penolakan over-refund ditelan lalu aksi tetap disimpan (RV2-04); scheduler otomasi tidak pernah dijalankan (RV2-02); dua bug yang disuntikkan, guard state machine dan arah seleksi audit, lolos dari seluruh suite tes.

**Konteks.** Per 3 November tersisa 9 hari menuju deadline 12 November. `.env` sengaja disertakan pemilik dan tidak dinilai.

**Tindakan pertama yang disarankan:** tutup penerbitan token terbuka dan bypass webhook (hitungan jam), lalu bangun eksekutor refund yang transaksional (Bagian J).

## R. Verifikasi perbaikan atas 38 temuan terbuka

Revisi ke-2 menutup 16 temuan dan memperbaiki 19 lainnya sebagian; hanya 2 yang belum tersentuh. Perbaikan terpenting: endpoint uang kini memakai Policy Engine dan settlement, endpoint memakai database, token gagal-tertutup (terbukti runtime), seed audit acak, dan Compose kini punya driver Postgres. Namun perbaikan RV-09 membuka celah CRITICAL baru: endpoint penerbitan token menyerahkan token staff dan shopper kepada siapa pun tanpa autentikasi (RV2-01).

| Severity di audit ulang pertama | TERATASI | SEBAGIAN | BELUM | Dinilai di Fase 6 | Tidak dinilai |
| --- | --- | --- | --- | --- | --- |
| CRITICAL (3) | 2 | 1 | 0 | 0 | 0 |
| HIGH (7) | 3 | 3 | 1 | 0 | 0 |
| MEDIUM (16) | 5 | 9 | 1 | 0 | 1 |
| LOW (12) | 6 | 6 | 0 | 0 | 0 |
| Total (38) | 16 | 19 | 2 | 0 | 1 |

**Bukti runtime.** Harness token menunjukkan delapan perilaku gagal-tertutup yang benar: token tanpa `exp`, kedaluwarsa, audience salah, kunci lain, settings gagal dimuat, kunci sama dengan salt, dan kunci kurang dari 32 byte semuanya ditolak, dan konstanta `DEFAULT_AUTH_SECRET` sudah hilang. Mekanisme §8.8 tetap 180/180. Gate AG-01 dengan margin baru hanya lulus 4 dari 10 ulangan untuk model terkalibrasi dan 0 dari 10 untuk model yang memburuk.

### Status per temuan

| ID | Temuan | Status | Bukti verifikasi |
| --- | --- | --- | --- |
| AUD-01 | Endpoint uang mengarang hasil | TERATASI | `decide_release` dipanggil di endpoint evidence (baris 854) dengan fallback degradasi; settlement di review (1354); keep-offer dihitung dan disimpan; nonce challenge acak. Sisa: placeholder `pass_demo_1` saat data Passport tidak ada, metrik biaya/latensi simulator tetap |
| AUD-02 | Refund PayPal stub | SEBAGIAN | `refund_capture_live`, `capture_order_live`, dan `verify_webhook_signature_live` kini ada. Namun aksi refund disimpan berstatus PLANNED dan tidak ada kode non-tes yang mengeksekusinya; tanpa kredensial, fallback tetap mengembalikan COMPLETED |
| RV-01 | Kunci token fail-open | TERATASI | rt: delapan pemeriksaan gagal-tertutup lulus; `AUTH_SIGNING_KEY` terpisah dan divalidasi di settings |
| AUD-04 | Validasi input | SEBAGIAN | 22 `model_validate` dan handler 422 `VALIDATION_FAILED`; persetujuan dan blur tanpa default permisif; `self_test_passed` wajib. Sisa: `declared_grade` default B di skema |
| AUD-06 | State di memori | TERATASI | Dict state sudah hilang; 108 pemanggilan repository |
| AUD-07 | Compose tidak bisa start | TERATASI (statis) | `psycopg[binary]` di dependensi, URL `postgresql+psycopg`, migrasi membaca `DATABASE_URL`, kredensial wajib diisi; belum diuji jalan di mesin bersih |
| AUD-24 | Verifikasi webhook | BELUM | Header `X-PayPal-Signature-Valid: true` tetap diterima dan didahulukan. Tanpa kredensial live, event diterima bila header `paypal-cert-url` berawalan domain PayPal, yang bisa diisi siapa pun. Dampaknya kini lebih besar karena processor sudah tersambung ke ledger |
| AUD-34 | Jenis tes kunci tidak ada | SEBAGIAN | Tes frontend Node dan tes tahap 1–7 ditambahkan; tetap tanpa Postgres, E2E browser, maupun refund lewat sistem; tes ST-01 live memanggil client langsung (Bagian G) |
| RV-02 | Seed audit dapat diturunkan | TERATASI | Seed `secrets.token_hex(32)` per return disimpan di `audit_seed_hex` |
| RV-03 | Guard literal True | SEBAGIAN | 29 argumen guard pada `apply_return_transition` masih literal `True`; guard lain (`within_window`, `evidence_complete`, persetujuan, otorisasi, `exposure_cap_ok`) kini dihitung atau divalidasi sebelum transisi. Namun `retakes_ok`, `eligible`, `not_expired`, dan `seal_nonce_matches` tidak divalidasi, dan agen yang menerima keep-offer dari DECLARED melewati bukti dan asesmen |
| AUD-03 | Artefak verifikasi hardcode | SEBAGIAN | Skenario CT tautologis tetap (`return_state.py` tidak berubah) |
| AUD-14 | Konfigurasi tidak tersambung | SEBAGIAN | `create_app` kini membaca parameter, env, lalu settings (default `demo_mode=False`), tetapi objek `app` di baris 2373 tetap dibuat dengan `demo_mode=True` |
| AUD-15 | Fallback tidak dipanggil | TERATASI | `apply_fallback_degradation` dipanggil di endpoint evidence |
| AUD-22 | BOLA pada resale | BELUM | Principal apa pun yang terautentikasi masih bisa membeli dan memindahkan Passport ke `new_owner_ref` dari body |
| AUD-25 | Endpoint operasional tanpa autentikasi | SEBAGIAN | Demo reset kini nyata dan dibatasi DEMO\_MODE serta MERCHANT\_ADMIN. Penghapusan data masih `required=False` |
| AUD-28 | Indikator kriptografi | SEBAGIAN | Kunci platform dan packer persisten dari settings dengan registry kunci publik dan fungsi verifikasi. `/passports/{id}/verify` tetap mengembalikan `chain_valid: True` tanpa memverifikasi |
| AUD-29 | Independensi reviewer | SEBAGIAN | Fallback ke reviewer dari record review; nilai `original_reviewer_id` dari body tetap didahulukan |
| AUD-33 | Tes mengunci perilaku keliru | SEBAGIAN | Kunci lama (22157, 20 tabel) sudah hilang; kunci baru muncul: staff-token tanpa autentikasi di-assert 200, webhook dikirim dengan header uji, stub refund di-assert COMPLETED (Bagian G.3) |
| AUD-36 | Celah kasus batas | SEBAGIAN | Tes untuk AUD-08, 12, 13, 17 ada; mutan guard T-SM01 dan arah seleksi audit lolos dari seluruh suite (Bagian G.2) |
| AUD-40 | Skema vs API | SEBAGIAN | Model Pydantic dipakai; tidak divalidasi terhadap file JSON Schema yang dipublikasikan |
| RV-04 | Harga keep-offer tidak konsisten | TERATASI | Tawaran dihitung sekali lewat `_get_or_compute_keep_offer` dan dipakai GET maupun respond |
| RV-05 | Pemindai secret buta | Tidak dinilai | Berkaitan dengan `.env`, yang sesuai permintaan pemilik tidak dinilai |
| RV-06 | CI menimpa marker | TERATASI | `-m "not live_model and not sandbox"` |
| RV-08 | Skema DB saat startup | TERATASI | Tanpa `create_all`; model dan migrasi sama-sama 22 tabel; file DB tidak lagi disalin ke image |
| RV-09 | Tanpa penerbitan identitas | SEBAGIAN | Endpoint `/v1/auth/staff-token` dan `/v1/auth/shopper-magic-link` ditambahkan, tetapi tanpa autentikasi (RV2-01) |
| RV-11 | Metrik tanpa autentikasi | TERATASI | Kedua endpoint mensyaratkan principal; label memakai template route |
| AUD-16 | Konstanta terduplikasi | SEBAGIAN | `domain/constants.py` dipakai 2 modul; cap tier di `trust.py` dan himpunan {EU, ID} di `policy.py` tetap |
| AUD-19 | Dependensi runtime hanya untuk tes | TERATASI | `jsonschema` dan `pyyaml` dipindah ke grup dev |
| AUD-26 | Kunci literal di journeys | TERATASI | Kunci literal `SerialRegistry` sudah dihapus |
| AUD-30 | Tanpa rate limiting | TERATASI | Rate limiter token bucket per IP/token dengan `Retry-After` dan batas body 10 MB |
| AUD-31 | Default kredensial Compose | SEBAGIAN | Kredensial DB wajib diisi; 5 default `:-` lain tetap |
| AUD-37 | Observability | SEBAGIAN | Log kini memuat `return_id`; scheduler alert tidak dijalankan (RV2-02) |
| AUD-38 | CI dan image | SEBAGIAN | `uv` dipin versi 0.6.3 dan base image `python:3.12-slim-bookworm`, belum digest; repo tanpa commit sehingga CI belum pernah berjalan |
| AUD-42 | Drift enum dan model | TERATASI | Model `RefundAction` memuat `merchant_id`, `capture_id`, `paypal_debug_id`, `attempt_count`, `version`; tier `ORIGIN_WITNESSED`/`LIGHT` hilang dari API dan frontend |
| RV-07 | Gate AG-01 tanpa margin | SEBAGIAN | Margin z·SE ditambahkan, tetapi rt: model terkalibrasi hanya lulus 4/10 karena margin mengabaikan ketidakpastian dari set kalibrasi |
| RV-12 | Audience, issuer, revocation | SEBAGIAN | `iss` dan `aud` diverifikasi (rt); `register_revocation_persistence` tidak dipanggil aplikasi; principal service tidak dibatasi tenant di GET return |
| RV-13 | Hardening container | TERATASI | `USER appuser`; semua port Compose di-bind ke `127.0.0.1` |
| RV-14 | Dedupe webhook hilang saat restart | TERATASI | `WebhookProcessor` menerima repository dan memeriksa event di DB |

### Status temuan dokumentasi

| ID | Status | Bukti |
| --- | --- | --- |
| DOC-01, DOC-02, DOC-03, DOC-04 | SEBAGIAN, kini usang | `rtm.csv`, gate record, dan `sandbox-tests.md` identik dengan revisi pertama: klaim yang dulu bertentangan masih ada, dan perbaikan baru belum tercatat |
| DOC-05 ADR generik | BELUM | Hanya ADR-028 yang berubah |
| DOC-06 Nama model AI | TERATASI | `config.py`, `models.yaml`, ADR-028, dan `.env.example` kini sama-sama `gemini-3.6-flash` |
| DOC-09 Repo tanpa commit | BELUM | `.git/objects` kosong |
| DOC-07, DOC-08, DOC-10 | BELUM | Tidak berubah |

### Temuan baru dari verifikasi

Detail lengkap akan masuk Bagian E.

- **RV2-01 (CRITICAL) Penerbitan token tanpa autentikasi.** `POST /v1/auth/staff-token` menerbitkan token untuk peran apa pun, termasuk MERCHANT\_ADMIN, cukup dengan `merchant_id`. `POST /v1/auth/shopper-magic-link` mengembalikan token shopper untuk `order_id` apa pun langsung di respons HTTP, tanpa pengiriman ke email pemilik. Dalam DEMO\_MODE, yang selalu aktif pada objek `app`, keberadaan merchant bahkan tidak diperiksa.
- **RV2-02 (MEDIUM) Scheduler otomasi tidak pernah dijalankan.** `BackgroundAutomationScheduler` tidak dirujuk aplikasi, Compose, maupun endpoint mana pun, sehingga eskalasi SLA, kedaluwarsa keep-offer, dan CUSUM tidak pernah berjalan.
- **Bukti tambahan untuk temuan lama.** Refund berstatus PLANNED tidak pernah dieksekusi (AUD-02); webhook bisa dipalsukan lewat header `paypal-cert-url` (AUD-24); 29 guard literal `True` (RV-03).

## B. Project Understanding: perubahan sejak revisi pertama

Revisi ke-2 adalah perubahan terbesar sejauh ini, dan sebagian besar menyasar langsung temuan audit ulang pertama: repository kini dipanggil API, client PayPal punya refund, capture, dan verifikasi webhook live, token gagal-tertutup dengan kunci terpisah, dan ada skema Pydantic, konstanta tunggal, scheduler, migrasi 0002, serta frontend TypeScript. Sebaliknya, `rtm.csv`, gate record, `sandbox-tests.md`, dan README tidak diperbarui sama sekali.

### Ringkasan perubahan

| Kategori | Jumlah | Isi utama |
| --- | --- | --- |
| File ditambahkan | 25 | `backend/api/schemas.py`, `backend/domain/constants.py`, `backend/jobs/automation.py`, migrasi `0002_complete_canonical_schema.py`, empat `App.ts` frontend, `packages/ui/src/index.ts`, tes frontend, 7 file tes remediasi tahap 1–7, bukti sesi 15–21, salinan laporan audit ulang pertama |
| File dihapus | 4 | Empat `App.tsx` lama |
| File diubah | 36 | `app.py` (1.449 menjadi 2.373 baris), `repository.py` (245 menjadi 753), `payments/client.py` (138 menjadi 295), `middleware.py` (107 menjadi 256), `auth/tokens.py`, `config.py`, `models.py`, `webhooks.py`, `signing.py`, `metrics.py`, `api-client`, Compose, Dockerfile, CI, `pyproject.toml`, `uv.lock` |
| Tidak berubah tetapi relevan | — | `docs/rtm.csv`, `docs/gates/final-acceptance.md`, `docs/sandbox-tests.md`, README, SSOT |

### Tech stack: revisi pertama dan revisi ke-2

| Lapisan | Revisi pertama | Revisi ke-2 (klaim, diverifikasi di Fase R) |
| --- | --- | --- |
| Persistensi | Repository hanya untuk seed dan ping | 108 pemanggilan repository di `app.py`; repository menerapkan migrasi Alembic tanpa `create_all` |
| Driver DB | Tidak ada driver Postgres | `psycopg[binary]`; Compose memakai `postgresql+psycopg`; `migrations/env.py` membaca `DATABASE_URL` |
| Autentikasi | Fallback ke konstanta, kunci = salt serial | Gagal-tertutup; `AUTH_SIGNING_KEY` terpisah; menolak nilai placeholder dan salt; `exp`, `iss`, `aud` wajib |
| PayPal | Refund dan capture stub | `refund_capture_live`, `capture_order_live`, `verify_webhook_signature_live`; fungsi stub tetap ada sebagai fallback tanpa kredensial |
| Validasi request | Tidak ada model | `backend/api/schemas.py` (181 baris) |
| Proses latar belakang | Tidak ada | `backend/jobs/automation.py` (202 baris) |
| Definisi bersama | Terduplikasi | `backend/domain/constants.py` (137 baris) |
| Frontend | Fungsi render string `.tsx` | Empat `App.ts` (140–224 baris) yang mengembalikan template string HTML; tanpa React atau Vite; skrip `dev` masih `echo` |
| Venv | Windows | Masih Windows (Python 3.12.13); tambahan `psycopg_binary` terkompilasi |

### Dokumentasi dan bukti pengujian yang disediakan

| Dokumen | Isi | Catatan awal |
| --- | --- | --- |
| `docs/evidence/session-15..21` | Remediasi tahap 1–7: auth gagal-tertutup, persistensi, PayPal live, hardening, konstanta, otomasi, frontend dan smoke run | Diverifikasi di Fase R |
| Klaim jumlah tes | 100, 111, lalu 144 passed (sesi 15, 16, 20) | Repo kini berisi 151 fungsi tes backend dan 6 tes frontend |
| `docs/rtm.csv`, gate record, `sandbox-tests.md` | Identik dengan revisi pertama | Tidak mencerminkan perbaikan maupun koreksi yang direkomendasikan |
| `data/proofreturn.db` | Diperbarui | Masih ikut dalam arsip |
| Laporan audit ulang pertama | Ditambahkan ke root repo | — |

### Perhatian awal

Poin di bawah sudah terlihat secara statis; status finalnya ditetapkan di Bagian R.

- **Literal tersisa di `app.py`.** `via_policy_engine: True` (baris 1427), `chain_valid: True` (1538, 1623, 1642), metrik biaya dan latensi tetap (2046), `RESET_COMPLETE` (2299), parameter header `X-PayPal-Signature-Valid` (2099), dan `app = create_app(demo_mode=True, mode="judge")` (2373).
- **Fallback stub PayPal.** `capture_order` dan `refund_capture` masih bisa mengembalikan status COMPLETED tanpa panggilan nyata bila kredensial tidak ada.
- **Frontend.** Kini berupa fungsi TypeScript yang menghasilkan HTML sebagai string; belum ada aplikasi yang bisa dijalankan di browser.
- **Dokumen status tidak diperbarui.** Klaim yang sebelumnya bertentangan dengan kode masih tercatat.

### Keterbatasan

Venv masih build Windows, sehingga tes yang membutuhkan FastAPI, pydantic, SQLModel, PyNaCl, psycopg, atau Hypothesis kemungkinan tetap BLOCKED. Node.js 22 tersedia di sandbox, sehingga tes frontend berpotensi dijalankan. Pendekatan lainnya sama seperti audit sebelumnya: modul pure-Python dijalankan langsung, fungsi tertentu diekstrak, dan test double berlabel dipakai bila perlu.

## C. SSOT Compliance Report — RTM revisi ke-2

Dari 137 requirement, 21 kini PASS, 90 PARTIAL, 10 FAIL, 12 NOT IMPLEMENTED, dan 4 NOT VERIFIED. FAIL turun dari 27 ke 10 dan PASS naik dari 10 ke 21, terutama karena endpoint uang kini memanggil Policy Engine dan settlement. Satu baris memburuk: isolasi tenant (NFR-11) kembali FAIL karena token bisa diminta siapa pun (RV2-01).

Rubrik status sama dengan audit sebelumnya. PASS berarti perilaku terverifikasi dan tersambung ke jalur sistem yang dituntut requirement; PARTIAL berarti logika ada tetapi tidak tersambung atau hanya sebagian terpenuhi; FAIL berarti implementasi bertentangan dengan requirement.

| Status | Audit awal | Revisi pertama | Revisi ke-2 |
| --- | --- | --- | --- |
| PASS | 9 | 10 | 21 |
| PARTIAL | 75 | 82 | 90 |
| FAIL | 35 | 27 | 10 |
| NOT IMPLEMENTED | 15 | 15 | 12 |
| NOT VERIFIED | 3 | 3 | 4 |

**Bukti eksekusi tes.** Backend: 39 lulus (14 native, 25 indikatif dengan test double `pydantic` dan stub Hypothesis), 108 BLOCKED karena FastAPI, pydantic, SQLAlchemy, atau jsonschema tidak tersedia, 1 tes Sandbox di-deselect, dan tidak ada yang gagal. Frontend: 6 dari 6 tes Node lulus (`node --test --experimental-strip-types`).

### Baris yang berubah status (29)

| ID | Revisi pertama | Revisi ke-2 | Bukti |
| --- | --- | --- | --- |
| FR-11 | NOT IMPLEMENTED | PARTIAL | Komponen rubrik di `packages/ui`; aplikasi belum bisa dijalankan di browser |
| FR-14 | FAIL | PARTIAL | Persetujuan eksplisit diwajibkan skema; penyajian syarat hanya berupa template string |
| FR-16 | FAIL | PARTIAL | Tanpa default permisif; blur tetap berdasarkan pernyataan klien |
| FR-21 | PARTIAL | PASS | `decide_release` dipanggil per return di endpoint evidence |
| FR-22 | NOT IMPLEMENTED | PARTIAL | Tranche direncanakan dan disimpan, tetapi tidak dieksekusi ke PayPal |
| FR-23 | PARTIAL | PASS | `settle_return` dipanggil di endpoint review |
| FR-26 | PARTIAL | PASS | Aturan adjacent dijalankan lewat `settle_return` yang tersambung |
| FR-28 | PARTIAL | PASS | Top-up dijalankan lewat `settle_return` yang tersambung |
| FR-33 | FAIL | PARTIAL | Evidence pack dibangun dari data; placeholder `pass_demo_1` bila data kosong |
| FR-35 | FAIL | PARTIAL | Sama dengan FR-33 |
| FR-39 | FAIL | PARTIAL | Refund keep-offer direncanakan, tidak dieksekusi |
| FR-49 | NOT IMPLEMENTED | PARTIAL | KPI dirender template console lewat API client |
| FR-50 | FAIL | PASS | Keputusan review lewat settlement, dengan pemeriksaan peran dan tenant |
| FR-51 | FAIL | PARTIAL | Request policy bertipe dan versi dibuat; tanpa preview simulator wajib |
| FR-58 | PARTIAL | PASS | Matriks timing diterapkan lewat `decide_release` di endpoint |
| FR-60 | PARTIAL | PASS | Rute STANDARD saat floor tidak layak, lewat engine di endpoint |
| FR-61 | FAIL | PASS | Seed acak per return; hanya commitment yang dikirim |
| FR-74 | PARTIAL | PASS | `has_origin_passport` dikirim ke engine |
| FR-76 | FAIL | PARTIAL | Kunci platform persisten; `verified: True` tetap literal; tidak ada endpoint kunci publik |
| FR-80 | FAIL | PARTIAL | Evaluator dipanggil dengan label replay; rekaman masih berupa daftar hash fixture |
| FR-85 | FAIL | PARTIAL | Compose lengkap secara statis; belum diuji di mesin bersih |
| FR-90 | FAIL | PARTIAL | Request policy bertipe; cap jurisdiksi tidak divalidasi |
| FR-95 | FAIL | PASS | Seed rahasia acak per return |
| FR-98 | FAIL | PARTIAL | `self_test_passed` wajib eksplisit; tanpa video atau hash |
| NFR-07 | FAIL | PARTIAL | Compose lengkap secara statis |
| NFR-11 | PARTIAL | FAIL | Token staff dan shopper bisa diminta siapa pun tanpa autentikasi (RV2-01) |
| NFR-15 | FAIL | NOT VERIFIED | Belum ada run di mesin bersih |
| INV-14 | FAIL | PARTIAL | Tranche tidak lagi hardcode; exposure dicek saat approval; cap akun dan merchant tidak dikirim ke engine |
| INV-16 | FAIL | PASS | Seed rahasia acak; hanya commitment yang dikirim |

### Matriks lengkap per status

| Status | Requirement |
| --- | --- |
| PASS (21) | FR-21, 23, 26, 28, 31, 43, 44, 50, 58, 60, 61, 74, 89, 95; INV-05, 07, 08, 10, 15, 16, 18 |
| FAIL (10) | FR-20, 63, 69, 96; NFR-04, 11, 13, 16; INV-09, 11 |
| NOT IMPLEMENTED (12) | FR-02, 07, 17, 34, 41, 54, 77, 83; NFR-01, 06, 09, 10 |
| NOT VERIFIED (4) | FR-48, 86; NFR-02, 15 |
| PARTIAL (90) | FR-01, 03, 04, 05, 06, 08, 09, 10, 11, 12, 13, 14, 15, 16, 18, 19, 22, 24, 25, 27, 29, 30, 32, 33, 35, 36, 37, 38, 39, 40, 42, 45, 46, 47, 49, 51, 52, 53, 55, 56, 57, 59, 62, 64, 65, 66, 67, 68, 70, 71, 72, 73, 75, 76, 78, 79, 80, 81, 82, 84, 85, 87, 88, 90, 91, 92, 93, 94, 97, 98, 99, 100, 101, 102, 103; NFR-03, 05, 07, 08, 12, 14; INV-01, 02, 03, 04, 06, 12, 13, 14, 17 |

Bukti untuk baris yang tidak berubah tetap seperti di laporan audit ulang pertama.

### Akurasi rtm.csv

`docs/rtm.csv` tidak diperbarui sejak revisi pertama, sehingga kini meleset ke dua arah.

| Penilaian | Jumlah | Requirement |
| --- | --- | --- |
| Klaim VERIFIED yang didukung (PASS) | 13 | FR-31, 43, 44, 61, 74, 89; INV-05, 07, 08, 10, 15, 16, 18 |
| Klaim VERIFIED yang hanya PARTIAL | 12 | FR-09, 37, 45, 72, 76, 80, 82, 91; NFR-08; INV-01, 04, 12 |
| Klaim VERIFIED yang bertentangan | 2 | NFR-04 (webhook masih menerima header klien), NFR-11 (RV2-01) |
| PASS menurut audit, tetapi belum VERIFIED di rtm.csv | 8 | FR-21, 23, 26, 28, 50, 58, 60, 95 |

## D. Architecture Compliance Report

Untuk pertama kalinya API benar-benar mengorkestrasi domain: Policy Engine, settlement, keep-offer, ledger, webhook processor, evaluator AI, dan repository berada di jalur endpoint. Tiga celah arsitektural tersisa: tidak ada eksekutor refund (aksi berhenti di PLANNED), scheduler otomasi tidak pernah dijalankan, dan beberapa komponen domain (trust, CUSUM, konformal, custody, seal, MCP) masih di luar jalur.

&#91;embedded content: arsitektur aktual revisi ke-2\]

Kotak hijau adalah logika keputusan uang yang kini dipanggil endpoint; garis merah menandai titik di mana aliran uang berhenti.

### Status penyimpangan sebelumnya

| ID | Penyimpangan | Status | Bukti |
| --- | --- | --- | --- |
| ARC-01 | API tidak memakai engine | TERATASI | `release`, `settlement`, `keep_offer`, ledger, webhook processor, dan evaluator di-import langsung oleh `app.py` |
| ARC-02 | Jalur uang PayPal | SEBAGIAN | Fungsi live refund, capture, dan verifikasi webhook ada; tidak ada eksekutor untuk aksi PLANNED (ARC-19) |
| ARC-03 | Model autentikasi API-04 | SEBAGIAN | Token kuat dan gagal-tertutup; penerbitan token staff dan shopper tanpa autentikasi (RV2-01) |
| ARC-04 | Persistensi | TERATASI | Endpoint memakai 36 dari 56 metode repository; dict state hilang |
| ARC-05 | Workflow dan timer | SEBAGIAN | `BackgroundAutomationScheduler` ada tetapi tidak pernah dijalankan (RV2-02) |
| ARC-06 | Server ASGI | TERATASI (statis) | `uvicorn` di service `api` Compose dengan driver Postgres |
| ARC-07 | Frontend | SEBAGIAN | Controller TypeScript dengan API client dan template HTML string; tanpa bundler atau halaman yang bisa dibuka |
| ARC-08 | Kontrak Pydantic | SEBAGIAN | Request divalidasi lewat `model_validate`; karena handler menerima `Request` mentah, skema tidak muncul di OpenAPI (API-11) |
| ARC-09 | DB, RLS, migrasi | SEBAGIAN | Migrasi sinkron dan constraint lengkap; tanpa RLS |
| ARC-10 | Konfigurasi | SEBAGIAN | Resolusi parameter, env, settings sudah benar; objek `app` memaksa `demo_mode=True` |
| ARC-11 | Penyedia AI tanpa Change Control | BELUM | Tetap Gemini; nama model kini konsisten |
| ARC-12 | MCP bukan server | BELUM | Tanpa SDK maupun transport |
| ARC-13 | Arah dependensi | SEBAGIAN | `config.py` tidak lagi meng-import payments; `domain/journeys.py` masih meng-import payments dan agent gateway |
| ARC-14 | Dua sumber state | TERATASI | Semua state lewat repository |
| ARC-15 | Skema lewat `create_all` | TERATASI | Migrasi Alembic; model dan migrasi sama-sama 22 tabel |
| ARC-16 | SQLite sebagai default | SEBAGIAN | Postgres di Compose; default lokal dan `alembic.ini` tetap SQLite |
| ARC-17 | Penerbitan identitas | SEBAGIAN | Endpoint ada, tetapi terbuka (RV2-01) |

### Penyimpangan baru

| ID | Penyimpangan | Bukti | Severity indikatif |
| --- | --- | --- | --- |
| ARC-18 | Komponen domain masih terputus | `domain/trust.py`, `account_monitor.py`, `ai/calibration/conformal.py`, `custody.py`, `return_seal.py`, dan MCP tidak terjangkau dari API; tier dan cap tidak dihitung dari riwayat akun | MEDIUM |
| ARC-19 | Tidak ada eksekutor outbox refund | Ledger menyimpan aksi PLANNED; tidak ada sweeper, worker, maupun endpoint yang memanggil `refund_capture` (ADR-006) | HIGH |

### Database (§30)

| Aturan | Temuan |
| --- | --- |
| DB-01 BIGINT + `currency` | 35 kolom `BigInteger`, 10 kolom `currency` |
| DB-02 `ON DELETE RESTRICT` | 35 relasi |
| DB-03 dan INV-01 | 8 CHECK constraint, termasuk batas refund terhadap capture |
| DB-07 kolom `version` | 10 tabel |
| ADR-012 RLS | Tidak ada |
| MG-01 Alembic | Model dan migrasi sinkron (22 tabel) |

### Konvensi API (§28.1)

| Konvensi | Status | Bukti |
| --- | --- | --- |
| API-01 base `/v1` | Sesuai | 42 route |
| API-02 UUIDv7 | Tidak | ID berbasis potongan UUID4 |
| API-04 jenis token | Sebagian | Token kuat; penerbitan terbuka |
| API-05 di luar scope menjadi 404 | Sebagian besar | Pemeriksaan tenant dan order di endpoint return |
| API-06 `Idempotency-Key` | Tidak | Dirujuk di 2 tempat untuk 25 endpoint POST |
| API-07 problem+json | Sebagian | 13 dari 18 kode error di luar katalog §28.2 |
| API-08 `If-Match` | Tidak | Kolom `version` ada di DB, tidak dipakai API |
| API-10 `X-Request-Id` | Sesuai | Middleware |
| API-11 OpenAPI dari Pydantic | Sebagian | Lihat ARC-08 |

Endpoint pembatalan (`POST /v1/returns/{id}/cancel`) dan penerbitan token agen kini ada; seluruh route tetap di satu file tanpa `APIRouter`.

### Perubahan kepatuhan ADR

| ADR | Revisi pertama | Revisi ke-2 |
| --- | --- | --- |
| ADR-001 FastAPI + Pydantic | Tanpa model request | Model request dengan 422; belum di OpenAPI |
| ADR-006 Outbox + request ID | Ledger in-memory | Aksi PLANNED dipersistenkan; tanpa sweeper |
| ADR-017 Konformal | Ada, tidak tersambung | Tetap tidak tersambung ke keputusan |
| ADR-018, ADR-026 Commit–reveal, receipt | Seed dapat diturunkan, kunci efemeral | Seed acak rahasia; kunci penandatangan persisten |
| ADR-003, 010, 012 | Tidak dipenuhi | Tetap tidak dipenuhi |

## E. Technical Findings revisi ke-2

Revisi ke-2 memiliki 26 temuan terbuka ditambah 1 catatan informasional: 2 CRITICAL, 4 HIGH, 10 MEDIUM, dan 10 LOW. Enam di antaranya baru (RV2-01 sampai RV2-06); sisanya temuan lama yang masih terbuka dengan severity dinilai ulang. Temuan yang teratasi tidak dihitung (lihat Bagian R).

| Severity | Audit awal | Revisi pertama | Revisi ke-2 |
| --- | --- | --- | --- |
| CRITICAL | 3 | 3 | 2 |
| HIGH | 9 | 7 | 4 |
| MEDIUM | 20 | 16 | 10 |
| LOW | 8 | 12 | 10 |
| Total terbuka | 40 | 38 | 26 |

### CRITICAL

#### RV2-01 · CRITICAL · Security — Token staff dan shopper bisa diminta siapa pun

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 391–422 (`POST /v1/auth/staff-token`), 424–454 (`POST /v1/auth/shopper-magic-link`) |
| Bukti | Kedua handler tidak memanggil `_resolve_principal` maupun memeriksa kredensial apa pun. Staff-token menerima `merchant_id`, `role` (termasuk MERCHANT\_ADMIN), dan `staff_id` dari body, lalu langsung mengembalikan token. Magic link mengembalikan token shopper untuk `order_id` apa pun di respons HTTP. Bila DEMO\_MODE aktif, yang selalu terjadi pada objek `app`, keberadaan merchant dan order bahkan tidak diperiksa. |
| Penjelasan | Mesin token kini kuat (RV-01 teratasi), tetapi server sendiri menandatangani token untuk siapa saja. API-04 mensyaratkan login staff lewat penyedia identitas dan magic link yang dikirim ke pemilik order. |
| Skenario eksploitasi | `curl -X POST /v1/auth/staff-token -d '{"merchant_id":"merch_a","role":"MERCHANT_ADMIN","staff_id":"x"}'` menghasilkan token admin; dengan magic link, penyerang mengambil alih return milik shopper lain. |
| Dampak | Isolasi tenant dan kepemilikan return tidak bermakna; NFR-11 kembali FAIL. |
| Rekomendasi | Untuk demo: aktifkan kedua endpoint hanya bila DEMO\_MODE benar-benar diatur lewat environment, dan beri label jelas. Untuk rilis: login staff dengan kredensial atau SSO; magic link dikirim ke email pemilik order dan ditukar dengan token sekali pakai. |
| Confidence | High |

#### AUD-02 · CRITICAL · Functional — Refund tidak pernah dieksekusi ke PayPal

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 884–925, 1376–1405; `backend/payments/client.py`: 162–262 |
| Bukti | Aksi refund disimpan dengan status PLANNED. Tidak ada kode non-tes yang memanggil `refund_capture` atau `refund_capture_live`, dan tidak ada sweeper outbox (ARC-19). `capture_id` yang dipakai adalah karangan `CAP-{order_id}`, bukan ID capture PayPal. Tanpa kredensial, `refund_capture` dan `capture_order` tetap mengembalikan status COMPLETED. |
| Penjelasan | Fungsi live yang ditambahkan benar secara bentuk, tetapi tidak berada di jalur mana pun. |
| Dampak | Nilai utama produk, yaitu refund bertahap via PayPal, tetap tidak terjadi. Bila eksekutor ditambahkan apa adanya, refund akan diarahkan ke capture yang tidak ada. |
| Rekomendasi | Simpan ID capture asli saat pembelian; buat eksekutor outbox yang mengambil aksi PLANNED, memanggil `refund_capture_live` dengan `PayPal-Request-Id`, lalu memperbarui status; hapus fallback COMPLETED dari jalur produksi; jalankan ST-01. |
| Confidence | High |

### HIGH

#### RV2-04 · HIGH · Functional — Penolakan INV-01 ditelan lalu refund tetap disimpan

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 890–908 (evidence), 1376–1390 (review), 1416–1417 (`InvalidStateTransitionError`), 201–212 (registrasi ledger saat startup) |
| Bukti | `plan_refund_action` dibungkus `except Exception: pass`, lalu `RefundAction` tetap dibuat dan disimpan ke DB. Ledger hidup di memori dan hanya merehidrasi order saat startup, bukan aksi yang sudah direncanakan; kolom `pending_refunded_minor` di DB tidak diperbarui, sehingga CHECK constraint INV-01 tidak pernah berlaku. Kegagalan transisi di endpoint review juga ditelan dan respons tetap 200. |
| Penjelasan | Pelindung yang sudah terbukti benar di pustaka (lock ledger, OverRefundError) dinetralkan oleh penanganan exception di endpoint. |
| Dampak | Aksi refund yang melampaui capture bisa tersimpan, dan setelah restart batas yang tersisa dihitung ulang dari nol. Saat eksekutor ditambahkan, ini menjadi over-refund nyata. |
| Rekomendasi | Biarkan `OverRefundError` menghasilkan 409; perbarui `pending_refunded_minor` dalam transaksi yang sama dengan penyimpanan aksi (row lock); rehidrasi ledger dari DB atau ganti ledger in-memory dengan query DB; jangan menelan kegagalan transisi. |
| Confidence | High |

### MEDIUM (temuan baru)

#### RV2-02 · MEDIUM · Reliability — Scheduler otomasi tidak pernah dijalankan

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/jobs/automation.py` (`BackgroundAutomationScheduler`, `run_all_automation_jobs`); `backend/api/app.py`; `infra/docker-compose.yml` |
| Bukti | Tidak ada rujukan ke modul otomasi di aplikasi, Compose, maupun endpoint mana pun. |
| Penjelasan | Kode scheduler sudah ada, tetapi tidak pernah dimulai. |
| Dampak | Eskalasi SLA (FR-97), kedaluwarsa keep-offer, drift CUSUM, serta timer NOT\_RECEIVED dan holdback tidak pernah berjalan. |
| Rekomendasi | Jalankan di `lifespan` FastAPI atau sebagai service worker terpisah di Compose, lalu uji end-to-end. |
| Confidence | High |

#### RV2-03 · MEDIUM · Functional — Keep-offer tetap ditawarkan saat engine menolak

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 1157–1195 (`_get_or_compute_keep_offer`) |
| Bukti | `posted_price = ko_dec.posted_price_minor or 5250`: bila `compute_posted_keep_offer` tidak menghasilkan harga (tidak layak atau `k_max` tidak positif), handler tetap menawarkan 5250. |
| Penjelasan | FR-37 dan FR-78 mensyaratkan tidak ada tawaran untuk return yang tidak layak, dan harga tidak melampaui (1−θ)·k\_max. |
| Dampak | Tawaran yang melanggar batas dan kelayakan; untuk barang murah, tawaran bisa melebihi refund yang terutang. |
| Rekomendasi | Kembalikan “tidak ada tawaran” (misalnya 404 `NO_KEEP_OFFER`) bila engine tidak menghasilkan harga. |
| Confidence | High |

#### RV2-05 · MEDIUM · Architecture — Komponen domain kunci belum tersambung

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/domain/trust.py`, `account_monitor.py`, `custody.py`, `return_seal.py`; `backend/ai/calibration/conformal.py`; `backend/api/app.py`: 800–900 |
| Bukti | Modul-modul ini tidak terjangkau dari API (ARC-18). `decide_release` dipanggil tanpa `account_cap_remaining_minor` dan `merchant_cap_remaining_minor`, sehingga memakai default 100000 dan 500000. |
| Penjelasan | Tier, cap exposure, CUSUM, dan uji konformal yang sudah benar di pustaka tidak memengaruhi keputusan. |
| Dampak | Cap INV-14 dan FR-92 tidak ditegakkan per akun; promosi dan downgrade tier tidak terjadi; set konformal dari evaluator tidak terkalibrasi. |
| Rekomendasi | Hitung tier dan cap dari riwayat akun di DB, kirim ke engine, dan pakai kalibrator konformal untuk uji misdeclaration. |
| Confidence | High |

### LOW (temuan baru)

#### RV2-06 · LOW · Security — Kunci idempotensi tidak dibatasi per pengguna

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 525 |
| Bukti | `cache_key = f"POST:/v1/returns:{idempotency_key}"` tidak memuat identitas principal. |
| Penjelasan | Pengguna lain yang memakai `Idempotency-Key` sama dengan body identik menerima respons tersimpan milik pengguna pertama; dengan body berbeda, ia menerima 409. |
| Dampak | Kebocoran respons lintas pengguna bila kunci bisa ditebak, dan gangguan kecil antarpengguna. |
| Rekomendasi | Sertakan subjek token (dan tenant) dalam kunci cache, sesuai API-06. |
| Confidence | High |

### Temuan lama yang masih terbuka

Severity dinilai ulang sesuai kondisi revisi ke-2. Kartu atribut asli ada di laporan sebelumnya; tabel ini mencatat sisa masalah dan lokasinya sekarang.

| ID | Severity | Kategori | Sisa masalah | Rekomendasi | Confidence |
| --- | --- | --- | --- | --- | --- |
| AUD-24 | HIGH | Security | Header `X-PayPal-Signature-Valid: true` diterima dan didahulukan; tanpa kredensial, header `paypal-cert-url` berawalan domain PayPal cukup untuk lolos; processor kini membekukan order dan menolkan refundable (`app.py`: 2099–2140) | Hapus header uji dari jalur produksi; verifikasi selalu lewat API PayPal; tolak bila kredensial tidak ada | High |
| RV-03 | HIGH | Functional | 29 argumen guard pada `apply_return_transition` literal `True`; sebagian guard lain dihitung atau divalidasi sebelumnya; `retakes_ok`, `eligible`, `not_expired`, `seal_nonce_matches` tidak divalidasi; agen yang menerima keep-offer dari DECLARED melewati bukti dan asesmen | Hitung guard dari data | High |
| AUD-34 | HIGH | Testing | Tanpa Playwright, Postgres, dan refund Sandbox; tes ST-01 live memanggil client langsung, bukan alur sistem; skor mutasi subset 55% (Bagian G) | Contract test endpoint vs engine; integrasi Postgres; ST-01 lewat sistem | High |
| AUD-14 | MEDIUM | Architecture | `app = create_app(demo_mode=True, mode="judge")` mengabaikan env dan settings; endpoint demo dan pelonggaran RV2-01 aktif di semua deploy | Buat `app` tanpa memaksa `demo_mode` | High |
| AUD-22 | MEDIUM | Security | Resale order: principal apa pun memindahkan Passport ke `new_owner_ref` dari body, tanpa capture | Batasi ke pembeli terverifikasi setelah capture | High |
| AUD-25 | MEDIUM | Security | Permintaan penghapusan data dengan `required=False` | Autentikasi wajib dan verifikasi subjek | High |
| AUD-28 | MEDIUM | Security | `/passports/{id}/verify` mengembalikan `chain_valid: True` tanpa verifikasi; receipt memuat `verified: True` literal; tanpa endpoint kunci publik | Verifikasi signature dan chain sungguhan; terbitkan kunci publik | High |
| AUD-29 | MEDIUM | Security | `original_reviewer_id` dari body didahulukan atas record review | Ambil hanya dari record | High |
| AUD-33 | MEDIUM | Testing | Tes meng-assert staff-token tanpa autentikasi menghasilkan 200, mengirim webhook dengan header uji, dan meng-assert stub refund COMPLETED (Bagian G.3) | Ubah assertion menjadi perilaku aman yang diharapkan (401, 400, tanpa COMPLETED palsu) | High |
| AUD-36 | MEDIUM | Testing | Mutan guard T-SM01 dan arah seleksi audit lolos dari seluruh suite; tanpa tes untuk RV2-02, RV2-03, RV2-04 | Tes regresi untuk tiap temuan, termasuk guard bernilai False dan laju seleksi audit | High |
| AUD-04 | LOW | Functional | `declared_grade` default B di skema dan di beberapa fallback endpoint | Jadikan field wajib | High |
| AUD-40 | LOW | Functional | Model Pydantic tidak divalidasi terhadap JSON Schema publik dan tidak tampil di OpenAPI | Generate dari skema yang sama; parameter bertipe | High |
| AUD-03 | LOW | Testing | Skenario CT tautologis di `return_state.py` | Uji konkurensi sungguhan | High |
| RV-07 | LOW | Testing | Margin AG-01 hanya memperhitungkan ukuran set uji; rt: model terkalibrasi lulus 4/10 | Sertakan ketidakpastian set kalibrasi | High |
| RV-12 | LOW | Security | Persistensi revocation tidak didaftarkan; principal service tanpa batas tenant di GET return | Daftarkan persistensi; batasi principal service | High |
| AUD-16 | LOW | Architecture | Cap tier di `trust.py` dan himpunan {EU, ID} di `policy.py` tetap terduplikasi | Pakai `domain/constants.py` | High |
| AUD-31 | LOW | Security | Lima default `:-` tersisa di Compose | Wajibkan semua nilai | High |
| AUD-37 | LOW | Reliability | Log tanpa `decision_id` dan `paypal_debug_id`; alert tanpa scheduler (RV2-02) | Tambah field; jadwalkan alert | High |
| AUD-38 | LOW | Reliability | Base image tanpa digest; repo tanpa commit sehingga CI belum pernah berjalan | Pin digest; jalankan CI | High |

RV-05 tidak dinilai karena berkaitan dengan `.env`, sesuai permintaan pemilik.

### INFORMATIONAL

#### RV2-INFO — Kekuatan yang terverifikasi

| Area | Bukti |
| --- | --- |
| Orkestrasi | Endpoint evidence dan review memanggil `decide_release`, fallback degradasi, dan `settle_return` |
| Autentikasi | Token gagal-tertutup, `exp`/`iss`/`aud` wajib, kunci terpisah dari salt (rt) |
| Persistensi | Semua state lewat repository; model dan migrasi sinkron; constraint DB lengkap kecuali RLS |
| Kriptografi | Seed audit acak rahasia; kunci penandatangan persisten dengan registry kunci publik |
| Hardening | Rate limiting, batas body, container non-root, port lokal, dedupe webhook di DB |
| Kualitas kode | 400/400 fungsi beranotasi tipe; mekanisme §8.8 tetap 180/180 |

## F. Security Assessment revisi ke-2

Fondasi keamanan kini kuat: token gagal-tertutup dengan kunci terpisah, validasi request, rate limiting, seed audit rahasia, kunci penandatangan persisten, dan container non-root. Namun dua celah menghapus sebagian besar manfaat itu: token bisa diminta siapa pun (RV2-01), dan webhook bisa dipalsukan (AUD-24), kini dengan efek nyata pada ledger.

### Ringkasan per kategori

| Kategori | Revisi pertama | Revisi ke-2 | Temuan terkait |
| --- | --- | --- | --- |
| Autentikasi dan session | Rentan | Rentan | RV2-01: mesin token kuat, tetapi penerbitan terbuka; TTL token mandiri hingga 7 hari; token magic link di query string |
| Otorisasi dan BOLA | Sebagian | Sebagian | AUD-22 (resale), AUD-29 (reviewer), AUD-25 (penghapusan data), RV-12 (principal service) |
| Integritas webhook | Rentan | Rentan, dampak naik | AUD-24 |
| Manajemen secret di kode | Sebagian | Baik | Default acak, validator, kunci token terpisah; AUD-31 tersisa; `.env` tidak dinilai |
| Paparan data | Sebagian | Membaik | Metrik kini terautentikasi; RV2-06 (idempotensi lintas pengguna) |
| Validasi input | Rentan | Membaik | Model Pydantic dan 422; AUD-04 tersisa |
| Kriptografi | Sebagian | Membaik | Seed rahasia, kunci persisten, AEAD; AUD-28 (verifikasi literal) |
| Rate limiting | Tidak ada | Ada | Token bucket per IP/token, batas body 10 MB |
| Injection, deserialisasi, path traversal | Tidak ditemukan | Tidak ditemukan | ORM; satu-satunya SQL mentah `SELECT 1` |
| SSRF | Tidak ditemukan | Tidak ditemukan | `cert_url` diteruskan sebagai data ke API PayPal, tidak di-fetch server |
| Container dan jaringan | Lemah | Baik | Non-root; port Compose hanya ke `127.0.0.1` |
| Logging data sensitif | Baik | Baik | Middleware mencatat path tanpa query string |

### Kepatuhan threat model (§32.4)

| Ancaman | Revisi pertama | Revisi ke-2 |
| --- | --- | --- |
| TM-05 IDOR lintas tenant | Sebagian | Sebagian: scoping per endpoint baik, tetapi RV2-01 memberi token untuk tenant dan order mana pun; tanpa RLS |
| TM-06 Webhook palsu | Tidak ada di endpoint | Tidak ada: header uji dan prefiks `cert-url` cukup untuk lolos |
| TM-07 Over-refund lewat race | Lock di pustaka | Lock dinetralkan oleh exception yang ditelan di endpoint (RV2-04) |
| TM-14 SSRF | Terpenuhi | Terpenuhi |
| TM-15 DoS dan biaya | Tidak ada | Terpenuhi sebagian: rate limit dan batas body |
| TM-16 Pembayaran live tak sengaja | Terpenuhi | Terpenuhi |
| TM-17 Retake oracle | Guard literal | Tetap guard literal (RV-03) |
| TM-22 Operator mengubah record | Tidak terverifikasi | Sebagian: seed dan signature nyata; verifikasi Passport tetap literal (AUD-28) |
| TM-24 Carrier event palsu | Sebagian | Gagal secara efektif: endpoint mensyaratkan staff atau service, tetapi token staff bisa diminta siapa pun |

### Rantai serangan paling realistis

1. Penyerang memanggil `POST /v1/auth/shopper-magic-link` dengan `order_id` korban dan menerima token shopper, lalu mendeklarasikan, menerima keep-offer, atau mengajukan banding atas return milik korban.
2. Penyerang memanggil `POST /v1/auth/staff-token` dengan peran REVIEWER, lalu memutus review dengan grade terverifikasi pilihannya sendiri.
3. Penyerang mengirim webhook `PAYMENT.CAPTURE.REVERSED` dengan header `X-PayPal-Signature-Valid: true`, sehingga sisa refundable order mana pun menjadi nol.

Uang belum berpindah karena tidak ada eksekutor refund, tetapi keputusan dan state tercemar. Begitu eksekutor ditambahkan, rantai yang sama berdampak finansial langsung.

### Area yang tidak dapat dinilai

- **Kerentanan dependensi.** Tanpa akses ke basis data advisori; tidak ada klaim CVE.
- **Uji penetrasi HTTP.** FastAPI tidak bisa dijalankan di sandbox audit; temuan HTTP berbasis analisis statis dan eksekusi fungsi terisolasi.
- **PayPal Sandbox dan Gemini.** Tidak ada panggilan jaringan, sesuai aturan audit.
- **`.env` dan pemindai secret.** Tidak dinilai sesuai permintaan pemilik.

## G. Testing & QA Report revisi ke-2

Suite tes tumbuh menjadi 151 tes backend (1.037 assertion) dan 6 tes frontend. Cakupannya lebar: ke-42 route dipanggil sedikitnya oleh satu tes. Namun kedalamannya belum sebanding. Mutation testing menunjukkan 5 dari 11 bug yang disuntikkan lolos dari tes yang bisa dijalankan, dan 2 di antaranya lolos dari seluruh suite. Beberapa tes juga mengunci celah keamanan sebagai perilaku yang benar.

| Ukuran | Revisi pertama | Revisi ke-2 |
| --- | --- | --- |
| Tes backend | 98 di 15 file, 662 assertion | 151 di 22 file, 1.037 assertion |
| Tes frontend | — | 6 (Node, `node --test`) |
| Lulus saat dijalankan auditor | 39 (14 native, 25 indikatif) | 45: 14 native, 25 indikatif, 6 frontend |
| BLOCKED | 58 | 111: 108 tidak bisa dikoleksi, 3 tes `@given` |
| Deselected | 1 | 1 (tes Sandbox) |
| Gagal | 0 | 0 |
| Route tercakup secara statis | — | 42 dari 42 |
| Skor mutasi (subset yang bisa dijalankan) | — | 6 dari 11 mutan tertangkap (55%) |

### G.1 Testing Verification Report

| Kategori | Tes | Status eksekusi | Hasil | Catatan |
| --- | --- | --- | --- | --- |
| Unit: state machine | 4 | Native | 4 lulus | Tidak ada tes guard bernilai `False` |
| Unit: provider Gemini | 5 | Native | 5 lulus | HTTP di-mock |
| Unit: payments, ledger, webhook, FX | 6 | Native | 5 lulus, 1 deselected | Menangkap mutan INV-01 dan dedupe |
| Unit: golden examples | 10 | Indikatif | 10 lulus | Menangkap mutan margin μ dan rute STANDARD |
| Unit: Policy Engine | 18 | Indikatif | 15 lulus, 3 BLOCKED | Menangkap mutan INV-10 dan batas keep-offer |
| Remediasi tahap 1–7 | 53 | BLOCKED | — | FastAPI, SQLAlchemy |
| Remediasi fase 3–6 dan API lama | 32 | BLOCKED | — | FastAPI |
| Mekanisme, AI pipeline, ops, domain | 23 | BLOCKED | — | pydantic, FastAPI, jsonschema |
| Frontend (`packages/ui/tests`) | 6 | Node 22 | 6 lulus | Memeriksa HTML string dan state controller; tanpa DOM, aksesibilitas, atau performa |
| E2E browser, integrasi Postgres, refund Sandbox lewat sistem | 0 | Tidak ada | — | Tes ST-01 live memanggil client langsung, tidak melalui API |

### G.2 Mutation testing

Setiap mutan diterapkan di salinan sementara terpisah, lalu 38 tes yang bisa dijalankan (state machine, payments, golden, Policy Engine) dieksekusi ulang. Baseline: 34 lulus, 3 di-skip, 1 deselected.

| Mutan | Bug yang disuntikkan | Hasil di subset | Tes BLOCKED yang merujuk perilaku ini |
| --- | --- | --- | --- |
| M01 | Cek over-refund ledger dimatikan (INV-01) | Tertangkap oleh 3 tes | — |
| M02 | Konflik re-plan ledger dimatikan (AUD-18) | Lolos | Ada (tahap 4, fase 4) |
| M03 | Dedupe webhook dimatikan | Tertangkap oleh 2 tes | — |
| M04 | Margin μ dihapus dari `X_max` (FR-89) | Tertangkap oleh 6 tes | — |
| M05 | Rute STANDARD saat `p > p_max` dimatikan (FR-60) | Tertangkap oleh 2 tes | — |
| M06 | Eskalasi gross tanpa reviewer dimatikan (AUD-08) | Lolos | Ada (fase 4, fase 6) |
| M07 | Syarat konfirmasi manusia INV-10 dihapus | Tertangkap oleh 1 tes | — |
| M08 | Promosi NEW langsung ke TRUSTED (AUD-13) | Lolos | Ada (fase 4, fase 6) |
| M09 | Guard T-SM01 state machine dimatikan (INV-04) | Lolos | Tidak ada: tidak satu pun tes memakai guard bernilai `False` |
| M10 | Batas (1−θ)·k\_max keep-offer dihapus (FR-37) | Tertangkap oleh 1 tes | — |
| M11 | Arah seleksi audit dibalik (FR-95) | Lolos | Tidak ada: tes hanya memeriksa determinisme, bukan arah |

Tiga mutan yang lolos (M02, M06, M08) kemungkinan tertangkap oleh tes yang BLOCKED di lingkungan audit. M09 dan M11 lolos dari seluruh suite: logika guard state machine dan arah seleksi audit tidak teruji sama sekali.

### G.3 Tes yang mengunci perilaku keliru

- **Penerbitan token terbuka (RV2-01).** `test_remediation_tahap4` (baris 75) dan `tahap7` (baris 167) meng-assert `POST /v1/auth/staff-token` tanpa autentikasi menghasilkan 200.
- **Bypass webhook (AUD-24).** Lima pemanggilan di `tahap3` mengirim webhook dengan header `X-PayPal-Signature-Valid: true` sebagai cara normal. Ada tes negatif untuk `cert-url` domain penyerang, tetapi tidak untuk header uji maupun `cert-url` palsu berprefiks domain PayPal.
- **Stub refund (AUD-02).** `tahap3` (baris 44–62) meng-assert `status == "COMPLETED"` dan `paypal_debug_id` tidak kosong dari client offline.
- **Guard “dinamis” (RV-03).** `test_rv03_dynamic_state_machine_guards` menguji jendela waktu, cap exposure, dan agen yang menolak keep-offer, tetapi tidak menguji agen yang menerima keep-offer dari DECLARED, yaitu jalur yang melewati bukti.

### G.4 Celah cakupan

Tidak ada tes untuk: guard bernilai `False` di state machine; arah dan laju seleksi audit; keep-offer saat engine menyatakan tidak layak (RV2-03); over-refund lewat endpoint, tempat `OverRefundError` ditelan (RV2-04); scheduler yang dijalankan oleh aplikasi (RV2-02); webhook dengan `cert-url` palsu berprefiks PayPal; start service `api` di Compose; integrasi Postgres; dan E2E di browser.

### G.5 Verifikasi klaim sesi 15–21

| Klaim | Sesi | Hasil verifikasi |
| --- | --- | --- |
| Auth gagal-tertutup, kunci terpisah, seed CSPRNG, migrasi 22 tabel, driver Postgres | 15 | Sesuai (rt untuk token) |
| Policy Engine nyata dan persistensi DB | 16 | Sesuai |
| “Menghapus literal `True` di semua transisi” | 16 | Sebagian: beberapa guard dihitung atau divalidasi sebelumnya, tetapi 29 argumen tetap literal dan jalur agen melewati bukti |
| Refund dan capture nyata “wired” | 17 | Sebagian: fungsi live ada di client, tetapi tidak dipanggil sistem |
| Verifikasi webhook gagal-tertutup | 17 | Tidak sesuai: header uji dan prefiks `cert-url` tetap diterima |
| Identity minting untuk merchant terverifikasi | 18 | Tidak sesuai: endpoint tidak memeriksa kredensial apa pun |
| Margin konformal | 18 | Sebagian: rt lulus 4 dari 10 untuk model terkalibrasi |
| Konkurensi refund aman | 18 | Benar di ledger; dinetralkan di endpoint (RV2-04) |
| Alert scheduler dan otomasi berjalan | 19, 20 | Tidak sesuai: tidak pernah dijalankan aplikasi |
| Frontend suite | 21 | Sebagian: controller dan template string, tanpa aplikasi browser |
| ST-01 refund bertahap live PASSED | 21 | Tidak dapat diverifikasi ulang (tanpa jaringan); tes memanggil client langsung, bukan alur sistem |
| 144 passed, 3 deselected | 20 | Konsisten dengan suite saat itu; repo kini berisi 151 tes |

### G.6 Infrastruktur tes

Marker `live_model` dan `sandbox` kini dikecualikan di `addopts` maupun CI. Coverage tetap tidak diukur, dan repo tanpa commit sehingga CI belum pernah berjalan.

## H. Reliability & Production Readiness revisi ke-2

Untuk pertama kalinya sistem punya bentuk yang bisa dijalankan dan diamati: state di database, migrasi saat startup, readiness probe, log terstruktur, rate limiting, dan service Compose dengan healthcheck. Kesiapan masih tertahan tiga hal: refund tidak pernah dieksekusi, proses latar belakang tidak berjalan, dan beberapa pelindung uang dinetralkan oleh exception yang ditelan.

| Area | Revisi pertama | Revisi ke-2 | Bukti |
| --- | --- | --- | --- |
| Penanganan error | Sebagian | Sebagian | Handler 422 dan 500 global sudah ada, tetapi `except Exception: pass` di jalur perencanaan refund dan registrasi ledger menelan pelanggaran INV-01 (RV2-04) |
| Logging dan observability | Sebagian | Membaik | Request ID, trace ID, `return_id`, dan `decision_id` diekstrak di middleware; metrik dengan label template route |
| Health dan readiness | Membaik | Baik | `/v1/ready` mem-ping DB; healthcheck dan `depends_on: service_healthy` di Compose |
| Database | Ada, tidak dipakai | Dipakai | Semua state lewat repository; Postgres di Compose; migrasi Alembic sinkron |
| Transaksi | Hanya di pustaka | Sebagian | Commit per metode repository; penyimpanan aksi refund dan pembaruan saldo order tidak dalam satu transaksi |
| Konkurensi | Sebagian | Sebagian | Ledger, cache idempotensi, rate limiter, dan revocation disimpan per proses; aman selama satu worker (Compose memakai uvicorn tanpa `--workers`), tidak konsisten bila diskalakan |
| Rehidrasi setelah restart | — | Rapuh | Ledger dibangun ulang dari order saja, tanpa aksi PLANNED, sehingga sisa refundable kembali penuh setelah restart (RV2-04) |
| Background task | Tidak ada | Ada, tidak berjalan | Scheduler otomasi dan `AlertScheduler` tidak dijalankan aplikasi (RV2-02) |
| Exactly-once webhook | Rapuh | Baik | Dedupe event di DB lewat repository |
| Manajemen resource | Membaik | Membaik | TTL cache untuk idempotensi; riwayat rate limiter per kunci tidak pernah dibersihkan, sehingga memori tumbuh seiring jumlah IP dan token unik |
| Performa komputasi | Memadai | Memadai | `release.py` tidak berubah sejak revisi pertama: `decide_release` sekitar 80 µs p50 |
| Migrasi saat startup | — | Risiko | `run_migrations_on_init=True` menjalankan Alembic di setiap proses aplikasi; dengan beberapa replika, migrasi berjalan bersamaan |
| Pemisahan konfigurasi | Tidak ada | Sebagian | Settings dengan validator dan default aman, tetapi objek `app` memaksa `demo_mode=True` (AUD-14) |
| Kesiapan deployment | Sebagian | Membaik | Dockerfile non-root, `uv` dipin, Compose lengkap; belum diuji di mesin bersih; CI belum pernah berjalan |
| Backup dan recovery | Tidak ada | Tidak ada | Hanya fungsi drill dengan parameter; tanpa `pg_dump` atau prosedur restore |
| Kegagalan yang anggun | Memburuk di satu titik | Membaik | Token gagal-tertutup; fallback degradasi tersambung; verifikasi webhook gagal berarti ditolak |

### Risiko yang perlu pengujian lanjutan

- `docker compose up` di mesin bersih, termasuk migrasi Alembic ke Postgres sungguhan.
- Perilaku dengan lebih dari satu worker: ledger, idempotensi, rate limit, dan revocation yang tidak dibagi antarproses.
- Restart di tengah alur return: sisa refundable dan aksi PLANNED yang tidak direhidrasi.
- Latensi dan kegagalan PayPal sungguhan terhadap NFR-01, setelah eksekutor refund ada.

### Kesimpulan kesiapan

Revisi ke-2 sudah layak dijalankan sebagai demo satu proses, dengan catatan RV2-01 dan AUD-24 ditutup lebih dulu. Untuk rilis, tiga pekerjaan menentukan: eksekutor refund yang transaksional, scheduler yang benar-benar dijalankan, dan penghapusan exception yang ditelan di jalur uang.

## I. Missing Implementation, Technical Debt, dan konsistensi lintas modul

Utang yang tersisa kini terkonsentrasi di “jembatan terakhir”: eksekusi refund, penjadwalan, dan beberapa komponen domain yang belum tersambung. Konsistensi antarmodul jauh membaik dibanding dua versi sebelumnya.

### I.1 Konsistensi lintas modul (Fase 8)

| Pasangan yang dicek | Revisi pertama | Revisi ke-2 | Bukti |
| --- | --- | --- | --- |
| SSOT ↔ implementasi | Tidak | Sebagian | 21 PASS dari 137 (Bagian C) |
| JSON Schema ↔ model request | Sebagian | Sebagian | Field skema kini ada di model Pydantic, ditambah alias lama; `order_id` dan `schema_version` yang diwajibkan skema tidak ada di model |
| Kontrak §28 ↔ API | Tidak | Sebagian | Idempotensi di 2 dari 25 POST; 13 dari 18 kode error di luar katalog |
| Model DB ↔ migrasi ↔ ledger | Tidak | Ya | 22 tabel sinkron; `RefundAction` memuat semua field ledger |
| `Order.capture_id` ↔ refund | — | Tidak | Kolom `capture_id` ada, tetapi `app.py` memakai `CAP-{order_id}` di 7 tempat |
| Enum tier Passport | Tidak | Ya | FULL/LITE/NONE di konstanta, API, dan frontend |
| Curve refund | Ya | Ya | 0,80/0,50 di semua lapisan |
| Scope REST ↔ MCP | Ya | Ya | Sama |
| API client frontend ↔ API | Tidak ada | Ya | 16 path, semuanya ada di API |
| `.env.example` ↔ settings | Tidak | Sebagian | 14 kunci tidak dibaca aplikasi, termasuk `ALPHA_ACCUSE`, `EXPOSURE_CAPS`, `VALUE_BANDS` |
| Nama model AI | Tidak | Ya | `gemini-3.6-flash` di semua file |
| Dokumen status ↔ kode | Sebagian | Tidak | `rtm.csv`, gate record, `sandbox-tests.md`, dan README tidak diperbarui |

### I.2 Implementasi yang belum ada

| Area | Yang belum ada | Referensi |
| --- | --- | --- |
| Jalur uang | Eksekutor outbox refund; tracking; Disputes API | AUD-02, FR-07, FR-34 |
| Proses latar belakang | Scheduler yang dijalankan aplikasi | RV2-02 |
| Frontend | Bundler, halaman yang bisa dibuka di browser, blur on-device | ARC-07, FR-16 |
| Media dan bukti | Object storage dan upload media | FR-02 |
| Pipeline AI | Forensik media nyata, OCR/VLM, grader kedua, rekaman judge mode | FR-18, FR-80 |
| Agen | Server MCP dengan transport | ARC-12 |
| Data | RLS, backup dan restore | ARC-09, NFR-13 |
| P2 | Anchoring RFC 3161, deposit sewa, delivery receipt | FR-83, FR-54, FR-77 |

### I.3 Placeholder yang tersisa

| Placeholder | Lokasi | Temuan |
| --- | --- | --- |
| ID capture `CAP-{order_id}` | `backend/api/app.py` (7 tempat) | AUD-02 |
| Fallback COMPLETED tanpa kredensial | `backend/payments/client.py` | AUD-02 |
| `chain_valid: True` pada verifikasi Passport; `verified: True` pada receipt | `backend/api/app.py` | AUD-28 |
| Harga keep-offer 5250 saat engine menolak | `backend/api/app.py`: 1178 | RV2-03 |
| Metrik biaya 0,05 sen dan latensi 1,2 s di simulator | `backend/api/app.py`: 2046 | NFR-16 |
| `pass_demo_1` saat data Passport kosong | `backend/api/app.py`: 1129, 2219 | AUD-01 (sisa) |

### I.4 Technical debt

- **Exception ditelan di jalur uang:** `except Exception: pass` di sekitar perencanaan refund dan registrasi ledger (RV2-04).
- **State per proses:** ledger, idempotensi, rate limiter, dan revocation tidak dibagi antarproses; migrasi dijalankan di setiap startup.
- **Komponen domain belum tersambung:** trust, CUSUM, konformal, custody, dan seal (RV2-05).
- **Duplikasi tersisa:** cap tier di `trust.py` dan himpunan {EU, ID} di `policy.py` (AUD-16).
- **Tes mengunci celah keamanan:** perlu diubah bersamaan dengan perbaikannya (AUD-33).
- **Dokumentasi:** dokumen status usang, ADR generik, repo tanpa commit (DOC-01..05, DOC-09).

## J. Remediation Roadmap

Sisa waktu menuju deadline 12 November adalah 9 hari. Dua item pertama bisa selesai dalam hitungan jam dan menutup celah keamanan paling mudah dieksploitasi; eksekutor refund adalah satu-satunya pekerjaan berskala hari di jalur kritis. Urutan di bawah mengikuti dependensi teknis.

### J.1 Must Fix Before Release

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-01 | Tutup penerbitan token terbuka: aktifkan endpoint staff-token dan magic-link hanya bila DEMO\_MODE diatur lewat environment, dan hapus `demo_mode=True` yang dipaksa pada objek `app` | RV2-01, AUD-14 | CRITICAL dan bisa dieksploitasi dengan satu request | — |
| J-02 | Webhook gagal-tertutup: hapus header `X-PayPal-Signature-Valid` dan penerimaan berdasarkan prefiks `cert-url`; tolak bila verifikasi PayPal tidak bisa dilakukan | AUD-24 | Event palsu kini mengubah ledger | — |
| J-03 | Ubah tes yang mengunci J-01 dan J-02 menjadi tes negatif (401, 400) | AUD-33 | Tanpa ini perbaikan akan tampak sebagai regresi | J-01, J-02 |
| J-04 | Jalur uang transaksional: hentikan `except Exception: pass`; simpan aksi refund dan perbarui saldo order dalam satu transaksi; rehidrasi ledger dari DB; pakai `Order.capture_id` | RV2-04, AUD-02 | Prasyarat aman sebelum uang benar-benar dipindahkan | — |
| J-05 | Eksekutor outbox: ambil aksi PLANNED, panggil `refund_capture_live` dengan `PayPal-Request-Id`, perbarui status; hapus fallback COMPLETED di jalur produksi; jalankan ST-01 lewat sistem | AUD-02, ARC-19 | Nilai utama produk | J-02, J-04 |
| J-06 | Jalankan scheduler otomasi dan alert di `lifespan` atau worker terpisah | RV2-02 | SLA, kedaluwarsa keep-offer, dan CUSUM | — |
| J-07 | Perbarui `rtm.csv`, gate record, `sandbox-tests.md`, dan README sesuai hasil audit ini | DOC-01..04 | Keputusan gate harus bersandar pada status yang benar | J-01..J-06 |

### J.2 Should Fix Before Production

| ID | Tindakan | Temuan | Bergantung pada |
| --- | --- | --- | --- |
| J-08 | Validasi guard yang tersisa dan tutup jalur agen yang melewati bukti; jangan menawarkan keep-offer bila engine menolak; kirim cap akun dan merchant, tier, CUSUM, dan uji konformal ke keputusan | RV-03, RV2-03, RV2-05 | J-04 |
| J-09 | Otorisasi resale, penghapusan data, dan reviewer banding; batasi principal service; daftarkan persistensi revocation; kunci idempotensi per principal | AUD-22, AUD-25, AUD-29, RV-12, RV2-06 | J-01 |
| J-10 | Verifikasi Passport dan receipt sungguhan; terbitkan kunci publik | AUD-28 | — |
| J-11 | Tes guard bernilai False, arah dan laju seleksi audit, over-refund lewat endpoint, integrasi Postgres, dan E2E browser | AUD-34, AUD-36 | J-04, J-08 |
| J-12 | Migrasi dipisah dari startup; state bersama untuk multi-worker; rate limiter berbatas; backup dan restore; pin digest image; jalankan CI | AUD-37, AUD-38, H | J-05 |

### J.3 Recommended Improvements

| ID | Tindakan | Temuan |
| --- | --- | --- |
| J-13 | Satukan konstanta yang tersisa; hapus 14 kunci `.env.example` yang tidak dipakai; samakan model request dengan JSON Schema dan tampilkan di OpenAPI; jadikan `declared_grade` wajib; perbaiki margin AG-01; hapus default Compose | AUD-16, AUD-40, AUD-04, RV-07, AUD-31 |

### J.4 Optional Optimizations

| ID | Tindakan | Alasan |
| --- | --- | --- |
| J-14 | Bundler frontend (misalnya Vite) agar controller bisa dibuka di browser | Demo visual untuk juri; ditandai DEGRADED bila tidak sempat |
| J-15 | Transport MCP | Agen eksternal bisa memakai tool tanpa REST |

## K. Final Verdict

**NOT READY, tetapi kini dekat ke REQUIRES REMEDIATION.** Backend sudah substansial: keputusan uang dihitung engine, state tersimpan di database, dan token gagal-tertutup. Dua masalah fundamental masih tersisa: siapa pun bisa meminta token staff atau shopper (RV2-01), dan refund tidak pernah dieksekusi ke PayPal (AUD-02).

| Dimensi | Dasar verdict |
| --- | --- |
| Implementasi | 21 dari 137 requirement PASS dan FAIL turun ke 10; aliran uang berhenti di status PLANNED; frontend belum bisa dibuka di browser |
| Keamanan | Penerbitan token terbuka (CRITICAL) dan webhook bisa dipalsukan (HIGH); fondasi lain sudah kuat |
| Reliability | Layak sebagai demo satu proses; scheduler tidak berjalan; exception ditelan di jalur uang |
| Integritas bukti | Klaim inti sesi 15–16 terbukti; klaim webhook, identity minting, dan scheduler di sesi 17–20 tidak sesuai kode; dokumen status usang |

**Mengapa belum REQUIRES REMEDIATION.** Kategori itu mengandaikan tidak ada masalah fundamental. Penerbitan token terbuka meniadakan seluruh model otorisasi, dan tanpa eksekusi refund nilai utama produk belum terwujud.

**Apa yang mengubah verdict.** J-01 dan J-02 (hitungan jam) menutup kedua celah keamanan utama. J-04 dan J-05 (hitungan hari) membuat uang benar-benar bergerak secara aman. Setelah keempatnya selesai dan ST-01 berjalan lewat sistem, verdict yang wajar adalah REQUIRES REMEDIATION atau lebih baik.

**Kemajuan yang terverifikasi.** Dari 38 temuan terbuka sebelumnya, 16 teratasi dan 19 sebagian. Temuan terbuka turun dari 38 ke 26. Mekanisme inti tetap 180/180 dengan §8.8, dan 45 tes yang bisa dijalankan lulus tanpa kegagalan.

**Keyakinan dan batas cakupan.** Keyakinan atas verdict: High. FastAPI dan SQLAlchemy tidak bisa dijalankan di sandbox, sehingga 111 tes BLOCKED dan lapisan HTTP dinilai secara statis; tidak ada panggilan ke PayPal maupun Gemini; `.env` tidak dinilai sesuai permintaan pemilik.

Seluruh file revisi ke-2 tetap tidak berubah selama audit (manifest SHA-256 diverifikasi setiap fase), mutasi hanya dilakukan di salinan sementara yang sudah dihapus, dan kredensial di `.env` tidak pernah dipakai.

## Audit Ledger

Posisi per 3 November 2026, setelah Fase 8. Semua bagian sudah diisi.

### Eksekusi

| Eksekusi | Perintah ringkas | Hasil |
| --- | --- | --- |
| Harness mekanisme (ulang) | `harness/mechanism_check.py` dengan test double `pydantic` berlabel | 180/180 cocok dengan §8.8; label NO\_PASSPORT benar |
| Harness token dan konformal | `harness/rev2_check.py` dengan stub `backend.config` berlabel | Delapan perilaku gagal-tertutup terkonfirmasi; AG-01 lulus 4/10 (terkalibrasi) dan 0/10 (memburuk) |

Semua eksekusi berjalan di salinan kerja tanpa `.env` dan tanpa jaringan. Manifest SHA-256 salinan asli diverifikasi tanpa perubahan setelah fase ini.

**Fase 2.** Tes backend dijalankan sejauh lingkungan memungkinkan: state machine dan provider Gemini (9 lulus, native), payments (5 lulus, 1 di-deselect, native), golden dan Policy Engine (25 lulus, 3 tes `@given` di-skip, indikatif). Enam belas file lain, termasuk tes tahap 3, tidak bisa dikoleksi karena FastAPI, pydantic, SQLAlchemy, atau jsonschema tidak tersedia. Tes frontend dijalankan dengan `node --test --experimental-strip-types packages/ui/tests/frontend.test.ts` di Node 22: 6 lulus. RTM dinilai ulang dengan pemeriksaan tertarget pada endpoint evidence, keep-offer, receipt, Passport, policy, banding, resale, dan aplikasi frontend.

**Fase 3.** Graf import non-tes termasuk import lazy, keterjangkauan modul domain dari `backend.api.app`, pemakaian 56 metode repository, fitur skema DB di model dan migrasi, konvensi API §28.1, kode error terhadap katalog §28.2, MCP, dan arah dependensi. Diagram arsitektur dirender dan diperiksa visual.

**Fase 4.** Metrik kualitas kode (anotasi tipe, pola exception), pembacaan blok `try/except` di sekitar perencanaan refund dan registrasi ledger, rehidrasi ledger, pembaruan kolom refund di DB, serta fallback keep-offer. Temuan disusun di Bagian E: 5 temuan baru dan 20 temuan lama yang masih terbuka.

**Fase 5.** Pemindaian pola berbahaya dan SQL mentah, alur verifikasi webhook dan potensi SSRF, CORS, batas TTL token di skema, pengecualian rate limit, field log middleware, dan kunci cache idempotensi. Bukti runtime token dari Fase R dipakai ulang. Hasilnya Bagian F dan temuan RV2-06.

**Fase 6.** Inventaris AST atas 151 tes dan pembacaan 6 tes frontend; cakupan route statis (42/42); pencarian tes yang mengunci RV2-01, AUD-24, AUD-02, RV-03, RV2-02, RV2-03, dan RV2-04; mutation testing 11 mutan dengan `harness/mutation.py`, masing-masing di salinan sementara terpisah, atas 38 tes yang bisa dijalankan; pencocokan klaim sesi 15–21. Pemeriksaan guard per endpoint di fase ini mengoreksi status RV-03 di Bagian R dan E dari BELUM menjadi SEBAGIAN.

**Fase 7.** Pemeriksaan tipe cache idempotensi, state rate limiter, migrasi saat startup, jumlah worker uvicorn, healthcheck Compose, artefak backup, dan pemicu scheduler. Angka performa `decide_release` memakai hasil sebelumnya karena `release.py` tidak berubah.

**Fase 8.** Pencocokan JSON Schema dengan model request, path API client frontend dengan route API, `.env.example` dengan settings, kolom `capture_id` dengan pemakaian di endpoint, dan enum tier di konstanta, API, serta frontend. Hasilnya dirangkum di Bagian I.1; laporan final A, I, J, dan K disusun dari seluruh fase.

### Cakupan inspeksi

- **Dibaca rinci:** handler token staff dan shopper, GET return, evidence, review, resale, banding, penghapusan data, webhook, demo reset, verifikasi Passport, dan inisialisasi `create_app`; `auth/tokens.py`; `config.py` (default dan validator); `domain/signing.py`; `payments/client.py`; `payments/webhooks.py`; `jobs/automation.py` (struktur); `conformal.py` (gate); Compose, Dockerfile, CI; skema request di `api/schemas.py`.
- **Analisis AST:** semua pemanggilan `apply_return_transition` dan argumen guard-nya; sinkronisasi tabel model dan migrasi.
- **Belum dibaca rinci:** `db/repository.py` (sebagian), `api/middleware.py` (sebagian), `observability/metrics.py`, empat `App.ts` dan `packages/ui`, isi tes tahap 1–7, CHANGELOG dan PROJECT\_LOG.

### Catatan pemilik

`.env` sengaja diletakkan di folder proyek dan tidak dinilai dalam audit ini.
