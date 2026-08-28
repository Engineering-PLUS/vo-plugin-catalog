#!/usr/bin/env python3
"""
consolidate.py, generalized PlanGrid pull consolidator.

Replaces the NVA06B-era script, which hardcoded a single export directory.
Two things changed in the Miner Building A pull that this handles:

  1. Delta folders. A pull may contain `delta_<from>_to_<to>/` holding a LATER,
     SUPERSET tasks.json plus only the NEW photo binaries. The base folder keeps
     the earlier photos. Neither folder alone is complete: you need the delta's
     tasks.json and BOTH photo directories.
  2. Sheet resolution lives in the base. The delta's sheets.json is an empty
     array, so sheet names must be resolved from the base sheets.json.

Usage:
    python3 consolidate.py <project_root> -o data/items.json [--only 11-30]

`--only` accepts ranges and comma lists ("11-30", "2,5,9-12") and scopes the
output to those PlanGrid issue numbers.
"""
import argparse
import glob
import json
import os
import re
import sys
from collections import Counter


def load_json(path, default=None):
    if not os.path.exists(path):
        return default
    with open(path) as fh:
        return json.load(fh)


def parse_only(spec):
    if not spec:
        return None
    keep = set()
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if "-" in chunk:
            lo, hi = chunk.split("-", 1)
            keep.update(range(int(lo), int(hi) + 1))
        else:
            keep.add(int(chunk))
    return keep


def find_deltas(root):
    """
    Every delta folder, oldest first.

    A pull can carry MORE THAN ONE delta. Miner Building A had
    delta_2026-08-14_to_2026-08-24 (30 tasks) and
    delta_2026-08-25_to_2026-08-26 (8 tasks). The later one is NOT a superset:
    it holds only that window's tasks. Taking the newest delta alone dropped
    items 12-30 and every photo belonging to them, with no error.

    Sort by the window start date parsed out of the folder name rather than
    lexically, so the merge order is chronological whatever the naming.
    """
    hits = glob.glob(os.path.join(root, "delta_*_to_*"))
    hits = [h for h in hits if os.path.isdir(h)]

    def key(path):
        m = re.search(r"delta_(\d{4}-\d{2}-\d{2})_to_(\d{4}-\d{2}-\d{2})",
                      os.path.basename(path))
        return (m.group(1), m.group(2)) if m else ("", os.path.basename(path))

    return sorted(hits, key=key)


def index_photo_files(dirs):
    """uid -> absolute path, across every photo directory in the pull."""
    index = {}
    for d in dirs:
        for p in glob.glob(os.path.join(d, "*.jpg")):
            uid = os.path.basename(p).split("__")[0]
            index[uid] = p
    return index


