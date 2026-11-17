"""
Pure-NumPy Live Inference Engines for `visualization_studio/`:
  1. `PortableDiseaseToDrugEngine` — `<15ms` reverse `Disease -> Drug` ranking across 18,025 diseases x 9,860+ drugs
  2. `score_inductive_asset_portable` — `<1.5s` live `⚡ Score New Target` inductive hypothesis scorer
"""

from __future__ import annotations

import json
import os
import threading
import time
from typing import Any, Dict, List, Optional, Sequence, Tuple

import numpy as np

from .bite_biomarker_and_expansion import (
    TCELL_EFFECTOR_GENES,
    build_bite_solid_tumor_exclusion_mask,
    compute_bite_taa_genetics_and_conditioned_scores,
    deduplicate_bite_indication_families,
    extract_nonlymphoid_bite_taas,
    load_bite_biomarker_atlas,
    lookup_or_infer_bite_biomarker_map,
    partition_bite_specs_for_projection_and_genetics,
)
from .numpy_models import (
    classify_combination_archetype,
    is_therapeutic_disease_name,
    load_amgen_portfolio_configs_portable,
    load_numpy_portable_pack,
)
from .option1_protocol_and_omics import (
    compute_option1_protocol_priority_score,
    load_option1_empirical_bundle,
    lookup_empirical_rna_positivity_for_disease,
    lookup_trial_landscape_for_disease,
)


def parse_target_spec_string(spec_str: str) -> List[Tuple[str, str]]:
    out: List[Tuple[str, str]] = []
    for part in spec_str.split(","):
        part = part.strip()
        if not part:
            continue
        if ":" in part:
            sym, act = part.split(":", 1)
            out.append((sym.strip().upper(), act.strip().lower()))
        else:
            out.append((part.upper(), "modulates"))
    return out


class PortableStudioRuntime:
    """Shared lazy-loaded memory cache for both `Disease -> Drug` and `Score New Target`."""

    def __init__(self, studio_root: str) -> None:
        self.studio_root = os.path.abspath(studio_root)
        self.engine_data_dir = os.path.join(self.studio_root, "engine_data")
        self._lock = threading.Lock()
        self._loaded = False
        self.pack: Dict[str, Any] = {}
        self.models: Dict[str, Any] = {}

    def ensure_pack(self) -> Tuple[Dict[str, Any], Dict[str, Any]]:
        if self._loaded:
            return self.pack, self.models
        with self._lock:
            if self._loaded:
                return self.pack, self.models
            self.pack, self.models = load_numpy_portable_pack(self.engine_data_dir)
            self._loaded = True
            return self.pack, self.models


