"""
Bispecific T-Cell Engager (`BiTE`) Multiplicative `AND`-Gate Scoring, Congenital Germline `LoF`
Phenocopy Masking, and Pan-Cancer Surface Antigen (`DLL3`, `STEAP1`) Biomarker Conditioning.

Addresses four structural failure modes when scoring non-lymphoid `TAA x CD3` T-cell engagers
(such as `Tarlatamab [IMDELLTRA / AMG 757, DLL3 x CD3]` and `Xaluritamig [AMG 509, STEAP1 x CD3]`):
  1. **Additive `CD3` Lymphoid/Autoimmune Confounding**: Separates the universal T-cell effector arm
     (`CD3D`, `CD3E`, `CD3G`, `CD247`) from the Tumor-Associated Antigen (`TAA`) anchor (`DLL3`,
     `STEAP1`, etc.) so `CD3` `L2G=1.0` in B-cell lymphomas, `CD3`-SCID, and Type 1 Diabetes never
     hijacks `TAA`-negative diseases.
  2. **Congenital Germline `LoF` Phenocopy Traps**: Masks embryonic loss-of-function phenotypes of
     the target gene (e.g., *spondylocostal dysostosis* for `DLL3`, *SCID* for `CD3D/E/G`) that cannot
     be treated by a cytotoxic tumor-lysing T-cell engager.
  3. **Transcriptional Surface Overexpression vs. Germline GWAS Absence**: Replaces false zero-GWAS
     penalties when a surface `TAA` is transcriptionally driven onto tumor membranes (`ASCL1/INSM1/IDH1`
     -> `DLL3`; `AR/EWSR1-FLI1` -> `STEAP1`) and conditions therapeutic log-odds on published
     immunohistochemistry (`IHC`) `% biomarker-positive` patient prevalence.
  4. **CRS / ICANS & Blood-Brain-Barrier Clinical Guardrails**: Annotates every candidate indication
     with companion-diagnostic gating tiers, Cycle 1 `6-8h` outpatient vs. CNS/ICANS inpatient
     monitoring requirements, and rational combination archetypes.
"""

from __future__ import annotations

from dataclasses import dataclass
import os
import re
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

import numpy as np
import json
try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]


_STUDIO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DEFAULT_BITE_BIOMARKER_YAML = os.path.join(_STUDIO_ROOT, "configs", "bite_pan_cancer_biomarkers_v5.yaml")
_COMPILED_CFGS_JSON = os.path.join(_STUDIO_ROOT, "engine_data", "configs_compiled.json")

TCELL_EFFECTOR_GENES: Set[str] = {"CD3D", "CD3E", "CD3G", "CD247"}

# Hematologic / B-cell / plasma-cell / myeloid surface antigens where lymphoid/heme diseases ARE on-target
LYMPHOID_OR_HEME_TAAS: Set[str] = {
    "CD19",
    "MS4A1",
    "CD20",
    "CD22",
    "TNFRSF17",
    "BCMA",
    "GPRC5D",
    "FCRL5",
    "CD33",
    "IL3RA",
    "CD123",
    "CLEC12A",
    "FLT3",
    "CD38",
    "SLAMF7",
}

_CONGENITAL_LOF_RE = re.compile(
    r"(?:dysostosis|spondylocostal|spondylothoracic|congenital disorder of glycosylation|"
    r"severe combined immunodeficiency|combined immunodeficiency|agammaglobulinemia|"
    r"inborn error|malformation syndrome|segmentation defect|hypoplasia|agenesis|"
    r"immunodeficiency\b)",
    re.IGNORECASE,
)

# Confirmed lymphoid/myeloid hematologic malignancies where solid/neuroendocrine TAAs (DLL3, STEAP1) are absent
_HEME_MALIGNANCY_RE = re.compile(
    r"(?:\blymphoma\b|\bleukemia\b|\bleukaemia\b|\bmyeloma\b|\bplasmacytoma\b|"
    r"\bwaldenstrom|\bmyelodysplastic|\bmyeloproliferative|\blymphoblastic\b|"
    r"\blymphoproliferative\b|\bmacroglobulinemia\b|\bsezary\b|\bmycosis fungoides\b|"
    r"\bhodgkin\b)",
    re.IGNORECASE,
)

# Malignant / Locally Aggressive Solid & Neuroendocrine Neoplasm Gate for Cytotoxic Solid-Tumor BiTEs
_MALIGNANT_SOLID_OR_NE_TUMOR_RE = re.compile(
    r"(?:cancer|carcinoma|sarcoma|blastoma|glioma|astrocytoma|oligodendroglioma|"
    r"oligoastrocytoma|glioblastoma|pheochromocytoma|paraganglioma|melanoma|mesothelioma|"
    r"neuroendocrine|carcinoid|ependymoma|chordoma|seminoma|dysgerminoma|choriocarcinoma|"
    r"thymoma|teratoma|medulloblastoma|retinoblastoma|craniopharyngioma|schwannoma|meningioma|"
    r"malignant\s+.*(?:neoplasm|tumou?r))",
    re.IGNORECASE,
)