def detect_filler_title(tasks):
    """
    Field staff reuse a marker string as the title on nearly every pin
    ("Jim2" on NVA06B, "General" here). It is a personal bookmark, not content.
    Returns the title to treat as empty, or None.
    """
    titles = [(t.get("title") or "").strip() for t in tasks]
    titles = [t for t in titles if t]
    if not titles:
        return None
    title, count = Counter(titles).most_common(1)[0]
    return title if count >= max(3, 0.5 * len(titles)) else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("project_root")
    ap.add_argument("-o", "--out", default="data/items.json")
    ap.add_argument("--only", default=None, help='e.g. "11-30" or "2,5,9-12"')
    args = ap.parse_args()

    root = os.path.abspath(args.project_root)
    deltas = find_deltas(root)
    keep = parse_only(args.only)

    # Layers, oldest first: the base pull, then every delta in date order.
    # Later layers overwrite earlier ones on collision, so the newest state of
    # a task wins, but nothing that appears only in an older layer is lost.
    layers = [root] + deltas

    # tasks: merged by uid across every layer, keyed so a task revised in a
    # later delta replaces its earlier version rather than duplicating it.
    by_uid = {}
    for layer in layers:
        for t in load_json(os.path.join(layer, "tasks.json"), []) or []:
            by_uid[t["uid"]] = t
    tasks = list(by_uid.values())
    tasks_src = " + ".join(os.path.basename(l) or "." for l in layers)

    # sheets: the base is authoritative, a delta's sheets.json is usually empty
    sheets = []
    for layer in layers:
        sheets += load_json(os.path.join(layer, "sheets.json"), []) or []
    sheet_by_uid = {s["uid"]: s for s in sheets}

    # photo binaries: each layer ships only its own new files
    photo_dirs = [os.path.join(l, "photos") for l in layers]
    photo_files = index_photo_files([d for d in photo_dirs if os.path.isdir(d)])

    # task_details, merged, later layers win on collision
    details = {}
    for base_dir in layers:
        for f in glob.glob(os.path.join(base_dir, "task_details", "*.json")):
            d = load_json(f)
            if d:
                details[d["task_uid"]] = d

    filler = detect_filler_title(tasks)

    items, missing_photos = [], []
    for t in sorted(tasks, key=lambda z: z.get("number", 0)):
        num = t.get("number")
        if keep is not None and num not in keep:
            continue
        if t.get("deleted"):
            continue

        title = (t.get("title") or "").strip()
        if filler and title == filler:
            title = ""

        ann = t.get("current_annotation") or {}
        sheet = sheet_by_uid.get((ann.get("sheet") or {}).get("uid"), {})
        detail = details.get(t["uid"], {})

        photos = []
        for p in detail.get("photos", []):
            path = photo_files.get(p["uid"])
            if path is None:
                missing_photos.append((num, p["uid"]))
                continue
            stamp = None
            m = re.search(r"(\d{8})_(\d{6})", p.get("title") or "")
            if m:
                stamp = f"{m.group(1)}T{m.group(2)}"
            photos.append({
                "uid": p["uid"],
                "title": p.get("title"),
                "path": path,
                "captured": stamp,
                "photographer": (p.get("created_by") or {}).get("email"),
            })

        items.append({
            "number": num,
            "uid": t["uid"],
            "title": title,
            "description": (t.get("description") or "").strip(),
            "status": t.get("status"),
            "room": t.get("room", ""),
            "sheet_name": sheet.get("name"),
            "sheet_description": sheet.get("description"),
            "pin_stamp": ann.get("stamp"),
            "photo_count_field": (t.get("photos") or {}).get("total_count"),
            "photos": photos,
            "created_at": t.get("created_at"),
            "updated_at": t.get("updated_at"),
            "created_by": (t.get("created_by") or {}).get("email"),
        })

    os.makedirs(os.path.dirname(os.path.abspath(args.out)) or ".", exist_ok=True)
    with open(args.out, "w") as fh:
        json.dump(items, fh, indent=2)

    # triage summary, read this before anything else
    described = [i for i in items if i["description"]]
    photo_only = [i for i in items if not i["description"] and i["photos"]]
    no_content = [i for i in items if not i["description"] and not i["photos"]]
    with_room = [i for i in items if (i["room"] or "").strip()]
    no_sheet = [i["number"] for i in items if not i["sheet_name"]]

    print(f"tasks source     : {tasks_src}")
    print(f"filler title     : {filler!r}" if filler else "filler title     : none detected")
    print(f"items            : {len(items)}")
    print(f"  described      : {len(described)} -> {[i['number'] for i in described]}")
    print(f"  photo_only     : {len(photo_only)} -> {[i['number'] for i in photo_only]}")
    print(f"  no_photos      : {len(no_content)} -> {[i['number'] for i in no_content]}")
    print(f"  with_room      : {len(with_room)}")
    print(f"  no_sheet_ref   : {len(no_sheet)} -> {no_sheet}")
    print(f"photos resolved  : {sum(len(i['photos']) for i in items)}"
          f" (declared {sum(i['photo_count_field'] or 0 for i in items)})")
    if missing_photos:
        print(f"MISSING BINARIES : {missing_photos}", file=sys.stderr)
    print("sheet usage      :", dict(Counter(i["sheet_name"] for i in items)))
    print(f"wrote {args.out}")


if __name__ == "__main__":
    main()
