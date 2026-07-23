"""RAG chat: hybrid retrieval over patients -> gpt-5.5 grounded answer with citations."""
from __future__ import annotations

from ..search.service import hybrid_search
from . import grove

DEFAULT_K = 6


def _format_patient(p: dict) -> str:
    conds = ", ".join(
        c["display"] for c in p.get("conditions", [])
        if c.get("clinicalStatus") == "active" and c.get("category") == "clinical"
    )[:400]
    meds = ", ".join(m["display"] for m in p.get("medications", []) if m.get("status") == "active")[:400]
    lines = [
        f"[patientId: {p['_id']}] {p['name']['full']} — {p.get('age')}yo {p.get('gender')}",
        f"  Summary: {p.get('summaryText', '')}",
    ]
    if conds:
        lines.append(f"  Active conditions: {conds}")
    if meds:
        lines.append(f"  Active medications: {meds}")
    return "\n".join(lines)


def _instructions(tenant_name: str | None) -> str:
    who = f"the {tenant_name} patient portal" if tenant_name else "a patient portal"
    return (
        f"You are a helpful clinical assistant for {who}. "
        "Answer the user's question using ONLY the provided patient context. "
        "Cite the patients you use by name and patientId in parentheses, e.g. (Jane Doe, <id>). "
        "If the context does not contain enough information, say so plainly. "
        "Be concise and accurate; do not invent clinical facts."
    )


def chat(question: str, tenant_name: str | None = None, k: int = DEFAULT_K) -> dict:
    patients = hybrid_search(question, limit=k)
    if not patients:
        return {
            "answer": "I couldn't find any matching patients. Try loading a batch of patients first.",
            "citations": [], "retrieved": [],
        }
    context = "\n\n".join(_format_patient(p) for p in patients)
    prompt = f"Question: {question}\n\nPatient context:\n{context}"
    answer = grove.respond(prompt, instructions=_instructions(tenant_name))
    citations = [{"patientId": p["_id"], "name": p["name"]["full"]} for p in patients]
    return {
        "answer": answer,
        "citations": citations,
        "retrieved": [
            {"patientId": p["_id"], "name": p["name"]["full"], "age": p.get("age"),
             "score": round(p.get("score", 0), 4)}
            for p in patients
        ],
    }
