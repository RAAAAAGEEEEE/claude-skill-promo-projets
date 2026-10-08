"""Lecteur d'un sous-ensemble volontairement minimal de YAML (aucune dépendance).

Format accepté, dans l'en-tête d'un fichier Markdown encadré par deux lignes `---` :

    cle: valeur
    autre_cle:
      - élément
      - élément

Les valeurs sont des textes, des entiers ou true/false. Les listes ne contiennent que des textes.
Les lignes vides et celles qui commencent par # sont ignorées. Rien d'autre n'est interprété.
"""
from __future__ import annotations

import re
from typing import Any

_KEY = re.compile(r"^([A-Za-z_][A-Za-z0-9_]*):\s*(.*)$")


class MiniYamlError(ValueError):
    pass


def _scalar(raw: str) -> Any:
    value = raw.strip()
    if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
        return value[1:-1]
    if value.lower() in ("true", "false"):
        return value.lower() == "true"
    if re.fullmatch(r"-?\d+", value):
        return int(value)
    return value


def parse_front_matter(text: str) -> tuple[dict[str, Any], str]:
    """Retourne (en-tête, corps). Lève MiniYamlError si l'en-tête est absent ou mal formé."""
    lines = text.lstrip("﻿").splitlines()
    if not lines or lines[0].strip() != "---":
        raise MiniYamlError("en-tête absent : le fichier doit commencer par '---'")
    try:
        end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    except StopIteration:
        raise MiniYamlError("en-tête non fermé : deuxième '---' introuvable") from None
    data: dict[str, Any] = {}
    current: str | None = None
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        stripped = line.strip()
        if stripped.startswith("- ") or stripped == "-":
            if current is None or not isinstance(data.get(current), list):
                raise MiniYamlError(f"ligne {number} : élément de liste sans clé de liste")
            data[current].append(str(_scalar(stripped[1:])))
            continue
        match = _KEY.match(line)
        if not match or line[0] in " \t":
            raise MiniYamlError(f"ligne {number} : forme non reconnue ({stripped[:40]})")
        key, rest = match.group(1), match.group(2)
        if key in data:
            raise MiniYamlError(f"ligne {number} : clé en double ({key})")
        if rest == "":
            data[key] = []
            current = key
        else:
            data[key] = _scalar(rest)
            current = None
    return data, "\n".join(lines[end + 1 :]).strip()
