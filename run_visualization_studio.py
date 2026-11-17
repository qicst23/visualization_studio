#!/usr/bin/env python3
"""
Self-Contained Cross-Platform (Windows 11 + Linux) Visualization & Live KG Server.

Run directly inside this folder on either OS:
  - Windows 11 : double-click `Launch_Visualization_Windows.bat`  OR  `python run_visualization_studio.py --open-browser`
  - Linux      : `./launch_visualization_linux.sh`                OR  `python3 run_visualization_studio.py --open-browser`

Zero external repo dependency: every HTML studio, D3 library, 47-asset KG bundle, and FP16 neural
inference array is stored inside this folder.
"""

from __future__ import annotations

import argparse
from functools import partial
import html as html_lib
import http.server
import json
import os
from pathlib import Path
import re
import socket
import socketserver
import sys
import threading
import time
from urllib.parse import parse_qs, urlparse
import urllib.request
import webbrowser

STUDIO_ROOT = Path(__file__).resolve().parent
if str(STUDIO_ROOT) not in sys.path:
    sys.path.insert(0, str(STUDIO_ROOT))

# Probe optional NumPy live neural engine (gracefully degrades to static HTTP portal if numpy is absent)
LIVE_ENGINE_AVAILABLE = False
LIVE_ENGINE_ERROR = ""
try:
    import numpy as _np  # noqa: F401
    from studio_engine.bite_biomarker_and_expansion import load_bite_biomarker_atlas
    from studio_engine.live_engines import (
        PortableDiseaseToDrugEngine,
        PortableStudioRuntime,
        parse_target_spec_string,
        score_inductive_asset_portable,
    )
    from studio_engine.option1_protocol_and_omics import load_option1_empirical_bundle

    LIVE_ENGINE_AVAILABLE = (STUDIO_ROOT / "engine_data" / "pack_tensors_fp16.npz").exists()
except Exception as _exc:  # pragma: no cover
    LIVE_ENGINE_ERROR = str(_exc)


# Explicit cross-platform MIME map (immune to Windows 11 Registry `.js -> text/plain` issues)
EXPLICIT_MIME_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".htm": "text/html; charset=utf-8",
    ".js": "application/javascript; charset=utf-8",
    ".mjs": "application/javascript; charset=utf-8",
    ".css": "text/css; charset=utf-8",
    ".json": "application/json; charset=utf-8",
    ".svg": "image/svg+xml",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".ico": "image/x-icon",
    ".md": "text/markdown; charset=utf-8",
    ".txt": "text/plain; charset=utf-8",
}


