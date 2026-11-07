# Laporan Audit Ulang ke-3 — ProofReturn (Revisi ke-3)

Nov 4, 2026 · @Wahyuni

## Status audit ulang ke-3 dan aturan kerja

Audit ulang ke-3 selesai: Fase 1, R, dan 2–8 telah dijalankan, dan verdict akhir ada di Bagian K. Semua bagian sudah terisi; Audit Ledger mencatat cakupan dan keterbatasan.

| Fase | Status | Cakupan |
| --- | --- | --- |
| 1 Discovery dan perubahan | Selesai (statis + gerbang) | Diff terhadap revisi ke-2, tech stack, dokumen, bukti, gerbang anti-pola |
| R Verifikasi perbaikan | Selesai (statis + runtime) | T0–T11, 26 temuan terbuka, klaim sesi 22 |
| 2 Requirement traceability | Selesai (statis + runtime) | 137 baris RTM |
| 3 Arsitektur | Selesai (statis) |  |
| 4 Backend | Selesai (statis + runtime) |  |
| 5 Keamanan | Selesai (statis) |  |
| 6 Testing dan mutation testing | Selesai (mutasi 11/11 lama, 4/6 baru) | 229 tes backend, 6 tes frontend |
| 7 Reliability | Selesai (statis) |  |
| 8 Konsistensi lintas modul | Selesai (statis) |  |

**Integritas sumber.** Arsip `ProofReturnRevisike3.zip` (49.604.612 byte, 7.371 entri, SHA-256 `5b126a5e…93e0790`) diperiksa bebas path traversal dan symlink, lalu diekstrak ke salinan terpisah yang dikunci read-only. Manifest SHA-256 untuk 668 file plus hash agregat `.venv` dicatat. Revisi ke-2 (SHA-256 `6ce29863…4e5f10a`) dipakai sebagai pembanding.

**Aturan eksekusi.** Tidak ada file proyek yang diubah. Eksekusi hanya di salinan kerja terpisah tanpa `.env` dan tanpa jaringan; kredensial tidak pernah dipakai. Sesuai permintaan pemilik, `.env` tidak dinilai.

## A. Executive Summary

**Verdict: REQUIRES REMEDIATION**, naik dari NOT READY di tiga audit sebelumnya. Revisi ke-3 menutup semua temuan CRITICAL, membuat gerbang anti-pola bersih, dan menghadirkan eksekutor refund, scheduler, serta autentikasi yang benar. Dua masalah HIGH tersisa di jalur uang: refund belum pernah dibuktikan sampai ke PayPal, dan pembekuan dispute tidak berlaku di jalur refund berbasis DB.

| Ukuran | Audit awal | Revisi 1 | Revisi 2 | Revisi 3 |
| --- | --- | --- | --- | --- |
| Requirement (PASS / PARTIAL / FAIL / NOT IMPL. / NOT VERIF.) | 9 / 75 / 35 / 15 / 3 | 10 / 82 / 27 / 15 / 3 | 21 / 90 / 10 / 12 / 4 | 44 / 75 / 4 / 10 / 4 |
| Temuan terbuka (CRITICAL / HIGH / MEDIUM / LOW) | 40 (3 / 9 / 20 / 8) | 38 (3 / 7 / 16 / 12) | 26 (2 / 4 / 10 / 10) | 19 (0 / 2 / 7 / 10) |
| Gerbang anti-pola | — | — | 71 | 0 |
| Mutan lama tertangkap | — | — | 6 dari 11 | 11 dari 11 |
| Mutan baru tertangkap | — | — | — | 4 dari 6 |
| Tes lulus / BLOCKED / gagal | 44 / 27 / 0 | 39 / 58 / 0 | 45 / 111 / 0 | 45 / 189 / 0 |
| Mekanisme vs §8.8 | 180/180 | 180/180 | 180/180 | 180/180 |

**Yang tertutup di revisi ini.** Penerbitan token hanya di DEMO\_MODE dengan bootstrap key; webhook gagal-tertutup; guard state machine dihitung dari data; over-refund ditolak dengan row lock; eksekutor outbox dengan `SKIP LOCKED` dan retry idempoten; scheduler dengan lease; verifikasi Passport dan receipt sungguhan; cap akun dan merchant di engine; `rtm.csv` dan `sandbox-tests.md` jujur.

**Dua temuan HIGH.**

- **AUD-02:** aliran uang ke PayPal belum pernah dijalankan lewat sistem; bukti ST-01 hanya order berstatus CREATED.
- **RV3-11:** pembekuan dispute dan reversal hanya ada di ledger in-memory yang tidak lagi dipakai API, sehingga tranche berikutnya tetap dikirim setelah dispute dibuka. Ditemukan lewat mutan baru yang tidak pernah diungkap.

**Temuan penting lainnya.** Refund dikonfirmasi untuk respons 2xx apa pun, termasuk PENDING (RV3-01); di luar DEMO\_MODE tidak ada jalur login (RV3-05); cap jurisdiksi tidak ditegakkan, terbukti runtime (RV3-06); gate record mengklaim G0–G5 PASSED tanpa kriterianya terpenuhi (RV3-13).

**Konteks.** Per 4 November tersisa 8 hari menuju deadline 12 November. Lima tindakan Must Fix (Bagian J) bisa selesai dalam 2–3 hari kerja. `.env` tidak dinilai sesuai permintaan pemilik.

## R. Verifikasi tugas T0–T11 dan 26 temuan terbuka

Revisi ke-3 menutup 20 dari 26 temuan terbuka, termasuk kedua celah keamanan paling serius: penerbitan token terbuka (RV2-01) dan webhook palsu (AUD-24). Lima temuan teratasi sebagian dan satu belum. Sisa terpentingnya ada di eksekutor refund, yang menandai refund CONFIRMED untuk respons 2xx apa pun dan belum pernah dibuktikan berjalan ke PayPal.

| Severity di revisi ke-2 | TERATASI | SEBAGIAN | BELUM | Dinilai di Fase 6 |
| --- | --- | --- | --- | --- |
| CRITICAL (2) | 1 | 1 | 0 | 0 |
| HIGH (4) | 3 | 1 | 0 | 0 |
| MEDIUM (10) | 8 | 2 | 0 | 0 |
| LOW (10) | 8 | 1 | 1 | 0 |
| Total (26) | 20 | 5 | 1 | 0 |

**Bukti runtime dan otomatis.** Gerbang anti-pola: 0 temuan (dari 71). Gate AG-01 dengan margin baru: model terkalibrasi lulus 20 dari 20 ulangan, model yang memburuk 0 dari 20. Mekanisme §8.8 tetap 180/180. Mesin token tidak berubah sejak revisi ke-2, sehingga hasil runtime gagal-tertutup sebelumnya tetap berlaku.

### Status per temuan

