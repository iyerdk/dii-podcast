#!/usr/bin/env python3
"""
DII Podcast — RSS Feed Builder (Stage 4)

Reads a show-notes JSON sidecar and an MP3 file, then:
  1. Adds a new <item> to feed.xml (creates it on first run)
  2. Optionally uploads the MP3 + feed to a hosting location

Supported upload targets (set via --upload-to):
  - local      : no upload, just write feed.xml (default)
  - s3://...   : upload to Amazon S3 using boto3
  - r2://...   : upload to Cloudflare R2 (also uses boto3 with custom endpoint)

Usage:
    # Local only
    python publish_rss.py --shownotes shownotes/ep1_2026-03-15.json --mp3 DII_EP1_2026-03-15.mp3

    # Upload to S3
    python publish_rss.py \\
        --shownotes shownotes/ep1_2026-03-15.json \\
        --mp3 DII_EP1_2026-03-15.mp3 \\
        --upload-to s3://my-podcast-bucket \\
        --base-url https://media.dii.podcast
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from email.utils import format_datetime
from pathlib import Path
from xml.etree import ElementTree as ET

# ── RSS / Podcast namespace URIs ──────────────────────────────────────────────
NS_ITUNES = "http://www.itunes.com/dtds/podcast-1.0.dtd"
NS_CONTENT = "http://purl.org/rss/1.0/modules/content/"
NS_PODCAST = "https://podcastindex.org/namespace/1.0"

ET.register_namespace("itunes", NS_ITUNES)
ET.register_namespace("content", NS_CONTENT)
ET.register_namespace("podcast", NS_PODCAST)

FEED_FILE = "feed.xml"

# ── Show-level defaults (edit or move to a config.json) ──────────────────────
SHOW_DEFAULTS = {
    "title": "Digital Infrastructure Insider",
    "description": (
        "The executive briefing for global digital infrastructure leaders and investors. "
        "Weekly analysis of data centres, fibre networks, towers, subsea cables, "
        "power assets, and the macro forces shaping them."
    ),
    "link": "https://dii.podcast",
    "language": "en-us",
    "copyright": f"© {datetime.now().year} Digital Infrastructure Insider",
    "itunes_author": "Digital Infrastructure Insider",
    "itunes_category": "Business",
    "itunes_explicit": "false",
    "itunes_type": "episodic",
    "image_url": "https://dii.podcast/artwork.jpg",  # replace with real artwork URL
}


# ── Feed helpers ──────────────────────────────────────────────────────────────

def _itunes(tag: str) -> str:
    return f"{{{NS_ITUNES}}}{tag}"

def _content(tag: str) -> str:
    return f"{{{NS_CONTENT}}}{tag}"

def _podcast(tag: str) -> str:
    return f"{{{NS_PODCAST}}}{tag}"


def build_new_feed(show: dict) -> ET.ElementTree:
    """Create a brand-new RSS feed document."""
    rss = ET.Element("rss", {"version": "2.0"})
    channel = ET.SubElement(rss, "channel")

    _sub(channel, "title", show["title"])
    _sub(channel, "link", show["link"])
    _sub(channel, "description", show["description"])
    _sub(channel, "language", show["language"])
    _sub(channel, "copyright", show["copyright"])
    _sub(channel, "lastBuildDate", _rfc2822_now())

    _sub(channel, _itunes("author"), show["itunes_author"])
    _sub(channel, _itunes("explicit"), show["itunes_explicit"])
    _sub(channel, _itunes("type"), show["itunes_type"])

    image = ET.SubElement(channel, _itunes("image"))
    image.set("href", show["image_url"])

    category = ET.SubElement(channel, _itunes("category"))
    category.set("text", show["itunes_category"])

    return ET.ElementTree(rss)


def load_or_create_feed(show: dict, feed_path: str = FEED_FILE) -> tuple[ET.ElementTree, ET.Element]:
    """Load existing feed.xml or create a new one. Returns (tree, channel)."""
    if os.path.isfile(feed_path):
        tree = ET.parse(feed_path)
        channel = tree.getroot().find("channel")
        if channel is None:
            raise ValueError(f"{feed_path} exists but has no <channel> element")
        # Update lastBuildDate
        lb = channel.find("lastBuildDate")
        if lb is not None:
            lb.text = _rfc2822_now()
        else:
            _sub(channel, "lastBuildDate", _rfc2822_now())
    else:
        tree = build_new_feed(show)
        channel = tree.getroot().find("channel")

    return tree, channel


def episode_already_exists(channel: ET.Element, guid: str) -> bool:
    for item in channel.findall("item"):
        g = item.find("guid")
        if g is not None and g.text == guid:
            return True
    return False


def build_episode_item(
    meta: dict,
    mp3_path: str,
    base_url: str,
) -> ET.Element:
    """Construct a <item> element from show-notes metadata."""
    item = ET.Element("item")

    ep = meta["episode_number"]
    ep_date = meta["date"]
    title = meta.get("title", f"Episode {ep}")
    summary = meta.get("summary", "")
    description_html = meta.get("description_html", f"<p>{summary}</p>")
    subtitle = meta.get("subtitle", summary[:120] if summary else "")
    keywords = ", ".join(meta.get("keywords", []))
    audio_filename = meta.get("audio_file", os.path.basename(mp3_path))

    audio_url = f"{base_url.rstrip('/')}/{audio_filename}"
    guid_value = f"dii-ep{ep}-{ep_date}"

    # File size
    try:
        mp3_size = os.path.getsize(mp3_path)
    except FileNotFoundError:
        print(f"  WARNING: MP3 not found at {mp3_path} — using size 0", file=sys.stderr)
        mp3_size = 0

    # Pub date: parse ep_date or fall back to now
    try:
        pub_dt = datetime.strptime(ep_date, "%Y-%m-%d").replace(
            hour=6, minute=0, tzinfo=timezone.utc
        )
    except ValueError:
        pub_dt = datetime.now(timezone.utc)

    _sub(item, "title", title)
    _sub(item, "link", meta.get("show_url", SHOW_DEFAULTS["link"]))
    _sub(item, "description", summary)
    _sub(item, "pubDate", format_datetime(pub_dt))

    guid_el = _sub(item, "guid", guid_value)
    guid_el.set("isPermaLink", "false")

    enc = ET.SubElement(item, "enclosure")
    enc.set("url", audio_url)
    enc.set("length", str(mp3_size))
    enc.set("type", "audio/mpeg")

    _sub(item, _itunes("title"), title)
    _sub(item, _itunes("subtitle"), subtitle)
    _sub(item, _itunes("summary"), summary)
    _sub(item, _itunes("author"), SHOW_DEFAULTS["itunes_author"])
    _sub(item, _itunes("explicit"), "false")
    _sub(item, _itunes("duration"), "0")  # overwrite after audio is generated
    _sub(item, _itunes("episode"), str(ep))
    _sub(item, _itunes("episodeType"), meta.get("episode_type", "full"))
    _sub(item, _itunes("keywords"), keywords)

    encoded = ET.SubElement(item, _content("encoded"))
    encoded.text = description_html

    # Podcast namespace chapters (titles only — no timestamps yet)
    chapters = meta.get("chapters", [])
    if chapters:
        chaps_el = ET.SubElement(item, _podcast("chapters"))
        chaps_el.set("version", "1.2")
        for ch in chapters:
            c = ET.SubElement(chaps_el, _podcast("chapter"))
            c.set("start", str(ch.get("start_seconds") or 0))
            c.set("title", ch.get("title", ""))

    # Takeaways as show notes
    takeaways = meta.get("takeaways", [])
    if takeaways:
        bullets = "\n".join(f"  • {t}" for t in takeaways)
        ET.SubElement(item, _podcast("transcript")).text = bullets

    return item


def insert_episode(channel: ET.Element, item: ET.Element) -> None:
    """Insert episode item after the last channel metadata tag, before existing items."""
    # Find the position of the first existing <item>
    items = list(channel)
    first_item_idx = next(
        (i for i, el in enumerate(items) if el.tag == "item"), len(items)
    )
    channel.insert(first_item_idx, item)


def write_feed(tree: ET.ElementTree, path: str = FEED_FILE) -> None:
    ET.indent(tree, space="  ")
    tree.write(path, encoding="UTF-8", xml_declaration=True)


# ── Upload helpers ────────────────────────────────────────────────────────────

def upload_to_s3(mp3_path: str, feed_path: str, bucket_url: str) -> None:
    """Upload MP3 + feed.xml to S3 or R2 (boto3 required)."""
    try:
        import boto3
    except ImportError:
        sys.exit("Error: boto3 not installed. Run: pip install boto3")

    # Parse s3://bucket-name or r2://bucket-name
    scheme, _, rest = bucket_url.partition("://")
    bucket = rest.strip("/")

    kwargs = {}
    if scheme == "r2":
        endpoint = os.environ.get("R2_ENDPOINT_URL")
        if not endpoint:
            sys.exit("Error: R2_ENDPOINT_URL environment variable not set")
        kwargs["endpoint_url"] = endpoint

    s3 = boto3.client("s3", **kwargs)

    for local_path, s3_key in [
        (mp3_path, os.path.basename(mp3_path)),
        (feed_path, "feed.xml"),
    ]:
        if not os.path.isfile(local_path):
            print(f"  SKIP: {local_path} not found", file=sys.stderr)
            continue
        print(f"  Uploading {local_path} → s3://{bucket}/{s3_key}")
        s3.upload_file(
            local_path,
            bucket,
            s3_key,
            ExtraArgs={"ContentType": "audio/mpeg" if local_path.endswith(".mp3") else "application/rss+xml"},
        )
    print("  Upload complete.")


# ── Utilities ─────────────────────────────────────────────────────────────────

def _sub(parent: ET.Element, tag: str, text: str = "") -> ET.Element:
    el = ET.SubElement(parent, tag)
    el.text = text
    return el

def _rfc2822_now() -> str:
    return format_datetime(datetime.now(timezone.utc))


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser(
        description="Add an episode to the DII podcast RSS feed."
    )
    parser.add_argument("--shownotes", required=True, help="Path to the episode JSON sidecar")
    parser.add_argument("--mp3", required=True, help="Path to the episode MP3 file")
    parser.add_argument(
        "--base-url",
        default=os.environ.get("DII_BASE_URL", "https://media.dii.podcast"),
        help="Base URL where MP3 files are hosted (env: DII_BASE_URL)",
    )
    parser.add_argument(
        "--upload-to",
        default="local",
        help="Upload target: 'local' (default), 's3://bucket', or 'r2://bucket'",
    )
    parser.add_argument(
        "--feed",
        default=FEED_FILE,
        help=f"Path to write feed.xml (default: {FEED_FILE})",
    )
    args = parser.parse_args()

    if not os.path.isfile(args.shownotes):
        sys.exit(f"Error: show notes file not found: {args.shownotes}")

    print(f"Loading show notes: {args.shownotes}")
    with open(args.shownotes, encoding="utf-8") as f:
        meta = json.load(f)

    ep = meta.get("episode_number", "?")
    guid = f"dii-ep{ep}-{meta.get('date', 'unknown')}"

    print(f"Loading/creating RSS feed: {args.feed}")
    tree, channel = load_or_create_feed(SHOW_DEFAULTS, args.feed)

    if episode_already_exists(channel, guid):
        print(f"  Episode {ep} already in feed (guid: {guid}). Use --force to overwrite.")
        # Remove existing item to allow re-insert if needed (not implemented here)
        sys.exit(0)

    print(f"Building episode item for EP{ep}…")
    item = build_episode_item(meta, args.mp3, args.base_url)
    insert_episode(channel, item)

    print(f"Writing feed: {args.feed}")
    write_feed(tree, args.feed)
    print(f"  Feed updated — {len(channel.findall('item'))} episode(s) total")

    if args.upload_to != "local":
        print(f"Uploading to {args.upload_to}…")
        upload_to_s3(args.mp3, args.feed, args.upload_to)

    print(f"\nDone! RSS feed: {args.feed}")
    if "title" in meta:
        print(f"  Episode: EP{ep} — {meta['title']}")
        print(f"  Audio:   {meta.get('audio_file')}")
        print(f"  GUID:    {guid}")


if __name__ == "__main__":
    main()
