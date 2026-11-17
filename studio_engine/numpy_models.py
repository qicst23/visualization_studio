"""
Pure-NumPy implementations of:
  - `AmgenRepurposeRanker`
  - `MondrianConformalCalibrator`
  - `OptimusComboNet` & `TrainedComboEngine`
  - `load_numpy_portable_pack`

Zero dependency on PyTorch, Scikit-Learn, SciPy, DGL, Polars, or PyYAML.
Matches PyTorch `portable_pack.py` outputs to < 1e-5 numerical precision on Windows 11 & Linux.
"""

from __future__ import annotations

import json
import math
import os
import re
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

_NON_THERAPEUTIC_DISEASE_RE = re.compile(
    r"(^response to | measurement$| level$| levels$| count$| trait$| phenotype$|"
    r" status$| finding$| procedure$|^adverse reaction to |^susceptibility to )",
    re.IGNORECASE,
)

_VEC_ERF = np.vectorize(math.erf, otypes=[np.float64])


def is_therapeutic_disease_name(name: str) -> bool:
    s = (name or "").strip()
    if not s:
        return False
    return not bool(_NON_THERAPEUTIC_DISEASE_RE.search(s))


def _gelu(x: np.ndarray) -> np.ndarray:
    x64 = x.astype(np.float64)
    return (0.5 * x64 * (1.0 + _VEC_ERF(x64 / math.sqrt(2.0)))).astype(np.float32)


def _layernorm(x: np.ndarray, weight: np.ndarray, bias: np.ndarray, eps: float = 1e-5) -> np.ndarray:
    mean = x.mean(axis=-1, keepdims=True)
    var = ((x - mean) ** 2).mean(axis=-1, keepdims=True)
    x_hat = (x - mean) / np.sqrt(var + eps)
    return (x_hat * weight + bias).astype(np.float32)


def _linear(x: np.ndarray, weight: np.ndarray, bias: np.ndarray) -> np.ndarray:
    return (x @ weight.T + bias).astype(np.float32)


def _drug_deg_bucket(deg: np.ndarray) -> np.ndarray:
    return np.where(deg <= 0, 0, np.where(deg <= 4, 1, 2)).astype(np.int32)


def _disease_deg_bucket(deg: np.ndarray) -> np.ndarray:
    return np.where(deg <= 0, 0, np.where(deg <= 3, 1, np.where(deg <= 20, 2, 3))).astype(np.int32)


class NumpyRepurposeRanker:
    def __init__(
        self,
        fitted: bool,
        scaler_mean: np.ndarray,
        scaler_scale: np.ndarray,
        clf_coef: np.ndarray,
        clf_intercept: np.ndarray,
    ) -> None:
        self.fitted = fitted
        self.scaler_mean = scaler_mean.astype(np.float64)
        self.scaler_scale = np.where(scaler_scale == 0, 1.0, scaler_scale).astype(np.float64)
        self.clf_coef = clf_coef.reshape(-1).astype(np.float64)
        self.clf_intercept = float(clf_intercept.reshape(-1)[0])

    def score(
        self,
        X: np.ndarray,
        has_defined_targets: bool = False,
        drug_train_ind_deg: Optional[int] = None,
    ) -> np.ndarray:
        if not self.fitted:
            base = (
                0.55 * X[:, 0]
                + 0.15 * X[:, 3] * 3.0
                + 0.15 * X[:, 4]
                + 0.10 * X[:, 5]
                + 0.05 * X[:, 6]
            ).astype(np.float32)
        else:
            Xs = (X.astype(np.float64) - self.scaler_mean) / self.scaler_scale
            base = (Xs @ self.clf_coef + self.clf_intercept).astype(np.float32)

        if has_defined_targets and (drug_train_ind_deg is not None and drug_train_ind_deg <= 2):
            zero_pathway = (X[:, 3] < 0.01) & (X[:, 4] < 0.03)
            weak_pathway = (X[:, 3] < 0.05) & (X[:, 4] < 0.12) & (~zero_pathway)
            penalty = np.where(zero_pathway, 1.35, np.where(weak_pathway, 0.55, 0.0)).astype(np.float32)
            base = base - penalty
        return base


