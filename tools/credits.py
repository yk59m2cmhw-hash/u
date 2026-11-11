#!/usr/bin/env python3
"""Query the startup-credits database (research/credits/programs.csv).

Standard library only. Examples:

  python3 tools/credits.py validate
  python3 tools/credits.py list --phase P1 --sort amount --limit 15
  python3 tools/credits.py list --phase P0,P1 --gpu --format md
  python3 tools/credits.py summary
  python3 tools/credits.py export-json

Phases are cumulative: P0 = possible today without a company; P1 = after a legal
entity, website and domain email; P2 = after an MVP / first traction; P3 = after an
institutional investor or accelerator. "--phase P2" means "what is available once you
reach P2", i.e. P0+P1+P2.

All amounts are published ceilings ("up to"), not what a startup will receive.
"""
import argparse
import csv
import json
import pathlib
import sys
from collections import defaultdict

ROOT = pathlib.Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "research" / "credits" / "programs.csv"
JSON_PATH = ROOT / "research" / "credits" / "programs.json"

FIELDS = [
    "id", "provider", "program", "category", "tier", "max_credits_usd", "validity_months",
    "self_serve", "requires_entity", "requires_funding", "requires_partner_code",
    "company_age_limit", "gpu_eligible", "covers_ai_apis", "prohibited_uses",
    "prior_credits_rule", "excluded_countries", "application_url", "source_url",
    "verified_on", "confidence", "phase", "priority", "notes",
]
PHASES = ["P0", "P1", "P2", "P3"]
TRI = {"yes", "no", "partial", "unknown"}
CONFIDENCE = {"high", "medium", "low"}
CATEGORIES = {"hyperscaler", "gpu-cloud", "cloud", "ai-api", "dev-tools", "saas",
              "free-tier", "regional", "subsidized-compute"}


def load(path=CSV_PATH):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    for r in rows:
        r["max_credits_usd"] = int(r["max_credits_usd"]) if r["max_credits_usd"].strip() else 0
        r["priority"] = int(r["priority"]) if r["priority"].strip() else 5
    return rows


def validate(rows):
    """Return a list of human-readable problems (empty list = valid)."""
    problems, seen = [], set()
    for i, r in enumerate(rows, 2):  # line 1 is the header
        rid = r.get("id", "")
        where = f"line {i} ({rid or 'no id'})"
        if not rid:
            problems.append(f"{where}: empty id")
        elif rid in seen:
            problems.append(f"{where}: duplicate id")
        seen.add(rid)
        if set(r) != set(FIELDS):
            problems.append(f"{where}: columns differ from the schema")
            continue
        for k in ("self_serve", "requires_entity", "requires_funding", "requires_partner_code",
                  "gpu_eligible", "covers_ai_apis"):
            if r[k] not in TRI:
                problems.append(f"{where}: {k}={r[k]!r} not in {sorted(TRI)}")
        if r["confidence"] not in CONFIDENCE:
            problems.append(f"{where}: confidence={r['confidence']!r}")
        if r["phase"] not in PHASES:
            problems.append(f"{where}: phase={r['phase']!r}")
        if r["category"] not in CATEGORIES:
            problems.append(f"{where}: category={r['category']!r}")
        if not 1 <= int(r["priority"]) <= 5:
            problems.append(f"{where}: priority out of 1..5")
        for k in ("application_url", "source_url"):
            if r[k] and not r[k].startswith("https://"):
                problems.append(f"{where}: {k} must start with https://")
        if r["confidence"] == "high" and not r["verified_on"]:
            problems.append(f"{where}: high confidence needs verified_on")
    return problems


def available_by(rows, phase):
    """Programs reachable once the startup is at `phase` (phases are cumulative)."""
    limit = PHASES.index(phase)
    return [r for r in rows if PHASES.index(r["phase"]) <= limit]


COMPUTE = {"hyperscaler", "cloud", "gpu-cloud", "ai-api"}


def summary(rows, categories=None):
    """Per phase: count, naive sum of ceilings, and a conservative sum that keeps only the
    largest program per provider (tiers of one provider are usually alternatives)."""
    out = []
    for ph in PHASES:
        avail = [r for r in available_by(rows, ph) if r["max_credits_usd"] > 0
                 and (not categories or r["category"] in categories)]
        best = defaultdict(int)
        for r in avail:
            best[r["provider"]] = max(best[r["provider"]], r["max_credits_usd"])
        out.append({
            "phase": ph,
            "programs": len(avail),
            "sum_of_ceilings_usd": sum(r["max_credits_usd"] for r in avail),
            "best_per_provider_usd": sum(best.values()),
            "providers": len(best),
        })
    return out


