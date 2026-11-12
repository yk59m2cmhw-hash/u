#!/usr/bin/env python3
"""Weighted niche scoring (strategy/niches.csv). Standard library only.

  python3 tools/niches.py                       # ranking as a Markdown table
  python3 tools/niches.py --access clinics=5    # re-score with your real access to a niche

Each criterion is scored 1-5 (5 = best for us); the total is a weighted score out of 100.
"""
import argparse
import csv
import pathlib

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "strategy" / "niches.csv"

# criterion -> (weight, Russian label). Weights sum to 100.
CRITERIA = {
    "pain": (15, "Боль и частота"),
    "wtp": (15, "Готовность платить"),
    "access": (20, "Доступ к клиентам"),
    "competition": (10, "Мало конкурентов"),
    "regulation": (10, "Простая регуляторика"),
    "own_model": (5, "Польза своей модели"),
    "pilot_speed": (15, "Скорость пилота"),
    "market": (10, "Размер рынка"),
}
assert sum(w for w, _ in CRITERIA.values()) == 100


def load(path=CSV_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        for k in CRITERIA:
            r[k] = int(r[k])
            if not 1 <= r[k] <= 5:
                raise ValueError(f"{r['id']}: {k}={r[k]} not in 1..5")
    return rows


def score(row):
    return sum(w * row[k] for k, (w, _) in CRITERIA.items()) / 5


def rank(rows, overrides=None):
    """overrides: {niche_id: {criterion: value}}"""
    out = []
    for r in rows:
        r = dict(r)
        for k, v in (overrides or {}).get(r["id"], {}).items():
            r[k] = v
        out.append((score(r), r))
    return sorted(out, key=lambda t: (-t[0], t[1]["id"]))


def markdown(ranked):
    head = "| # | Ниша | " + " | ".join(f"{lbl} ({w})" for w, lbl in CRITERIA.values()) + " | Итого |"
    lines = [head, "|" + "---|" * (len(CRITERIA) + 3)]
    for i, (s, r) in enumerate(ranked, 1):
        lines.append(f"| {i} | {r['niche']} | " + " | ".join(str(r[k]) for k in CRITERIA) + f" | **{s:.0f}** |")
    return "\n".join(lines)


def main(argv=None):
    ap = argparse.ArgumentParser(description="Rank niches by weighted score")
    ap.add_argument("--access", action="append", default=[],
                    help="override access score, e.g. clinics=5 (repeatable)")
    args = ap.parse_args(argv)
    overrides = {}
    for item in args.access:
        nid, val = item.split("=")
        overrides.setdefault(nid, {})["access"] = int(val)
    print(markdown(rank(load(), overrides)))


if __name__ == "__main__":
    main()