class NumpyConformalCalibrator:
    def __init__(
        self,
        unc_penalty: float,
        global_sorted_neg_scores: np.ndarray,
        bucket_sorted_neg_scores: Dict[Tuple[int, int], np.ndarray],
        iso_x: Optional[np.ndarray] = None,
        iso_y: Optional[np.ndarray] = None,
        platt_coef: Optional[np.ndarray] = None,
        platt_intercept: Optional[np.ndarray] = None,
    ) -> None:
        self.unc_penalty = float(unc_penalty)
        self.global_sorted_neg_scores = global_sorted_neg_scores.astype(np.float32)
        self.bucket_sorted_neg_scores = bucket_sorted_neg_scores
        self.iso_x = iso_x
        self.iso_y = iso_y
        self.platt_coef = float(platt_coef.reshape(-1)[0]) if platt_coef is not None else None
        self.platt_intercept = float(platt_intercept.reshape(-1)[0]) if platt_intercept is not None else None

    def calibrate_drug_row(
        self,
        drug_scores_d: np.ndarray,
        drug_std_z_d: np.ndarray,
        drug_deg: int,
        disease_train_deg: np.ndarray,
        exclude_known_mask_d: Optional[np.ndarray] = None,
    ) -> Dict[str, np.ndarray]:
        D = len(drug_scores_d)
        nonconf_d = -drug_scores_d + self.unc_penalty * drug_std_z_d
        ub = int(_drug_deg_bucket(np.array([drug_deg]))[0])
        d_bins = _disease_deg_bucket(disease_train_deg)
        max_db_present = max((k[1] for k in (self.bucket_sorted_neg_scores or {}).keys()), default=3)
        if max_db_present <= 2:
            d_bins = np.where(disease_train_deg <= 3, 0, np.where(disease_train_deg <= 20, 1, 2)).astype(np.int32)
            active_dbs: Tuple[int, ...] = (0, 1, 2)
        else:
            active_dbs = (0, 1, 2, 3)

        pvals = np.ones(D, dtype=np.float32)
        for db in active_dbs:
            mask = d_bins == db
            if not np.any(mask):
                continue
            ref = self.bucket_sorted_neg_scores.get((ub, db), self.global_sorted_neg_scores)
            cnt_le = np.searchsorted(ref, nonconf_d[mask], side="right")
            pvals[mask] = (1.0 + cnt_le) / (len(ref) + 1.0)

        qvals = np.ones(D, dtype=np.float32)
        novel_mask = (~exclude_known_mask_d) if exclude_known_mask_d is not None else np.ones(D, dtype=bool)
        for db in active_dbs:
            sub_idx = np.where(novel_mask & (d_bins == db))[0]
            if len(sub_idx) == 0:
                continue
            sub_p = pvals[sub_idx]
            sub_nc = nonconf_d[sub_idx]
            order = np.lexsort((sub_nc, sub_p))
            ranked_p = sub_p[order]
            m_b = float(len(sub_idx))
            ranks = np.arange(1, len(sub_idx) + 1, dtype=np.float32)
            raw_q = ranked_p * (m_b / ranks)
            mono_q = np.minimum.accumulate(raw_q[::-1])[::-1]
            mono_q = np.clip(mono_q, 0.0, 1.0)
            inv_q = np.empty_like(mono_q)
            inv_q[order] = mono_q
            qvals[sub_idx] = inv_q

        adj_score = -nonconf_d
        if self.iso_x is not None and self.iso_y is not None and self.platt_coef is not None and self.platt_intercept is not None:
            p_iso = np.clip(np.interp(adj_score.astype(np.float64), self.iso_x, self.iso_y), 0.001, 0.995).astype(np.float32)
            z_plt = np.clip(adj_score.astype(np.float64) * self.platt_coef + self.platt_intercept, -30.0, 30.0)
            p_plt = (1.0 / (1.0 + np.exp(-z_plt))).astype(np.float32)
            p_cal = (0.35 * p_iso + 0.65 * p_plt).astype(np.float32)
        elif self.iso_x is not None and self.iso_y is not None:
            p_cal = np.clip(np.interp(adj_score.astype(np.float64), self.iso_x, self.iso_y), 0.001, 0.995).astype(np.float32)
        else:
            p_cal = (1.0 / (1.0 + np.exp(-np.clip(adj_score, -20.0, 20.0)))).astype(np.float32)

        return {
            "adj_score": adj_score.astype(np.float32),
            "conformal_pvalue": pvals,
            "fdr_qvalue": qvals,
            "p_calibrated": p_cal,
        }


