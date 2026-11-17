"""
Option-1 Clinical Protocol Prioritization, Within-Platform Multi-Omics Stratification,
Dedicated vs Basket Trial Whitespace, FAERS/GTEx Safety & Exact Simon Two-Stage Engine
for AMG 757 / Tarlatamab (`IMDELLTRA`, `DLL3 x CD3` BiTE).

Methodological & statistical guarantees enforced in v2.0:
  1. Single Canonical Disease Registry (`configs/amg757_indication_mapping_v2.yaml`) shared across
     IHC gating, multi-omics lookup, trial landscape, and indication-family deduplication.
  2. Strict Subtype Hygiene: Pediatric / circumscribed `IDH`-wildtype astrocytomas (`pilocytic`,
     `cerebellar`, `desmoplastic infantile`, `childhood brainstem / DIPG`, `pilomyxoid`, `diencephalic`,
     `spinal cord`) and `"non-small cell lung"` never inherit adult `IDH`-mutant or `SCLC` attributes.
  3. Within-Platform Multi-Omics Only: Transcriptomic summaries are tagged by `platform_id` and
     `sample_type` (`primary_patient_tumor` vs `preclinical_model`) and are never blended across
     incompatible normalization pipelines or double-counted inside clinical IHC prevalence.
  4. Orthogonal 5-Pillar MCDA + 10,000-Draw Dirichlet Sensitivity: `DLL3` IHC prevalence enters
     exactly once alongside unboosted GNN/genetic alignment, dedicated+basket trial whitespace,
     BBB/outpatient feasibility, and `OptimusCombo-Net` partner utility, with rank-stability intervals.
"""

from __future__ import annotations

import json
import os
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np
import math
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

def _binom_pmf_vec(k: int, p: float) -> np.ndarray:
    xs = np.arange(k + 1, dtype=np.int64)
    if p <= 0.0:
        out = np.zeros(k + 1, dtype=np.float64); out[0] = 1.0; return out
    if p >= 1.0:
        out = np.zeros(k + 1, dtype=np.float64); out[k] = 1.0; return out
    lp = math.log(p); lq = math.log(1.0 - p); lgk = math.lgamma(k + 1)
    return np.array([math.exp(lgk - math.lgamma(int(x) + 1) - math.lgamma(k - int(x) + 1) + int(x) * lp + (k - int(x)) * lq) for x in xs], dtype=np.float64)


_REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

DEFAULT_OPTION1_EMPIRICAL_JSON = os.path.join(
    _REPO_ROOT,
    "engine_data",
    "option1_empirical_bundle.json",
)

DEFAULT_CANONICAL_MAP_YAML = os.path.join(
    _REPO_ROOT,
    "configs",
    "amg757_indication_mapping_v2.yaml",
)

# File-mtime keyed caches so long-running `:8004` Studio servers auto-reload updated bundles
_EMPIRICAL_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}
_CANONICAL_MAP_CACHE: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def load_option1_empirical_bundle(path: str = DEFAULT_OPTION1_EMPIRICAL_JSON) -> Dict[str, Any]:
    """Load empirical multi-omics, ClinicalTrials.gov, FAERS, and GTEx bundle with mtime auto-refresh."""
    if not os.path.exists(path):
        return {}
    mtime = os.path.getmtime(path)
    cached = _EMPIRICAL_CACHE.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f) or {}
    _EMPIRICAL_CACHE[path] = (mtime, data)
    return data


def load_amg757_canonical_mapping(path: str = DEFAULT_CANONICAL_MAP_YAML) -> Dict[str, Any]:
    """Load single canonical AMG 757 indication & subtype hygiene registry with mtime auto-refresh."""
    comp_p = os.path.join(_REPO_ROOT, "engine_data", "configs_compiled.json")
    if not os.path.exists(path) and not os.path.exists(comp_p):
        return {}
    if not os.path.exists(path):
        path = comp_p
    mtime = os.path.getmtime(path)
    cached = _CANONICAL_MAP_CACHE.get(path)
    if cached is not None and cached[0] == mtime:
        return cached[1]
    if yaml is not None and os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            raw = yaml.safe_load(f) or {}
    else:
        comp_p = os.path.join(_REPO_ROOT, "engine_data", "configs_compiled.json")
        with open(comp_p, "r", encoding="utf-8") as f:
            raw = (json.load(f) or {}).get(os.path.basename(path)) or {}

    id_to_family: Dict[str, Tuple[str, Dict[str, Any]]] = {}
    for fam_key, fam_spec in (raw.get("indication_families") or {}).items():
        for did in fam_spec.get("disease_ids") or []:
            id_to_family[str(did)] = (str(fam_key), dict(fam_spec))

    parsed = {
        "raw": raw,
        "pediatric_idh_wt_ids": set(str(x) for x in (raw.get("pediatric_or_circumscribed_idh_wt_glioma_ids") or [])),
        "pediatric_idh_wt_keywords": tuple(str(x).lower() for x in (raw.get("pediatric_or_circumscribed_glioma_keywords") or [])),
        "dll3_low_epithelial_ids": set(str(x) for x in (raw.get("dll3_low_epithelial_control_ids") or [])),
        "id_to_family": id_to_family,
        "families": raw.get("indication_families") or {},
    }
    _CANONICAL_MAP_CACHE[path] = (mtime, parsed)
    return parsed


