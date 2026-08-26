#!/usr/bin/env python3
"""
read_comments.py, extract reviewer comments from a .docx so the model can see them.

The review loop has two channels. The spreadsheet round trip (review_sheet.py) is
the bulk-edit path, but reviewers also comment directly in Word, and until now
nothing could read those back. A comment is useless to a model that cannot see
it, and "what did the reviewer say" is not answerable by reading the document
text.

What makes this useful rather than just a dump: each comment is reported WITH THE
TEXT IT IS ANCHORED TO and with the item heading it falls under. A comment that
says "reword this" means nothing without the span it points at.

Reads three parts:
  word/comments.xml           the comment bodies, authors, dates
  word/commentsExtended.xml   threading (replies) and resolved/done state
  word/document.xml           the anchors, so each comment gets its span

Usage:
    python3 read_comments.py <report.docx>                # readable summary
    python3 read_comments.py <report.docx> --json         # machine readable
    python3 read_comments.py <report.docx> --json -o comments.json
    python3 read_comments.py <report.docx> --include-resolved

By default resolved comments are omitted, since the reviewer has already closed
them. Pass --include-resolved to see everything.

Stdlib only. No python-docx, no lxml.
"""
import argparse
import json
import os
import re
import sys
import zipfile
import xml.etree.ElementTree as ET

W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
W14 = "{http://schemas.microsoft.com/office/word/2010/wordml}"
W15 = "{http://schemas.microsoft.com/office/word/2012/wordml}"


def para_text(p):
    """Visible text of a w:p. Joining runs is the whole job here."""
    return "".join(t.text or "" for t in p.iter(W + "t"))


def squash(s):
    """Collapse whitespace.

    Joining <w:t> runs routinely doubles spaces, which turns any exact match or
    eyeball comparison into a false mismatch. Normalise once, here, so no caller
    has to remember.
    """
    return re.sub(r"\s+", " ", s or "").strip()


def load_comments(z):
    """comment id -> {author, initials, date, text, para_id}."""
    try:
        root = ET.fromstring(z.read("word/comments.xml"))
    except KeyError:
        return {}
    out = {}
    for c in root.iter(W + "comment"):
        paras = list(c.iter(W + "p"))
        # commentsExtended keys off the LAST paragraph's paraId.
        para_id = paras[-1].get(W14 + "paraId") if paras else None
        out[c.get(W + "id")] = {
            "author": c.get(W + "author") or "",
            "initials": c.get(W + "initials") or "",
            "date": c.get(W + "date") or "",
            "text": squash(" ".join(para_text(p) for p in paras)),
            "_para_id": para_id,
        }
    return out


def load_extended(z):
    """paraId -> {done, parent_para_id}. Absent in older documents."""
    try:
        root = ET.fromstring(z.read("word/commentsExtended.xml"))
    except KeyError:
        return {}
    out = {}
    for ex in root.iter(W15 + "commentEx"):
        pid = ex.get(W15 + "paraId")
        if not pid:
            continue
        out[pid] = {
            "done": ex.get(W15 + "done") in ("1", "true"),
            "parent": ex.get(W15 + "paraIdParent"),
        }
    return out