def render_markdown_guide_html(title: str, md_text: str) -> bytes:
    """Lightweight self-contained Markdown-to-HTML viewer for `demo_guides/*.md`."""
    lines = md_text.splitlines()
    out = []
    in_code = False
    in_ul = False
    in_table = False

    def _inline(s: str) -> str:
        s = html_lib.escape(s)
        s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
        s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
        s = re.sub(r"\*([^*]+)\*", r"<em>\1</em>", s)
        return s

    for raw in lines:
        if raw.strip().startswith("```"):
            if in_ul:
                out.append("</ul>"); in_ul = False
            if in_table:
                out.append("</tbody></table>"); in_table = False
            if not in_code:
                out.append("<pre><code>"); in_code = True
            else:
                out.append("</code></pre>"); in_code = False
            continue
        if in_code:
            out.append(html_lib.escape(raw))
            continue

        stripped = raw.strip()
        if stripped.startswith("|") and stripped.endswith("|"):
            if in_ul:
                out.append("</ul>"); in_ul = False
            cells = [_inline(c.strip()) for c in stripped.strip("|").split("|")]
            if all(re.match(r"^[-:\s]+$", c) for c in stripped.strip("|").split("|")):
                continue
            if not in_table:
                out.append("<table><thead><tr>" + "".join(f"<th>{c}</th>" for c in cells) + "</tr></thead><tbody>")
                in_table = True
            else:
                out.append("<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>")
            continue
        elif in_table:
            out.append("</tbody></table>"); in_table = False

        if not stripped:
            if in_ul:
                out.append("</ul>"); in_ul = False
            continue
        if stripped == "---":
            out.append("<hr>")
        elif stripped.startswith("# "):
            out.append(f"<h1>{_inline(stripped[2:])}</h1>")
        elif stripped.startswith("## "):
            out.append(f"<h2>{_inline(stripped[3:])}</h2>")
        elif stripped.startswith("### "):
            out.append(f"<h3>{_inline(stripped[4:])}</h3>")
        elif stripped.startswith("#### "):
            out.append(f"<h4>{_inline(stripped[5:])}</h4>")
        elif stripped.startswith("> "):
            out.append(f"<blockquote>{_inline(stripped[2:])}</blockquote>")
        elif stripped.startswith(("- ", "* ")):
            if not in_ul:
                out.append("<ul>"); in_ul = True
            out.append(f"<li>{_inline(stripped[2:])}</li>")
        else:
            out.append(f"<p>{_inline(stripped)}</p>")

    if in_ul:
        out.append("</ul>")
    if in_table:
        out.append("</tbody></table>")
    if in_code:
        out.append("</code></pre>")

    body = "\n".join(out)
    doc = f"""<!DOCTYPE html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{html_lib.escape(title)}</title>
<style>
  body {{ margin:0; background:#0f172a; color:#e2e8f0; font:15px/1.7 "Segoe UI",Inter,system-ui,"PingFang SC","Microsoft YaHei",sans-serif; }}
  .bar {{ position:sticky; top:0; background:rgba(15,23,42,0.95); border-bottom:1px solid #334155; padding:12px 24px; display:flex; gap:16px; align-items:center; }}
  .bar a {{ color:#38bdf8; text-decoration:none; font-weight:600; font-size:13.5px; }}
  .wrap {{ max-width:980px; margin:0 auto; padding:28px 24px 64px; }}
  h1,h2,h3,h4 {{ color:#f8fafc; line-height:1.3; }}
  h1 {{ font-size:26px; border-bottom:1px solid #334155; padding-bottom:12px; }}
  h2 {{ font-size:20px; margin-top:30px; color:#7dd3fc; }}
  code {{ background:#1e293b; color:#bae6fd; padding:2px 6px; border-radius:5px; font-family:Consolas,Menlo,monospace; font-size:13px; }}
  pre {{ background:#1e293b; padding:14px; border-radius:10px; overflow-x:auto; border:1px solid #334155; }}
  pre code {{ background:none; padding:0; }}
  blockquote {{ margin:14px 0; padding:10px 16px; border-left:4px solid #38bdf8; background:#1e293b; border-radius:0 8px 8px 0; }}
  table {{ width:100%; border-collapse:collapse; margin:16px 0; font-size:13.5px; }}
  th,td {{ border:1px solid #334155; padding:8px 11px; text-align:left; vertical-align:top; }}
  th {{ background:#1e293b; color:#f8fafc; }}
  hr {{ border:none; border-top:1px solid #334155; margin:24px 0; }}
</style></head><body>
<div class="bar">
  <a href="index.html">&larr; Visualization Hub</a>
  <a href="AMG757_Tarlatamab_Indication_Expansion_Studio.html">AMG 757 Studio</a>
  <a href="AMG691_CD30_Combination_Discovery_Studio.html">AMG 691 Studio</a>
</div>
<div class="wrap">{body}</div></body></html>"""
    return doc.encode("utf-8")