# Benign / non-malignant hyperplastic / anatomic lesions excluded from cytotoxic Boxed-Warning BiTE discovery
_BENIGN_OR_NONNEOPLASTIC_TRAP_RE = re.compile(
    r"(?:\bbenign\b|\bin\s+situ\b|\bintraepithelial\b|\bpolyp\b|\bcyst\b|\bhyperplasia\b|"
    r"\blipoma\b|\bhemangioma\b|\bleiomyoma\b|\bfibroma\b|\bpapilloma\b|"
    r"\bglaucoma\b|\btrachoma\b|\bhematoma\b|\bgranuloma\b|\bxanthoma\b|\bscotoma\b|\bcoma\b)",
    re.IGNORECASE,
)


@dataclass
class BiTEIndicationBiomarkerInfo:
    disease_id: str
    canonical_group: str
    taa_gene: str
    pos_pct: float
    high_pct: float
    biomarker_gate: str
    lineage_subtypes: str
    cns_icans_risk: str
    clinical_status: str
    evidence_citation: str
    expansion_tier: str
    source_type: str  # "curated_ihc_cohort" | "histologic_lineage_prior"
    effective_pop_share: float = 1.0


_CACHED_ATLAS_BY_PATH: Dict[str, Tuple[float, Dict[str, Any]]] = {}