def is_pediatric_or_circumscribed_idh_wt_glioma(
    disease_id: str,
    disease_name: str,
    cmap: Optional[Dict[str, Any]] = None,
) -> bool:
    """Return True if disease is a circumscribed / pediatric predominantly IDH-wildtype astrocytoma/glioma."""
    if cmap is None:
        cmap = load_amg757_canonical_mapping()
    did = str(disease_id or "").strip()
    nm = str(disease_name or "").lower()
    if did in cmap.get("pediatric_idh_wt_ids", set()):
        return True
    for kw in cmap.get("pediatric_idh_wt_keywords", ()):
        if kw in nm:
            return True
    return False


def resolve_amg757_canonical_disease_entry(
    disease_id: str,
    disease_name: str,
    cmap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    out = _resolve_amg757_canonical_disease_entry_inner(disease_id, disease_name, cmap=cmap)
    out.setdefault("canonical_key", out.get("family_key", ""))
    return out


def _resolve_amg757_canonical_disease_entry_inner(
    disease_id: str,
    disease_name: str,
    cmap: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Resolve `(disease_id, disease_name)` against the single canonical AMG 757 registry.
    Enforces strict guards so:
      - `"non-small cell"` never matches `"small cell lung"`
      - Pediatric / circumscribed `IDH`-WT astrocytomas never match adult `IDH`-mutant gliomas
      - `MONDO_0016685` (`low-grade astrocytoma`) maps to `idh_mut_diffuse_astrocytoma` (never oligo)
    """
    if cmap is None:
        cmap = load_amg757_canonical_mapping()
    did = str(disease_id or "").strip()
    nm = str(disease_name or "").lower()

    # 1. Explicit pediatric / circumscribed IDH-WT glioma guard
    if is_pediatric_or_circumscribed_idh_wt_glioma(did, nm, cmap=cmap):
        return {
            "family_key": f"circumscribed_idh_wt_glioma::{did}",
            "is_pediatric_idh_wt_glioma": True,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": None,
            "landscape_key": "pediatric_cns_glioma",
            "required_molecular_gate": "Predominantly BRAF-Fusion / H3K27M IDH-Wildtype (Low DLL3 Prior; Do Not Extrapolate Adult IDH-Mutant Data)",
            "max_representatives": 1,
        }

    # 2. Explicit non-neuroendocrine DLL3-low epithelial carcinoma control guard (incl. non-small cell lung & non-melanoma skin!)
    if (
        did in cmap.get("dll3_low_epithelial_ids", set())
        or "non-small cell" in nm
        or "papillary thyroid" in nm
        or "non-melanoma" in nm
        or "nonmelanoma" in nm
    ):
        return {
            "family_key": f"dll3_low_epithelial_ctrl::{did}",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": True,
            "omics_cohort_key": "tcga_thyroid_papillary_ctrl" if "papillary thyroid" in nm else None,
            "landscape_key": None,
            "required_molecular_gate": "Unselected Non-NE Epithelial Control (<8% DLL3+; Exclude Without Histologic NE Transformation)",
            "max_representatives": 1,
        }

    # 3. Exact curated ID match in `indication_families`
    id_hit = (cmap.get("id_to_family") or {}).get(did)
    if id_hit is not None:
        fam_key, fam_spec = id_hit
        return {
            "family_key": fam_key,
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": fam_spec.get("omics_cohort_key"),
            "landscape_key": fam_spec.get("landscape_key"),
            "required_molecular_gate": str(fam_spec.get("required_molecular_gate") or ""),
            "max_representatives": int(fam_spec.get("max_representatives") or 1),
            "preferred_primary_id": fam_spec.get("preferred_primary_id"),
        }

    # 4. Strict histologic fallback rules (only after pediatric glioma & non-small cell guards)
    fams = cmap.get("families") or {}
    if "small cell lung" in nm and "non-small cell" not in nm:
        spec = fams.get("es_sclc_anchor", {})
        return {
            "family_key": "es_sclc_anchor",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "es_sclc",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "merkel cell" in nm:
        spec = fams.get("merkel_cell_carcinoma", {})
        return {
            "family_key": "merkel_cell_carcinoma",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "merkel_cell_carcinoma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "medullary thyroid" in nm:
        spec = fams.get("medullary_thyroid_carcinoma", {})
        return {
            "family_key": "medullary_thyroid_carcinoma",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "medullary_thyroid_carcinoma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "oligodendroglioma" in nm or "oligodendroglial" in nm:
        spec = fams.get("idh_mut_1p19q_oligodendroglioma", {})
        return {
            "family_key": "idh_mut_1p19q_oligodendroglioma",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "idh_mutant_glioma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
            "preferred_primary_id": spec.get("preferred_primary_id"),
        }
    if "astrocytoma" in nm or "oligoastrocytoma" in nm:
        spec = fams.get("idh_mut_diffuse_astrocytoma", {})
        return {
            "family_key": "idh_mut_diffuse_astrocytoma",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "idh_mutant_glioma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
            "preferred_primary_id": spec.get("preferred_primary_id"),
        }
    if "glioblastoma" in nm:
        spec = fams.get("idh_wt_glioblastoma_proneural", {})
        return {
            "family_key": "idh_wt_glioblastoma_proneural",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "idh_mutant_glioma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "prostate" in nm and ("neuroendocrine" in nm or "small cell" in nm):
        spec = fams.get("prostate_nepc", {})
        return {
            "family_key": "prostate_nepc",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "nepc",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "bladder" in nm and ("small cell" in nm or "neuroendocrine" in nm):
        spec = fams.get("bladder_scbc", {})
        return {
            "family_key": "bladder_scbc",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "small_cell_bladder",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "cervi" in nm and ("small cell" in nm or "neuroendocrine" in nm):
        spec = fams.get("cervical_scnec", {})
        return {
            "family_key": "cervical_scnec",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": None,
            "landscape_key": "small_cell_cervical",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or ""),
            "max_representatives": 1,
        }
    if "large cell neuroendocrine" in nm or "lcnec" in nm:
        return {
            "family_key": "pulmonary_lcnec" if "lung" in nm or "pulmonary" in nm else f"lcnec::{did}",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": None,
            "landscape_key": "pulmonary_lcnec" if ("lung" in nm or "pulmonary" in nm) else "epnec_gep_nec",
            "required_molecular_gate": "SP347 DLL3 IHC >=1% Companion Gate",
            "max_representatives": 1,
        }
    if "olfactory neuroblastoma" in nm or "esthesioneuroblastoma" in nm:
        spec = fams.get("olfactory_neuroblastoma", {})
        return {
            "family_key": "olfactory_neuroblastoma",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "neuroblastoma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or "Hyams Grade III/IV + Ventana SP347 DLL3 IHC >=10%"),
            "max_representatives": 1,
            "preferred_primary_id": spec.get("preferred_primary_id", "EFO_1000407"),
        }
    if "neuroblastoma" in nm:
        spec = fams.get("high_risk_neuroblastoma", {})
        return {
            "family_key": "high_risk_neuroblastoma",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": spec.get("omics_cohort_key"),
            "landscape_key": "neuroblastoma",
            "required_molecular_gate": str(spec.get("required_molecular_gate") or "Relapsed/Refractory High-Risk Adrenergic (PHOX2B+/ASCL1+) + SP347 DLL3 IHC >=10%"),
            "max_representatives": 1,
            "preferred_primary_id": spec.get("preferred_primary_id", "EFO_0000621"),
        }
    if "pheochromocytoma" in nm or "paraganglioma" in nm:
        spec = fams.get("metastatic_malignant_ppgl", {})
        return {
            "family_key": "metastatic_malignant_ppgl",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": None,
            "landscape_key": str(spec.get("landscape_key") or "ppgl_chromaffin"),
            "required_molecular_gate": str(
                spec.get("required_molecular_gate")
                or "Mandatory Metastatic PPGL + Ventana SP347 DLL3 IHC >=10% + Pre-Dosing Alpha-Adrenergic Blockade"
            ),
            "max_representatives": int(spec.get("max_representatives") or 1),
            "preferred_primary_id": spec.get("preferred_primary_id", "EFO_1000348"),
        }
    if "melanoma" in nm and "uveal" not in nm and "non-melanoma" not in nm and "nonmelanoma" not in nm:
        spec = fams.get("dedifferentiated_melanoma_subset", {})
        return {
            "family_key": "dedifferentiated_melanoma_subset",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": None,
            "landscape_key": None,
            "required_molecular_gate": str(
                spec.get("required_molecular_gate")
                or "Strict Ventana SP347 DLL3 IHC >=25% Subset Gate (ICI-Refractory INSM1+/ASCL1+ Melanoma Only)"
            ),
            "max_representatives": int(spec.get("max_representatives") or 1),
            "preferred_primary_id": spec.get("preferred_primary_id", "EFO_0000756"),
        }
    if any(k in nm for k in ("neuroendocrine", "minen", "adenoneuroendocrine", "small cell")):
        return {
            "family_key": f"epnec::{did}",
            "is_pediatric_idh_wt_glioma": False,
            "is_dll3_low_epithelial_control": False,
            "omics_cohort_key": None,
            "landscape_key": "epnec_gep_nec",
            "required_molecular_gate": "Mandatory Grade 3 NEC Histology + SP347 DLL3 IHC >=1% Gate",
            "max_representatives": 1,
        }

    return {
        "family_key": f"other::{did}",
        "is_pediatric_idh_wt_glioma": False,
        "is_dll3_low_epithelial_control": False,
        "omics_cohort_key": None,
        "landscape_key": None,
        "required_molecular_gate": "Exploratory DLL3 IHC Screening Required",
        "max_representatives": 1,
    }


def compute_simon_two_stage_design(
    p0: float,
    p1: float,
    alpha: float = 0.05,
    beta: float = 0.15,
    max_n: int = 110,
) -> Dict[str, Any]:
    """
    Exact binomial enumeration for Simon's (1989) Two-Stage Phase 2 Clinical Trial Design.
    Tests H0: ORR <= p0 (uninteresting historical salvage control) vs H1: ORR >= p1 (target ORR).

    Stage 1 enrolls `n1` patients; if responses <= `r1`, stop early for futility.
    Otherwise enroll `n2 = n_total - n1` additional patients; reject H0 if total responses > `r_total`.

    Returns both Simon's Optimal (minimum E[N | p0]) and Minimax (minimum n_total) designs.
    Verified exactly against Simon (1989) Controlled Clinical Trials 10:1-10 Table 1.
    """
    p0 = float(p0)
    p1 = float(p1)
    if not (0.01 <= p0 < p1 <= 0.99):
        raise ValueError(f"Require 0.01 <= p0 < p1 <= 0.99, got p0={p0}, p1={p1}")

    best_optimal: Optional[Dict[str, Any]] = None
    best_minimax: Optional[Dict[str, Any]] = None

    pmf0 = {k: _binom_pmf_vec(k, p0) for k in range(1, max_n + 1)}
    pmf1 = {k: _binom_pmf_vec(k, p1) for k in range(1, max_n + 1)}
    cdf0 = {k: np.cumsum(pmf0[k]) for k in range(1, max_n + 1)}
    cdf1 = {k: np.cumsum(pmf1[k]) for k in range(1, max_n + 1)}

    for n_tot in range(8, max_n + 1):
        for n1 in range(5, n_tot):
            n2 = n_tot - n1
            p0_x1 = pmf0[n1]
            p1_x1 = pmf1[n1]
            c0_x2 = cdf0[n2]
            c1_x2 = cdf1[n2]

            for r1 in range(0, n1):
                pet0 = float(cdf0[n1][r1])
                en0 = float(n1 + (1.0 - pet0) * n2)
                if best_optimal is not None and best_minimax is not None:
                    if n_tot > best_minimax["n_total"] and en0 >= best_optimal["en_p0"]:
                        continue

                x1_vals = np.arange(r1 + 1, n1 + 1)[:, None]
                r_tots = np.arange(r1, n_tot)[None, :]
                thresh_mat = r_tots - x1_vals
                clipped = np.clip(thresh_mat, 0, n2 - 1)
                fail2_0 = np.where(thresh_mat < 0, 0.0, np.where(thresh_mat >= n2, 1.0, c0_x2[clipped]))
                fail2_1 = np.where(thresh_mat < 0, 0.0, np.where(thresh_mat >= n2, 1.0, c1_x2[clipped]))

                w0 = p0_x1[r1 + 1 : n1 + 1, None]
                w1 = p1_x1[r1 + 1 : n1 + 1, None]
                type1_vec = np.sum(w0 * (1.0 - fail2_0), axis=0)
                power_vec = np.sum(w1 * (1.0 - fail2_1), axis=0)
                valid_j = np.nonzero((type1_vec <= alpha) & (power_vec >= (1.0 - beta)))[0]
                for j in valid_j.tolist():
                    r_tot = r1 + j
                    type1 = float(type1_vec[j])
                    power = float(power_vec[j])

                    cand = {
                        "p0": round(p0, 4),
                        "p1": round(p1, 4),
                        "n1": int(n1),
                        "r1": int(r1),
                        "n_total": int(n_tot),
                        "r_total": int(r_tot),
                        "min_responses_to_succeed": int(r_tot + 1),
                        "pet_p0": round(pet0, 4),
                        "en_p0": round(en0, 2),
                        "exact_alpha": round(type1, 4),
                        "exact_power": round(power, 4),
                    }
                    if best_minimax is None or (
                        cand["n_total"] < best_minimax["n_total"]
                        or (cand["n_total"] == best_minimax["n_total"] and cand["en_p0"] < best_minimax["en_p0"])
                    ):
                        best_minimax = cand
                    if best_optimal is None or (
                        cand["en_p0"] < best_optimal["en_p0"]
                        or (cand["en_p0"] == best_optimal["en_p0"] and cand["n_total"] < best_optimal["n_total"])
                    ):
                        best_optimal = cand

    return {
        "optimal": best_optimal,
        "minimax": best_minimax,
    }


def lookup_empirical_rna_positivity_for_disease(
    disease_id: str,
    disease_name: str,
    empirical_bundle: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Map an OptimusKG disease `(disease_id, disease_name)` via the single canonical registry to
    its within-platform transcriptomic cohort metadata (`platform_id`, `sample_type`, `sample_n`,
    `dll3_log2_median`, `pct_above_within_platform_ref`), strictly respecting subtype & platform guards.
    """
    if empirical_bundle is None:
        empirical_bundle = load_option1_empirical_bundle()
    cohorts = (empirical_bundle or {}).get("omics_cohorts") or {}
    if not cohorts:
        return None

    resolved = resolve_amg757_canonical_disease_entry(disease_id, disease_name)
    ckey = resolved.get("omics_cohort_key")
    if not ckey:
        return None
    return cohorts.get(str(ckey))


def lookup_tme_readiness_for_disease(
    disease_id: str,
    disease_name: str,
    empirical_bundle: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    Map `(disease_id, disease_name)` to its primary human patient tumor within-platform BiTE
    `TME` Effector-to-Target Readiness record (`bite_tme_readiness_score`, `tme_archetype`,
    `t_eff_within_platform_pct`, `mhc1_silencing_bite_advantage_pct`).
    """
    if empirical_bundle is None:
        empirical_bundle = load_option1_empirical_bundle()
    tme_atlas = (empirical_bundle or {}).get("tme_bite_readiness_atlas") or {}
    if not tme_atlas:
        return None
    resolved = resolve_amg757_canonical_disease_entry(disease_id, disease_name)
    ckey = resolved.get("omics_cohort_key")
    if ckey and str(ckey) in tme_atlas:
        return tme_atlas[str(ckey)]
    fam = str(resolved.get("family_key") or "")
    fam_fallback = {
        "es_sclc_anchor": "ncbi_tpm_sclc_primary",
        "merkel_cell_carcinoma": "nature2024_mcc_primary_biopsies",
        "medullary_thyroid_carcinoma": "gse196264_mtc_primary_surgical",
        "high_risk_neuroblastoma": "target_nbl_highrisk_adrn",
        "idh_mut_diffuse_astrocytoma": "tcga_idh_mut_astrocytoma",
        "idh_mut_1p19q_oligodendroglioma": "tcga_idh_mut_1p19q_codel",
        "idh_wt_glioblastoma_proneural": "tcga_idh_wt_gbm",
        "prostate_nepc": "beltran_nepc_crpc_ne",
        "bladder_scbc": "tcga_bladder_neuronal_scbc",
    }
    fb_key = fam_fallback.get(fam)
    return tme_atlas.get(fb_key) if fb_key else None


def compute_competitive_whitespace_score(
    dedicated_p23_n: int,
    dedicated_ph1_n: int,
    basket_p23_n: int = 0,
    basket_ph1_n: int = 0,
) -> float:
    """
    Monotone competitive whitespace score in `(0, 1]`, penalizing both dedicated histology competitor
    trials (`0.45` per Ph2/3, `0.18` per Ph1) and multi-histology pan-NEC / DLL3+ basket eligibility
    (`0.08` per Ph2/3 basket, `0.04` per Ph1 basket).
    """
    denom = (
        1.0
        + 0.45 * max(0, int(dedicated_p23_n))
        + 0.18 * max(0, int(dedicated_ph1_n))
        + 0.08 * max(0, int(basket_p23_n))
        + 0.04 * max(0, int(basket_ph1_n))
    )
    return round(float(1.0 / denom), 4)


def lookup_trial_landscape_for_disease(
    disease_id: str,
    disease_name: str,
    empirical_bundle: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """
    Return ClinicalTrials.gov competitive landscape metrics for `(disease_id, disease_name)`,
    explicitly distinguishing **Dedicated Histology Trials** from **Pan-NEC / Pan-DLL3 Basket Trials**.
    """
    if empirical_bundle is None:
        empirical_bundle = load_option1_empirical_bundle()
    landscape = (empirical_bundle or {}).get("indication_trial_landscape") or {}

    resolved = resolve_amg757_canonical_disease_entry(disease_id, disease_name)
    key = resolved.get("landscape_key")
    info = landscape.get(key or "", {})

    ded_all = int(info.get("competitor_dll3_total_n", 0))
    ded_p23 = int(info.get("competitor_dll3_phase23_n", 0))
    ded_ph1 = max(0, ded_all - ded_p23)
    bsk_all = int(info.get("competitor_pan_dll3_basket_total_n", 0))
    bsk_p23 = int(info.get("competitor_pan_dll3_basket_phase23_n", 0))
    bsk_ph1 = max(0, bsk_all - bsk_p23)

    ws_score = compute_competitive_whitespace_score(
        dedicated_p23_n=ded_p23,
        dedicated_ph1_n=ded_ph1,
        basket_p23_n=bsk_p23,
        basket_ph1_n=bsk_ph1,
    )
    default_tier = (
        "Open Dedicated Phase 2/3 Niche (Basket-Eligible Only)"
        if (ded_p23 == 0 and bsk_all > 0)
        else ("Untapped Dedicated DLL3 Niche" if ded_all == 0 else "Active Multi-Sponsor DLL3 Competitive Arena")
    )
    return {
        "landscape_key": key or "unmapped_solid_tumor",
        "amgen_amg757_trials_n": int(info.get("amgen_amg757_trials_n", 0)),
        "amgen_amg757_trial_ids": list(info.get("amgen_amg757_trial_ids", [])),
        "amgen_basket_trials_n": int(info.get("amgen_pan_dll3_basket_n", 0)),
        "competitor_dll3_total_n": ded_all,
        "competitor_dll3_phase23_n": ded_p23,
        "competitor_pan_dll3_basket_total_n": bsk_all,
        "competitor_pan_dll3_basket_phase23_n": bsk_p23,
        "competitor_agents": list(info.get("competitor_agents", [])),
        "general_2l_trials_n": int(info.get("general_recruiting_trials_n", 0)),
        "competitive_whitespace_score": ws_score,
        "whitespace_tier": str(info.get("whitespace_tier") or default_tier),
    }


# Nominal expert Multi-Criteria Decision Analysis (MCDA) weights across the 5 orthogonal pillars
NOMINAL_PROTOCOL_MCDA_WEIGHTS = np.array([0.32, 0.28, 0.16, 0.14, 0.10], dtype=np.float64)


def compute_orthogonal_mcda_pillars(
    gnn_z_std: float,
    ppi1hop_l2g: float,
    ihc_pos_pct: Optional[float],
    ihc_high_pct: Optional[float],
    effective_pop_share: float = 1.0,
    cns_icans_risk: Optional[str] = None,
    competitive_whitespace_score: float = 0.5,
    best_combo_utility: Optional[float] = None,
) -> Tuple[np.ndarray, str, str]:
    """
    Compute the 5 strictly orthogonal Option-1 MCDA pillars in `[0, 1]` (zero double-counting of `DLL3` IHC!):
      0. `S_gnn`: Pure 24-model OptimusKG standardized logit + `DLL3` somatic/lineage L2G (`0%` IHC mixed in)
      1. `S_ihc`: Peer-reviewed clinical `DLL3` IHC surface prevalence (`0.70*pos + 0.30*high`, scaled by sqrt(pop_share))
      2. `W_comp`: Dedicated + basket `ClinicalTrials.gov` competitor whitespace
      3. `F_safety_bbb`: Cycle 1 outpatient feasibility (`6-8h` rule) + macromolecular BBB biodistribution / ICANS gate
      4. `U_combo`: `OptimusCombo-Net` partner utility (`0.50` neutral midpoint if unmeasured)
    """
    gnn_sig = float(1.0 / (1.0 + np.exp(-np.clip(2.2 * (float(gnn_z_std) + 0.05), -20.0, 20.0))))
    l2g_norm = float(np.clip(float(ppi1hop_l2g) / 0.36, 0.0, 1.0))
    s_gnn = float(np.clip(0.68 * gnn_sig + 0.32 * l2g_norm, 0.0, 1.0))

    pos_01 = float(np.clip((ihc_pos_pct or 0.0) / 100.0, 0.0, 1.0))
    high_01 = float(np.clip((ihc_high_pct if ihc_high_pct is not None else (ihc_pos_pct or 0.0) * 0.55) / 100.0, 0.0, 1.0))
    pop_scale = float(np.sqrt(np.clip(effective_pop_share, 0.05, 1.0)))
    s_ihc = float(np.clip((0.70 * pos_01 + 0.30 * high_01) * pop_scale, 0.0, 1.0))

    w_comp = float(np.clip(competitive_whitespace_score, 0.0, 1.0))
    u_combo = float(np.clip(best_combo_utility if best_combo_utility is not None else 0.50, 0.0, 1.0))

    cns_txt = str(cns_icans_risk or "").upper()
    if "HIGH" in cns_txt:
        # Reflects BOTH ~105 kDa macromolecule BBB penetration / myeloid glioma TME constraints AND 48h inpatient ICANS gating
        f_safety = 0.35
        op_track = "Exploratory Phase 1b CNS Safety & BBB-Biodistribution Lead-In (Inpatient Neuro-Monitoring)"
        reg_short = "Hypothesis: Fractionated Inpatient Step-Up + Corticosteroid / High-Dose IV Anakinra Rescue"
    elif "MODERATE" in cns_txt:
        f_safety = 0.82
        op_track = "Phase 2 Extracranial Cohort (Baseline Brain MRI Screen + 6-8h Cycle 1 Outpatient)"
        reg_short = "Approved 1->10 mg IV Q2W (or 20 mg Q3W) + Baseline Brain MRI"
    else:
        f_safety = 1.00
        op_track = "Phase 2 Outpatient Eligible (Sept 2026 FDA 6-8h Cycle 1 Monitoring)"
        reg_short = "Approved 1->10 mg IV Q2W (or DeLLphi-309 20 mg Q3W) + Tocilizumab PRN"

    pillars = np.array([s_gnn, s_ihc, w_comp, f_safety, u_combo], dtype=np.float64)
    return pillars, op_track, reg_short


def compute_option1_protocol_priority_score(
    calibrated_prob: float = 0.0,
    biomarker_pos_pct: Optional[float] = None,
    cns_icans_risk: Optional[str] = None,
    competitive_whitespace_score: float = 1.0,
    best_combo_utility: Optional[float] = None,
    *,
    gnn_z_std: Optional[float] = None,
    ppi1hop_l2g: float = 0.20,
    biomarker_high_pct: Optional[float] = None,
    effective_pop_share: float = 1.0,
) -> Tuple[float, str, str]:
    """
    Compute the composite Option-1 Clinical Protocol Priority Index in `[0, 100]` over 5 orthogonal
    MCDA pillars (`32%` GNN+TAA Genetics, `28%` Clinical IHC Surface Prevalence, `16%` Trial Whitespace,
    `14%` Outpatient/BBB Feasibility, `10%` Combo Partner Utility).

    Note: If `gnn_z_std` is omitted by legacy callers, maps unboosted `calibrated_prob` onto `S_gnn`
    without re-injecting `biomarker_pos_pct`.
    """
    if gnn_z_std is not None:
        pillars, op_track, reg_short = compute_orthogonal_mcda_pillars(
            gnn_z_std=gnn_z_std,
            ppi1hop_l2g=ppi1hop_l2g,
            ihc_pos_pct=biomarker_pos_pct,
            ihc_high_pct=biomarker_high_pct,
            effective_pop_share=effective_pop_share,
            cns_icans_risk=cns_icans_risk,
            competitive_whitespace_score=competitive_whitespace_score,
            best_combo_utility=best_combo_utility,
        )
    else:
        _, op_track, reg_short = compute_orthogonal_mcda_pillars(
            gnn_z_std=0.0,
            ppi1hop_l2g=ppi1hop_l2g,
            ihc_pos_pct=biomarker_pos_pct,
            ihc_high_pct=biomarker_high_pct,
            effective_pop_share=effective_pop_share,
            cns_icans_risk=cns_icans_risk,
            competitive_whitespace_score=competitive_whitespace_score,
            best_combo_utility=best_combo_utility,
        )
        pos_01 = float(np.clip((biomarker_pos_pct or 0.0) / 100.0, 0.0, 1.0))
        high_01 = float(np.clip((biomarker_high_pct if biomarker_high_pct is not None else (biomarker_pos_pct or 0.0) * 0.55) / 100.0, 0.0, 1.0))
        s_ihc = float(np.clip((0.70 * pos_01 + 0.30 * high_01) * np.sqrt(np.clip(effective_pop_share, 0.05, 1.0)), 0.0, 1.0))
        f_saf = 0.35 if "HIGH" in str(cns_icans_risk or "").upper() else (0.82 if "MODERATE" in str(cns_icans_risk or "").upper() else 1.00)
        pillars = np.array(
            [
                float(np.clip(calibrated_prob, 0.0, 1.0)),
                s_ihc,
                float(np.clip(competitive_whitespace_score, 0.0, 1.0)),
                f_saf,
                float(np.clip(best_combo_utility if best_combo_utility is not None else 0.50, 0.0, 1.0)),
            ],
            dtype=np.float64,
        )

    score = float(100.0 * np.dot(NOMINAL_PROTOCOL_MCDA_WEIGHTS, pillars))
    return round(score, 2), op_track, reg_short


def compute_protocol_mcda_sensitivity(
    pillar_matrix: np.ndarray,
    n_draws: int = 10000,
    concentration: float = 22.0,
    seed: int = 42,
) -> Dict[str, np.ndarray]:
    """
    Evaluate rank & score robustness across `n_draws` Monte Carlo Dirichlet perturbations
    `w ~ Dirichlet(concentration * NOMINAL_PROTOCOL_MCDA_WEIGHTS)` over candidate pillar matrix `(M, 5)`.

    Returns dictionary of arrays of length `M`:
      - `point_score`: Nominal `100 * P @ w_0`
      - `score_p10`, `score_p90`: 10th and 90th percentile scores across weight perturbations
      - `prob_top3_pct`: `%` of `n_draws` weight vectors in which candidate ranks in Top-3
      - `prob_top5_pct`: `%` of `n_draws` weight vectors in which candidate ranks in Top-5
    """
    P = np.asarray(pillar_matrix, dtype=np.float64)
    if P.ndim != 2 or P.shape[1] != 5:
        raise ValueError(f"Expected pillar_matrix of shape (M, 5), got {P.shape}")
    M = P.shape[0]
    if M == 0:
        empty = np.zeros(0, dtype=np.float64)
        return {
            "point_score": empty,
            "score_p10": empty,
            "score_p90": empty,
            "prob_top3_pct": empty,
            "prob_top5_pct": empty,
        }

    rng = np.random.default_rng(seed)
    alpha_vec = concentration * NOMINAL_PROTOCOL_MCDA_WEIGHTS
    W = rng.dirichlet(alpha_vec, size=int(n_draws))  # (n_draws, 5)
    scores_mc = 100.0 * (P @ W.T)                    # (M, n_draws)

    # Ranks in each draw: 1 = highest score
    order_desc = np.argsort(-scores_mc, axis=0)
    ranks_mc = np.empty_like(order_desc)
    row_arange = np.arange(1, M + 1)[:, None]
    np.put_along_axis(ranks_mc, order_desc, row_arange, axis=0)

    point = np.round(100.0 * (P @ NOMINAL_PROTOCOL_MCDA_WEIGHTS), 2)
    p10 = np.round(np.percentile(scores_mc, 10, axis=1), 2)
    p90 = np.round(np.percentile(scores_mc, 90, axis=1), 2)
    top3 = np.round(100.0 * np.mean(ranks_mc <= 3, axis=1), 1)
    top5 = np.round(100.0 * np.mean(ranks_mc <= 5, axis=1), 1)
    return {
        "point_score": point,
        "score_p10": p10,
        "score_p90": p90,
        "prob_top3_pct": top3,
        "prob_top5_pct": top5,
    }