class NumpyComboEngine:
    def __init__(
        self,
        sd: Dict[str, np.ndarray],
        scaler_mean: np.ndarray,
        scaler_scale: np.ndarray,
        iso_x: Optional[np.ndarray],
        iso_y: Optional[np.ndarray],
        gamma_tox: float,
        gamma_antag: float,
        tox_logit_shift: float = 0.0,
        antag_logit_shift: float = 0.0,
    ) -> None:
        self.sd = sd
        self.scaler_mean = scaler_mean.astype(np.float64)
        self.scaler_scale = np.where(scaler_scale == 0, 1.0, scaler_scale).astype(np.float64)
        self.iso_x = iso_x
        self.iso_y = iso_y
        self.gamma_tox = float(gamma_tox)
        self.gamma_antag = float(gamma_antag)
        self.tox_logit_shift = float(tox_logit_shift)
        self.antag_logit_shift = float(antag_logit_shift)

    def predict_batch(self, X: np.ndarray, device: str = "cpu") -> Dict[str, np.ndarray]:
        Xs = ((X.astype(np.float64) - self.scaler_mean) / self.scaler_scale).astype(np.float32)
        s = self.sd
        h = _linear(Xs, s["stem.0.weight"], s["stem.0.bias"])
        h = _layernorm(h, s["stem.1.weight"], s["stem.1.bias"])
        h = _gelu(h)

        r = _linear(h, s["res_block.0.weight"], s["res_block.0.bias"])
        r = _layernorm(r, s["res_block.1.weight"], s["res_block.1.bias"])
        r = _gelu(r)
        r = _linear(r, s["res_block.4.weight"], s["res_block.4.bias"])
        r = _layernorm(r, s["res_block.5.weight"], s["res_block.5.bias"])
        h = h + r

        le = _linear(_gelu(_linear(h, s["head_eff.0.weight"], s["head_eff.0.bias"])), s["head_eff.2.weight"], s["head_eff.2.bias"]).reshape(-1)
        lt = _linear(_gelu(_linear(h, s["head_tox.0.weight"], s["head_tox.0.bias"])), s["head_tox.2.weight"], s["head_tox.2.bias"]).reshape(-1)
        la = _linear(_gelu(_linear(h, s["head_antag.0.weight"], s["head_antag.0.bias"])), s["head_antag.2.weight"], s["head_antag.2.bias"]).reshape(-1)

        raw_eff = (1.0 / (1.0 + np.exp(-np.clip(le, -25.0, 25.0)))).astype(np.float32)
        p_tox = (1.0 / (1.0 + np.exp(-np.clip(lt - self.tox_logit_shift, -25.0, 25.0)))).astype(np.float32)
        p_antag = (1.0 / (1.0 + np.exp(-np.clip(la - self.antag_logit_shift, -25.0, 25.0)))).astype(np.float32)

        if self.iso_x is not None and self.iso_y is not None:
            p_eff = np.clip(np.interp(raw_eff.astype(np.float64), self.iso_x, self.iso_y), 0.0, 1.0).astype(np.float32)
        else:
            p_eff = raw_eff

        mech_antag_floor = np.maximum.reduce(
            [
                X[:, 18] * 0.90,
                X[:, 21] * 0.70,
                np.clip(X[:, 15] * 0.45, 0.0, 0.45),
            ]
        )
        p_antag = np.clip(np.maximum(p_antag, mech_antag_floor), 0.0, 0.99).astype(np.float32)

        mech_tox_floor = np.clip(0.30 * X[:, 22] + 0.18 * X[:, 23] + 0.45 * X[:, 9], 0.0, 0.95)
        p_tox = np.clip(np.maximum(p_tox, mech_tox_floor), 0.0, 0.99).astype(np.float32)
        utility = (
            p_eff
            * np.power(np.clip(1.0 - p_tox, 0.01, 1.0), self.gamma_tox)
            * np.power(np.clip(1.0 - p_antag, 0.01, 1.0), self.gamma_antag)
        ).astype(np.float32)
        return {
            "p_efficacy": p_eff,
            "p_toxicity": p_tox,
            "p_antagonism": p_antag,
            "combo_utility": utility,
        }