| ID | Temuan | Status | Bukti verifikasi |
| --- | --- | --- | --- |
| RV2-01 | Penerbitan token terbuka | TERATASI | Di luar DEMO\_MODE: staff-token 404, magic-link 202 tanpa token. Di DEMO\_MODE: wajib `X-Demo-Bootstrap-Key` yang dibandingkan dengan `hmac.compare_digest`; settings menolak kunci kosong atau placeholder |
| AUD-02 | Refund tidak dieksekusi | SEBAGIAN | `RefundOutboxExecutor` tersambung ke endpoint `POST /v1/ops/outbox/run` dan scheduler; fallback COMPLETED di client dihapus; `Order.capture_id` dipakai. Namun aksi ditandai CONFIRMED untuk respons 2xx apa pun tanpa memeriksa status refund, ID refund dikarang bila kosong (RV3-01), dan ST-01 belum pernah dijalankan ke PayPal |
| AUD-24 | Webhook palsu | TERATASI | Header uji dan prefiks `cert-url` dihapus; hanya verifikasi live atau HMAC demo yang diterima; selain itu 400 `INVALID_WEBHOOK_SIGNATURE` |
| RV-03 | Guard literal True | TERATASI | Gerbang: 0 guard literal; `retakes_ok`, `challenge_valid`, `eligible`, `not_expired`, `seal_nonce_matches` dihitung. Sisa kecil: `exposure_cap_ok` bernilai True bila merchant tidak ditemukan (RV3-03) |
| RV2-04 | INV-01 ditelan | TERATASI | `OverRefundError` dan `CAPTURE_MISSING` menjadi 409; repository memakai `with_for_update()` di empat tempat; tidak ada `except Exception: pass` |
| AUD-34 | Jenis tes kunci | SEBAGIAN | CI kini punya job Postgres; tanpa Playwright dan tanpa refund Sandbox lewat sistem |
| AUD-14 | Demo mode dipaksa | TERATASI | `app = create_app()` |
| AUD-22 | BOLA resale | TERATASI | Hanya principal shopper; capture wajib; pemilik baru dari token. Sisa: fallback `CAP_{order_id}` (RV3-02) |
| AUD-25 | Penghapusan data | TERATASI | Autentikasi wajib; shopper hanya subjeknya sendiri; MERCHANT\_ADMIN hanya dalam merchant-nya |
| AUD-28 | Verifikasi kriptografi | TERATASI | Verifikasi Passport memeriksa signature Ed25519 dan rantai hash; `GET /v1/keys` menerbitkan kunci publik; gerbang 0 untuk `verified` dan `chain_valid` literal |
| AUD-29 | Independensi reviewer | TERATASI | Reviewer asal diambil dari record review terakhir |
| AUD-33 | Tes mengunci perilaku keliru | TERATASI | Tidak ada lagi tes yang mengunci perilaku tidak aman; tes webhook memakai HMAC demo dan tes token memakai bootstrap key (Bagian G.3) |
| AUD-36 | Celah kasus batas | SEBAGIAN | Mutan M01–M11 tertangkap semua; mutan baru N01 dan N05 lolos dari seluruh suite (Bagian G.2) |
| RV2-02 | Scheduler tidak berjalan | TERATASI | Dijalankan di `lifespan` bila `enable_scheduler` aktif, dengan lease antarinstans |
| RV2-03 | Fallback harga keep-offer | TERATASI | 404 `NO_KEEP_OFFER` bila tidak layak atau tanpa harga |
| RV2-05 | Cap dan tier tidak sampai engine | SEBAGIAN | Tier, cap akun, dan cap merchant kini dihitung dari DB; CUSUM berjalan lewat scheduler; seal dan retake dihitung. Kalibrasi konformal tetap tidak dipakai dalam keputusan (hanya muncul di skema Gemini). Cap dikirim ke `decide_release` |
| AUD-04 | `declared_grade` default | TERATASI | Field wajib di skema |
| AUD-40 | Skema dan OpenAPI | BELUM | Handler tetap menerima `Request` mentah dengan 22 `model_validate`; skema request tidak tampil di OpenAPI |
| AUD-03 | Skenario CT tautologis | TERATASI | Pola `outbox_locked = True` hilang dari `return_state.py` |
| RV-07 | Margin AG-01 | TERATASI | rt: 20/20 untuk model terkalibrasi, 0/20 untuk model memburuk |
| RV-12 | Audience, revocation, service | TERATASI | `register_revocation_persistence` dipanggil saat startup; principal service dibatasi |
| AUD-16 | Duplikasi konstanta | TERATASI | Cap tier dan himpunan jurisdiksi tidak lagi terduplikasi |
| AUD-31 | Default kredensial Compose | TERATASI | Tidak ada default `:-` |
| AUD-37 | Observability | TERATASI | Log memuat `decision_id` dan `paypal_debug_id`; alert scheduler berjalan |
| AUD-38 | CI dan image | SEBAGIAN | Image di-pin dengan digest; repo tetap tanpa commit sehingga CI belum pernah berjalan |
| RV2-06 | Kunci idempotensi | TERATASI | Kunci memuat merchant dan subjek principal |

### Kepatuhan proses dan dokumentasi

| Item | Status | Bukti |
| --- | --- | --- |
| Commit per tugas (instruksi T0–T11) | Tidak dipenuhi | `.git/objects` kosong |
| Bukti suite akhir | Tidak lengkap | `session-22-R3.md` memuat 189 lulus dari 193 tes saat T7; repo kini berisi 229 tes tanpa output run terakhir |
| ST-01 | Jujur | Tetap IMPLEMENTED di `sandbox-tests.md` |
| `st01-system-run-R3.txt` | Menyesatkan | Berjudul “System Execution Evidence”, tetapi hanya memuat order Sandbox berstatus CREATED dan narasi langkah tanpa ID capture atau refund |

### Temuan baru dari verifikasi

- **RV3-01 (MEDIUM) Konfirmasi refund tanpa memeriksa status.** `outbox.py:57`: semua respons 2xx ditandai CONFIRMED, termasuk refund PayPal berstatus PENDING, dan ID refund dikarang sebagai `PP-REF-...` bila tidak ada di respons.
- **RV3-02 (LOW) Penghindaran pola gerbang di capture resale.** `app.py:2161`: `cap_res.get("id") or f"CAP_{order.order_id}"` memakai garis bawah sehingga lolos dari pola `CAP-{`.
- **RV3-03 (LOW) Guard cap exposure gagal-terbuka.** `exposure_cap_ok` bernilai True bila record merchant tidak ditemukan.
- **RV3-04 (LOW) Event webhook tanpa ID.** Fallback ke ID acak membuat dedupe tidak berlaku untuk event tanpa `id`.

## B. Project Understanding: perubahan sejak revisi ke-2

Revisi ke-3 mengikuti instruksi tahap 3 secara jauh lebih disiplin. Skrip gerbang anti-pola dipasang tanpa diubah, dan hasilnya turun dari 71 ke 0. Jumlah tes naik dari 151 ke 229, ada eksekutor outbox refund, dan dokumen status kini jujur untuk ST-01. Dua instruksi tidak diikuti: tidak ada commit per tugas, dan beberapa pola terlarang muncul kembali dalam bentuk yang lolos dari gerbang.

### Ringkasan perubahan

| Kategori | Jumlah | Isi utama |
| --- | --- | --- |
| File ditambahkan | 21 | `backend/payments/outbox.py`, `scripts/check_antipatterns.py`, `scripts/backup_restore.py`, 10 file tes tahap 8–17 (±3.800 baris), `backend/tests/conftest.py`, `backend/tests/support/` (journeys dan concurrency), bukti `gate-baseline-R3.txt`, `session-22-R3.md`, `st01-system-run-R3.txt` |
| File dihapus | 1 | `backend/domain/journeys.py`, dipindah ke `backend/tests/support/` sesuai T6 |
| File diubah | 44 | `app.py` (2.373 menjadi 2.731 baris), `repository.py` (753 menjadi 1.293), `automation.py` (202 menjadi 359), `return_state.py` (491 menjadi 389), `ledger.py`, `client.py`, `middleware.py`, `config.py`, migrasi 0002, CI (43 menjadi 90 baris), Compose, `rtm.csv`, gate record, `sandbox-tests.md`, README |
| Tidak berubah | — | Empat aplikasi frontend dan `packages/ui`, SSOT, JSON Schema |

### Kepatuhan terhadap instruksi tahap 3

| Instruksi | Kondisi di revisi ke-3 |
| --- | --- |
| Skrip gerbang dipasang tanpa diubah (T0) | Dipenuhi: identik dengan versi instruksi kecuali newline di akhir file; baseline 71 tercatat |
| Gerbang nol setelah T11 | Dipenuhi menurut skrip: 0 temuan, 0 penanda `guard-verified` |
| Commit per tugas | Tidak dipenuhi: `.git/objects` tetap kosong, sehingga diff per tugas tidak bisa diperiksa |
| Tidak ada nilai karangan dalam bentuk lain | Tidak sepenuhnya: `f"CAP_{order.order_id}"` di `app.py:2161` dan `f"PP-REF-{...}"` di `outbox.py:57` lolos dari pola gerbang |
| ST-01 hanya VERIFIED dengan ID PayPal nyata | Dipenuhi secara jujur: ST-01 tetap IMPLEMENTED; bukti hanya memuat satu order Sandbox berstatus CREATED, tanpa capture maupun refund |

### Tech stack yang berubah

| Lapisan | Revisi ke-2 | Revisi ke-3 (klaim, diverifikasi di Fase R) |
| --- | --- | --- |
| Refund | Aksi PLANNED tanpa eksekutor | `RefundOutboxExecutor` dengan klaim `FOR UPDATE SKIP LOCKED`, status SUBMITTED/CONFIRMED/UNKNOWN/FAILED\_PERMANENT, endpoint `POST /v1/ops/outbox/run` |
| Penerbitan token | Terbuka | Hanya di DEMO\_MODE dengan `X-Demo-Bootstrap-Key` |
| Webhook | Header uji diterima | Verifikasi live atau HMAC demo; selain itu 400 |
| State machine | 46 guard literal | Guard dihitung; gerbang 0 |
| Scheduler | Tidak dijalankan | Diklaim berjalan di lifespan dengan lease |
| Operasional | Tanpa backup | `scripts/backup_restore.py`; CI 90 baris |
| Venv | Windows | Masih Windows (Python 3.12.13); dependensi tidak berubah |

### Dokumentasi dan bukti

| Dokumen | Isi | Catatan awal |
| --- | --- | --- |
| `docs/rtm.csv` | 25 VERIFIED, 50 IMPLEMENTED, 62 SPECIFIED; kolom `evidence`, `evidence_links`, `test_ids` baru | Diverifikasi di Fase 2 |
| Gate record | “Tasks T0..T7 Accepted; Gate: 0 Anti-Patterns; 189 Tests Passing” | Repo kini berisi 229 tes backend |
| `docs/sandbox-tests.md` | ST-01 IMPLEMENTED; ST-09 VERIFIED dengan ID order Sandbox | ST-01 jujur; ST-09 tidak bisa diverifikasi ulang tanpa jaringan |
| `docs/evidence/st01-system-run-R3.txt` | Langkah alur refund dijelaskan, tetapi tanpa ID capture atau refund | Judulnya “System Execution Evidence”, isinya narasi |

### Perhatian awal

Gerbang nol adalah kemajuan nyata, tetapi pemindaian penghindaran gerbang menemukan beberapa sisa: ID capture dan ID refund karangan sebagai fallback, eksekutor yang menandai refund CONFIRMED untuk respons 2xx apa pun tanpa memeriksa status refund PayPal, dan guard `exposure_cap_ok` yang bernilai `True` bila data merchant tidak ditemukan. Status finalnya ditetapkan di Bagian R.

