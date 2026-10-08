"""Retours constructifs : ce que les gens répondent à un projet (bug, difficulté, idée, compliment...).

Un fichier `retours.csv` par utilisateur ; le résumé groupe par type et par fréquence pour alimenter un backlog.
Aucun pseudo Reddit n'est stocké : seulement la communauté ou la source, la date et le texte (paraphrasé de préférence).
"""
from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

KINDS = ("bug", "difficulte", "interface", "contenu", "idee", "compliment", "autre")
FIELDS = ["date", "project", "source", "kind", "severity", "text", "status"]
STATUSES = ("nouveau", "retenu", "fait", "ecarte")


class FeedbackError(ValueError):
    pass


def _read(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    with path.open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def _write(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def add(path: Path, day: str, project: str, source: str, kind: str, severity: int, text: str) -> dict[str, str]:
    if kind not in KINDS:
        raise FeedbackError(f"type inconnu : {kind} (attendu : {', '.join(KINDS)})")
    if not 1 <= severity <= 3:
        raise FeedbackError("gravité attendue : 1 (confort), 2 (gêne) ou 3 (bloque ou décourage)")
    text = " ".join(text.split())
    if len(text) < 8:
        raise FeedbackError("texte trop court pour être utile")
    row = {"date": day, "project": project, "source": source.removeprefix("r/")[:80], "kind": kind,
           "severity": str(severity), "text": text[:400], "status": "nouveau"}
    rows = _read(path)
    rows.append(row)
    _write(path, rows)
    return row


def set_status(path: Path, index: int, status: str) -> None:
    if status not in STATUSES:
        raise FeedbackError(f"statut inconnu : {status} (attendu : {', '.join(STATUSES)})")
    rows = _read(path)
    if not 1 <= index <= len(rows):
        raise FeedbackError(f"retour n°{index} introuvable")
    rows[index - 1]["status"] = status
    _write(path, rows)


def listing(path: Path, project: str | None = None) -> list[tuple[int, dict[str, str]]]:
    return [(i, r) for i, r in enumerate(_read(path), 1) if project is None or r["project"] == project]


def summary(path: Path, project: str | None = None) -> str:
    """Résumé Markdown : gravité décroissante, puis fréquence par type ; prêt à copier dans un backlog."""
    items = [(i, r) for i, r in listing(path, project) if r["status"] != "ecarte"]
    if not items:
        return "Aucun retour enregistré."
    kinds = Counter(r["kind"] for _i, r in items)
    lines = [f"# Retours{' : ' + project if project else ''} ({len(items)})", "",
             "Par type : " + ", ".join(f"{k} {n}" for k, n in kinds.most_common()), ""]
    for severity in (3, 2, 1):
        group = [(i, r) for i, r in items if int(r["severity"]) == severity]
        if not group:
            continue
        lines.append({3: "## Bloque ou décourage", 2: "## Gêne", 1: "## Confort et idées"}[severity])
        for i, r in group:
            lines.append(f"- n°{i} [{r['kind']}] ({r['source'] or 'direct'}, {r['date']}, {r['status']}) {r['text']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