class PortableDiseaseToDrugEngine:
    def __init__(self, runtime: PortableStudioRuntime) -> None:
        self.runtime = runtime
        self._lock = threading.Lock()
        self._ready = False

    def ensure_loaded(self) -> None:
        if self._ready:
            return
        with self._lock:
            if self._ready:
                return
            t0 = time.time()
            pack, rc = self.runtime.ensure_pack()
            studio_root = self.runtime.studio_root
            assets = load_amgen_portfolio_configs_portable(studio_root)
            amgen_by_pid = {a["preferred_id"]: a for a in assets}

            self.dis_ids: List[str] = pack["dis_ids"]
            self.dis_names: List[str] = pack["dis_names"]
            self.dis_id_to_idx = {d: i for i, d in enumerate(self.dis_ids)}

            known_path = os.path.join(studio_root, "explorer_data", "known_indications_by_disease.json")
            if os.path.exists(known_path):
                with open(known_path, "r", encoding="utf-8") as f:
                    raw_known = json.load(f)
                self.known_by_dis = {k: set(v) for k, v in raw_known.items()}
            else:
                self.known_by_dis = {}

            ext_ids: List[str] = pack["ext_drug_ids"]
            ext_names: List[str] = pack["ext_drug_names"]
            cand_us: List[int] = pack["compact_cand_us"]
            ip_meta_by_u: Dict[int, Dict[str, Any]] = rc.get("ip_meta_by_u", {})
            tier2_set = set(pack.get("partner_us_tier2", []))
            gene_syms: List[str] = pack["gene_syms"]
            sym2g = {str(s).upper(): i for i, s in enumerate(gene_syms) if s}

            self.drug_catalog: List[Dict[str, Any]] = []
            seen_pids = set()
            for u_idx in cand_us:
                pid = ext_ids[u_idx]
                seen_pids.add(pid)
                amg = amgen_by_pid.get(pid)
                ipm = ip_meta_by_u.get(u_idx, {})
                is_off = u_idx in tier2_set or str(ipm.get("ip_tier", "")).startswith("off_patent")
                if amg:
                    badge = "Amgen Pipeline" if amg.get("category") == "amgen_pipeline" else "Amgen Commercial"
                    nm = amg["display_name"]
                    akey = amg["key"]
                    fran = amg["franchise"]
                elif is_off:
                    badge = "Off-Patent Generic / Biosimilar"
                    nm = ext_names[u_idx] or pid
                    akey = ""
                    fran = ""
                else:
                    badge = "External Clinical Drug"
                    nm = ext_names[u_idx] or pid
                    akey = ""
                    fran = ""
                self.drug_catalog.append(
                    {
                        "drug_id": pid,
                        "drug_name": nm,
                        "amgen_key": akey,
                        "is_amgen": bool(amg is not None),
                        "franchise": fran,
                        "ip_badge": badge,
                    }
                )

            synth_assets: List[Tuple[Dict[str, Any], List[Tuple[int, float]]]] = []
            for a in assets:
                if a["preferred_id"] not in seen_pids:
                    raw_specs = [
                        (sym2g[str(t["gene"]).upper()], f"drug_{t.get('action', 'binds')}_protein", 1.0)
                        for t in a.get("signed_targets", [])
                        if str(t.get("gene", "")).upper() in sym2g
                    ]
                    bpart = partition_bite_specs_for_projection_and_genetics(raw_specs, gene_syms, sym2g)
                    gw_list = (
                        [(int(gi), float(wt)) for gi, _sr, wt in bpart["projection_specs"]]
                        if bpart is not None
                        else [(int(gi), 1.0) for gi, _sr, _wt in raw_specs]
                    )
                    if gw_list:
                        synth_assets.append((a, gw_list))
                        self.drug_catalog.append(
                            {
                                "drug_id": a["preferred_id"],
                                "drug_name": a["display_name"],
                                "amgen_key": a["key"],
                                "is_amgen": True,
                                "franchise": a["franchise"],
                                "ip_badge": "Amgen Pipeline",
                            }
                        )

            atlas = load_bite_biomarker_atlas()
            pid_to_row = {d["drug_id"]: i for i, d in enumerate(self.drug_catalog)}
            override_proj_rows: List[Tuple[int, List[Tuple[int, float]]]] = []
            self.bite_row_adjustments: List[Tuple[int, np.ndarray, np.ndarray]] = []
            for a in assets:
                r_idx = pid_to_row.get(a["preferred_id"])
                if r_idx is None:
                    continue
                raw_specs = [
                    (sym2g[str(t["gene"]).upper()], f"drug_{t.get('action', 'binds')}_protein", 1.0)
                    for t in a.get("signed_targets", [])
                    if str(t.get("gene", "")).upper() in sym2g
                ]
                bpart = partition_bite_specs_for_projection_and_genetics(raw_specs, gene_syms, sym2g, atlas=atlas)
                if bpart is not None or a.get("category") == "amgen_pipeline":
                    gw_list = (
                        [(int(gi), float(wt)) for gi, _sr, wt in bpart["projection_specs"]]
                        if bpart is not None
                        else [(int(gi), 1.0) for gi, _sr, _wt in raw_specs]
                    )
                    if gw_list and r_idx < len(cand_us):
                        override_proj_rows.append((r_idx, gw_list))
                if bpart is not None:
                    taa_syms = bpart["taa_syms"]
                    excl_mask = build_bite_solid_tumor_exclusion_mask(self.dis_ids, self.dis_names, taa_syms)
                    bmap = lookup_or_infer_bite_biomarker_map(self.dis_ids, self.dis_names, taa_syms[0], atlas=atlas)
                    eff_vec = np.array(
                        [float(bmap[di].pos_pct) / 100.0 if di in bmap else 0.08 for di in range(len(self.dis_ids))],
                        dtype=np.float32,
                    )
                    self.bite_row_adjustments.append((r_idx, eff_vec, excl_mask))

            self.amgen_mask = np.array([d["is_amgen"] for d in self.drug_catalog], dtype=bool)
            self.seeds_prepared: List[Dict[str, Any]] = []
            for sd in pack["seeds"]:
                med_norm = float(sd["median_active_drug_norm"])
                base_h = sd["cand_drug_unit_emb"].astype(np.float32) * med_norm
                proj_g = sd["proj_gene_rev_drug_protein"]
                for r_idx, gw_list in override_proj_rows:
                    gs_t = [gi for gi, _w in gw_list]
                    ws_t = np.array([w for _gi, w in gw_list], dtype=np.float32)[:, None]
                    v = (proj_g[gs_t].astype(np.float32) * ws_t).sum(axis=0) / max(float(ws_t.sum()), 1e-6)
                    base_h[r_idx] = v * (med_norm / max(float(np.linalg.norm(v)), 1e-6))
                extra_rows: List[np.ndarray] = []
                for _a, gw_list in synth_assets:
                    gs_t = [gi for gi, _w in gw_list]
                    ws_t = np.array([w for _gi, w in gw_list], dtype=np.float32)[:, None]
                    v = (proj_g[gs_t].astype(np.float32) * ws_t).sum(axis=0) / max(float(ws_t.sum()), 1e-6)
                    v = v * (med_norm / max(float(np.linalg.norm(v)), 1e-6))
                    extra_rows.append(v[None, :])
                full_h = np.concatenate([base_h] + extra_rows, axis=0) if extra_rows else base_h
                self.seeds_prepared.append(
                    {
                        "H_drugs": full_h.astype(np.float16),
                        "eff_ind": sd["eff_dis_ind"],
                        "mu_d": sd["mu_d"].astype(np.float32),
                        "sd_d": np.maximum(sd["sd_d"].astype(np.float32), 1e-5),
                    }
                )
            self._ready = True
            print(
                f"[Portable Visualization Studio] Ready: {len(self.dis_ids):,} diseases x {len(self.drug_catalog):,} drugs ({time.time()-t0:.2f}s)",
                flush=True,
            )

    def query_disease(self, disease_id: str, scope: str = "all", top_n: int = 60) -> Dict[str, Any]:
        self.ensure_loaded()
        t0 = time.time()
        if disease_id not in self.dis_id_to_idx:
            raise ValueError(f"Unknown disease_id: {disease_id}")
        d_idx = self.dis_id_to_idx[disease_id]
        d_name = self.dis_names[d_idx]
        known_set = self.known_by_dis.get(disease_id, set())

        z_list: List[np.ndarray] = []
        p_list: List[np.ndarray] = []
        for sp in self.seeds_prepared:
            vec_d = sp["eff_ind"][d_idx].astype(np.float32)
            logits = sp["H_drugs"].astype(np.float32) @ vec_d
            z_d = (logits - float(sp["mu_d"][d_idx])) / float(sp["sd_d"][d_idx])
            z_list.append(z_d)
            p_list.append(1.0 / (1.0 + np.exp(-np.clip(logits, -20.0, 20.0))))

        z_mean = np.mean(z_list, axis=0)
        z_std = np.std(z_list, axis=0)
        p_raw = np.mean(p_list, axis=0)
        p_cal = 0.5 * p_raw + 0.5 * (1.0 / (1.0 + np.exp(-np.clip(z_mean - 1.5, -20.0, 20.0))))

        for r_idx, eff_vec, excl_mask in self.bite_row_adjustments:
            if bool(excl_mask[d_idx]):
                z_mean[r_idx] = -25.0
                p_cal[r_idx] = 0.0001
            else:
                eff_s = float(eff_vec[d_idx])
                z_adj = float(z_mean[r_idx]) * (0.45 + 0.55 * eff_s) + 2.10 * (eff_s - 0.12)
                z_mean[r_idx] = z_adj
                p_cal[r_idx] = float(
                    np.clip(
                        (0.5 * float(p_raw[r_idx]) + 0.5 * (1.0 / (1.0 + np.exp(-np.clip(z_adj - 1.2, -20.0, 20.0)))))
                        * np.clip(0.30 + 0.90 * eff_s, 0.05, 1.0),
                        0.0001,
                        0.995,
                    )
                )

        n_total = len(self.drug_catalog)
        cand_indices = np.where(self.amgen_mask)[0] if scope == "amgen" else np.arange(n_total)
        sub_scores = z_mean[cand_indices]
        order = cand_indices[np.argsort(-sub_scores)][: max(1, min(200, top_n))]

        global_ranks = np.empty(n_total, dtype=np.int32)
        global_ranks[np.argsort(-z_mean)] = np.arange(1, n_total + 1)

        drugs_out: List[Dict[str, Any]] = []
        for rank_i, idx_u in enumerate(order, start=1):
            meta = self.drug_catalog[int(idx_u)]
            did_str = meta["drug_id"]
            g_rk = int(global_ranks[int(idx_u)])
            drugs_out.append(
                {
                    "rank": rank_i,
                    "global_rank": g_rk,
                    "drug_id": did_str,
                    "drug_name": meta["drug_name"],
                    "amgen_key": meta["amgen_key"],
                    "is_amgen": meta["is_amgen"],
                    "franchise": meta["franchise"],
                    "ip_badge": meta["ip_badge"],
                    "known": did_str in known_set,
                    "z_std": round(float(z_mean[int(idx_u)]), 3),
                    "epistemic_std": round(float(z_std[int(idx_u)]), 3),
                    "calibrated_prob": round(float(p_cal[int(idx_u)]), 4),
                    "percentile": round(max(0.01, 100.0 * (1.0 - (g_rk - 1) / float(n_total))), 2),
                }
            )

        return {
            "disease_id": disease_id,
            "disease_name": d_name,
            "treatable": len(known_set) > 0,
            "known_fda_drug_count": len(known_set),
            "scope": scope,
            "elapsed_ms": round((time.time() - t0) * 1000.0, 2),
            "drugs": drugs_out,
        }


