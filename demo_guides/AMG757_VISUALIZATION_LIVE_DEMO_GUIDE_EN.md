# AMG 757 (`IMDELLTRA®` / `tarlatamab-dlle`) Indication Expansion (`Canonical v4.3.2`): Interactive Visualization & Live Demo Playbook

**Primary Governance Demo (`v4.3.2` Audited Evidence Studio — 100% Offline Single-File HTML5)**:
- `AMG757_Tarlatamab_V4_Evidence_Studio.html` (`5` interactive governance tabs + instant top-right `中文 / EN` toggle; zero server or internet required)

**Companion Translational Multi-Omics & Subgraph Workbench (Optional Deep-Dive)**:
- `AMG757_Tarlatamab_Indication_Expansion_Studio.html` (`18,025` diseases, `2,215` primary patient biopsies, `60,026` SCLC single cells, `<=14 nm` synapse biophysics, and `<1.5s` pure-`NumPy` live target projection via `visualization_studio/`)

---

## 1. Two-Studio Architecture & Pre-Meeting Setup (`< 30 Seconds`)

1. **For Biostatistics, Clinical Development, Regulatory & Portfolio Governance (`95%` of meetings)**:
   - Double-click **`AMG757_Tarlatamab_V4_Evidence_Studio.html`** in Chrome, Edge, or Safari.
   - Click **`中文 / EN`** in the top-right bar to switch instantly between English and Simplified Chinese.
   - Every table, posterior interval, route `rNPV`, operating-characteristic curve, and ledger hash in this HTML5 file is compiled directly from `results_v4/` artifacts (`0` hand-typed numbers; enforced by `tests/test_doc16_zero_drift.py`).
2. **For Optional Live Knowledge-Graph Subgraph & Custom Target Scoring (`5%` deep-dive Q&A)**:
   - On Windows 11, double-click `visualization_studio\Launch_Visualization_Windows.bat`; on Linux/macOS, run `bash visualization_studio/launch_visualization_linux.sh` (`http://127.0.0.1:8004`).

---

## 2. 7-Minute Click-by-Click Executive & Biostatistics Walkthrough

### Act 1 (`0:00 – 1:15`): Top KPI Banner & Registry Ground Truth
- **Where to Point**: Header KPI strip + **`中文 / EN`** toggle.
- **Exact Words to Say**:
  > *"Everything in `v4.3.2` rests on `260` offline-verified primary provenance rows (`208` verbatim value-in-excerpt `verified`, `25` dual-curated `verified_source_only`, `27` bounded `analyst_estimate`) and `120` enriched `ClinicalTrials.gov` `DLL3` studies. Crucially, `Table A` (`$2,610.8M` under the shared `2036-05-16` `PHS Act §351(k)(7)` biologic floor; `$3,306.6M` under `2039` patent protection) is physically segregated from incremental new options in `Table B`."*

---

### Act 2 (`1:15 – 3:00`): Segregated `Table A` (`12+7=19`) & `Table B` (`V0 / V1 / V2` Routes) — **Tab `1. Table A (12+7) & Table B (V0 / V1 / V2)`**
- **Where to Click**:
  1. Stay on **`1. Table A (12+7) & Table B (V0 / V1 / V2)`** and point first to **`Table A`** (`EXP-S1` `DeLLphi-305` OS HR `0.42 [0.32–0.54]` + `DeLLphi-312` = `$2,145.6M`; `EXP-S2` `+ZL-1310 NCT07531095` & `+YL201 NCT06898957` = `$23.4M`; `EXP-S3` `DeLLphi-306` = `$441.8M`; net of `-$469.3M` `2L` cannibalization across `12` active/committed SCLC expansion studies + `7` historical baseline studies = `19` registry entries).
  2. Scroll to **`Table B`** (`#1..#10`) and highlight `#1 EXP-S4` (`ES-SCLC` Active Brain Mets, `NCT07402343`, `N=35`, `+$59.7M`, noting `33.0%†` is a systemic SCLC reference only) and `#2 EXP-L1` (`Pulmonary LCNEC`, `IFCT NCT06937905`, `Q2 = 44.5% [17.0%, 81.3%]` under `a_0 = 0.50`, `+$27.1M` `V1` / `+$34.3M` `V2`).
  3. Point to the `7` rare extra-pulmonary cohorts (`EXP-A..G`): **`Route V0` (Standalone INDs) = `-$34.6M`**, **`Route V1` (External IIT Signal Federation across `11` open academic trials, `N=517` slots) = `+$1.8M`** (`-$4.3M` at `0.75` drug-supply attrition; **`EVSI = +$12.94M` [`$12.35M` exact `2036` LOE]**), and **`Route V2` (De Novo Amgen Master Basket) = `+$10.6M`**, plus `EXP-G` pediatric neuroblastoma (`FD&C §529 PRV = $0.0M`; `-$12.5M` direct vs **`+$172.3M`** net only under voluntary `BPCA §351(m)` `+$184.8M`).

---