## C. SSOT Compliance Report — RTM revisi ke-3

Dari 137 requirement, 44 kini PASS, 75 PARTIAL, 4 FAIL, 10 NOT IMPLEMENTED, dan 4 NOT VERIFIED. PASS naik dua kali lipat dari revisi ke-2, terutama di invariant uang (INV-01 sampai INV-04), webhook, dan kriptografi. Empat FAIL tersisa: red-team sintetis (FR-20), tier Passport dari body request (FR-63), pembekuan tranche saat dispute yang tidak berlaku di jalur refund berbasis DB (FR-75, RV3-11), dan cap jurisdiksi yang tidak divalidasi (INV-11, terbukti runtime: curve C=0,50 diterima engine).

Rubrik status sama dengan audit sebelumnya. Requirement yang bergantung pada eksekusi uang ke PayPal (FR-22, FR-39, NFR-01) tetap PARTIAL sampai ST-01 berjalan lewat sistem.

| Status | Audit awal | Revisi 1 | Revisi 2 | Revisi 3 |
| --- | --- | --- | --- | --- |
| PASS | 9 | 10 | 21 | 44 |
| PARTIAL | 75 | 82 | 90 | 75 |
| FAIL | 35 | 27 | 10 | 4 |
| NOT IMPLEMENTED | 15 | 15 | 12 | 10 |
| NOT VERIFIED | 3 | 3 | 4 | 4 |

**Bukti eksekusi tes.** `backend/tests/conftest.py` baru meng-import `DatabaseRepository` untuk seluruh suite, sehingga tanpa SQLAlchemy dan SQLModel tidak satu pun tes bisa dikoleksi. Dengan `--noconftest`, subset murni berjalan: 39 lulus (9 native state machine dan Gemini, 5 native payments, 25 indikatif golden dan Policy Engine), 1 deselected, 3 BLOCKED (`@given`). Sebanyak 186 tes lain BLOCKED. Frontend: 6 dari 6 lulus di Node 22. Tidak ada yang gagal.

### Baris yang berubah status (29)

| ID | Revisi 2 | Revisi 3 | Bukti |
| --- | --- | --- | --- |
| FR-05 | PARTIAL | PASS | Signature Ed25519 dengan kunci packer persisten; diverifikasi ulang di endpoint verify |
| FR-37 | PARTIAL | PASS | Harga dari `compute_posted_keep_offer`; tanpa fallback |
| FR-41 | NOT IMPLEMENTED | PARTIAL | Resale mencoba capture lewat Orders v2 dan mensyaratkan capture; alur persetujuan pembeli tidak ada |
| FR-45 | PARTIAL | PASS | Penerbitan token tertutup; token agen terikat order, ber-scope, dan kedaluwarsa |
| FR-57 | PARTIAL | PASS | Tier dihitung dari riwayat akun di DB dan dipakai keputusan |
| FR-64 | PARTIAL | PASS | `seal_nonce_matches` dihitung dari seal tersimpan |
| FR-66 | PARTIAL | PASS | `retakes_ok` dihitung dari retake tersimpan |
| FR-69 | FAIL | PARTIAL | Reviewer asal dari record; refund kompensasi dihitung; batas 14 hari tidak ditemukan |
| FR-76 | PARTIAL | PASS | Receipt diverifikasi dengan kunci publik dari `GET /v1/keys` |
| FR-78 | PARTIAL | PASS | Kelayakan keep-offer dari engine; 404 bila tidak layak |
| FR-82 | PARTIAL | PASS | AEAD dan endpoint penghapusan terautentikasi dengan scope |
| FR-92 | PARTIAL | PASS | Cap akun dan merchant dikirim ke engine; exposure dicek saat approval |
| FR-97 | PARTIAL | PASS | `SLAEscalationScanner` dijalankan scheduler |
| NFR-01 | NOT IMPLEMENTED | PARTIAL | Eksekutor dijalankan scheduler; belum diukur terhadap PayPal |
| NFR-03 | PARTIAL | PASS | `PayPal-Request-Id` deterministik dipakai ulang saat retry |
| NFR-04 | FAIL | PASS | Verifikasi live atau HMAC demo; selain itu 400; dedupe di DB |
| NFR-08 | PARTIAL | PASS | Log memuat request ID, `return_id`, `decision_id`, `paypal_debug_id` |
| NFR-11 | FAIL | PARTIAL | Isolasi di level aplikasi kini konsisten; tanpa RLS |
| NFR-12 | PARTIAL | PASS | Lockfile dan image ber-digest |
| NFR-13 | FAIL | PARTIAL | `scripts/backup_restore.py` ada; tidak ada output drill di bukti |
| NFR-16 | FAIL | PASS | Latensi diukur dengan `perf_counter`; biaya dari model ROI |
| INV-01 | PARTIAL | PASS | Lock baris order, saldo pending diperbarui dalam transaksi, over-refund 409 |
| INV-02 | PARTIAL | PASS | Refund memakai `Order.capture_id` |
| INV-03 | PARTIAL | PASS | Request ID deterministik per keputusan dan tranche |
| INV-04 | PARTIAL | PASS | Guard dihitung; gerbang 0 guard literal |
| INV-09 | FAIL | PASS | Verifikasi signature dan rantai hash sungguhan |
| INV-12 | PARTIAL | PASS | Agen tidak bisa memicu bukti atau asesmen; keep-offer hanya dari ASSESSED |

Ditambah **FR-96** (FAIL menjadi PASS): endpoint carrier event dipindah ke `POST /v1/carrier-events` dan menolak permintaan di luar DEMO\_MODE, dengan peran service atau staff yang diperiksa. Status ini dikoreksi di Fase 4; pencarian awal memakai path lama. Ditambah **FR-75** (PARTIAL menjadi FAIL) di Fase 6: pembekuan tranche setelah dispute hanya ada di ledger in-memory yang tidak lagi dipakai API (RV3-11).

### Matriks lengkap per status

| Status | Requirement |
| --- | --- |
| PASS (44) | FR-05, 21, 23, 26, 28, 31, 37, 43, 44, 45, 50, 57, 58, 60, 61, 64, 66, 74, 76, 78, 82, 89, 92, 95, 96, 97; NFR-03, 04, 08, 12, 16; INV-01, 02, 03, 04, 05, 07, 08, 09, 10, 12, 15, 16, 18 |
| FAIL (4) | FR-20, 63, 75; INV-11 |
| NOT IMPLEMENTED (10) | FR-02, 07, 17, 34, 54, 77, 83; NFR-06, 09, 10 |
| NOT VERIFIED (4) | FR-48, 86; NFR-02, 15 |
| PARTIAL (75) | FR-01, 03, 04, 06, 08, 09, 10, 11, 12, 13, 14, 15, 16, 18, 19, 22, 24, 25, 27, 29, 30, 32, 33, 35, 36, 38, 39, 40, 41, 42, 46, 47, 49, 51, 52, 53, 55, 56, 59, 62, 65, 67, 68, 69, 70, 71, 72, 73, 79, 80, 81, 84, 85, 87, 88, 90, 91, 93, 94, 98, 99, 100, 101, 102, 103; NFR-01, 05, 07, 11, 13, 14; INV-06, 13, 14, 17. FR-22, FR-39, dan NFR-01 bergantung pada ST-01; FR-25 pada kalibrasi konformal yang belum tersambung |

### Akurasi rtm.csv

`rtm.csv` kini memuat kolom `evidence`, `evidence_links`, dan `test_ids`, dan semua 25 baris VERIFIED merujuk tes yang benar-benar ada. Dokumen ini kini cenderung konservatif.

| Penilaian | Jumlah | Requirement |
| --- | --- | --- |
| Klaim VERIFIED yang didukung (PASS) | 18 | FR-37, 43, 44, 45, 61, 74, 76, 82, 97; NFR-04, 08; INV-01, 03, 04, 07, 10, 12, 16 |
| Klaim VERIFIED yang hanya PARTIAL | 7 | FR-09, FR-12, FR-69 (tanpa batas 14 hari), FR-72, FR-80, FR-91, NFR-11 (tanpa RLS) |
| Klaim VERIFIED yang bertentangan | 0 | — |
| PASS menurut audit, belum VERIFIED di rtm.csv | 26 | Antara lain FR-05, 21, 23, 50, 58, 60, 92, 95; NFR-03, 12, 16; INV-02, 09 |

## D. Architecture Compliance Report

Hampir semua lapisan domain kini berada di jalur endpoint atau scheduler: Policy Engine, settlement, keep-offer, tier dan cap, ledger, webhook processor, eksekutor outbox, evaluator, dan scheduler dengan lease. Yang tersisa di luar jalur adalah kalibrasi konformal, modul custody dan seal, serta MCP. Celah arsitektural terbesar kini bukan lagi wiring, melainkan bukti: aliran uang ke PayPal belum pernah dijalankan lewat sistem.

&#91;embedded content: arsitektur aktual revisi ke-3\]

Kotak hijau adalah logika keputusan uang yang tersambung; garis putus-putus menandai panggilan ke PayPal yang sudah ada di kode tetapi belum dibuktikan di Sandbox.