def classify_combination_archetype(feat_row: np.ndarray, u_modality: str = "", v_modality: str = "") -> str:
    t_jacc = float(feat_row[15])
    n1_jacc = float(feat_row[16])
    cov_gain = float(feat_row[14])
    z_min = float(feat_row[1])
    z_diff = float(feat_row[3])
    mods = f"{u_modality} {v_modality}".lower()

    if "bite" in mods or "engager" in mods or "oncolytic" in mods:
        return "Immune Effector + Tumor Microenvironment Synergy"
    if t_jacc < 0.10 and n1_jacc >= 0.06 and cov_gain >= 0.25:
        return "Convergent Pathway Co-Blockade (Shared Intracellular Hub)"
    if t_jacc < 0.10 and z_diff >= 1.5 and z_min < 1.2:
        return "Anchor Therapy + Pathway Sensitizer / Feedback Bypass"
    if t_jacc < 0.15 and cov_gain >= 0.15:
        return "Orthogonal Multi-Axis Disease Module Coverage"
    return "Complementary Systemic Regimen"


def load_amgen_portfolio_configs_portable(studio_root: str) -> List[Dict[str, Any]]:
    port_yaml = os.path.join(studio_root, "configs", "amgen_portfolio_v5.yaml")
    int_yaml = os.path.join(studio_root, "configs", "amgen_internal_targets.yaml")
    comp_json = os.path.join(studio_root, "engine_data", "configs_compiled.json")
    try:
        import yaml  # type: ignore
        if os.path.exists(port_yaml):
            with open(port_yaml, "r", encoding="utf-8") as f:
                base = yaml.safe_load(f) or {}
            assets = list(base.get("portfolio", []))
            if os.path.exists(int_yaml):
                with open(int_yaml, "r", encoding="utf-8") as f:
                    ext = yaml.safe_load(f) or {}
                for item in ext.get("custom_assets", []) or []:
                    assets.append(item)
            return assets
    except ImportError:
        pass
    with open(comp_json, "r", encoding="utf-8") as f:
        all_c = json.load(f) or {}
    assets = list((all_c.get("amgen_portfolio_v5.yaml") or {}).get("portfolio", []))
    for item in ((all_c.get("amgen_internal_targets.yaml") or {}).get("custom_assets") or []):
        assets.append(item)
    return assets


