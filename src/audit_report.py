"""Build a self-contained, privacy-conscious HTML prediction audit report."""
from __future__ import annotations

from datetime import datetime, timezone
from html import escape
import re

from . import config as C

DISCLAIMER = (
    "Educational research output only. This is not a medical device, diagnosis, "
    "screening result, or an individual's medical probability. Do not use it to "
    "make health decisions. SHAP explains model behavior, not medical causation."
)


def normalize_case_reference(value: str | None) -> str | None:
    """Keep only a short anonymous code; discard names, contact details and free text."""
    candidate = (value or "").strip()
    if re.fullmatch(r"(?:P|CASE|REF)-[A-Z0-9]{1,12}", candidate, re.IGNORECASE):
        return candidate[:20]
    return None


def build_audit_html(result: dict, card: dict, case_reference: str | None = None) -> str:
    """Return an HTML report without names, contact details, or other identifiers."""
    if not result.get("ok"):
        raise ValueError("An audit report requires a valid prediction.")
    contributions = result["explanation"].get("contributions", [])[:5]
    rows = "".join(
        "<tr><td>{}</td><td>{}</td><td>{:+.5f} {}</td><td>{}</td></tr>".format(
            escape(str(item["feature"])), escape(str(item.get("value", "Not measured"))),
            float(item["contribution"]), escape(str(result["explanation"]["units"])),
            "Yes" if item.get("was_missing") else "No")
        for item in contributions
    )
    inputs = "".join(
        f"<li><b>{escape(C.FEATURE_LABELS[feature])}:</b> "
        f"{escape(str(value)) if value is not None else 'Not measured (pipeline imputation)'}</li>"
        for feature, value in result["inputs"].items()
    )
    warnings = "".join(f"<li>{escape(str(warning))}</li>" for warning in result["warnings"]) or "<li>None reported.</li>"
    safe_ref = escape(normalize_case_reference(case_reference) or "Anonymous case")
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Prediction audit report</title><style>
body{{font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif;max-width:900px;margin:36px auto;padding:0 20px;color:#17212b;background:#f6f8fa}}
header,section{{background:white;border:1px solid #dce3e8;border-radius:14px;padding:22px;margin:16px 0}}
h1,h2{{margin-top:0}} h1{{font-size:1.8rem}} .tag{{color:#11866f;font-weight:700;text-transform:uppercase;letter-spacing:.1em;font-size:.75rem}}
.score{{font-size:2rem;font-weight:750;color:#11866f}} table{{border-collapse:collapse;width:100%}}td,th{{padding:9px;border-bottom:1px solid #e5eaee;text-align:left}}
.warning{{background:#fff6e6;border-left:4px solid #e9a33f;padding:14px}} footer{{font-size:.9rem;color:#53616d}}
</style></head><body>
<header><div class="tag">Diabetes Management System · Research audit</div><h1>Single-case model audit</h1>
<p>Generated: {escape(timestamp)} · Case reference: {safe_ref}</p><div class="score">{result['probability']:.1%}</div>
<p>Positive-class model score · predicted dataset class {int(result['label'])} at threshold {result['threshold']:.3f}</p>
<p>Selected model: {escape(str(result['model']))} · Model version: {escape(str(result['model_version']))}</p></header>
<section><h2>Submitted measurements</h2><ul>{inputs}</ul></section>
<section><h2>Local SHAP contributions</h2><p>Units: {escape(str(result['explanation']['units']))}; contributions describe this model output.</p>
<table><thead><tr><th>Feature</th><th>Value</th><th>Contribution</th><th>Imputed</th></tr></thead><tbody>{rows}</tbody></table>
<p>Additivity check error: {float(result['explanation']['additivity_error']):.6g}</p></section>
<section><h2>Validation and range notes</h2><ul>{warnings}</ul></section>
<section><h2>Traceability</h2><ul><li>Model artifact version: {escape(str(card.get('model_version', 'Unavailable')))}</li>
<li>Training dataset canonical SHA-256: {escape(str(card.get('dataset', {}).get('canonical_sha256', 'Unavailable')))}</li>
<li>Trained at: {escape(str(card.get('trained_at', 'Unavailable')))}</li></ul></section>
<section class="warning"><b>Scope and safety</b><p>{escape(DISCLAIMER)}</p>
<p>The benchmark contains 768 historical records from women of Pima heritage aged 21 and older. It has not been externally validated.</p></section>
<footer>No direct identifier is included in this report. Avoid entering real patient records in this educational demonstration.</footer>
</body></html>"""