### Status penyimpangan sebelumnya

| ID | Penyimpangan | Status | Bukti |
| --- | --- | --- | --- |
| ARC-01 | API tidak memakai engine | TERATASI | Sejak revisi ke-2 |
| ARC-02 | Jalur uang PayPal | SEBAGIAN | Eksekutor outbox tersambung ke endpoint dan scheduler; belum ada run Sandbox lewat sistem; konfirmasi tanpa cek status (RV3-01) |
| ARC-03 | Model autentikasi API-04 | SEBAGIAN | Penerbitan token aman; magic link di produksi hanya mencatat permintaan pengiriman, tanpa pengirim email |
| ARC-04 | Persistensi | TERATASI | 37 dari 65 metode repository dipakai |
| ARC-05 | Workflow dan timer | TERATASI | Scheduler di `lifespan` dengan lease; Temporal (ADR-003) tetap tidak dipakai |
| ARC-06 | Server ASGI | TERATASI (statis) | Service `api` plus service `migrate` terpisah di Compose |
| ARC-07 | Frontend | SEBAGIAN | Tidak berubah: controller TypeScript dengan template string |
| ARC-08 | Kontrak Pydantic | SEBAGIAN | Tidak berubah: `model_validate` atas `Request` mentah, skema tidak di OpenAPI |
| ARC-09 | DB dan RLS | SEBAGIAN | Model dan migrasi 23 tabel sinkron, 8 CHECK; tanpa RLS |
| ARC-10 | Konfigurasi | TERATASI | `app = create_app()` |
| ARC-11 | Penyedia AI tanpa Change Control | BELUM | Tetap Gemini |
| ARC-12 | MCP bukan server | BELUM | Tanpa transport |
| ARC-13 | Arah dependensi | TERATASI | `journeys.py` dipindah ke `backend/tests/support/` |
| ARC-14, ARC-15 | Dua sumber state, `create_all` | TERATASI | Sejak revisi ke-2 |
| ARC-16 | SQLite sebagai default | SEBAGIAN | Postgres di Compose dan CI; default lokal tetap SQLite |
| ARC-17 | Penerbitan identitas | SEBAGIAN | Sama dengan ARC-03 |
| ARC-18 | Komponen domain terputus | SEBAGIAN | Trust, cap, CUSUM tersambung; konformal, custody, dan seal belum |
| ARC-19 | Eksekutor outbox | TERATASI | `RefundOutboxExecutor` dengan klaim `FOR UPDATE SKIP LOCKED`; cacat konfirmasi dicatat terpisah (RV3-01) |

### Database (§30)

| Aturan | Temuan |
| --- | --- |
| MG-01 Alembic | 23 tabel model dan migrasi sinkron; migrasi dijalankan service `migrate` di Compose |
| DB-03 dan INV-01 | 8 CHECK constraint; saldo pending diperbarui dalam transaksi dengan row lock |
| ADR-012 RLS | Tidak ada |
| CI | Job `postgres-integration` menjalankan suite terhadap Postgres (belum pernah berjalan karena repo tanpa commit) |

### Konvensi API (§28.1)

| Konvensi | Status | Bukti |
| --- | --- | --- |
| API-01 base `/v1` | Sesuai | 44 route |
| API-02 UUIDv7 | Tidak | Potongan UUID4 |
| API-06 `Idempotency-Key` | Tidak | Dirujuk di 2 tempat untuk 26 endpoint POST |
| API-07 problem+json dengan katalog | Memburuk | 19 dari 25 kode error di luar katalog §28.2, misalnya `CAPTURE_MISSING`, `NO_KEEP_OFFER`, `INVALID_WEBHOOK_SIGNATURE` |
| API-08 `If-Match` | Tidak | Kolom `version` tidak dipakai API |
| API-11 OpenAPI dari Pydantic | Sebagian | Lihat ARC-08 |

Kode error baru wajar ditambahkan untuk perilaku baru, tetapi menurut SSOT perubahan katalog melewati Change Control dan didokumentasikan; tidak ada catatan itu di repo.

## E. Technical Findings revisi ke-3

Revisi ke-3 tidak lagi memiliki temuan CRITICAL. Ada 19 temuan terbuka ditambah 1 catatan informasional: 2 HIGH, 7 MEDIUM, dan 10 LOW. Tiga belas di antaranya baru (RV3-01 sampai RV3-13); AUD-33 teratasi dan AUD-36 tetap terbuka setelah Fase 6.

| Severity | Audit awal | Revisi 1 | Revisi 2 | Revisi 3 |
| --- | --- | --- | --- | --- |
| CRITICAL | 3 | 3 | 2 | 0 |
| HIGH | 9 | 7 | 4 | 2 |
| MEDIUM | 20 | 16 | 10 | 7 |
| LOW | 8 | 12 | 10 | 10 |
| Total terbuka | 40 | 38 | 26 | 19 |

### HIGH

#### AUD-02 · HIGH · Functional — Aliran uang ke PayPal belum pernah dibuktikan

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/outbox.py`; `backend/api/app.py`: 275 (eksekutor), endpoint `POST /v1/ops/outbox/run`; `docs/evidence/st01-system-run-R3.txt` |
| Bukti | Eksekutor outbox sudah ada dan tersambung ke endpoint dan scheduler. Bukti ST-01 hanya memuat satu order Sandbox berstatus CREATED dan narasi langkah, tanpa ID capture maupun refund; `sandbox-tests.md` jujur mencatat ST-01 sebagai IMPLEMENTED. |
| Penjelasan | Severity turun dari CRITICAL karena kodenya kini lengkap, tetapi nilai utama produk tetap belum terbukti berjalan. |
| Dampak | Cacat integrasi seperti RV3-01 baru akan muncul saat demo atau produksi. |
| Rekomendasi | Jalankan ST-01 lewat sistem: buat order, setujui dengan akun pembeli Sandbox, capture lewat API, jalankan alur return, jalankan outbox, lalu verifikasi refund lewat GET capture. Catat semua ID PayPal; baru setelah itu tandai VERIFIED. |
| Confidence | High |

#### RV3-11 · HIGH · Functional — Pembekuan dispute dan reversal tidak berlaku di jalur refund berbasis DB

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/db/repository.py` (`record_evidence_pack_transactional`, `record_review_and_settlement_transactional`, `plan_refund_action_transactional`, `claim_planned_refund_actions`); `backend/payments/outbox.py`; `backend/payments/webhooks.py`: 85–88 |
| Bukti | Pemeriksaan freeze hanya ada di `RefundLedger` in-memory (`ledger.py`: 181–182). Repository tidak punya kolom maupun pemeriksaan freeze (0 kemunculan `frozen`, `dispute`, `reversed`), eksekutor outbox juga tidak, dan API tidak lagi memakai ledger untuk merencanakan refund. Webhook dispute hanya membekukan ledger di memori. Mutan N01 (pemeriksaan freeze dimatikan) lolos dari seluruh suite. |
| Penjelasan | Saat jalur refund dipindah ke DB di revisi ke-3, perlindungan FR-75 tertinggal di objek yang tidak lagi dipakai. |
| Skenario | Shopper membuka dispute setelah R0 cair; webhook diterima; R1 dan R2 tetap direncanakan dan dikirim eksekutor outbox ke PayPal. |
| Dampak | Merchant bisa menanggung refund penuh sekaligus chargeback dari dispute yang sama. |
| Rekomendasi | Tambah kolom `frozen_by_dispute` dan `reversed_by_chargeback` pada `orders` (migrasi baru); perbarui dari webhook dalam transaksi yang sama dengan dedupe; tolak perencanaan dan lewati eksekusi untuk order yang dibekukan; tes API untuk dispute di antara tranche. |
| Confidence | High |

### MEDIUM (temuan baru)

#### RV3-01 · MEDIUM · Functional — Refund dikonfirmasi tanpa memeriksa status PayPal

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/payments/outbox.py`: 51–67 |
| Bukti | Setiap respons 2xx dari `refund_capture_live` langsung dicatat lewat `record_refund_confirmed`. Bila respons tidak memuat `id`, ID refund dikarang sebagai `f"PP-REF-{request_id[:8]}"`. |
| Penjelasan | Refund PayPal bisa berstatus COMPLETED, PENDING, FAILED, atau CANCELLED. Hanya COMPLETED yang boleh dipindah ke saldo confirmed; PENDING harus menunggu webhook atau GET refund. ID karangan juga lolos dari pola gerbang. |
| Dampak | `confirmed_refunded_minor` bisa melebihi refund yang benar-benar selesai; shopper diberi tahu refund selesai padahal masih tertunda atau gagal; rekonsiliasi tidak bisa mencocokkan ID karangan. |
| Rekomendasi | Petakan status: COMPLETED ke CONFIRMED, PENDING tetap SUBMITTED sampai webhook, FAILED dan CANCELLED ke FAILED\_PERMANENT. Wajibkan `id`; tanpa `id`, tandai UNKNOWN dan picu alert. |
| Confidence | High |

#### RV3-05 · MEDIUM · Functional — Di luar DEMO\_MODE, tidak ada yang bisa login

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/api/app.py`: 470–560 |
| Bukti | Di luar DEMO\_MODE, `staff-token` mengembalikan 404 dan tidak ada endpoint login lain. Magic link mengembalikan 202 dan mencatat permintaan pengiriman, tetapi tidak ada pengirim email. |
| Penjelasan | Penutupan RV2-01 benar dari sisi keamanan, tetapi meninggalkan sistem yang hanya bisa dipakai dalam DEMO\_MODE. API-04 mensyaratkan login staff lewat penyedia identitas dan magic link yang dikirim ke pemilik order. |
| Dampak | Deploy non-demo tidak bisa dipakai staff maupun shopper. |
| Rekomendasi | Login staff dengan SSO atau kredensial plus MFA (atau token yang diterbitkan admin dengan audit), dan pengiriman magic link lewat penyedia email dengan token sekali pakai. |
| Confidence | High |