def load_numpy_portable_pack(engine_data_dir: str) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    meta_path = os.path.join(engine_data_dir, "pack_metadata.json")
    tensors_path = os.path.join(engine_data_dir, "pack_tensors_fp16.npz")
    models_path = os.path.join(engine_data_dir, "portable_models_v1.npz")

    with open(meta_path, "r", encoding="utf-8") as f:
        meta = json.load(f)
    z_pack = np.load(tensors_path, allow_pickle=False)
    z_mod = np.load(models_path, allow_pickle=False)

    seeds = []
    for i, sm in enumerate(meta["seeds_meta"]):
        seeds.append(
            {
                "ckpt_name": sm["ckpt_name"],
                "median_active_drug_norm": float(sm["median_active_drug_norm"]),
                "proj_gene_rev_drug_protein": z_pack[f"seed{i}_proj_gene_rev_drug_protein"],
                "eff_dis_ind": z_pack[f"seed{i}_eff_dis_ind"],
                "eff_dis_con": z_pack[f"seed{i}_eff_dis_con"],
                "mu_d": z_pack[f"seed{i}_mu_d"],
                "sd_d": z_pack[f"seed{i}_sd_d"],
                "cand_drug_unit_emb": z_pack[f"seed{i}_cand_drug_unit_emb"],
                "dis_unit_emb": z_pack[f"seed{i}_dis_unit_emb"],
            }
        )

    pack: Dict[str, Any] = {
        "seeds": seeds,
        "compact_cand_us": meta["compact_cand_us"],
        "ext_drug_ids": meta["ext_drug_ids"],
        "ext_drug_names": meta["ext_drug_names"],
        "dis_ids": meta["dis_ids"],
        "dis_names": meta["dis_names"],
        "gene_syms": meta["gene_syms"],
        "dis_train_deg": z_pack["dis_train_deg"].astype(np.int32),
        "drug_train_deg": z_pack["drug_train_deg"].astype(np.int32),
        "partner_us_tier1": meta["partner_us_tier1"],
        "partner_us_tier2": meta["partner_us_tier2"],
        "partner_us_tier3": meta["partner_us_tier3"],
    }
    if "non_targetable_disease_mask" in z_pack:
        pack["non_targetable_disease_mask"] = z_pack["non_targetable_disease_mask"].astype(bool)
    if "dis_gene_d" in z_pack:
        pack["dis_gene_d"] = z_pack["dis_gene_d"].astype(np.int32)
        pack["dis_gene_g"] = z_pack["dis_gene_g"].astype(np.int32)
        pack["dis_gene_w"] = z_pack["dis_gene_w"].astype(np.float32)

    rk = NumpyRepurposeRanker(
        fitted=bool(meta["ranker_fitted"]),
        scaler_mean=z_mod["rk_scaler_mean"],
        scaler_scale=z_mod["rk_scaler_scale"],
        clf_coef=z_mod["rk_clf_coef"],
        clf_intercept=z_mod["rk_clf_intercept"],
    )

    buckets: Dict[Tuple[int, int], np.ndarray] = {}
    for bk in meta["conformal_bucket_keys"]:
        p0, p1 = bk.split("_")
        buckets[(int(p0), int(p1))] = z_mod[f"cf_bucket_{bk}"].astype(np.float32)

    cf = NumpyConformalCalibrator(
        unc_penalty=float(meta["conformal_unc_penalty"]),
        global_sorted_neg_scores=z_mod["cf_global_sorted_neg"],
        bucket_sorted_neg_scores=buckets,
        iso_x=z_mod["cf_iso_x"] if "cf_iso_x" in z_mod else None,
        iso_y=z_mod["cf_iso_y"] if "cf_iso_y" in z_mod else None,
        platt_coef=z_mod["cf_platt_coef"] if "cf_platt_coef" in z_mod else None,
        platt_intercept=z_mod["cf_platt_intercept"] if "cf_platt_intercept" in z_mod else None,
    )

    sd_dict = {k[len("ce_sd_"):]: z_mod[k] for k in z_mod.files if k.startswith("ce_sd_")}
    ce = NumpyComboEngine(
        sd=sd_dict,
        scaler_mean=z_mod["ce_scaler_mean"],
        scaler_scale=z_mod["ce_scaler_scale"],
        iso_x=z_mod["ce_iso_x"] if "ce_iso_x" in z_mod else None,
        iso_y=z_mod["ce_iso_y"] if "ce_iso_y" in z_mod else None,
        gamma_tox=float(meta["combo_gamma_tox"]),
        gamma_antag=float(meta["combo_gamma_antag"]),
        tox_logit_shift=float(meta["combo_tox_logit_shift"]),
        antag_logit_shift=float(meta["combo_antag_logit_shift"]),
    )

    models: Dict[str, Any] = {
        "repurpose_ranker": rk,
        "conformal_calibrator": cf,
        "combo_engine": ce,
        "ip_meta_by_u": {int(k): v for k, v in meta["ip_meta_by_u"].items()},
        "amgen_by_u": {int(k): v for k, v in meta["amgen_by_u"].items()},
        "target_syms_by_u": {int(k): v for k, v in meta["target_syms_by_u"].items()},
        "ppi_neighbors_by_gene": {int(k): [int(x) for x in v] for k, v in meta["ppi_neighbors_by_gene"].items()},
        "recurring_ade_by_gs": {
            (int(k.split("::", 1)[0]), str(k.split("::", 1)[1])): set(int(x) for x in v)
            for k, v in meta["recurring_ade_by_gs"].items()
            if "::" in str(k)
        },
    }
    return pack, models