def load_bite_biomarker_atlas(yaml_path: str = DEFAULT_BITE_BIOMARKER_YAML) -> Dict[str, Any]:
    if yaml is not None and os.path.exists(yaml_path):
        mtime = os.path.getmtime(yaml_path)
        cached = _CACHED_ATLAS_BY_PATH.get(yaml_path)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with open(yaml_path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        _CACHED_ATLAS_BY_PATH[yaml_path] = (mtime, data)
        return data
    if os.path.exists(_COMPILED_CFGS_JSON):
        mtime = os.path.getmtime(_COMPILED_CFGS_JSON)
        cached = _CACHED_ATLAS_BY_PATH.get(_COMPILED_CFGS_JSON)
        if cached is not None and cached[0] == mtime:
            return cached[1]
        with open(_COMPILED_CFGS_JSON, "r", encoding="utf-8") as f:
            all_c = json.load(f) or {}
        data = all_c.get(os.path.basename(yaml_path)) or {"bite_programs": {}, "crs_icans_management": {}}
        _CACHED_ATLAS_BY_PATH[_COMPILED_CFGS_JSON] = (mtime, data)
        return data
    return {"bite_programs": {}, "crs_icans_management": {}}


def extract_nonlymphoid_bite_taas(
    target_gene_symbols: Iterable[str],
    modality: str = "",
) -> List[str]:
    """
    Return ordered list of non-lymphoid Tumor-Associated Antigen (`TAA`) HGNC symbols if and only if
    the target profile represents a `TAA x CD3` T-cell engager (`BiTE`) targeting solid/neuroendocrine
    antigens rather than B/T/myeloid hematologic antigens.

    Returns `[]` for all standard small molecules, monospecific mAbs, ADCs, lymphoid BiTEs
    (e.g., `Blinatumomab [CD19 x CD3]`), and pure anti-CD3 mAbs (`Teplizumab`).
    """
    syms = [str(s).strip().upper() for s in target_gene_symbols if str(s).strip()]
    sym_set = set(syms)
    has_cd3 = bool(sym_set & TCELL_EFFECTOR_GENES)
    if not has_cd3:
        return []
    non_cd3 = [s for s in syms if s not in TCELL_EFFECTOR_GENES and not s.startswith(("FCGR", "C1Q"))]
    if not non_cd3:
        return []
    # If any primary TAA is a canonical lymphoid/heme BiTE antigen (e.g. CD19, CD20, BCMA), keep standard lymphoid behavior
    if any(s in LYMPHOID_OR_HEME_TAAS for s in non_cd3):
        return []
    # Preserve order without duplicates
    seen: Set[str] = set()
    out: List[str] = []
    for s in non_cd3:
        if s not in seen:
            seen.add(s)
            out.append(s)
    return out


def partition_bite_specs_for_projection_and_genetics(
    signed_target_specs: Sequence[Tuple[int, str, float]],
    gene_syms: Sequence[str],
    gene_sym2idx: Optional[Dict[str, int]] = None,
    atlas: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """
    If `signed_target_specs` represents a non-lymphoid `TAA x CD3` BiTE, return partitioned specs:
      - `taa_syms`: `List[str]` (e.g. `['DLL3']` or `['STEAP1']`)
      - `taa_g_indices`: `List[int]`
      - `lineage_g_weights`: `Dict[int, float]` (transcriptional regulators driving surface TAA)
      - `projection_specs`: `List[Tuple[int, str, float]]` (`TAA` at full weight, lineage regulators at
        gentle context weight, `CD3D/E/G` capped at `0.02` each so `CD3` never hijacks cold projection)
    Returns `None` for all non-BiTE or lymphoid-BiTE assets.
    """
    if not signed_target_specs:
        return None
    spec_syms = [
        str(gene_syms[gi]).upper()
        for gi, _, _ in signed_target_specs
        if 0 <= int(gi) < len(gene_syms)
    ]
    taa_syms = extract_nonlymphoid_bite_taas(spec_syms)
    if not taa_syms:
        return None

    if gene_sym2idx is None:
        gene_sym2idx = {str(s).upper(): i for i, s in enumerate(gene_syms) if s}
    if atlas is None:
        atlas = load_bite_biomarker_atlas()

    programs = atlas.get("bite_programs", {})
    proj_specs: List[Tuple[int, str, float]] = []
    taa_g_indices: List[int] = []
    seen_proj_g: Set[int] = set()

    for gi, srel, wt in signed_target_specs:
        gsym = str(gene_syms[int(gi)]).upper()
        if gsym in TCELL_EFFECTOR_GENES:
            # Cap universal CD3 effector arm at 0.02 per subunit so T-cell synapse is represented
            # without pulling embedding into B-ALL / DLBCL / SCID / T1D
            proj_specs.append((int(gi), str(srel), 0.02))
            seen_proj_g.add(int(gi))
        else:
            proj_specs.append((int(gi), str(srel), max(1.0, float(wt))))
            taa_g_indices.append(int(gi))
            seen_proj_g.add(int(gi))

    lineage_g_weights: Dict[int, float] = {}
    for taa in taa_syms:
        prog = programs.get(taa, {})
        for l_sym, l_wt in (prog.get("lineage_transcription_genes") or {}).items():
            l_gi = gene_sym2idx.get(str(l_sym).upper())
            if l_gi is not None:
                lineage_g_weights[int(l_gi)] = max(lineage_g_weights.get(int(l_gi), 0.0), float(l_wt))
                if int(l_gi) not in seen_proj_g:
                    # Include top core transcriptional surface drivers (e.g. ASCL1, INSM1) lightly in manifold projection
                    if float(l_wt) >= 0.24:
                        proj_specs.append((int(l_gi), "drug_binds_protein", float(l_wt) * 0.55))
                        seen_proj_g.add(int(l_gi))

    return {
        "taa_syms": taa_syms,
        "taa_g_indices": taa_g_indices,
        "lineage_g_weights": lineage_g_weights,
        "projection_specs": proj_specs,
    }


def build_bite_solid_tumor_exclusion_mask(
    dis_ids: Sequence[str],
    dis_names: Sequence[str],
    taa_syms: Sequence[str],
    keep_known_indices: Optional[Set[int]] = None,
) -> np.ndarray:
    """
    Build boolean mask `(D,)` of diseases excluded for a cytotoxic non-lymphoid solid/neuroendocrine
    `BiTE` (`DLL3 x CD3`, `STEAP1 x CD3`, etc.):
      1. Congenital germline `LoF` developmental/immunodeficiency phenocopies (*spondylocostal dysostosis*, *SCID*).
      2. Confirmed `TAA`-negative lymphoid/myeloid hematologic malignancies (*DLBCL*, *ALL*, *MM*, *AML*).
      3. Non-neoplastic / benign hyperplastic / autoimmune conditions inappropriate for a CRS/ICANS
         Boxed-Warning tumor-lysing T-cell engager.
    """
    D_cnt = len(dis_names)
    excl = np.zeros(D_cnt, dtype=bool)
    keep_set = keep_known_indices or set()

    for di in range(D_cnt):
        if di in keep_set:
            continue
        nm = str(dis_names[di] or "").strip()
        if not nm:
            excl[di] = True
            continue
        if _CONGENITAL_LOF_RE.search(nm):
            excl[di] = True
            continue
        if _HEME_MALIGNANCY_RE.search(nm):
            excl[di] = True
            continue
        if _BENIGN_OR_NONNEOPLASTIC_TRAP_RE.search(nm):
            excl[di] = True
            continue
        if not _MALIGNANT_SOLID_OR_NE_TUMOR_RE.search(nm):
            excl[di] = True

    return excl


def lookup_or_infer_bite_biomarker_map(
    dis_ids: Sequence[str],
    dis_names: Sequence[str],
    primary_taa: str,
    atlas: Optional[Dict[str, Any]] = None,
) -> Dict[int, BiTEIndicationBiomarkerInfo]:
    """
    Map OptimusKG disease indices to curated pan-cancer IHC prevalence & clinical gating metadata
    (plus principled histologic lineage priors for rare organ-specific small-cell / large-cell NECs).
    """
    if atlas is None:
        atlas = load_bite_biomarker_atlas()
    taa = str(primary_taa).upper()
    prog = (atlas.get("bite_programs") or {}).get(taa, {})
    out: Dict[int, BiTEIndicationBiomarkerInfo] = {}

    dis_id2idx = {str(did): i for i, did in enumerate(dis_ids)}

    # 1. Exact curated literature IHC cohorts from YAML
    for entry in prog.get("pan_cancer_indications") or []:
        for did in entry.get("disease_ids") or []:
            di = dis_id2idx.get(str(did))
            if di is not None:
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=str(did),
                    canonical_group=str(entry["canonical_label"]),
                    taa_gene=taa,
                    pos_pct=float(entry["dll3_pos_pct"]),
                    high_pct=float(entry["dll3_high_pct"]),
                    biomarker_gate=str(entry["biomarker_gate"]),
                    lineage_subtypes=str(entry["lineage_subtypes"]),
                    cns_icans_risk=str(entry["cns_icans_risk"]),
                    clinical_status=str(entry["clinical_status"]),
                    evidence_citation=str(entry["evidence_citation"]),
                    expansion_tier=str(entry["expansion_tier"]),
                    source_type="curated_ihc_cohort",
                    effective_pop_share=float(entry.get("effective_population_share", 1.0)),
                )

    # 2. Histologic lineage priors & explicit subtype hygiene guardrails for unmapped nodes
    if taa == "DLL3":
        from .option1_protocol_and_omics import (
            load_amg757_canonical_mapping,
            resolve_amg757_canonical_disease_entry,
        )

        cmap = load_amg757_canonical_mapping()
        for di, raw_nm in enumerate(dis_names):
            if di in out:
                continue
            nm = str(raw_nm or "").lower()
            did = str(dis_ids[di])
            resolved = resolve_amg757_canonical_disease_entry(did, nm, cmap=cmap)

            # Guard A: Pediatric / circumscribed IDH-wildtype astrocytomas (pilocytic, cerebellar, DIPG, etc.)
            if resolved.get("is_pediatric_idh_wt_glioma"):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Circumscribed / Pediatric Predominantly IDH-Wildtype Glioma (Low DLL3 Guardrail)",
                    taa_gene="DLL3",
                    pos_pct=9.0,
                    high_pct=2.0,
                    biomarker_gate="DO NOT EXTRAPOLATE ADULT IDH-MUTANT DATA (BRAF-fusion / H3K27M IDH-WT pediatric gliomas lack G-CIMP DLL3 overexpression)",
                    lineage_subtypes="Circumscribed BRAF-KIAA1549 / H3K27M IDH-wildtype astrocytic lineage",
                    cns_icans_risk="HIGH CNS/ICANS ALERT (Pediatric CNS neurotoxicity & BBB macromolecule barrier)",
                    clinical_status="Negative Subtype Guardrail (Excluded from IDH-Mutant Glioma Cohort)",
                    evidence_citation="WHO CNS5 Molecular Classification; Spino et al. Clin Cancer Res 2019 (IDH-WT specificity)",
                    expansion_tier="Biomarker Guardrail (Low Prevalence)",
                    source_type="histologic_lineage_prior",
                )
                continue

            # Guard B: Non-neuroendocrine epithelial carcinomas (untransformed NSCLC, papillary thyroid, squamous, RCC)
            if resolved.get("is_dll3_low_epithelial_control"):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Non-Neuroendocrine Epithelial Carcinoma (Low DLL3 Negative Control)",
                    taa_gene="DLL3",
                    pos_pct=4.5,
                    high_pct=1.0,
                    biomarker_gate="DO NOT ADVANCE UNSELECTED (<5% DLL3+ without biopsy-proven neuroendocrine transformation)",
                    lineage_subtypes="Non-neuroendocrine epithelial lineage (ASCL1/INSM1-negative)",
                    cns_icans_risk="Standard Systemic",
                    clinical_status="Negative Biomarker Control",
                    evidence_citation="TCGA PanCanAtlas & Clinical IHC Epithelial Controls (<5% DLL3+)",
                    expansion_tier="Biomarker Guardrail (Low Prevalence)",
                    source_type="histologic_lineage_prior",
                )
                continue

            # Guard C: Well-differentiated G1/G2 carcinoid/NET guardrail (~5.1% DLL3+)
            if (
                (
                    any(k in nm for k in ("grade 1", "grade 1/2", " g1", " g2", "well differentiated", "gastrin-producing", "vip-producing", "insulinoma", "glucagonoma"))
                    and "neuroendocrine" in nm
                )
                or (
                    "carcinoid" in nm
                    and not any(k in nm for k in ("atypical", "small cell", "large cell", "high-grade", "high grade", "poorly differentiated"))
                )
            ):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Well-Differentiated Low/Intermediate-Grade NET (Low DLL3 Guardrail)",
                    taa_gene="DLL3",
                    pos_pct=5.5,
                    high_pct=1.5,
                    biomarker_gate="DO NOT ADVANCE UNSELECTED (~5% DLL3+ in G1/G2 Carcinoid/NET; SSTR2 lineage)",
                    lineage_subtypes="Well-differentiated RB1/TP53-intact NET",
                    cns_icans_risk="Standard Systemic",
                    clinical_status="Negative Biomarker Guardrail (Require G3 Transformation + IHC)",
                    evidence_citation="Pan-NET IHC Cohort Prior (~5.1% DLL3+ in G1/G2 NET)",
                    expansion_tier="Biomarker Guardrail (Low Prevalence)",
                    source_type="histologic_lineage_prior",
                )
            elif "merkel cell" in nm:
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Merkel Cell Carcinoma (Cutaneous Neuroendocrine)",
                    taa_gene="DLL3",
                    pos_pct=89.0,
                    high_pct=52.0,
                    biomarker_gate="Broad High-Prevalence (~89% DLL3+ in MCPyV+ & UV-driven MCC)",
                    lineage_subtypes="ATOH1/SOX2/INSM1 cutaneous neuroendocrine carcinoma",
                    cns_icans_risk="Standard Systemic (6-8h Cycle 1 Outpatient Eligible)",
                    clinical_status="High-Priority Expansion Candidate (+Anti-PD-1 Combination Hypothesis)",
                    evidence_citation="Xie et al. Modern Pathology 2020 (89% DLL3+ in MCC)",
                    expansion_tier="Tier 1 High-Confidence Expansion",
                    source_type="curated_ihc_cohort",
                )
            elif resolved.get("family_key") in ("idh_mut_diffuse_astrocytoma", "idh_mut_1p19q_oligodendroglioma"):
                # Adult diffuse astrocytoma / oligodendroglioma terms (weighted by ~75% IDH-mutant share when term is not already IDH-restricted)
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Adult Diffuse / Anaplastic Glioma (IDH1/2-Mutant Molecular Gate Required)",
                    taa_gene="DLL3",
                    pos_pct=86.0,
                    high_pct=62.0,
                    biomarker_gate="MANDATORY Somatic IDH1/2 Mutation + DLL3 IHC >=25% (~86% DLL3+ in IDH-mutant gliomas)",
                    lineage_subtypes="IDH1/2 2-HG G-CIMP CTCF insulator hypermethylation associated with constitutive DLL3 expression",
                    cns_icans_risk="HIGH CNS/ICANS ALERT (Intracranial BBB biodistribution barrier + inpatient neuro-monitoring required)",
                    clinical_status="Exploratory CNS Biomarker Hypothesis (Requires BBB & Neuro-Safety Lead-In)",
                    evidence_citation="Flavahan et al. Nature 2016; Spino et al. Clin Cancer Res 2019",
                    expansion_tier="Tier 2 Molecularly Gated CNS Hypothesis",
                    source_type="curated_ihc_cohort",
                    effective_pop_share=0.75,
                )
            elif "small cell" in nm and ("carcinoma" in nm or "cancer" in nm):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Extrapulmonary Small Cell Neuroendocrine Carcinoma (EPSCC)",
                    taa_gene="DLL3",
                    pos_pct=72.0,
                    high_pct=42.0,
                    biomarker_gate="High-Prevalence EPSCC (~68-80% DLL3+); Confirm via DLL3 IHC >=1%",
                    lineage_subtypes="RB1/TP53-inactivated ASCL1/INSM1+ extrapulmonary small-cell lineage",
                    cns_icans_risk="Standard Systemic (6-8h Cycle 1 Outpatient Eligible)",
                    clinical_status="Eligible for NCT06788938 DLL3+ EPNEC Basket",
                    evidence_citation="Extrapulmonary Small-Cell Carcinoma IHC Lineage Prior (68-81% DLL3+)",
                    expansion_tier="Tier 1/2 Orphan EPNEC Basket",
                    source_type="histologic_lineage_prior",
                )
            elif "large cell neuroendocrine" in nm or "large-cell neuroendocrine" in nm or "neuroendocrine carcinoma" in nm:
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Extrapulmonary High-Grade Neuroendocrine Carcinoma (EPNEC)",
                    taa_gene="DLL3",
                    pos_pct=50.0,
                    high_pct=28.0,
                    biomarker_gate="Mandatory DLL3 IHC >=1% Companion Gate (~44-60% DLL3+ in high-grade NEC)",
                    lineage_subtypes="High-grade poorly differentiated neuroendocrine carcinoma",
                    cns_icans_risk="Standard Systemic",
                    clinical_status="Eligible for NCT06788938 DLL3+ EPNEC Basket",
                    evidence_citation="Pan-EPNEC High-Grade IHC Prior",
                    expansion_tier="Tier 2 Companion-Diagnostic Expansion",
                    source_type="histologic_lineage_prior",
                )
            elif any(k in nm for k in ("pheochromocytoma", "paraganglioma", "medulloblastoma", "retinoblastoma")):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group=(
                        "Metastatic / Malignant Pheochromocytoma & Sympathetic Paraganglioma (PPGL)"
                        if any(k in nm for k in ("pheochromocytoma", "paraganglioma"))
                        else "Embryonal Neuroectodermal CNS/Retinal Neoplasm"
                    ),
                    taa_gene="DLL3",
                    pos_pct=36.0,
                    high_pct=18.0,
                    biomarker_gate=(
                        "Mandatory Metastatic PPGL + Ventana SP347 DLL3 IHC >=10% + Pre-Dosing Alpha-Adrenergic Blockade"
                        if any(k in nm for k in ("pheochromocytoma", "paraganglioma"))
                        else "Exploratory Ventana SP347 DLL3 IHC >=10% Biomarker Gate (~30-45% neural-crest/embryonal expression)"
                    ),
                    lineage_subtypes="Neural-crest / neuroectodermal ASCL1/INSM1 developmental program",
                    cns_icans_risk=(
                        "HIGH CNS/ICANS ALERT (Intracranial/intraocular embryonal tumor; strict BBB neurotoxicity gating)"
                        if any(k in nm for k in ("medulloblastoma", "retinoblastoma"))
                        else "Moderate (Mandatory alpha-adrenergic blockade & inpatient Cycle 1 hemodynamic monitoring for CRS catecholamine surge)"
                    ),
                    clinical_status="Exploratory Translational Hypothesis",
                    evidence_citation="Neuroectodermal / Chromaffin Neural-Crest Surfaceome Expression Prior",
                    expansion_tier="Tier 3 Exploratory Biomarker Subset",
                    source_type="histologic_lineage_prior",
                )
            elif "melanoma" in nm and "uveal" not in nm and "non-melanoma" not in nm and "nonmelanoma" not in nm:
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Neuroendocrine-Transdifferentiated / Dedifferentiated Melanoma Subset",
                    taa_gene="DLL3",
                    pos_pct=24.0,
                    high_pct=10.0,
                    biomarker_gate="Strict Ventana SP347 DLL3 IHC >=25% Subset Gate (ICI-resistant neural-crest/INSM1+ melanoma subset only)",
                    lineage_subtypes="Neural-crest INSM1/ASCL1-reactivated melanoma subset",
                    cns_icans_risk="Moderate (Screen CNS metastases)",
                    clinical_status="Exploratory Biomarker-Selected Subset",
                    evidence_citation="TCGA / Caris Neural-Crest Melanoma DLL3 Subset (~20-30%)",
                    expansion_tier="Tier 3 Exploratory Biomarker Subset",
                    source_type="histologic_lineage_prior",
                )
            elif (
                any(
                    k in nm
                    for k in (
                        "squamous cell carcinoma",
                        "basal cell carcinoma",
                        "hepatocellular carcinoma",
                        "renal cell carcinoma",
                        "urothelial",
                        "gastric adenocarcinoma",
                        "breast carcinoma",
                        "endometrial carcinoma",
                        "uterine corpus cancer",
                        "urinary bladder cancer",
                        "ovarian cancer",
                    )
                )
                and not any(k in nm for k in ("small cell", "neuroendocrine", "merkel"))
            ):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Non-Neuroendocrine Epithelial Carcinoma (Low DLL3 Negative Control)",
                    taa_gene="DLL3",
                    pos_pct=4.5,
                    high_pct=1.0,
                    biomarker_gate="DO NOT ADVANCE UNSELECTED (<5% DLL3+ without biopsy-proven neuroendocrine transformation)",
                    lineage_subtypes="Non-neuroendocrine epithelial lineage (ASCL1/INSM1-negative)",
                    cns_icans_risk="Standard Systemic",
                    clinical_status="Negative Biomarker Control",
                    evidence_citation="TCGA PanCanAtlas & Clinical IHC Epithelial Controls (<5% DLL3+)",
                    expansion_tier="Biomarker Guardrail (Low Prevalence)",
                    source_type="histologic_lineage_prior",
                )

    elif taa == "STEAP1":
        for di, raw_nm in enumerate(dis_names):
            if di in out:
                continue
            nm = str(raw_nm or "").lower()
            did = str(dis_ids[di])
            if "ewing" in nm or "primitive neuroectodermal" in nm:
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Ewing Sarcoma Family Tumor (EWSR1-FLI1 Driven)",
                    taa_gene="STEAP1",
                    pos_pct=63.0,
                    high_pct=48.0,
                    biomarker_gate="High-Density STEAP1 IHC Gate (~63% high STEAP1 via EWSR1-FLI1)",
                    lineage_subtypes="EWSR1-FLI1 fusion sarcoma",
                    cns_icans_risk="Standard Systemic",
                    clinical_status="High-Priority Pediatric/AYA Expansion",
                    evidence_citation="Grunewald et al. / Nolan-Stevaux et al. (63% STEAP1+)",
                    expansion_tier="Tier 1 Fusion-Driven Expansion",
                    source_type="histologic_lineage_prior",
                )
            elif (
                "prostate" in nm
                and "small cell" not in nm
                and "neuroendocrine" not in nm
                and "rhabdomyosarcoma" not in nm
                and ("carcinoma" in nm or "cancer" in nm or "adenocarcinoma" in nm)
            ):
                out[di] = BiTEIndicationBiomarkerInfo(
                    disease_id=did,
                    canonical_group="Prostate Adenocarcinoma / mCRPC",
                    taa_gene="STEAP1",
                    pos_pct=84.0,
                    high_pct=68.0,
                    biomarker_gate="Broad High-Density Avidity Gate (80-89% STEAP1+ in prostate cancer)",
                    lineage_subtypes="AR-driven luminal prostate carcinoma",
                    cns_icans_risk="Standard Systemic",
                    clinical_status="Lead Registrational Franchise (AMG 509)",
                    evidence_citation="Kelly et al. Cancer Discov 2024",
                    expansion_tier="Lead Phase 3 Anchor",
                    source_type="histologic_lineage_prior",
                )

    return out


