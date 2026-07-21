"""Lightweight drug-drug interaction check (keyword/class based, demo-grade)."""
from __future__ import annotations

# Each rule: (drug A keywords, drug B keywords, severity, note)
_RULES = [
    (["warfarin"], ["aspirin", "ibuprofen", "naproxen", "clopidogrel"], "major",
     "Increased bleeding risk when anticoagulant is combined with antiplatelet/NSAID."),
    (["aspirin"], ["ibuprofen", "naproxen"], "moderate",
     "NSAIDs may reduce the cardioprotective effect of aspirin and increase GI bleeding."),
    (["clopidogrel"], ["omeprazole", "esomeprazole"], "moderate",
     "PPIs can reduce clopidogrel activation and antiplatelet effect."),
    (["lisinopril", "enalapril", "ramipril", "losartan", "valsartan"],
     ["potassium", "spironolactone", "triamterene"], "moderate",
     "ACE/ARB with potassium-sparing agents can cause hyperkalemia."),
    (["simvastatin", "atorvastatin", "rosuvastatin", "lovastatin"],
     ["clarithromycin", "erythromycin", "amiodarone", "gemfibrozil"], "major",
     "CYP3A4/transporter inhibition raises statin levels and myopathy risk."),
    (["metformin"], ["contrast"], "moderate",
     "Hold metformin around iodinated contrast to reduce lactic-acidosis risk."),
    (["insulin", "glipizide", "glyburide", "glimepiride"], ["metoprolol", "atenolol", "carvedilol"],
     "moderate", "Beta-blockers can mask hypoglycemia symptoms."),
]


def _matches(display: str, keywords: list[str]) -> bool:
    d = display.lower()
    return any(k in d for k in keywords)


def check_interactions(medications: list[dict]) -> list[dict]:
    active = [m for m in medications if m.get("status") == "active" and m.get("display")]
    found: list[dict] = []
    for i, a in enumerate(active):
        for b in active[i + 1:]:
            for ka, kb, severity, note in _RULES:
                a_first = _matches(a["display"], ka) and _matches(b["display"], kb)
                b_first = _matches(b["display"], kb) and _matches(a["display"], ka)
                rev = _matches(a["display"], kb) and _matches(b["display"], ka)
                if a_first or b_first or rev:
                    found.append({
                        "drugA": a["display"], "drugB": b["display"],
                        "severity": severity, "note": note,
                    })
                    break
    return found