#### RV3-06 · MEDIUM · Compliance — Cap jurisdiksi tidak ditegakkan (INV-11)

| Atribut | Detail |
| --- | --- |
| Lokasi | `backend/policy_engine/release.py`; `backend/api/schemas.py`: 139 (`jurisdiction`); `POST /v1/policies` |
| Bukti | rt: `decide_release` menerima curve dengan C=0,50 dan menghasilkan holdback 18000, padahal curve legal menghasilkan 6000. Pembuatan policy menerima field `jurisdiction` tanpa validasi cap. |
| Penjelasan | INV-11 dan FR-10 mensyaratkan curve yang melampaui cap jurisdiksi ditolak, termasuk F=0 di EU dan ID. |
| Dampak | Merchant bisa mengonfigurasi policy yang melanggar batas hukum konsumen. |
| Rekomendasi | Validasi curve terhadap tabel jurisdiksi saat policy dibuat dan sekali lagi di engine; tes per jurisdiksi. |
| Confidence | High |

#### RV3-13 · MEDIUM · Documentation — Gate record mengklaim G0–G5 PASSED tanpa kriterianya terpenuhi

| Atribut | Detail |
| --- | --- |
| Lokasi | `docs/gates/final-acceptance.md`: 12–17 |
| Bukti | G1 Money loop berstatus PASSED, padahal menurut `rtm.csv` proyek sendiri 10 dari 15 kriterianya belum VERIFIED (FR-22, FR-64, FR-71 masih SPECIFIED; FR-23, FR-24, FR-57, FR-58, FR-60, INV-05, INV-14 masih IMPLEMENTED). G2 PASSED tanpa laporan red-team (FR-20 FAIL). G5 Demo ready PASSED dengan bukti `npm test` dan tes scheduler, padahal kriterianya journey J-01..J-14 lulus 3 kali di lingkungan deploy, budget performa dan aksesibilitas, serta drill backup. G4 dan G5 bertarget 8 dan 10 November. |
| Penjelasan | Instruksi T7 meminta status hanya dari bukti; `rtm.csv` dan `sandbox-tests.md` mematuhinya, gate record tidak. |
| Dampak | Keputusan go/no-go dan narasi submission bisa bersandar pada gate yang tidak terpenuhi. |
| Rekomendasi | Kembalikan G1–G5 ke IN PROGRESS sampai setiap kriteria punya bukti; turunkan status gate langsung dari `rtm.csv` dan `sandbox-tests.md` dengan skrip. |
| Confidence | High |

### Temuan lama yang masih terbuka (MEDIUM)

| ID | Kategori | Sisa masalah | Rekomendasi | Confidence |
| --- | --- | --- | --- | --- |
| RV2-05 | Architecture | Kalibrasi konformal tidak dipakai keputusan; modul custody dan return seal tidak terjangkau API | Pakai kalibrator untuk uji misdeclaration; sambungkan atau hapus modul yang tidak dipakai | High |
| AUD-34 | Testing | CI Postgres sudah ada, tetapi belum pernah berjalan; tanpa Playwright; tanpa refund Sandbox lewat sistem | Jalankan CI; tambah ST-01 lewat sistem | High |
| AUD-33 | Testing | TERATASI di Fase 6: tidak ada lagi tes yang mengunci perilaku tidak aman; tidak dihitung sebagai temuan terbuka | — | — |
| AUD-36 | Testing | Mutan M01–M11 tertangkap semua, tetapi mutan baru N01 (freeze dispute) dan N05 (reveal seed palsu) lolos dari seluruh suite | Tes refund pada order yang di-dispute atau di-reverse lewat API, dan tes reveal seed palsu | High |

### LOW

| ID | Kategori | Masalah dan lokasi | Rekomendasi | Confidence |
| --- | --- | --- | --- | --- |
| RV3-02 | Functional | `app.py`: 2161: `cap_res.get("id") or f"CAP_{order.order_id}"`, lolos dari pola gerbang | Tanpa ID capture dari PayPal, jangan simpan capture | High |
| RV3-03 | Functional | `app.py`: 1150: `exposure_cap_ok` bernilai True bila merchant tidak ditemukan | Perlakukan merchant yang hilang sebagai error | High |
| RV3-04 | Reliability | Webhook tanpa `id` diberi ID acak sehingga dedupe tidak berlaku | Tolak event tanpa `id` | High |
| RV3-07 | Functional | `app.py`: 1669–1714: tier Passport diambil dari body request (FR-63) | Hitung tier dari value band | High |
| RV3-08 | Architecture | 19 dari 25 kode error di luar katalog §28.2; `Idempotency-Key` hanya di 2 dari 26 POST | Perbarui katalog lewat Change Control; idempotensi di semua POST yang memindahkan uang | High |
| RV3-09 | Testing | `conftest.py` me-reset `data/proofreturn.db` sebelum setiap tes dan membuat semua tes bergantung pada DB | DB sementara per sesi tes; tes unit tanpa DB | High |
| RV3-10 | Documentation | Tanpa commit; `st01-system-run-R3.txt` berjudul bukti eksekusi padahal narasi; gate record menyebut 189 tes, repo berisi 229, tanpa output run terakhir | Commit per tugas; bukti hanya berisi output mentah | High |
| AUD-38 | Reliability | Image ber-digest, tetapi CI belum pernah berjalan | Push dan jalankan CI | High |
| AUD-40 | Functional | Skema request tidak tampil di OpenAPI | Parameter body bertipe | High |

| ID | Kategori | Masalah dan lokasi | Rekomendasi | Confidence |
| --- | --- | --- | --- | --- |
| RV3-12 | Reliability | `outbox.py` dan `repository.py`: aksi UNKNOWN dicoba ulang setiap putaran scheduler tanpa batas percobaan, backoff, maupun eskalasi | Batas percobaan dengan backoff; setelah batas, cek status refund lewat GET dan picu alert | High |

### INFORMATIONAL

| Area | Bukti |
| --- | --- |
| Gerbang anti-pola | 0 temuan dari 71 |
| Keamanan | Token, webhook, otorisasi, dan verifikasi kriptografi kini benar |
| Uang | Lock baris order, saldo pending dalam transaksi, over-refund 409, eksekutor dengan `SKIP LOCKED` dan retry dengan request ID yang sama |
| AI | Gate AG-01 benar secara statistik (rt) |
| Kualitas kode | 427 dari 429 fungsi beranotasi tipe; mekanisme §8.8 tetap 180/180 |

## F. Security Assessment revisi ke-3

Tidak ditemukan celah keamanan CRITICAL maupun HIGH. Kedua celah utama revisi ke-2 tertutup: penerbitan token kini hanya di DEMO\_MODE dengan bootstrap key yang dibandingkan secara constant-time, dan webhook hanya diterima lewat verifikasi PayPal atau HMAC demo. Risiko yang tersisa bersifat defense-in-depth (tanpa RLS), integritas data (ID karangan sebagai fallback), dan kepatuhan (cap jurisdiksi).

### Ringkasan per kategori

| Kategori | Revisi 2 | Revisi 3 | Bukti dan temuan terkait |
| --- | --- | --- | --- |
| Autentikasi dan session | Rentan | Baik | Token gagal-tertutup; penerbitan hanya di DEMO\_MODE dengan bootstrap key; TTL dibatasi 8 jam (staff) dan 24 jam (shopper); di luar demo tidak ada jalur login (RV3-05, masalah fungsional) |
| Otorisasi dan BOLA | Sebagian | Baik | Resale, penghapusan data, banding, outbox run (MERCHANT\_ADMIN, merchant sendiri), principal service, dan kunci idempotensi kini dibatasi; tanpa RLS sebagai lapisan kedua |
| Integritas webhook | Rentan | Baik | Verifikasi live atau HMAC demo; selain itu 400; dedupe di DB. Sisa: event tanpa `id` lolos dedupe (RV3-04) |
| Manajemen secret di kode | Baik | Baik | Validator menolak placeholder dan kunci pendek; `.env` tidak dinilai |
| Paparan data | Membaik | Baik | Magic link di luar demo tidak mengembalikan token; `GET /v1/keys` hanya kunci publik |
| Validasi input | Membaik | Membaik | Model Pydantic dan 422; skema tidak di OpenAPI (AUD-40) |
| Kriptografi | Membaik | Baik | Signature Ed25519 dan rantai hash diverifikasi sungguhan; kunci persisten dengan publikasi kunci publik |
| Integritas data uang | Rentan | Membaik | Lock baris dan saldo pending dalam transaksi; sisa: ID capture dan refund karangan sebagai fallback (RV3-01, RV3-02), guard cap gagal-terbuka (RV3-03) |
| Rate limiting | Ada | Ada | Token bucket dan batas body |
| Injection, SSRF, deserialisasi | Tidak ditemukan | Tidak ditemukan | ORM; `scripts/backup_restore.py` memakai `subprocess.run` dengan daftar argumen tanpa shell |
| Container dan jaringan | Baik | Baik | Non-root, image ber-digest, semua port Compose ke `127.0.0.1` |
| Kepatuhan hukum konsumen | — | Rentan | Curve melampaui cap jurisdiksi diterima (RV3-06) |