def compute_bite_taa_genetics_and_conditioned_scores(
    base_X_d: np.ndarray,
    z_row: np.ndarray,
    repurpose_ranker: Any,
    drug_train_ind_deg: int,
    bite_part: Dict[str, Any],
    dis_ids: Sequence[str],
    dis_names: Sequence[str],
    dg_d: np.ndarray,
    dg_g: np.ndarray,
    dg_w: np.ndarray,
    ppi_neighbors_by_gene: Dict[int, List[int]],
    return_unboosted: bool = False,
) -> Any:
    """
    Compute BiTE `AND`-gate feature matrix `X_bite (D, 8)` and biomarker-conditioned `scores_d (D,)`:
      1. `X_bite[:, 3]` (`direct_l2g`) is computed strictly from `taa_g_indices` (excluding `CD3D/E/G`!).
      2. `X_bite[:, 4]` (`ppi1hop_l2g`) is computed from `taa_g_indices` 1-hop PPI + weighted transcriptional
         lineage regulators (`ASCL1`, `INSM1`, `IDH1`, etc.), excluding `CD3D/E/G`!
      3. Rescues the `-1.35` germline-GWAS absence penalty when surface expression / lineage transcription
         supports `TAA` presence (`pos_pct >= 20%`), and modulates log-odds by a smooth `AND`-gate between
         24-model GNN manifold alignment (`sigmoid(2.0 * z_row)`) and `P(TAA+ | d)`.
      4. Attenuates confirmed low-prevalence traps (`pos_pct < 12%`, e.g., G1/G2 well-diff NETs at `5.1%`).
    """
    D_cnt = len(dis_ids)
    X_bite = base_X_d.copy()

    taa_g_arr = np.array(bite_part["taa_g_indices"], dtype=np.int32)
    if len(taa_g_arr) > 0 and len(dg_g) > 0:
        dir_m = np.isin(dg_g, taa_g_arr)
        dir_sum = (
            np.bincount(dg_d[dir_m], weights=dg_w[dir_m], minlength=D_cnt).astype(np.float32)
            if np.any(dir_m)
            else np.zeros(D_cnt, dtype=np.float32)
        )
    else:
        dir_sum = np.zeros(D_cnt, dtype=np.float32)

    # 1-hop PPI around TAA + transcriptional lineage drivers (never CD3!)
    n1_weights: Dict[int, float] = {}
    taa_set = set(int(x) for x in taa_g_arr.tolist())
    for tg in taa_set:
        for nb in ppi_neighbors_by_gene.get(tg, [])[:40]:
            if int(nb) not in taa_set:
                n1_weights[int(nb)] = max(n1_weights.get(int(nb), 0.0), 0.30)
    for lg, lw in (bite_part.get("lineage_g_weights") or {}).items():
        if int(lg) not in taa_set:
            n1_weights[int(lg)] = max(n1_weights.get(int(lg), 0.0), float(lw))

    ppi_sum = dir_sum.copy()
    if n1_weights and len(dg_g) > 0:
        n1_keys = np.array(list(n1_weights.keys()), dtype=np.int32)
        n1_m = np.isin(dg_g, n1_keys)
        if np.any(n1_m):
            w_lookup = np.array([n1_weights.get(int(g), 0.0) for g in dg_g[n1_m]], dtype=np.float32)
            ppi_sum += np.bincount(
                dg_d[n1_m],
                weights=dg_w[n1_m] * w_lookup,
                minlength=D_cnt,
            ).astype(np.float32)

    X_bite[:, 3] = np.minimum(1.0, dir_sum)
    X_bite[:, 4] = np.log1p(ppi_sum)

    primary_taa = bite_part["taa_syms"][0]
    bmap = lookup_or_infer_bite_biomarker_map(dis_ids, dis_names, primary_taa)

    # Base ranker score with clean TAA-only genetics (exchangeability-preserving scale for conformal calibration)
    scores_d = repurpose_ranker.score(
        X_bite,
        has_defined_targets=True,
        drug_train_ind_deg=int(drug_train_ind_deg),
    ).astype(np.float32)

    # Vectorized surface biomarker & GNN multiplicative AND-gate prioritization score.
    # Strictly uses peer-reviewed clinical IHC prevalence (`binfo.pos_pct`), never mixing cross-platform
    # or preclinical cell-line RNA-seq thresholds into `pos_pct_vec`!
    pos_pct_vec = np.zeros(D_cnt, dtype=np.float32)
    high_pct_vec = np.zeros(D_cnt, dtype=np.float32)
    eff_share_vec = np.ones(D_cnt, dtype=np.float32)
    has_bmap = np.zeros(D_cnt, dtype=bool)
    for di, binfo in bmap.items():
        pos_pct_vec[di] = float(binfo.pos_pct)
        high_pct_vec[di] = float(binfo.high_pct)
        eff_share_vec[di] = float(binfo.effective_pop_share)
        has_bmap[di] = True

    # Smooth GNN manifold alignment gate in [0, 1]: high only when 24-model GNN agrees!
    gnn_gate = (1.0 / (1.0 + np.exp(-np.clip(2.2 * (z_row - 0.15), -20.0, 20.0)))).astype(np.float32)
    # Weight by sqrt(effective_pop_share) so transformation subsets (e.g. t-SCLC within EGFR+ LUAD) stay prioritized
    # without crowding out pure primary neuroendocrine carcinomas (Merkel cell, MTC, NEPC, SCBC, SCNEC)
    sub_scale = np.sqrt(np.clip(eff_share_vec, 0.05, 1.0)).astype(np.float32)
    prev_01 = np.clip(pos_pct_vec / 100.0, 0.0, 1.0) * sub_scale
    high_01 = np.clip(high_pct_vec / 100.0, 0.0, 1.0) * sub_scale

    # Rescue the -1.35 germline-GWAS absence penalty when surface IHC prevalence >= 20% AND GNN z > 0
    was_zero_l2g_penalized = (int(drug_train_ind_deg) <= 2) & (X_bite[:, 3] < 0.01) & (X_bite[:, 4] < 0.05)
    rescue_term = np.where(
        was_zero_l2g_penalized & (pos_pct_vec >= 20.0),
        1.35 * np.minimum(1.0, prev_01 / 0.65) * gnn_gate,
        0.0,
    ).astype(np.float32)

    # Multiplicative AND-gate prioritization term (used for ordering only; never passed into conformal calibrator!)
    and_gate_boost = (1.65 * prev_01 + 0.55 * high_01) * gnn_gate

    # Explicit negative biomarker guardrail for confirmed low-expression histologies (<12% DLL3+, e.g. G1/G2 NET, pediatric IDH-WT glioma, non-NE epithelial)
    low_prev_guard = np.where(has_bmap & (pos_pct_vec < 12.0), -1.75, 0.0).astype(np.float32)

    scores_conditioned = (scores_d + rescue_term + and_gate_boost + low_prev_guard).astype(np.float32)
    if return_unboosted:
        return X_bite, scores_conditioned, bmap, scores_d
    return X_bite, scores_conditioned, bmap