def score_inductive_asset_portable(
    runtime: PortableStudioRuntime,
    asset_name: str,
    target_specs: Sequence[Tuple[str, str]],
    modality: str = "Investigational Biologic / Small Molecule",
    top_diseases: int = 25,
    top_combos: int = 10,
) -> Dict[str, Any]:
    t0 = time.time()
    pack, models = runtime.ensure_pack()

    gene_syms: List[str] = pack["gene_syms"]
    sym2g = {str(s).upper(): i for i, s in enumerate(gene_syms) if s}
    resolved_g: List[int] = []
    resolved_specs: List[Tuple[int, str, float]] = []
    resolved_labels: List[str] = []
    for sym, act in target_specs:
        gi = sym2g.get(sym.upper())
        if gi is not None:
            srel = (
                "drug_inhibits_protein"
                if "inhibit" in act
                else ("drug_activates_protein" if "activat" in act else "drug_binds_protein")
            )
            resolved_g.append(gi)
            resolved_specs.append((gi, srel, 1.0))
            resolved_labels.append(f"{sym.upper()}:{act}")
    if not resolved_g:
        raise ValueError(f"None of the requested target symbols {target_specs} matched OptimusKG HGNC symbols.")

    ppi_nbrs_map: Dict[int, List[int]] = models.get("ppi_neighbors_by_gene") or {}
    recurring_ade_by_gs: Dict[Tuple[int, str], Any] = models.get("recurring_ade_by_gs") or {}

    bite_part = partition_bite_specs_for_projection_and_genetics(resolved_specs, gene_syms, gene_sym2idx=sym2g)
    active_proj_specs = bite_part["projection_specs"] if bite_part is not None else resolved_specs

    proj_weights_by_g: Dict[int, float] = {}
    primary_set = {gi for gi, _, _ in active_proj_specs}
    for gi, _srel, wt in active_proj_specs:
        proj_weights_by_g[gi] = proj_weights_by_g.get(gi, 0.0) + float(wt)
        nbrs = [n for n in ppi_nbrs_map.get(gi, []) if n not in primary_set][:12]
        if nbrs:
            per_n = (0.25 * float(wt)) / len(nbrs)
            for nb in nbrs:
                proj_weights_by_g[nb] = proj_weights_by_g.get(nb, 0.0) + per_n
    exp_g_idx = np.array(list(proj_weights_by_g.keys()), dtype=np.int64)
    exp_g_wt = np.array(list(proj_weights_by_g.values()), dtype=np.float32)
    exp_g_wt = exp_g_wt / max(float(exp_g_wt.sum()), 1e-6)

    seeds = pack["seeds"]
    dis_ids = pack["dis_ids"]
    dis_names = pack["dis_names"]
    dis_train_deg = pack["dis_train_deg"]
    D_cnt = len(dis_ids)

    z_seeds: List[np.ndarray] = []
    p_ind_seeds: List[np.ndarray] = []
    p_con_seeds: List[np.ndarray] = []
    u_unit_seeds: List[np.ndarray] = []

    for sd in seeds:
        proj_rows = sd["proj_gene_rev_drug_protein"][exp_g_idx].astype(np.float32)
        h_ind = (proj_rows * exp_g_wt[:, None]).sum(axis=0)
        h_norm = max(float(np.linalg.norm(h_ind)), 1e-6)
        h_u = (h_ind * (float(sd["median_active_drug_norm"]) / h_norm)).astype(np.float32)

        logits_ind = sd["eff_dis_ind"].astype(np.float32) @ h_u
        logits_con = sd["eff_dis_con"].astype(np.float32) @ h_u

        mu_d = sd["mu_d"].astype(np.float32)
        sd_d = np.maximum(sd["sd_d"].astype(np.float32), 1e-5)
        z_d = (logits_ind - mu_d) / sd_d
        z_seeds.append(z_d.astype(np.float32))
        p_ind_seeds.append((1.0 / (1.0 + np.exp(-np.clip(logits_ind, -20.0, 20.0)))).astype(np.float32))
        p_con_seeds.append((1.0 / (1.0 + np.exp(-np.clip(logits_con, -20.0, 20.0)))).astype(np.float32))
        u_unit_seeds.append((h_u / max(float(np.linalg.norm(h_u)), 1e-6)).astype(np.float32))

    z_mean = np.mean(z_seeds, axis=0)
    z_std = np.std(z_seeds, axis=0)
    p_ind = np.mean(p_ind_seeds, axis=0)
    p_con = np.mean(p_con_seeds, axis=0)

    p_deb = 1.0 / (1.0 + np.exp(-np.clip(z_mean - 1.5, -20.0, 20.0)))
    X_g1 = np.zeros((D_cnt, 8), dtype=np.float32)
    X_g1[:, 0] = z_mean
    X_g1[:, 1] = (0.50 * p_ind + 0.50 * p_deb).astype(np.float32)
    X_g1[:, 2] = -z_std
    if "dis_gene_d" in pack:
        dg_d = pack["dis_gene_d"]
        dg_g = pack["dis_gene_g"]
        dg_w = pack["dis_gene_w"]
        dir_mask = np.isin(dg_g, np.array(resolved_g, dtype=np.int32))
        if np.any(dir_mask):
            dir_sum = np.bincount(dg_d[dir_mask], weights=dg_w[dir_mask], minlength=D_cnt).astype(np.float32)
            X_g1[:, 3] = np.minimum(1.0, dir_sum)
        n1_set = set(resolved_g)
        for gi in resolved_g:
            n1_set.update(ppi_nbrs_map.get(gi, []))
        n1_only = sorted(n1_set - set(resolved_g))
        ppi_sum = X_g1[:, 3].copy()
        if n1_only:
            n1_mask = np.isin(dg_g, np.array(n1_only, dtype=np.int32))
            if np.any(n1_mask):
                ppi_sum += 0.35 * np.bincount(dg_d[n1_mask], weights=dg_w[n1_mask], minlength=D_cnt).astype(np.float32)
        X_g1[:, 4] = np.log1p(ppi_sum)
    else:
        dg_d = np.zeros(0, dtype=np.int32)
        dg_g = np.zeros(0, dtype=np.int32)
        dg_w = np.zeros(0, dtype=np.float32)
    X_g1[:, 6] = -p_con
    X_g1[:, 7] = 1.0 / np.log2(np.maximum(2.0, dis_train_deg.astype(np.float32) + 2.0))

    therapeutic_mask = np.array([is_therapeutic_disease_name(str(nm)) for nm in dis_names], dtype=bool)
    excl_mask = ~therapeutic_mask
    if pack.get("non_targetable_disease_mask") is not None and len(pack["non_targetable_disease_mask"]) == D_cnt:
        excl_mask = excl_mask | np.asarray(pack["non_targetable_disease_mask"], dtype=bool)
    for gi, srel, _wt in resolved_specs:
        if bite_part is not None and str(gene_syms[gi]).upper() in TCELL_EFFECTOR_GENES:
            continue
        for tox_di in recurring_ade_by_gs.get((gi, srel), ()):
            if 0 <= int(tox_di) < D_cnt and X_g1[int(tox_di), 3] < 0.15:
                excl_mask[int(tox_di)] = True

    ranker = models["repurpose_ranker"]
    conformal = models["conformal_calibrator"]
    bmap: Dict[int, Any] = {}
    if bite_part is not None:
        X_g1, scores_conditioned_d, bmap, unboosted_scores_d = compute_bite_taa_genetics_and_conditioned_scores(
            base_X_d=X_g1,
            z_row=z_mean,
            repurpose_ranker=ranker,
            drug_train_ind_deg=0,
            bite_part=bite_part,
            dis_ids=dis_ids,
            dis_names=dis_names,
            dg_d=dg_d,
            dg_g=dg_g,
            dg_w=dg_w,
            ppi_neighbors_by_gene=ppi_nbrs_map,
            return_unboosted=True,
        )
        scores_d = unboosted_scores_d
        excl_mask = excl_mask | build_bite_solid_tumor_exclusion_mask(
            dis_ids=dis_ids, dis_names=dis_names, taa_syms=bite_part["taa_syms"]
        )
    else:
        scores_d = ranker.score(X_g1, has_defined_targets=True, drug_train_ind_deg=0)
        scores_conditioned_d = scores_d

    cal = conformal.calibrate_drug_row(
        drug_scores_d=scores_d,
        drug_std_z_d=z_std,
        drug_deg=0,
        disease_train_deg=dis_train_deg,
        exclude_known_mask_d=excl_mask,
    )
    if bite_part is not None:
        masked_cond = (scores_conditioned_d - 0.20 * z_std).astype(np.float64)
        masked_cond[excl_mask] = -1e9
        raw_d_order = np.argsort(-masked_cond)[: max(240, top_diseases * 6)]
        seen_norm_names = set()
        dedup_norm: List[int] = []
        for di_cand in raw_d_order.tolist():
            if bool(excl_mask[di_cand]):
                continue
            norm_nm = " ".join(str(dis_names[di_cand]).lower().replace("-", " ").split())
            if norm_nm in seen_norm_names:
                continue
            seen_norm_names.add(norm_nm)
            dedup_norm.append(int(di_cand))
        top_d_order = deduplicate_bite_indication_families(
            dedup_norm, dis_ids=dis_ids, dis_names=dis_names, primary_taa=bite_part["taa_syms"][0], max_keep=top_diseases
        )
    else:
        masked_adj = cal["adj_score"].copy()
        masked_adj[excl_mask] = -1e9
        q_arr = cal["fdr_qvalue"]
        tier_pri = np.where(excl_mask, 9, np.where(q_arr <= 0.05, 0, np.where(q_arr <= 0.10, 1, 2)))
        raw_d_order = np.lexsort((-masked_adj, tier_pri))[: max(100, top_diseases * 3)]
        seen_norm_names = set()
        top_d_order = []
        for di_cand in raw_d_order.tolist():
            if bool(excl_mask[di_cand]):
                continue
            norm_nm = " ".join(str(dis_names[di_cand]).lower().replace("-", " ").split())
            if norm_nm in seen_norm_names:
                continue
            seen_norm_names.add(norm_nm)
            top_d_order.append(int(di_cand))
            if len(top_d_order) >= top_diseases:
                break

    goal1_list = []
    emp_b = load_option1_empirical_bundle() if (bite_part is not None and "DLL3" in bite_part["taa_syms"]) else {}
    for rk, di in enumerate(top_d_order, start=1):
        binfo = bmap.get(di)
        row_g1: Dict[str, Any] = {
            "rank": rk,
            "disease_id": str(dis_ids[di]),
            "disease_name": str(dis_names[di]),
            "calibrated_prob": round(float(cal["p_calibrated"][di]), 4),
            "bite_and_gate_score": round(float(scores_conditioned_d[di]), 4) if bite_part is not None else None,
            "z_std": round(float(z_mean[di]), 4),
            "direct_l2g": round(float(X_g1[di, 3]), 3),
            "ppi1hop_l2g": round(float(X_g1[di, 4]), 3),
            "conformal_pvalue": round(float(cal["conformal_pvalue"][di]), 5),
            "fdr_qvalue": round(float(cal["fdr_qvalue"][di]), 5),
        }
        if bite_part is not None:
            row_g1["biomarker_gene"] = str(binfo.taa_gene) if binfo else str(bite_part["taa_syms"][0])
            row_g1["biomarker_pos_pct"] = round(float(binfo.pos_pct), 1) if binfo else None
            row_g1["biomarker_high_pct"] = round(float(binfo.high_pct), 1) if binfo else None
            row_g1["biomarker_gate"] = str(binfo.biomarker_gate) if binfo else ""
            row_g1["cns_icans_risk"] = str(binfo.cns_icans_risk) if binfo else ""
            row_g1["expansion_tier"] = str(binfo.expansion_tier) if binfo else ""
            if "DLL3" in bite_part["taa_syms"]:
                emp_om = lookup_empirical_rna_positivity_for_disease(str(dis_ids[di]), str(dis_names[di]), empirical_bundle=emp_b)
                tl = lookup_trial_landscape_for_disease(str(dis_ids[di]), str(dis_names[di]), empirical_bundle=emp_b)
                if emp_om and int(emp_om.get("sample_n") or 0) > 0:
                    row_g1["empirical_rna_pos_pct"] = emp_om.get("pct_above_within_platform_ref")
                    row_g1["empirical_rna_platform"] = str(emp_om.get("platform_id") or "")
                    row_g1["empirical_rna_sample_type"] = str(emp_om.get("sample_type") or "")
                p_sc, op_tr, _ = compute_option1_protocol_priority_score(
                    gnn_z_std=float(z_mean[di]),
                    ppi1hop_l2g=float(X_g1[di, 4]),
                    biomarker_pos_pct=row_g1["biomarker_pos_pct"],
                    biomarker_high_pct=row_g1["biomarker_high_pct"],
                    effective_pop_share=float(binfo.effective_pop_share) if binfo else 1.0,
                    cns_icans_risk=row_g1["cns_icans_risk"],
                    competitive_whitespace_score=float(tl["competitive_whitespace_score"]),
                )
                row_g1["competitor_dll3_trials_n"] = int(tl["competitor_dll3_total_n"])
                row_g1["competitor_pan_dll3_basket_n"] = int(tl.get("competitor_pan_dll3_basket_total_n", 0))
                row_g1["option1_protocol_score"] = p_sc
                row_g1["operational_safety_track"] = op_tr
        goal1_list.append(row_g1)

    top_di = int(top_d_order[0])
    compact_cand_us: List[int] = pack["compact_cand_us"]
    cand_to_c = {u: i for i, u in enumerate(compact_cand_us)}
    ext_drug_names = pack["ext_drug_names"]
    ext_drug_ids = pack["ext_drug_ids"]
    combo_engine = models["combo_engine"]
    ip_meta_by_u = models["ip_meta_by_u"]
    amgen_by_u = models["amgen_by_u"]
    target_syms_by_u = models["target_syms_by_u"]

    u_mech_gis = set(int(g) for g in bite_part["taa_g_indices"]) if bite_part is not None else set(resolved_g)
    u_n1_gis = set(u_mech_gis)
    for g_u in list(u_mech_gis):
        u_n1_gis.update(ppi_nbrs_map.get(g_u, [])[:24])
    if bite_part is not None:
        u_n1_gis.update(int(lg) for lg in (bite_part.get("lineage_g_weights") or {}).keys())

    d_gene_w_top: Dict[int, float] = {}
    if len(dg_d) > 0:
        d_m_top = dg_d == top_di
        if np.any(d_m_top):
            for g_top, w_top in zip(dg_g[d_m_top].tolist(), dg_w[d_m_top].tolist()):
                d_gene_w_top[int(g_top)] = max(d_gene_w_top.get(int(g_top), 0.0), float(w_top))
    u_l2g_top = min(1.0, sum(d_gene_w_top.get(g, 0.0) for g in u_mech_gis))

    def _score_partner_pool(pool_us: List[int]) -> List[Dict[str, Any]]:
        valid_vs = [v for v in pool_us if v in cand_to_c]
        if not valid_vs:
            return []
        M = len(valid_vs)
        X_c = np.zeros((M, 24), dtype=np.float32)
        vc_idxs = np.array([cand_to_c[v] for v in valid_vs], dtype=np.int32)

        zv_acc = np.zeros(M, dtype=np.float32)
        pv_acc = np.zeros(M, dtype=np.float32)
        cv_acc = np.zeros(M, dtype=np.float32)
        cos_uv_acc = np.zeros(M, dtype=np.float32)
        jgain_acc = np.zeros(M, dtype=np.float32)
        for s_i, sd in enumerate(seeds):
            hv_unit = sd["cand_drug_unit_emb"][vc_idxs].astype(np.float32)
            hv_scaled = hv_unit * float(sd["median_active_drug_norm"])
            e_ind_d = sd["eff_dis_ind"][top_di].astype(np.float32)
            e_con_d = sd["eff_dis_con"][top_di].astype(np.float32)
            lv = hv_scaled @ e_ind_d
            lc = hv_scaled @ e_con_d
            zv = (lv - float(sd["mu_d"][top_di])) / max(float(sd["sd_d"][top_di]), 1e-5)
            zv_acc += zv
            pv_acc += 1.0 / (1.0 + np.exp(-np.clip(lv, -20.0, 20.0)))
            cv_acc += 1.0 / (1.0 + np.exp(-np.clip(lc, -20.0, 20.0)))

            hu = u_unit_seeds[s_i]
            hd = sd["dis_unit_emb"][top_di].astype(np.float32)
            c_uv = hv_unit @ hu
            c_ud = float(hu @ hd)
            c_vd = hv_unit @ hd
            h_mid = hv_unit + hu[None, :]
            c_joint = (h_mid @ hd) / np.maximum(np.linalg.norm(h_mid, axis=1), 1e-6)
            cos_uv_acc += c_uv
            jgain_acc += c_joint - np.maximum(c_ud, c_vd)

        ns = float(len(seeds))
        zv_m = zv_acc / ns
        pv_m = pv_acc / ns
        cv_m = cv_acc / ns
        zu_val = float(z_mean[top_di])
        pu_val = float(p_ind[top_di])
        cu_val = float(p_con[top_di])

        X_c[:, 0] = np.maximum(zu_val, zv_m)
        X_c[:, 1] = np.minimum(zu_val, zv_m)
        X_c[:, 2] = zu_val + zv_m
        X_c[:, 3] = np.abs(zu_val - zv_m)
        X_c[:, 4] = np.maximum(pu_val, pv_m)
        X_c[:, 5] = pu_val * pv_m
        X_c[:, 6] = cos_uv_acc / ns
        X_c[:, 7] = 1.0 - np.abs(X_c[:, 6] - 0.35)
        X_c[:, 8] = jgain_acc / ns
        X_c[:, 9] = np.maximum(cu_val, cv_m)
        X_c[:, 10] = cu_val + cv_m
        X_c[:, 11] = float(z_std[top_di])

        for li, vi in enumerate(valid_vs):
            v_raw_syms = [str(s).upper() for s, _ in target_syms_by_u.get(vi, [])]
            v_taas = extract_nonlymphoid_bite_taas(v_raw_syms)
            v_use_syms = v_taas if v_taas else v_raw_syms
            v_gis = {sym2g[s] for s in v_use_syms if s in sym2g}
            union_t = u_mech_gis | v_gis
            t_jacc = float(len(u_mech_gis & v_gis)) / float(len(union_t)) if union_t else 0.0
            v_n1 = set(v_gis)
            for gv in v_gis:
                v_n1.update(ppi_nbrs_map.get(gv, [])[:24])
            union_n1 = u_n1_gis | v_n1
            n1_jacc = float(len(u_n1_gis & v_n1)) / float(len(union_n1)) if union_n1 else 0.0
            v_l2g = min(1.0, sum(d_gene_w_top.get(g, 0.0) for g in v_gis))
            marg_gain = min(
                1.5,
                sum(d_gene_w_top.get(g, 0.0) for g in (v_gis - u_mech_gis))
                + 0.25 * sum(d_gene_w_top.get(g, 0.0) for g in (v_n1 - u_n1_gis)),
            )
            comp_sc = (marg_gain if (u_l2g_top + v_l2g) > 0.02 else 0.25) * (1.0 - t_jacc)
            X_c[li, 12] = max(u_l2g_top, v_l2g)
            X_c[li, 13] = min(u_l2g_top, v_l2g)
            X_c[li, 14] = marg_gain
            X_c[li, 15] = t_jacc
            X_c[li, 16] = n1_jacc
            X_c[li, 17] = max(0.0, comp_sc)

        preds = combo_engine.predict_batch(X_c, device="cpu")
        redundancy_pen = np.where(X_c[:, 15] > 0.65, 0.35, np.where(X_c[:, 15] > 0.40, 0.75, 1.0)).astype(np.float32)
        util = preds["combo_utility"] * redundancy_pen
        order = np.argsort(-util)[:top_combos]
        rows_out = []
        for rk_i, li in enumerate(order.tolist(), start=1):
            vi = valid_vs[li]
            amg = amgen_by_u.get(vi)
            meta = ip_meta_by_u.get(vi, {})
            v_nm = amg["display_name"] if amg else ext_drug_names[vi]
            v_targs = ", ".join(s for s, _ in target_syms_by_u.get(vi, [])[:4])
            rows_out.append(
                {
                    "rank": rk_i,
                    "partner_node_id": ext_drug_ids[vi],
                    "partner_drug": v_nm,
                    "partner_targets": v_targs,
                    "cost_badge": str(meta.get("cost_badge") or "Amgen Internal Portfolio"),
                    "combo_utility": round(float(util[li]), 4),
                    "p_efficacy": round(float(preds["p_efficacy"][li]), 4),
                    "safety_clearance": round(float(1.0 - preds["p_toxicity"][li]), 4),
                    "target_jaccard": round(float(X_c[li, 15]), 4),
                    "marginal_genetic_gain": round(float(X_c[li, 14]), 4),
                    "archetype": classify_combination_archetype(X_c[li], modality, str(meta.get("modality") or "")),
                }
            )
        return rows_out

    t1_combos = _score_partner_pool(pack["partner_us_tier1"])
    t2_combos = _score_partner_pool(pack["partner_us_tier2"])
    t3_combos = _score_partner_pool(pack.get("partner_us_tier3") or [])

    return {
        "asset_name": asset_name,
        "resolved_targets": resolved_labels,
        "bite_and_gate_active": bite_part is not None,
        "bite_tumor_antigens": bite_part["taa_syms"] if bite_part is not None else [],
        "bite_nonlymphoid_taas": bite_part["taa_syms"] if bite_part is not None else [],
        "elapsed_seconds": round(time.time() - t0, 3),
        "goal1_top_repurposed_diseases": goal1_list,
        "goal2_anchor_disease": {
            "disease_id": str(dis_ids[top_di]),
            "disease_name": str(dis_names[top_di]),
        },
        "goal2_tier1_amgen_x_amgen": t1_combos,
        "goal2_tier2_amgen_x_offpatent_generic": t2_combos,
        "goal2_tier2_offpatent_combos": t2_combos,
        "goal2_tier3_external_clinical_benchmarks": t3_combos,
    }