def load_anchors(z):
    """comment id -> {anchor_text, heading}.

    Walks the body in document order, tracking which comment ranges are open and
    which heading was seen most recently. A range can span paragraphs, so the
    open set is carried across them rather than reset per paragraph.
    """
    root = ET.fromstring(z.read("word/document.xml"))
    body = root.find(W + "body")
    if body is None:
        return {}

    spans = {}
    open_ids = set()
    heading = None

    for p in body.iter(W + "p"):
        style = p.find(f"{W}pPr/{W}pStyle")
        style_val = style.get(W + "val") if style is not None else ""
        is_heading = bool(style_val) and style_val.lower().startswith("heading")

        text_here = squash(para_text(p))
        if is_heading and text_here:
            heading = text_here

        # Walk this paragraph's descendants in order so anchors and runs interleave
        # correctly. A comment that opens and closes mid-paragraph gets only its
        # own span, not the whole paragraph.
        for el in p.iter():
            tag = el.tag
            if tag == W + "commentRangeStart":
                cid = el.get(W + "id")
                open_ids.add(cid)
                spans.setdefault(cid, {"parts": [], "heading": heading})
            elif tag == W + "commentRangeEnd":
                open_ids.discard(el.get(W + "id"))
            elif tag == W + "t" and open_ids:
                for cid in open_ids:
                    spans[cid]["parts"].append(el.text or "")
            elif tag == W + "commentReference":
                # A zero-length anchor still tells us where the comment sits.
                cid = el.get(W + "id")
                spans.setdefault(cid, {"parts": [], "heading": heading})

    return {cid: {"anchor_text": squash("".join(v["parts"])), "heading": v["heading"] or ""}
            for cid, v in spans.items()}


def collect(path, include_resolved=False):
    z = zipfile.ZipFile(path)
    comments = load_comments(z)
    extended = load_extended(z)
    anchors = load_anchors(z)

    # paraId -> comment id, so a reply can name its parent comment.
    by_para = {c["_para_id"]: cid for cid, c in comments.items() if c.get("_para_id")}

    rows = []
    for cid, c in comments.items():
        ex = extended.get(c.get("_para_id") or "", {})
        parent_para = ex.get("parent")
        a = anchors.get(cid, {})
        rows.append({
            "id": cid,
            "author": c["author"],
            "initials": c["initials"],
            "date": c["date"],
            "comment": c["text"],
            "anchor_text": a.get("anchor_text", ""),
            "heading": a.get("heading", ""),
            "resolved": bool(ex.get("done")),
            "reply_to": by_para.get(parent_para) if parent_para else None,
        })

    rows.sort(key=lambda r: int(r["id"]) if r["id"].isdigit() else 0)
    if not include_resolved:
        rows = [r for r in rows if not r["resolved"]]
    return rows


def main():
    ap = argparse.ArgumentParser(
        description="Extract reviewer comments from a .docx, with the text each one is anchored to.")
    ap.add_argument("docx", help="the reviewed .docx")
    ap.add_argument("--json", action="store_true", help="emit JSON instead of a readable summary")
    ap.add_argument("-o", "--out", default=None, help="write to a file instead of stdout")
    ap.add_argument("--include-resolved", action="store_true",
                    help="include comments the reviewer already marked resolved")
    args = ap.parse_args()

    if not os.path.isfile(args.docx):
        sys.exit(f"not a file: {args.docx}")

    rows = collect(args.docx, args.include_resolved)

    if args.json:
        payload = json.dumps(rows, indent=2, ensure_ascii=False)
    else:
        lines = [f"{len(rows)} comment(s) in {os.path.basename(args.docx)}"]
        if not args.include_resolved:
            lines.append("(resolved comments hidden; pass --include-resolved to see them)")
        lines.append("")
        for r in rows:
            who = r["author"] or "unknown"
            head = f"[{r['id']}] {who}"
            if r["date"]:
                head += f"  {r['date'][:19]}"
            if r["resolved"]:
                head += "  (resolved)"
            if r["reply_to"]:
                head += f"  (reply to {r['reply_to']})"
            lines.append(head)
            if r["heading"]:
                lines.append(f"    under : {r['heading']}")
            if r["anchor_text"]:
                anchor = r["anchor_text"]
                if len(anchor) > 300:
                    anchor = anchor[:300] + " ..."
                lines.append(f"    on    : \"{anchor}\"")
            lines.append(f"    says  : {r['comment']}")
            lines.append("")
        payload = "\n".join(lines)

    if args.out:
        with open(args.out, "w", encoding="utf8") as fh:
            fh.write(payload + "\n")
        print(f"wrote {args.out} ({len(rows)} comments)")
    else:
        print(payload)


if __name__ == "__main__":
    main()