def deduplicate_bite_indication_families(
    ordered_d_idxs: Iterable[int],
    dis_ids: Sequence[str],
    dis_names: Sequence[str],
    primary_taa: str,
    max_keep: int = 50,
) -> List[int]:
    """
    Collapse redundant ontology sibling terms within canonical clinical indication families
    (e.g., collapsing 7 diffuse astrocytoma nodes into `EFO_0002499` `anaplastic astrocytoma` and
    collapsing oligodendroglioma nodes into `EFO_0002501` `anaplastic oligodendroglioma`) so
    granular ontology synonyms never flood Top-20 expansion rankings.
    """
    if str(primary_taa).upper() != "DLL3":
        return list(ordered_d_idxs)[:max_keep]

    from .option1_protocol_and_omics import (
        load_amg757_canonical_mapping,
        resolve_amg757_canonical_disease_entry,
    )

    cmap = load_amg757_canonical_mapping()
    ordered_list = [int(d) for d in ordered_d_idxs]

    # When a family specifies a `preferred_primary_id` (e.g. `EFO_0002499` over generic `astrocytoma`),
    # promote that canonical ontology representative if it appears among the family's candidates.
    cand_by_did = {str(dis_ids[d]): d for d in ordered_list}
    fam_counts: Dict[str, int] = {}
    kept: List[int] = []
    used_d: Set[int] = set()

    for di in ordered_list:
        if di in used_d:
            continue
        did = str(dis_ids[di])
        nm = str(dis_names[di])
        res = resolve_amg757_canonical_disease_entry(did, nm, cmap=cmap)
        fkey = str(res.get("family_key") or f"other::{did}")
        max_rep = int(res.get("max_representatives") or 1)
        if fam_counts.get(fkey, 0) >= max_rep:
            continue

        chosen_di = di
        pref_id = res.get("preferred_primary_id")
        if pref_id and str(pref_id) in cand_by_did and cand_by_did[str(pref_id)] not in used_d:
            chosen_di = cand_by_did[str(pref_id)]

        kept.append(chosen_di)
        used_d.add(chosen_di)
        fam_counts[fkey] = fam_counts.get(fkey, 0) + 1
        if len(kept) >= max_keep:
            break

    return kept