class PortableStudioHandler(http.server.SimpleHTTPRequestHandler):
    def __init__(self, *args, runtime=None, d2d_engine=None, server_ref=None, **kwargs):
        self._runtime = runtime
        self._d2d_engine = d2d_engine
        self._server_ref = server_ref
        super().__init__(*args, directory=str(STUDIO_ROOT), **kwargs)

    def guess_type(self, path: str) -> str:
        ext = os.path.splitext(path)[1].lower()
        if ext in EXPLICIT_MIME_TYPES:
            return EXPLICIT_MIME_TYPES[ext]
        return super().guess_type(path)

    def log_message(self, fmt: str, *args) -> None:
        # Keep console clean while showing important API calls
        msg = fmt % args
        if "/api/" in msg or " 404 " in msg or " 500 " in msg:
            sys.stdout.write(f"[Studio] {msg}\n")
            sys.stdout.flush()

    def do_GET(self) -> None:
        parsed = urlparse(self.path)
        p = parsed.path

        # Friendly short aliases
        if p in ("/amg757", "/amg757/"):
            self._redirect("/AMG757_Tarlatamab_Indication_Expansion_Studio.html")
            return
        if p in ("/amg691", "/amg691/"):
            self._redirect("/AMG691_CD30_Combination_Discovery_Studio.html")
            return
        if p in ("/portal", "/portal/"):
            q = ("?" + parsed.query) if parsed.query else ""
            self._redirect("/Full_Portfolio_47_Assets_Discovery_Portal.html" + q)
            return
        if p in ("/slides", "/slides/"):
            self._redirect("/OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck.html")
            return

        if p == "/guide":
            qs = parse_qs(parsed.query)
            fname = os.path.basename((qs.get("file") or [""])[0].strip())
            gp = STUDIO_ROOT / "demo_guides" / fname
            if not fname or not gp.exists():
                self._send_json({"error": f"Guide not found: {fname}"}, code=404)
                return
            raw_html = render_markdown_guide_html(fname, gp.read_text(encoding="utf-8"))
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(raw_html)))
            self.end_headers()
            self.wfile.write(raw_html)
            return

        if p == "/api/health":
            self._send_json(
                {
                    "status": "ok",
                    "service": "Amgen Translational Discovery Studio (Portable)",
                    "platform": sys.platform,
                    "python": sys.version.split()[0],
                    "studio_root": str(STUDIO_ROOT),
                    "explorer_bundle_ready": (STUDIO_ROOT / "explorer_data" / "bundle_summary.json").exists(),
                    "live_engine_available": LIVE_ENGINE_AVAILABLE,
                    "live_engine_note": "" if LIVE_ENGINE_AVAILABLE else f"Install numpy for live scoring ({LIVE_ENGINE_ERROR})",
                }
            )
            return

        if p == "/api/shutdown":
            client_ip = self.client_address[0] if self.client_address else ""
            if client_ip not in ("127.0.0.1", "::1"):
                self._send_json({"error": "Forbidden"}, code=403)
                return
            self._send_json({"status": "shutting_down"})
            if self._server_ref is not None:
                threading.Thread(target=self._server_ref.shutdown, daemon=True).start()
            return

        if p == "/api/explorer/embeddings":
            emb_p = STUDIO_ROOT / "explorer_data" / "embeddings_2d.json"
            if not emb_p.exists():
                self._send_json({"error": "embeddings_2d.json not found"}, code=404)
                return
            self._send_file(emb_p)
            return

        if p == "/api/explorer/asset":
            qs = parse_qs(parsed.query)
            key = os.path.basename((qs.get("key") or [""])[0].strip())
            asset_p = STUDIO_ROOT / "explorer_data" / "assets" / f"{key}.json"
            if not key or not asset_p.exists():
                self._send_json({"error": f"Unknown Amgen asset key '{key}'"}, code=404)
                return
            self._send_file(asset_p)
            return

        if p == "/api/bite_biomarker_atlas":
            if not LIVE_ENGINE_AVAILABLE:
                self._send_json({"error": "NumPy live engine not installed"}, code=503)
                return
            self._send_json(load_bite_biomarker_atlas())
            return

        if p == "/api/amg757_option1_dossiers":
            if not LIVE_ENGINE_AVAILABLE:
                emp_p = STUDIO_ROOT / "engine_data" / "option1_empirical_bundle.json"
                if emp_p.exists():
                    self._send_file(emp_p)
                    return
                self._send_json({"error": "Bundle not found"}, code=404)
                return
            self._send_json(load_option1_empirical_bundle())
            return

        if p == "/api/explorer/disease_to_drugs":
            if not LIVE_ENGINE_AVAILABLE or self._d2d_engine is None:
                self._send_json(
                    {"error": "Live Disease->Drug engine requires Python `numpy`. Run `pip install numpy`."},
                    code=503,
                )
                return
            qs = parse_qs(parsed.query)
            did = (qs.get("disease_id") or [""])[0].strip()
            scope = (qs.get("scope") or ["all"])[0].strip().lower()
            top_n = int((qs.get("top_n") or ["60"])[0])
            try:
                res = self._d2d_engine.query_disease(disease_id=did, scope=scope, top_n=top_n)
                self._send_json(res)
            except Exception as exc:
                self._send_json({"error": str(exc)}, code=400)
            return

        if p == "/api/score_new_asset":
            if not LIVE_ENGINE_AVAILABLE or self._runtime is None:
                self._send_json(
                    {"error": "Live target scoring requires Python `numpy`. Run `pip install numpy`."},
                    code=503,
                )
                return
            qs = parse_qs(parsed.query)
            name = (qs.get("name") or ["AMG-CUSTOM"])[0]
            targets = (qs.get("targets") or ["DLL3:binds,CD3E:activates"])[0]
            modality = (qs.get("modality") or ["Bispecific T-Cell Engager (BiTE)"])[0]
            try:
                res = score_inductive_asset_portable(
                    runtime=self._runtime,
                    asset_name=name,
                    target_specs=parse_target_spec_string(targets),
                    modality=modality,
                )
                self._send_json(res)
            except Exception as exc:
                self._send_json({"error": str(exc)}, code=400)
            return

        super().do_GET()

    def _redirect(self, location: str) -> None:
        self.send_response(302)
        self.send_header("Location", location)
        self.end_headers()

    def _send_file(self, filepath: Path) -> None:
        raw = filepath.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Cache-Control", "public, max-age=300")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)

    def _send_json(self, obj: object, code: int = 200) -> None:
        raw = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(raw)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(raw)


