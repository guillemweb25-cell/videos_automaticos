#!/usr/bin/env python
"""Export / import per-channel configuration to a single JSON snapshot.

The config that keeps each channel producing correct images lives in TWO places
that do NOT travel with the code:
  - the database: default_style, default_workflow, image_style_prompt,
    negative_prompt, youtube_handle, creds_dir
  - cache/<user>/<NNNN-slug>/style-guide.md  (git-ignored)

After a migration or a DB restore from an old backup, that config is lost even
though the code is intact. This script snapshots it into one JSON file you CAN
commit, and restores it afterwards.

It does NOT touch secrets: OAuth credentials live in
cache/<...>/youtube_credentials/ and are never read or written here.

Run it INSIDE the api container (it needs DB + cache access):

    # snapshot current config -> backend/config/channels_config.json
    docker exec videos_automaticos-api-1 python scripts/manage_channels.py export

    # preview what a restore would change (no writes)
    docker exec videos_automaticos-api-1 python scripts/manage_channels.py import --dry-run

    # restore config into the DB + rewrite the style-guide.md files
    docker exec videos_automaticos-api-1 python scripts/manage_channels.py import

An optional [path] argument overrides the default JSON location.
"""
import os
import sys
import json
import glob
import argparse

# Make `import app.*` work no matter the current working directory.
APP_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # /app
sys.path.insert(0, APP_DIR)

from app.database import SessionLocal          # noqa: E402
from app.models.channel import Channel          # noqa: E402

# Fields we snapshot. user_id is captured for reference but never reassigned on
# import (that would change ownership / break FKs).
CONFIG_FIELDS = [
    "name", "youtube_handle", "creds_dir",
    "default_style", "default_workflow",
    "image_style_prompt", "negative_prompt",
    "user_id",
]

CACHE_DIR = os.path.join(APP_DIR, "cache")
DEFAULT_PATH = os.path.join(APP_DIR, "config", "channels_config.json")


def _find_style_guide(channel_id: int):
    """Locate cache/<user>/<NNNN-slug>/style-guide.md for a channel id."""
    pattern = os.path.join(CACHE_DIR, "*", f"{channel_id:04d}-*", "style-guide.md")
    matches = sorted(glob.glob(pattern))
    return matches[0] if matches else None


def export_config(path: str):
    db = SessionLocal()
    try:
        channels = db.query(Channel).order_by(Channel.id).all()
        out = {"channels": []}
        for c in channels:
            entry = {"id": c.id}
            for f in CONFIG_FIELDS:
                entry[f] = getattr(c, f, None)
            sg = _find_style_guide(c.id)
            if sg and os.path.isfile(sg):
                entry["style_guide_path"] = os.path.relpath(sg, APP_DIR).replace("\\", "/")
                with open(sg, encoding="utf-8") as fh:
                    entry["style_guide_md"] = fh.read()
            out["channels"].append(entry)

        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(out, fh, ensure_ascii=False, indent=2)

        print(f"[export] {len(out['channels'])} canal(es) -> {path}")
        for c in out["channels"]:
            guide = " +style-guide" if c.get("style_guide_md") else ""
            print(f"  #{c['id']:>2} {c['name']}  (style={c['default_style']}, "
                  f"wf={c['default_workflow']}){guide}")
    finally:
        db.close()


def import_config(path: str, dry_run: bool = False, write_guides: bool = True):
    with open(path, encoding="utf-8") as fh:
        data = json.load(fh)

    db = SessionLocal()
    changed = 0
    try:
        for entry in data.get("channels", []):
            cid = entry.get("id")
            c = db.query(Channel).filter(Channel.id == cid).first()
            if not c:
                print(f"  [skip] canal #{cid} ({entry.get('name')}) no existe en la BD. "
                      "Créalo en la app primero (no lo creo aquí para no romper user_id/FKs).")
                continue

            diffs = []
            for f in CONFIG_FIELDS:
                if f == "user_id":
                    continue  # never reassign ownership
                new = entry.get(f)
                if getattr(c, f, None) != new:
                    diffs.append(f)
                    if not dry_run:
                        setattr(c, f, new)

            sg_md = entry.get("style_guide_md")
            sg_rel = entry.get("style_guide_path")
            if write_guides and sg_md and sg_rel:
                sg_abs = os.path.join(APP_DIR, sg_rel)
                if os.path.isdir(os.path.dirname(sg_abs)):
                    current = ""
                    if os.path.isfile(sg_abs):
                        with open(sg_abs, encoding="utf-8") as fh:
                            current = fh.read()
                    if current != sg_md:
                        diffs.append("style-guide.md")
                        if not dry_run:
                            with open(sg_abs, "w", encoding="utf-8") as fh:
                                fh.write(sg_md)
                else:
                    print(f"  [warn] #{cid}: no existe {os.path.dirname(sg_rel)} "
                          "(el canal aún no tiene carpeta en cache/) -> no escribo style-guide.md")

            if diffs:
                changed += 1
                tag = "[dry]" if dry_run else "[upd]"
                print(f"  {tag} #{cid} {c.name}: {', '.join(diffs)}")

        if not dry_run:
            db.commit()
        prefix = "(dry-run) " if dry_run else ""
        verb = "a actualizar" if dry_run else "actualizados"
        print(f"[import] {prefix}{changed} canal(es) {verb}.")
    finally:
        db.close()


def main():
    ap = argparse.ArgumentParser(description="Export/import channel config (DB + style-guide.md).")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pe = sub.add_parser("export", help="snapshot channel config to JSON")
    pe.add_argument("path", nargs="?", default=DEFAULT_PATH)

    pi = sub.add_parser("import", help="restore channel config from JSON")
    pi.add_argument("path", nargs="?", default=DEFAULT_PATH)
    pi.add_argument("--dry-run", action="store_true", help="show changes without writing")
    pi.add_argument("--no-guides", action="store_true", help="do not rewrite style-guide.md files")

    args = ap.parse_args()
    if args.cmd == "export":
        export_config(args.path)
    else:
        import_config(args.path, dry_run=args.dry_run, write_guides=not args.no_guides)


if __name__ == "__main__":
    main()