### Kepatuhan threat model (§32.4)

| Ancaman | Revisi 2 | Revisi 3 |
| --- | --- | --- |
| TM-05 IDOR lintas tenant | Sebagian | Terpenuhi di level aplikasi; tanpa RLS |
| TM-06 Webhook palsu | Tidak ada | Terpenuhi |
| TM-07 Over-refund lewat race | Dinetralkan | Terpenuhi: row lock dan saldo pending dalam transaksi |
| TM-14 SSRF | Terpenuhi | Terpenuhi |
| TM-15 DoS dan biaya | Sebagian | Sebagian: rate limit dan batas body |
| TM-16 Pembayaran live tak sengaja | Terpenuhi | Terpenuhi |
| TM-17 Retake oracle | Guard literal | Terpenuhi: `retakes_ok` dihitung dari retake tersimpan |
| TM-22 Operator mengubah record | Sebagian | Terpenuhi: rantai hash dan signature diverifikasi |
| TM-24 Carrier event palsu | Gagal | Terpenuhi: hanya DEMO\_MODE dan peran service atau staff tertentu |

### Catatan untuk deploy demo

Dalam DEMO\_MODE, siapa pun yang memegang `DEMO_BOOTSTRAP_KEY` bisa menerbitkan token peran apa pun, termasuk MERCHANT\_ADMIN. Itu sesuai desain demo, tetapi kunci itu harus diperlakukan sebagai kredensial admin: jangan dicantumkan di slide atau video demo, dan rotasi setelah penjurian.

### Area yang tidak dapat dinilai

- **Kerentanan dependensi.** Tanpa akses ke basis data advisori.
- **Uji penetrasi HTTP.** FastAPI tidak bisa dijalankan di sandbox audit; temuan HTTP berbasis analisis statis.
- **PayPal Sandbox dan Gemini.** Tidak ada panggilan jaringan.
- **`.env`.** Tidak dinilai sesuai permintaan pemilik.

## G. Testing & QA Report revisi ke-3

Suite tes kini kuat secara nyata: 229 tes dengan 1.414 assertion, 44 dari 44 route tercakup, banyak tes negatif, dan tidak ada lagi tes yang mengunci perilaku tidak aman. Kesebelas mutan dari audit sebelumnya kini tertangkap. Namun uji dengan mutan baru yang tidak pernah diungkap menunjukkan sebagian tes ditulis khusus untuk daftar mutan yang sudah diketahui: dua dari enam mutan baru lolos, dan salah satunya membuka cacat nyata di jalur uang (RV3-11).

| Ukuran | Revisi 2 | Revisi 3 |
| --- | --- | --- |
| Tes backend | 151, 1.037 assertion | 229, 1.414 assertion |
| Tes frontend | 6 | 6 (lulus) |
| Route tercakup | 42/42 | 44/44 |
| Assertion status error | 4xx jarang, beberapa mengunci perilaku keliru | 401 (18), 403 (19), 404 (12), 409 (19), 400 (11), 422 (5), 413, 429 |
| Lulus saat dijalankan auditor | 45 | 45 (39 backend, 6 frontend) |
| BLOCKED | 111 | 189 (186 karena SQLAlchemy lewat `conftest.py`, 3 `@given`) |
| Mutan lama tertangkap | 6 dari 11 | 11 dari 11 (dengan tes yang diekstrak) |
| Mutan baru tertangkap | — | 4 dari 6 |
| Gagal | 0 | 0 |

### G.1 Eksekusi

`backend/tests/conftest.py` memasang fixture `autouse` yang meng-import `DatabaseRepository` dan me-reset database default sebelum setiap tes. Akibatnya bahkan tes unit murni membutuhkan SQLAlchemy dan SQLModel, dan menjalankan suite mengubah `data/proofreturn.db` yang ikut dalam repo (RV3-09). Auditor menjalankan subset murni dengan `--noconftest`: 39 tes backend lulus. Tes frontend dijalankan dengan Node 22: 6 lulus.

### G.2 Mutation testing

**Mutan lama (M01–M11).** Pada subset murni hasilnya tetap 6 dari 11. Tahap 13 dan 16 menambahkan tes khusus untuk setiap mutan; auditor mengekstrak 13 fungsi tes itu lewat AST (semuanya hanya memakai modul domain) dan menjalankannya. Hasilnya 11 dari 11 mutan tertangkap, termasuk guard T-SM01 dan arah seleksi audit yang sebelumnya lolos dari seluruh suite.

**Mutan baru (N01–N06).** Untuk menguji apakah kekuatan tes berlaku umum, auditor membuat enam mutan yang tidak pernah diungkap.

| Mutan | Bug yang disuntikkan | Hasil | Keterangan |
| --- | --- | --- | --- |
| N01 | Pembekuan dispute diabaikan saat merencanakan refund | Lolos | Tidak ada tes di seluruh suite; penelusuran mengungkap RV3-11 |
| N02 | Webhook reversal tidak menolkan sisa refundable | Tertangkap | 2 tes |
| N03 | Mismatch dua tingkat dianggap adjacent | Tertangkap | Simulator analitik |
| N04 | Ambang nilai promosi NEW ke ESTABLISHED diturunkan 10x | Tertangkap | Tes promosi berbobot nilai |
| N05 | Verifikasi commitment seed audit dimatikan | Lolos | Tidak ada tes reveal seed palsu |
| N06 | Adjacent mismatch tanpa top-up | Tertangkap | Tes jurisdiksi dan adjacent |

Pelajarannya: instruksi yang menyebut mutan secara eksplisit menghasilkan tes yang tepat untuk mutan itu, tetapi tidak otomatis menutup perilaku di sekitarnya. Ke depan, daftar mutan sebaiknya tidak diberikan ke agen.

### G.3 Tes yang mengunci perilaku keliru

Tidak ditemukan. Assertion `status == "COMPLETED"` yang tersisa hanya untuk permintaan penghapusan data, bukan pembayaran. Tes webhook memakai HMAC demo, dan tes penerbitan token memakai bootstrap key.

### G.4 Celah cakupan

Refund pada order yang sedang di-dispute atau di-reverse, reveal seed palsu pada commitment audit, konfirmasi refund berstatus PENDING (RV3-01), cap jurisdiksi (RV3-06), E2E browser, dan ST-01 lewat sistem.

### G.5 Verifikasi klaim bukti

| Klaim | Sumber | Hasil verifikasi |
| --- | --- | --- |
| 189 tes lulus | Gate record, sesi 22 | Konsisten untuk kondisi saat T7; repo kini berisi 229 tes tanpa output run terakhir |
| Gerbang 0 anti-pola | Gate record | Benar (dijalankan ulang); dua nilai karangan lolos dengan format lain |
| Mutan M01–M11 tertangkap | Tahap 16 | Benar (diverifikasi dengan ekstraksi) |
| ST-01 eksekusi sistem | `st01-system-run-R3.txt` | Tidak didukung: hanya order CREATED dan narasi |
| CI gate blocking dan job Postgres | `ci.yml` | Konfigurasinya benar; belum pernah berjalan karena repo tanpa commit |

## H. Reliability & Production Readiness revisi ke-3

Untuk pertama kalinya fondasi operasional lengkap: migrasi sebagai service terpisah, scheduler dengan lease antarinstans, eksekutor refund yang idempoten, dedupe webhook di DB, rate limiter berbatas, dan image ber-digest yang berjalan non-root. Kesiapan rilis kini tertahan oleh dua hal yang bisa dikerjakan dalam hitungan hari: membuktikan aliran uang di Sandbox, dan memindahkan pembekuan dispute ke jalur DB (RV3-11).