### Act 3 (`3:00 – 4:15`): Leak-Free `PE1` Back-Test & Why `Q5` Remains Retired — **Tab `2. PE1 Discovery Back-Test & Within-NE MDE`**
- **Where to Click**: Click **`2. PE1 Discovery Back-Test & Within-NE MDE`**.
- **Exact Words to Say**:
  > *"Why are there zero AI/KG ranking columns in `Table B`? Across `32` surface antigens and `178` strictly zero-prior-trial `PE1_new_indication` events, our frozen pre-cutoff `P5` omics model (`(16, 8)` `tanh`, `alpha=8.0`) beat single-gene expression (`0.378` vs `0.307`, Holm `p = 0.0042`), while comparing static `M5` (`0.501`) vs `P5` (`0.378`) caught `+0.123` post-cutoff hotspot leakage — and adding the KG (`M4 = 0.444`) did not beat omics (`wp25_passed = False`). We retired `Q5` so clinical decisions rest purely on calibrated `Q1/Q2` posteriors."*

---

### Act 4 (`4:15 – 5:30`): `WP9` Basket Error Control & `11`-Study IIT Network — **Tab `3. WP9 Trade-Off & IIT Network`**
- **Where to Click**: Click **`3. WP9 Trade-Off & IIT Network`**.
- **Exact Words to Say**:
  > *"Naive exchangeable BHM inflates worst-case mixed-null Type I error to `33.43%`. Under cohort-specific historical SoC nulls (`p0_k = 10%–15%`) across `3` prior regimes (`2.82/7`, `1.82/7`, `1.60/7` active), `Shared_Protocol_Independent_Simon` (`$20.96M`; FixedN20 `$16.66M`) caps per-cohort Type I error at `<=4.99%` with zero borrowing inflation, `EXNEX<=10%` (`$17.24M`, `<=8.25%` Type I) is preferred only if `>=3/7` cohorts are active, and `Federated_IIT_Signal_Pool_V1` (`$15.40M`) leverages `11` already-recruiting academic trials (`N=517`) as our Stage-1 filter."*

---

### Act 5 (`5:30 – 6:45`): Bitcoin `.ots` Ledger, `EVSI` Triggers & `Ion Guard` — **Tabs `4` & `5`**
- **Where to Click**:
  1. Click **`4. Bitcoin .ots Ledger & EVSI Triggers`** to show the `41`-row append-only ledger **`3/3` settled in Bitcoin blocks `#975,929`, `#975,963`, `#976,004` & `#976,009`**, with **`5` `q2_empirical_model` forecasts** (`FCST-09, 11..14`) scored strictly separately from **`4` `analyst_prior` forecasts** (`FCST-17..20`), alongside concrete trial `Go/No-Go` responder triggers (`NCT07402343 >= 12/35` [`8..11/35` subgroup-review sensitivity], `LCNEC <= 2/15` futility stop, `Korea EP-NEC >= 12/50`, `Strasbourg GYN >= 6/20`, `MSK NEPC >= 8/32`).
  2. Click **`5. Q4 Combos & Appendix B (Q6 Heuristics)`** to show `Q4` candidly disclosed at `recall@50 = 0.000` and Appendix B's `Ion Guard` demoting excitable channels `KCNB2` (`0.0467`) and `SCN3A` (`0.0371`) in favor of **`DLL3 + IGSF9` (`0.4745`, `13.4 nm`, `1.18%` TIL)**.

---

## 3. Quick Q&A Tab Cheat Sheet

| Governance / Red-Team Question | Exact Tab & Element to Show |
| :--- | :--- |
| *"Why isn't `NCT06788938` our shared basket anymore?"* | **Tab 1 & Tab 3** -> `NCT06788938` is a single-center UCLA study (`N=29`, `ACTIVE_NOT_RECRUITING`); compare `Route V1` (`11` open IITs, `N=517`, `EVSI = +$12.94M`) vs `Route V2` (`$20.96M` de novo basket). |
| *"Isn't `LCNEC` (`44.5%`) clearly ahead of `GEP-NEC` (`32.7%`)?"* | **Tab 1** -> Under `a_0 = 0.50`, `LCNEC` `[17.0%, 81.3%]`, `GEP-NEC` `[10.7%, 64.5%]`, `GU/GYN` `[10.0%, 64.8%]`, and `t-NEPC` `[10.3%, 48.1%]` overlap statistically (`0` tarlatamab LCNEC trials -> `N=15` futility gate). |
| *"Does `EXP-S4` (`33.0%†`) predict intracranial RANO-BM response?"* | **Tab 1 & Tab 4** -> Explicitly tagged `Systemic SCLC Reference Only†`; intracranial `RANO-BM` (`NCT07402343`, `N=35`) is tracked separately under `FCST-2026-17` (`analyst_prior`, `>=12/35` trigger). |
| *"What if academic IITs lose drug supply like `GETNE` / `NCI`?"* | **Tab 1 & Tab 3** -> Show the `0.75` drug-supply attrition column (`V1` shifts from `+$1.8M` to `-$4.3M`, still saving `>$30M` vs `V0 = -$34.6M`). |
| *"Why does pediatric neuroblastoma (`EXP-G`) get `$0` PRV?"* | **Tab 1** -> `FD&C Act §529(a)(4)(A)` excludes already-approved moieties (`2024-05-16`); only voluntary `BPCA §351(m)` adds `+0.5y` (`+$184.8M` base, `+$172.3M` net). |
| *"How do we know forecasts weren't tuned after readouts?"* | **Tab 4** -> Point to `SHA-256` hashes + offline-verified **`3/3` Bitcoin blocks `#975,929`, `#975,963`, `#976,004` & `#976,009`** `.ots` proofs and separated `Q2` vs `analyst_prior` scorecards. |
