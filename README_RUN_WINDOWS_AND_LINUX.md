# OptimusKG — AMG 757 & AMG 691 Self-Contained Visualization Studio
### Cross-Platform Portable Edition (Windows 11 & Linux)

Everything required to run all interactive visualizations, 47-asset Knowledge Graph explorers, demo playbooks, and the live `<1.5s` CPU target-scoring engine is **100% contained inside this single folder** (`visualization_studio/`). You can copy or zip this folder onto any **Windows 11** laptop or **Linux** workstation and run it directly from within the folder — with **zero internet connection** and **zero dependency on outside folders, GPUs, PyTorch, DGL, SciPy, or Scikit-Learn**.

---

## 1. Quick Start — Windows 11

Open this `visualization_studio` folder in **Windows File Explorer**:

1. **Recommended (Full Interactive Server + Live KG Scoring Mode):**
   - Double-click **`Launch_Visualization_Windows.bat`**
   - Or in **PowerShell / Command Prompt** inside this folder:
     ```bat
     python run_visualization_studio.py --open-browser
     ```
   - Your default browser (Edge / Chrome) opens automatically to `http://127.0.0.1:8004/` (binds strictly to `127.0.0.1`, so Windows Defender Firewall never prompts for administrator rights).
   - To stop the background server when finished, press `Ctrl+C` in the console window or double-click **`Stop_Visualization_Windows.bat`**.
   - *(Optional)* If your Windows 11 Python does not yet have `numpy` installed and you want live `⚡ Score New Target` neural inference, double-click **`Install_Optional_Live_Engine_Windows.bat`** once (installs only `numpy` into a local `.venv` inside this folder).

2. **Zero-Install Offline Browser Mode (Even on Locked-Down PCs Without Python):**
   - Simply double-click any of these standalone `.html` files in File Explorer:
     - **`index.html`** (Unified Visualization Launchpad)
     - **`AMG757_Tarlatamab_V4_Evidence_Studio.html`** (Primary Canonical `v4.3.2` AMG 757 Audited Evidence & Basket Studio, 5 tabs)
     - **`AMG757_Tarlatamab_Indication_Expansion_Studio.html`** (Companion 17-tab AMG 757 KG & Single-Cell Explorer, `v3.2`)
     - **`AMG691_CD30_Combination_Discovery_Studio.html`** (9-tab Bilingual EN/中文 AMG 691 Benign I&I Combination Discovery Studio, `v2.0`)
     - **`OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck_EN.html`** / **`OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck_ZH.html`** (Interactive Bilingual Widescreen Slide Decks)

---

## 2. Quick Start — Linux

Open a terminal inside this `visualization_studio` folder:

```bash
./launch_visualization_linux.sh
```

* Headless / custom port options:
  ```bash
  ./launch_visualization_linux.sh --port 8010 --no-browser
  ./launch_visualization_linux.sh --check   # Run built-in self-test & exit
  ```
* Stop any running server:
  ```bash
  ./stop_visualization_linux.sh
  ```

---

## 3. What Is Included Inside This Folder

| File / Subfolder | Purpose |
| :--- | :--- |
| `index.html` | Unified Visualization Launchpad Hub (auto-detects Live Server vs. Offline `file://` mode) |
| `AMG757_Tarlatamab_V4_Evidence_Studio.html` | Primary Canonical **`v4.3.2` AMG 757 (Tarlatamab)** Audited Bayesian Evidence, Split `Table A/B`, Temporal Back-Test & `WP9` Basket Studio (5 tabs, 100% offline) |
| `AMG757_Tarlatamab_Indication_Expansion_Studio.html` | Companion + Live-API-capable **AMG 757 (Tarlatamab)** KG, Metapath & Single-Cell Explorer (`v3.2`, 17 tabs) |
| `AMG691_CD30_Combination_Discovery_Studio.html` | Standalone Bilingual (EN/中文) **AMG 691 (`CD30/CD30L`, Phase 1 `NCT06637371` & `NCT07745907`)** 15-Indication & Combination Discovery Studio (`v2.0`, 9 tabs) |
| `Full_Portfolio_47_Assets_Discovery_Portal.html` | Full **47-Asset Amgen Translational Discovery Portal** (`?asset=tarlatamab`, `?asset=amg_691`, etc.) |
| `OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck_{EN,ZH}.html` | Browser-native interactive presentation slide decks in English and Simplified Chinese (plus alias `OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck.html`) |
| `Launch_Visualization_Windows.bat` / `Stop_Visualization_Windows.bat` | One-click **Windows 11** start/stop scripts (`CRLF`, Microsoft Store Python-stub safe) |
| `launch_visualization_linux.sh` / `stop_visualization_linux.sh` | One-click **Linux** start/stop scripts (`LF`, executable) |
| `run_visualization_studio.py` | Cross-platform Python 3 HTTP + Live KG API server |
| `d3.v7.min.js`, `studio_data.json`, `explorer_data/` | Local D3 v7 engine + 47-asset KG subgraphs, 2–10 hop metapaths, attention trees & 2D t-SNE (`0` CDN calls) |
| `engine_data/` & `studio_engine/` | Pure-NumPy FP16 neural inference pack (`18,025` diseases × `9,860+` drugs, Mondrian conformal calibrator, & 3-head `OptimusComboNet`) |
| `configs/` | Editable YAML configs (including `amgen_internal_targets.yaml` for custom targets) |
| `demo_guides/` | English & Chinese step-by-step live demo playbooks for AMG 757 and AMG 691 |
