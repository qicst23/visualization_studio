# OptimusKG — AMG 757 & AMG 691 Self-Contained Visualization Studio
### Cross-Platform Portable Edition (Windows 11 & Linux)

Everything required to run all interactive visualizations, 47-asset Knowledge Graph explorers, demo playbooks, and presentation decks is **100% self-contained inside this repository**. You can run all HTML studios directly in any modern browser with **zero internet connection** and **zero external dependencies**.

---

## 1. Quick Start

### A. Zero-Install Offline Browser Mode (Works on Any Machine)
Simply open any of these standalone `.html` files in your web browser:
- **`index.html`** — Unified Visualization Launchpad Hub
- **`AMG757_Tarlatamab_V4_Evidence_Studio.html`** — Primary Canonical v4.3.2 AMG 757 (Tarlatamab) Audited Bayesian Evidence, Split Table A/B, Temporal Back-Test & WP9 Basket Studio (5 tabs)
- **`AMG757_Tarlatamab_Indication_Expansion_Studio.html`** — Companion AMG 757 (Tarlatamab) KG, Metapath & Single-Cell Explorer (v3.2, 17 tabs)
- **`AMG691_CD30_Combination_Discovery_Studio.html`** — Standalone Bilingual (EN/中文) AMG 691 (CD30/CD30L) 15-Indication & Combination Discovery Studio (v2.0, 9 tabs)
- **`Full_Portfolio_47_Assets_Discovery_Portal.html`** — Full 47-Asset Amgen Translational Discovery Portal
- **`OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck_EN.html`** / **`..._ZH.html`** — Interactive Widescreen Slide Decks

### B. Interactive Python Server Mode
- **Windows 11:** Double-click `Launch_Visualization_Windows.bat` (or run `python run_visualization_studio.py --open-browser`).
- **Linux:** Run `./launch_visualization_linux.sh` (or `python3 run_visualization_studio.py --open-browser`).

---

## 2. Optional: Live Neural Target Scoring Engine

To enable the optional live `<1.5s` CPU neural inference feature (`⚡ Score New Target`), download the 1.61 GB FP16 embedding tensor pack and place it into `engine_data/`:

- **File Name:** `engine_data/pack_tensors_fp16.npz` (1.61 GB)
- **Download Link (Google Drive):** [Download pack_tensors_fp16.npz / Full Studio Package](https://drive.google.com/file/d/1MxgH0yQ3WvFosnPqOId2zNX0YHbWE6E5/view?usp=sharing)
- *(Note: If this file is not present, the studio runs in static browser/server mode with 100% of the interactive visualizations and precomputed results fully functional).*

---

## 3. Repository Structure

| File / Subfolder | Purpose |
| :--- | :--- |
| `index.html` | Unified Visualization Launchpad Hub |
| `AMG757_Tarlatamab_V4_Evidence_Studio.html` | Canonical v4.3.2 AMG 757 Evidence & Basket Studio (5 tabs) |
| `AMG757_Tarlatamab_Indication_Expansion_Studio.html` | AMG 757 KG, Metapath & Single-Cell Explorer (17 tabs) |
| `AMG691_CD30_Combination_Discovery_Studio.html` | Bilingual AMG 691 Combination Discovery Studio (9 tabs) |
| `Full_Portfolio_47_Assets_Discovery_Portal.html` | 47-Asset Amgen Translational Discovery Portal |
| `OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck_{EN,ZH}.html` | Interactive presentation slide decks in English and Chinese |
| `Launch_Visualization_Windows.bat` / `Stop_Visualization_Windows.bat` | One-click Windows 11 start/stop scripts |
| `launch_visualization_linux.sh` / `stop_visualization_linux.sh` | One-click Linux start/stop scripts |
| `run_visualization_studio.py` | Cross-platform Python HTTP + KG API server |
| `d3.v7.min.js`, `studio_data.json`, `explorer_data/` | Local D3 v7 engine + 47-asset KG subgraphs & 2D t-SNE |
| `engine_data/` & `studio_engine/` | NumPy inference runtime & model definitions |
| `configs/` | YAML configurations for custom assets and targets |
| `demo_guides/` | English & Chinese step-by-step live demo playbooks |