def select(rows, phase=None, gpu=False, self_serve=False, min_usd=0, category=None,
           max_priority=5):
    res = available_by(rows, phase) if phase else list(rows)
    if gpu:
        res = [r for r in res if r["gpu_eligible"] in ("yes", "partial")]
    if self_serve:
        res = [r for r in res if r["self_serve"] == "yes"]
    if min_usd:
        res = [r for r in res if r["max_credits_usd"] >= min_usd]
    if category:
        cats = set(category.split(","))
        res = [r for r in res if r["category"] in cats]
    return [r for r in res if r["priority"] <= max_priority]


def sort_rows(rows, key):
    if key == "amount":
        return sorted(rows, key=lambda r: (-r["max_credits_usd"], r["priority"], r["id"]))
    return sorted(rows, key=lambda r: (r["priority"], -r["max_credits_usd"], r["id"]))


def usd(n):
    return f"${n:,}" if n else "—"


def to_markdown(rows):
    lines = ["| # | Provider | Program | Phase | Up to | GPU | Self-serve | Confidence |",
             "|---|---|---|---|---|---|---|---|"]
    for i, r in enumerate(rows, 1):
        lines.append(f"| {i} | {r['provider']} | {r['program']}{' — ' + r['tier'] if r['tier'] else ''} "
                     f"| {r['phase']} | {usd(r['max_credits_usd'])} | {r['gpu_eligible']} "
                     f"| {r['self_serve']} | {r['confidence']} |")
    return "\n".join(lines)


def summary_markdown(rows, categories=None):
    lines = ["| Phase | Programs with credits | Providers | Sum of ceilings | Best program per provider |",
             "|---|---|---|---|---|"]
    for s in summary(rows, categories):
        lines.append(f"| {s['phase']} | {s['programs']} | {s['providers']} | "
                     f"{usd(s['sum_of_ceilings_usd'])} | {usd(s['best_per_provider_usd'])} |")
    return "\n".join(lines)


def export_json(rows, path=JSON_PATH):
    path.write_text(json.dumps(rows, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    return path


def main(argv=None):
    ap = argparse.ArgumentParser(description="Startup credits database tool")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    sm = sub.add_parser("summary")
    sm.add_argument("--compute", action="store_true",
                    help="only compute credits (hyperscaler, cloud, gpu-cloud, ai-api), no SaaS perks")
    sub.add_parser("export-json")
    ls = sub.add_parser("list")
    ls.add_argument("--phase", help="P0..P3; cumulative (P2 = P0+P1+P2)")
    ls.add_argument("--gpu", action="store_true", help="only programs usable for GPUs")
    ls.add_argument("--self-serve", action="store_true")
    ls.add_argument("--min", type=int, default=0, help="minimum ceiling in USD")
    ls.add_argument("--category")
    ls.add_argument("--max-priority", type=int, default=5)
    ls.add_argument("--sort", choices=["priority", "amount"], default="priority")
    ls.add_argument("--limit", type=int, default=0)
    ls.add_argument("--format", choices=["md", "ids"], default="md")
    args = ap.parse_args(argv)

    rows = load()
    if args.cmd == "validate":
        problems = validate(rows)
        print("\n".join(problems) if problems else f"OK: {len(rows)} programs, schema valid")
        return 1 if problems else 0
    if args.cmd == "summary":
        print(summary_markdown(rows, COMPUTE if args.compute else None))
        print("\nCeilings are 'up to' amounts; real awards are usually lower and need approval.")
        return 0
    if args.cmd == "export-json":
        print(f"wrote {export_json(rows).relative_to(ROOT)}")
        return 0
    res = sort_rows(select(rows, args.phase, args.gpu, args.self_serve, args.min,
                           args.category, args.max_priority), args.sort)
    if args.limit:
        res = res[:args.limit]
    print(to_markdown(res) if args.format == "md" else "\n".join(r["id"] for r in res))
    return 0


if __name__ == "__main__":
    sys.exit(main())
