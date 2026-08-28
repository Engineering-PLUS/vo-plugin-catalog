#!/usr/bin/env python3
"""
merge_pins.py, fold one PlanGrid pin's photos into another pin's item record.

STATUS: shipped. Used to produce Miner Building A r4 and r5.

Why this exists
---------------
The pipeline keys an item to a PlanGrid pin number, one to one. A reviewer
sometimes decides two pins are one finding and merges them by hand in Word,
which the pipeline cannot represent: re-running it would split the merged item
back into two and silently discard the reviewer's decision.

On Miner Building A the reviewer merged pins 22 and 23 into a single item,
"Security Rough-In Incomplete (Multiple Locations)", and dropped one of pin 23's
three photos. This script reproduces that decision as data, so a re-run lands in
the same place instead of undoing it.

The merged-away pin is then excluded from the render with
    build_master.py --omit 23
which keeps it visible in items.json for traceability while keeping it off the
page.

SUGGESTED IMPROVEMENT: promote this to a `merges` block inside
drafted_items.json that build_master.py reads directly, so the merge lives with
the rest of the judgment layer rather than as a mutation of items.json. See
CHANGE-LIST.md item 6.

Usage:
    python3 merge_pins.py --items data/items.json --into 22 --from 23 \
        [--drop-photo 20260820_162330_photo] ...
"""
import argparse
import json


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--items", default="data/items.json")
    ap.add_argument("--into", type=int, required=True,
                    help="pin number that keeps the item")
    ap.add_argument("--from", dest="src", type=int, required=True,
                    help="pin number whose photos are folded in")
    ap.add_argument("--drop-photo", action="append", default=[],
                    help="photo title substring to exclude; repeatable")
    ap.add_argument("--dry-run", action="store_true")
    args = ap.parse_args()

    items = json.load(open(args.items))
    by_num = {i["number"]: i for i in items}
    for n in (args.into, args.src):
        if n not in by_num:
            raise SystemExit(f"ERROR: pin {n} is not in {args.items}. "
                             f"Check --only scope on consolidate.py.")

    dst, src = by_num[args.into], by_num[args.src]
    have = {p["uid"] for p in dst["photos"]}

    added, dropped = [], []
    for p in src["photos"]:
        title = p.get("title") or ""
        if any(d in title for d in args.drop_photo):
            dropped.append(title)
            continue
        if p["uid"] in have:
            continue
        dst["photos"].append(p)
        added.append(title)

    # Photos are ordered oldest first so the captions read chronologically across
    # the merged set rather than restarting partway through, which is what the
    # hand merge in Word produced.
    dst["photos"].sort(key=lambda p: p.get("captured") or "")
    dst["merged_from"] = sorted(set(dst.get("merged_from", []) + [args.src]))
    dst["photo_count_field"] = len(dst["photos"])

    print(f"pin {args.src} -> pin {args.into}")
    print(f"  added   : {added}")
    print(f"  dropped : {dropped or 'none'}")
    print(f"  pin {args.into} now carries {len(dst['photos'])} photos")
    if args.dry_run:
        print("  (dry run, nothing written)")
        return
    json.dump(items, open(args.items, "w"), indent=2)
    print(f"  wrote {args.items}")


if __name__ == "__main__":
    main()