| Area | Revisi 2 | Revisi 3 | Bukti |
| --- | --- | --- | --- |
| Penanganan error | Sebagian | Baik | Tidak ada `except: pass`; over-refund dan capture hilang menjadi 409; eksekutor memetakan 4xx, 5xx, dan timeout ke status berbeda |
| Logging dan observability | Membaik | Baik | Log memuat `return_id`, `decision_id`, `paypal_debug_id`; alert scheduler berjalan |
| Health dan readiness | Baik | Baik | `/v1/ready` mem-ping DB dan menyertakan alert; tidak melaporkan status scheduler |
| Database dan migrasi | Dipakai | Baik | Service `migrate` (`alembic upgrade head`) di Compose; aplikasi tidak menjalankan migrasi kecuali di SQLite |
| Transaksi uang | Sebagian | Baik | Row lock, saldo pending dan confirmed dalam transaksi, konfirmasi idempoten |
| Konkurensi | Sebagian | Membaik | Klaim outbox `FOR UPDATE SKIP LOCKED`; lease scheduler di DB; cache idempotensi dan rate limiter tetap per proses |
| Background task | Tidak berjalan | Berjalan | Scheduler otomasi dan alert di `lifespan` |
| Retry eksternal | — | Rapuh | Aksi UNKNOWN dicoba ulang setiap putaran scheduler tanpa batas percobaan, tanpa backoff, dan tanpa eskalasi (RV3-12) |
| Exactly-once webhook | Baik | Baik | Dedupe di DB; event tanpa `id` lolos dedupe (RV3-04) |
| Manajemen resource | Membaik | Baik | Rate limiter dengan `max_keys` 10.000 dan TTL 300 detik; cache TTL |
| Performa komputasi | Memadai | Memadai | `release.py` tidak berubah: `decide_release` sekitar 80 µs p50 |
| Kesiapan deployment | Membaik | Membaik | Compose lengkap, image ber-digest, non-root; belum diuji di mesin bersih; CI belum pernah berjalan |
| Backup dan recovery | Tidak ada | Sebagian | `scripts/backup_restore.py` ada; tidak ada output drill di bukti |
| Kegagalan yang anggun | Membaik | Baik | Tanpa kredensial, eksekutor berhenti dengan `PAYPAL_NOT_CONFIGURED` tanpa memalsukan status |

### Risiko yang perlu pengujian lanjutan

- ST-01 lewat sistem di Sandbox, termasuk refund berstatus PENDING (RV3-01).
- Dispute di antara tranche: setelah RV3-11 diperbaiki, pastikan R1 dan R2 tidak dikirim.
- `docker compose up` dan job CI `postgres-integration` di mesin bersih.
- Drill backup dan restore ke database baru, diikuti rekonsiliasi.
- Dua replika API: lease scheduler, idempotensi, dan rate limit lintas proses.

### Kesimpulan kesiapan

Sistem layak didemokan dalam DEMO\_MODE satu proses. Untuk rilis, yang menentukan adalah bukti ST-01, perbaikan RV3-11, dan jalur login di luar DEMO\_MODE (RV3-05).

## I. Missing Implementation, Technical Debt, dan konsistensi lintas modul

Sisa pekerjaan kini kecil dan terlokalisasi. Dua inkonsistensi lintas modul paling berarti adalah status freeze yang hanya hidup di memori (RV3-11) dan gate record yang melampaui `rtm.csv` milik proyek sendiri (RV3-13).

### I.1 Konsistensi lintas modul (Fase 8)

| Pasangan yang dicek | Revisi 2 | Revisi 3 | Bukti |
| --- | --- | --- | --- |
| SSOT ↔ implementasi | Sebagian | Sebagian besar | 44 PASS, 4 FAIL dari 137 |
| Ledger in-memory ↔ repository | — | Tidak | Freeze dispute dan reversal hanya di ledger in-memory (RV3-11) |
| JSON Schema ↔ model request | Sebagian | Sebagian | `order_id` dan `schema_version` wajib di skema, tidak ada di model |
| Kontrak §28 ↔ API | Sebagian | Sebagian | 19 dari 25 kode error di luar katalog; idempotensi di 2 dari 26 POST |
| Model DB ↔ migrasi | Ya | Ya | 23 tabel sinkron |
| API client frontend ↔ API | Ya | Ya | 16 path, semuanya ada |
| `.env.example` ↔ settings | Sebagian | Ya | Empat kunci tersisa dipakai Compose (Postgres, Redis), bukan aplikasi |
| Enum tier, curve, nama model AI | Ya | Ya | Konsisten |
| `rtm.csv` ↔ kode | Usang | Ya | 25 VERIFIED, 0 bertentangan, cenderung konservatif |
| Gate record ↔ `rtm.csv` | — | Tidak | G1–G5 PASSED dengan kriteria yang belum VERIFIED (RV3-13) |
| Bukti ↔ kode | Tidak | Sebagian | ST-01 jujur IMPLEMENTED; file bukti ST-01 berupa narasi; output run terakhir (229 tes) tidak ada |
| README ↔ Compose | Tidak | Ya (statis) | `docker compose --profile lite up -d --build` sesuai service yang ada; belum diuji jalan |

### I.2 Implementasi yang belum ada

| Area | Yang belum ada | Referensi |
| --- | --- | --- |
| Bukti uang | Run ST-01 lewat sistem di Sandbox | AUD-02 |
| Identitas di luar demo | Login staff, pengiriman magic link | RV3-05 |
| AI | Kalibrasi konformal di keputusan, red-team nyata, rekaman judge mode | RV2-05, FR-20, FR-80 |
| Domain | Modul custody dan return seal terpisah | RV2-05 |
| Frontend | Aplikasi browser (bundler, halaman), blur on-device | ARC-07, FR-16 |
| Media | Object storage dan upload | FR-02 |
| Integrasi PayPal lain | Tracking, Disputes API | FR-07, FR-34 |
| Data | RLS | ARC-09 |
| Agen | Transport MCP | ARC-12 |

### I.3 Placeholder yang tersisa

| Placeholder | Lokasi | Temuan |
| --- | --- | --- |
| ID refund `PP-REF-...` bila respons tanpa `id` | `outbox.py`: 57 | RV3-01 |
| ID capture `CAP_{order_id}` bila respons tanpa `id` | `app.py`: 2161 | RV3-02 |
| `exposure_cap_ok = True` bila merchant tidak ada | `app.py`: 1150 | RV3-03 |
| ID webhook acak bila event tanpa `id` | `app.py`: sekitar 2459 | RV3-04 |
| Tier Passport dari body | `app.py`: 1669–1714 | RV3-07 |

### I.4 Technical debt

- **Dua sumber status freeze:** ledger in-memory dan repository (RV3-11).
- **State per proses:** cache idempotensi dan rate limiter tidak dibagi antarreplika.
- **Tes yang bergantung pada DB:** `conftest.py` membuat semua tes bergantung pada SQLModel dan me-reset DB di repo (RV3-09).
- **Tes yang ditulis untuk mutan tertentu:** tes tahap 16 menutup 11 mutan yang diketahui, tetapi perilaku di sekitarnya (freeze dispute, reveal seed palsu) tidak teruji.
- **Proses:** tanpa commit, katalog kode error tanpa Change Control, gate record tidak diturunkan dari bukti.

## J. Remediation Roadmap

Sisa waktu menuju deadline 12 November adalah 8 hari. Lima item Must Fix bisa selesai dalam 2–3 hari kerja; tidak ada lagi pekerjaan berskala besar di jalur kritis.

### J.1 Must Fix Before Release

| ID | Tindakan | Temuan | Alasan prioritas | Bergantung pada |
| --- | --- | --- | --- | --- |
| J-01 | Pindahkan pembekuan dispute dan reversal ke DB: kolom di `orders` (migrasi baru), diperbarui webhook dalam transaksi yang sama dengan dedupe; tolak perencanaan dan lewati eksekusi untuk order yang dibekukan | RV3-11 | Risiko kerugian ganda merchant | — |
| J-02 | Petakan status refund PayPal (COMPLETED, PENDING, FAILED, CANCELLED); tanpa `id`, tandai UNKNOWN dan picu alert; hapus fallback ID karangan untuk refund dan capture | RV3-01, RV3-02 | Saldo confirmed harus sesuai kenyataan | — |
| J-03 | Jalankan ST-01 lewat sistem di Sandbox (order disetujui akun pembeli, capture lewat API, alur return, outbox, verifikasi refund, dispute di antara tranche); simpan semua ID PayPal | AUD-02 | Bukti nilai utama produk | J-01, J-02 |
| J-04 | Validasi cap jurisdiksi saat policy dibuat dan di engine | RV3-06 | Kepatuhan hukum konsumen | — |
| J-05 | Turunkan gate record dari `rtm.csv` dan `sandbox-tests.md`; kembalikan G1–G5 ke IN PROGRESS sampai kriteria terpenuhi; commit per tugas; simpan output run terakhir | RV3-13, RV3-10 | Narasi submission harus bersandar pada bukti | J-03 |

### J.2 Should Fix Before Production

| ID | Tindakan | Temuan | Bergantung pada |
| --- | --- | --- | --- |
| J-06 | Login staff dan pengiriman magic link di luar DEMO\_MODE, atau nyatakan terbuka bahwa rilis hackathon hanya DEMO\_MODE | RV3-05 | — |
| J-07 | Batas percobaan dan backoff outbox dengan alert; tolak webhook tanpa `id`; guard cap gagal-tertutup; tier Passport dari value band | RV3-12, RV3-04, RV3-03, RV3-07 | J-02 |
| J-08 | Tes berbasis invariant: dispute di antara tranche, reveal seed palsu, refund PENDING, cap jurisdiksi; DB sementara di `conftest.py`; jalankan CI | AUD-36, RV3-09, AUD-34, AUD-38 | J-01, J-02, J-04 |
| J-09 | Sambungkan kalibrasi konformal ke uji misdeclaration; sambungkan atau hapus modul custody dan seal | RV2-05 | — |

### J.3 Recommended Improvements