class PortableTCPServer(socketserver.ThreadingMixIn, socketserver.TCPServer):
    allow_reuse_address = True
    daemon_threads = True


def _check_existing_studio(host: str, port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://{host}:{port}/api/health", timeout=0.8) as resp:
            if resp.status == 200:
                data = json.loads(resp.read().decode("utf-8"))
                return "Amgen Translational Discovery Studio" in str(data.get("service", ""))
    except Exception:
        return False
    return False


def _find_free_port(host: str, preferred: int) -> int:
    for cand in range(preferred, preferred + 25):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
            if s.connect_ex((host, cand)) != 0:
                return cand
    raise RuntimeError(f"No free local TCP port found in {preferred}..{preferred + 24}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Portable Cross-Platform Visualization Studio (Windows 11 + Linux)")
    parser.add_argument("--host", default="127.0.0.1", help="Bind address (default 127.0.0.1 avoids Windows Firewall prompt)")
    parser.add_argument("--port", type=int, default=8004, help="Preferred local port (default 8004)")
    parser.add_argument("--open-browser", action="store_true", help="Automatically open default web browser")
    parser.add_argument("--page", default="", help="Optional initial page (e.g. AMG757_Tarlatamab_Indication_Expansion_Studio.html)")
    parser.add_argument("--no-warmup", action="store_true", help="Lazy-load neural tensors on first API request instead of startup")
    parser.add_argument("--check", action="store_true", help="Run self-contained health & parity self-test and exit")
    args = parser.parse_args()

    if args.check:
        print(f"[Check] Studio root        : {STUDIO_ROOT}")
        print(f"[Check] Platform / Python  : {sys.platform} / {sys.version.split()[0]}")
        print(f"[Check] Live NumPy engine  : {LIVE_ENGINE_AVAILABLE} {LIVE_ENGINE_ERROR}")
        req_files = [
            "index.html",
            "AMG757_Tarlatamab_Indication_Expansion_Studio.html",
            "AMG691_CD30_Combination_Discovery_Studio.html",
            "Full_Portfolio_47_Assets_Discovery_Portal.html",
            "OptimusKG_Models_Apps_AMG757_AMG691_Slide_Deck.html",
            "d3.v7.min.js",
            "studio_data.json",
            "explorer_data/embeddings_2d.json",
            "explorer_data/assets/tarlatamab.json",
            "explorer_data/assets/amg_691.json",
        ]
        for rf in req_files:
            assert (STUDIO_ROOT / rf).exists(), f"Missing required file: {rf}"
        if LIVE_ENGINE_AVAILABLE:
            rt = PortableStudioRuntime(str(STUDIO_ROOT))
            d2d = PortableDiseaseToDrugEngine(rt)
            r1 = d2d.query_disease("MONDO_0008433", scope="amgen", top_n=5)
            r2 = score_inductive_asset_portable(rt, "AMG757-CHECK", [("DLL3", "binds"), ("CD3E", "activates")], "BiTE", top_diseases=5, top_combos=3)
            print(f"[Check] Disease->Drug SCLC top-1 Amgen : {r1['drugs'][0]['drug_name']} ({r1['elapsed_ms']} ms)")
            print(f"[Check] Score New Target DLL3xCD3 #1   : {r2['goal1_top_repurposed_diseases'][0]['disease_name']} ({r2['elapsed_seconds']} s)")
        print("[Check] ALL PORTABLE STUDIO CHECKS PASSED.")
        return

    # If an instance of this Studio is already running on `args.port`, reuse it cleanly!
    if _check_existing_studio(args.host, args.port):
        url = f"http://{args.host}:{args.port}/{args.page.lstrip('/')}"
        print(f"[Portable Visualization Studio] Existing server detected at {url}", flush=True)
        if args.open_browser:
            try:
                webbrowser.open(url)
            except Exception:
                pass
        return

    port = _find_free_port(args.host, args.port)
    runtime = PortableStudioRuntime(str(STUDIO_ROOT)) if LIVE_ENGINE_AVAILABLE else None
    d2d = PortableDiseaseToDrugEngine(runtime) if (LIVE_ENGINE_AVAILABLE and runtime is not None) else None

    if d2d is not None and not args.no_warmup:
        d2d.ensure_loaded()

    httpd_holder = {}
    handler = partial(PortableStudioHandler, runtime=runtime, d2d_engine=d2d)
    with PortableTCPServer((args.host, port), handler) as httpd:
        # Attach server reference for localhost-only `/api/shutdown`
        httpd.RequestHandlerClass = partial(
            PortableStudioHandler, runtime=runtime, d2d_engine=d2d, server_ref=httpd
        )
        url = f"http://{args.host}:{port}/{args.page.lstrip('/')}"
        print("=" * 74)
        print(" OptimusKG — AMG 757 & AMG 691 Portable Visualization Studio")
        print(f" OS / Python : {sys.platform} / Python {sys.version.split()[0]}")
        print(f" Folder      : {STUDIO_ROOT}")
        print(f" Live Engine : {'ENABLED (Pure-NumPy FP16)' if LIVE_ENGINE_AVAILABLE else 'STATIC HTTP ONLY (pip install numpy for live scoring)'}")
        print(f" Hub URL     : {url}")
        print(f" AMG 757 URL : http://{args.host}:{port}/AMG757_Tarlatamab_Indication_Expansion_Studio.html")
        print(f" AMG 691 URL : http://{args.host}:{port}/AMG691_CD30_Combination_Discovery_Studio.html")
        print(" Press Ctrl+C (or run Stop_Visualization_Windows.bat / stop_visualization_linux.sh) to stop.")
        print("=" * 74, flush=True)

        if args.open_browser:
            threading.Timer(0.4, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\n[Portable Visualization Studio] Stopped cleanly.")


if __name__ == "__main__":
    main()