| ID | Tindakan | Temuan |
| --- | --- | --- |
| J-10 | Perbarui katalog kode error lewat Change Control; idempotensi di semua POST yang memindahkan uang; skema request di OpenAPI; RLS sebagai lapisan kedua isolasi tenant | RV3-08, AUD-40, ARC-09 |

### J.4 Optional Optimizations

| ID | Tindakan | Alasan |
| --- | --- | --- |
| J-11 | Bundler frontend (misalnya Vite) agar aplikasi bisa dibuka di browser | Demo visual untuk juri |
| J-12 | Transport MCP; Temporal | Sesuai ADR-003 dan ADR-010, bukan syarat demo |

### Catatan untuk instruksi agen berikutnya

Jangan lagi memberikan daftar mutan secara eksplisit. Mintalah satu tes negatif untuk setiap invariant SSOT (INV-01 sampai INV-18) yang diuji lewat API, karena tes yang ditulis untuk mutan tertentu terbukti tidak menutup perilaku di sekitarnya (Bagian G.2). Pertahankan skrip gerbang dan tambahkan pola baru dari audit ini: ID karangan dengan format apa pun (`PP-REF-`, `CAP_`) dan `or True` pada guard.

## K. Final Verdict

**REQUIRES REMEDIATION.** Untuk pertama kalinya sistem sudah terbangun secara substansial dan tidak lagi memiliki masalah fundamental: tidak ada temuan CRITICAL, keputusan uang dihitung engine dan disimpan secara transaksional, keamanan inti benar, dan fondasi operasional lengkap. Masih ada masalah material yang harus diselesaikan sebelum proyek bisa dinyatakan selesai.

| Dimensi | Dasar verdict |
| --- | --- |
| Implementasi | 44 dari 137 requirement PASS, 4 FAIL; aliran uang ke PayPal belum pernah dibuktikan (AUD-02) |
| Keamanan | Tidak ada celah CRITICAL atau HIGH; sisa defense-in-depth (RLS) dan integritas data (ID karangan sebagai fallback) |
| Reliability | Layak sebagai demo satu proses; pembekuan dispute tidak berlaku di jalur DB (RV3-11) |
| Integritas bukti | `rtm.csv` dan `sandbox-tests.md` jujur; gate record mengklaim G0–G5 PASSED tanpa kriterianya terpenuhi (RV3-13) |

**Mengapa bukan READY.** Dua temuan HIGH menyangkut uang: refund belum terbukti sampai ke PayPal, dan dispute tidak menghentikan tranche berikutnya. Keduanya harus ditutup dan dibuktikan lewat ST-01 sebelum rilis.

**Mengapa bukan NOT READY.** Masalah yang tersisa terlokalisasi dan bisa diselesaikan dalam 2–3 hari kerja (J-01 sampai J-05) tanpa perubahan arsitektur. Fondasi yang dulu tidak ada, yaitu persistensi, orkestrasi engine, autentikasi, dan eksekutor refund, kini terbukti ada dan benar.

**Apa yang membawa ke READY.** J-01 sampai J-05 selesai, ST-01 lewat sistem berhasil dengan ID PayPal tercatat (termasuk skenario dispute di antara tranche), CI berjalan hijau dari commit nyata, dan gate record diturunkan dari bukti.

**Kemajuan selama empat audit.** Temuan terbuka turun dari 40 (3 CRITICAL) ke 19 (0 CRITICAL); requirement PASS naik dari 9 ke 44; gerbang anti-pola turun dari 71 ke 0; mutan lama tertangkap 11 dari 11; mekanisme inti tetap 180/180 sejak audit pertama.

**Keyakinan dan batas cakupan.** Keyakinan atas verdict: High. FastAPI, SQLAlchemy, dan SQLModel tidak bisa dijalankan di sandbox audit, sehingga 189 tes BLOCKED dan lapisan HTTP dinilai secara statis, ditopang oleh eksekusi fungsi domain, ekstraksi tes, dan mutation testing. Tidak ada panggilan ke PayPal maupun Gemini, dan `.env` tidak dinilai sesuai permintaan pemilik.

Seluruh file revisi ke-3 tetap tidak berubah selama audit (manifest SHA-256 diverifikasi setiap fase); mutasi hanya dilakukan di salinan sementara yang sudah dihapus.

## Audit Ledger

Posisi per 4 November 2026, setelah Fase 8. Semua bagian sudah diisi.

### Eksekusi

| Eksekusi | Perintah ringkas | Hasil |
| --- | --- | --- |
| Gerbang anti-pola (versi auditor dan versi proyek) | `python3 check_antipatterns.py <salinan read-only>` | 0 temuan, 0 penanda; skrip proyek identik kecuali newline akhir |
| Pemindaian penghindaran gerbang | Analisis AST dan regex: guard via variabel atau `**kwargs`, `except` tanpa raise, ID karangan dengan format lain, header huruf kecil, `COMPLETED` di payments | 1 capture ID dan 1 refund ID karangan, 1 guard gagal-terbuka; tidak ada guard tersembunyi lewat dict |
| Gate AG-01 | `harness/ag01_check.py`, 20 ulangan per skenario | 20/20 terkalibrasi, 0/20 memburuk |
| Mekanisme §8.8 | `harness/mechanism_check.py` | 180/180 |

Semua eksekusi berjalan di salinan kerja tanpa `.env` dan tanpa jaringan. Manifest SHA-256 salinan asli diverifikasi tanpa perubahan setelah fase ini.

**Fase 2.** Karena `backend/tests/conftest.py` meng-import `DatabaseRepository` secara global, subset murni dijalankan dengan `--noconftest` (penyimpangan dari konfigurasi proyek, dicatat di sini): state machine dan Gemini 9 lulus, payments 5 lulus dan 1 deselected (native), golden dan Policy Engine 25 lulus dan 3 skip (indikatif). Sebanyak 27 file lain tidak bisa dikoleksi karena SQLAlchemy. Tes frontend 6 lulus. Validitas `test_ids` di `rtm.csv` diperiksa lewat AST: semua 25 rujukan VERIFIED ada. Catatan: fixture `reset_default_demo_db` me-reset DB default `data/proofreturn.db`, sehingga menjalankan suite mengubah file DB di repo.

**Fase 3.** Graf import non-tes, keterjangkauan 16 modul domain dari `backend.api.app`, pemakaian 65 metode repository, sinkronisasi 23 tabel model dan migrasi, konvensi API dan katalog kode error §28.2, MCP, serta service Compose dan job CI. Diagram dirender dan diperiksa visual.

**Fase 4.** Metrik kode (427/429 anotasi, 16 `except Exception`), logika saldo refund di `repository.py` (`plan_refund_action_transactional`, `claim_planned_refund_actions`, `record_refund_confirmed`), konfirmasi di `outbox.py`, dan endpoint carrier event. Probe INV-11 dijalankan ulang secara runtime. Fase ini mengoreksi FR-96 di Bagian C dari FAIL menjadi PASS.

**Fase 5.** Otorisasi `POST /v1/ops/outbox/run`, isi pencatatan magic link di luar demo, pemanggilan `subprocess` di `scripts/backup_restore.py`, pemindaian pola berbahaya, port Compose, batas TTL token demo, dan isi `GET /v1/keys`. Tidak ada temuan keamanan baru selain yang sudah tercatat di Bagian E.

**Fase 6.** Inventaris AST 229 tes, cakupan route, distribusi assertion status, dan pencarian tes yang mengunci perilaku keliru. Mutation testing M01–M11 di subset murni dengan `--noconftest` (6/11), lalu dengan 13 tes pembunuh mutan dari tahap 13 dan 16 yang diekstrak lewat AST ke `harness/extracted/` (11/11). Enam mutan baru N01–N06 di `harness/mutation_new.py` (4/6). Penelusuran N01 menghasilkan RV3-11 dan mengubah FR-75 di Bagian C menjadi FAIL. Semua mutan diterapkan di salinan sementara yang langsung dihapus.

**Fase 7.** Pemeriksaan batas rate limiter, batas percobaan dan backoff eksekutor outbox, isi readiness probe, service `migrate` di Compose, bukti drill backup, dan cache idempotensi. Hasilnya Bagian H dan temuan RV3-12.

**Fase 8.** Pencocokan JSON Schema dengan model request, path API client dengan route, `.env.example` dengan settings, README dengan Compose, serta status gate record dengan status requirement di `rtm.csv` milik proyek. Hasilnya Bagian I.1 dan temuan RV3-13; laporan final A, I, J, dan K disusun dari seluruh fase.

### Cakupan inspeksi

- **Dibaca rinci:** handler penerbitan token, webhook, penghapusan data, verifikasi Passport, capture resale, cap exposure, lifespan dan scheduler; `payments/outbox.py`; konfigurasi demo; bukti `st01-system-run-R3.txt`, `session-22-R3.md`, gate record, dan `sandbox-tests.md`.
- **Diperiksa tertarget:** 26 temuan terbuka lewat pola kode, termasuk lock DB di repository dan isian guard pada transisi.
- **Belum dibaca rinci:** `db/repository.py` (sebagian), `jobs/automation.py` (sebagian), `scripts/backup_restore.py`, isi tes tahap 8–17, CHANGELOG dan PROJECT\_LOG.

### Catatan pemilik

`.env` sengaja diletakkan di folder proyek dan tidak dinilai.
