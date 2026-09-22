"""Build the local EDRDG dictionary index.

Reads the raw EDRDG XML files (downloaded once into ``data/``) and builds
``data/dictionary.sqlite`` with two tables:

- ``kanji``: one row per KANJIDIC2 character. List fields are stored as
  JSON strings (``json.dumps`` on write, ``json.loads`` on read).
- ``words``: minimal JMdict stub for ``lookup_word()`` (Day 3 verifier
  builds on this).

Reproducible: delete the .sqlite and re-run. Raw XML is never committed.

Usage (from repo root)::

    uv run python -m infrastructure.build_dictionary

Source data: KANJIDIC2 / JMdict (c) EDRDG, CC-BY-SA. See README attribution.
"""

from __future__ import annotations

import json
import sqlite3
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "data"
KANJIDIC_PATH = DATA_DIR / "kanjidic2.xml"
JMDICT_PATH = DATA_DIR / "JMdict_e"
DB_PATH = DATA_DIR / "dictionary.sqlite"

SCHEMA = """
CREATE TABLE IF NOT EXISTS kanji (
    kanji TEXT PRIMARY KEY,
    onyomi TEXT NOT NULL,
    kunyomi TEXT NOT NULL,
    meanings TEXT NOT NULL,
    stroke_count INTEGER,
    grade INTEGER
);
CREATE TABLE IF NOT EXISTS words (
    word TEXT NOT NULL,
    kana TEXT NOT NULL,
    meaning TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_words_word ON words(word);
"""


def parse_kanjidic(path: Path):
    """Yield (kanji, onyomi, kunyomi, meanings, strokes, grade) tuples."""
    rows = []
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "character":
            continue
        literal_el = elem.find("literal")
        if literal_el is None or not literal_el.text:
            elem.clear()
            continue
        literal = literal_el.text.strip()

        onyomi, kunyomi, meanings = [], [], []
        rmgroup = elem.find("reading_meaning/rmgroup")
        if rmgroup is not None:
            for r in rmgroup.findall("reading"):
                text = (r.text or "").strip()
                if not text:
                    continue
                if r.get("r_type") == "ja_on":
                    onyomi.append(text)
                elif r.get("r_type") == "ja_kun":
                    kunyomi.append(text)
            for m in rmgroup.findall("meaning"):
                # No m_lang attribute == English. Drop fr/es/pt translations.
                if "m_lang" in m.attrib:
                    continue
                text = (m.text or "").strip()
                if text:
                    meanings.append(text)

        misc = elem.find("misc")
        strokes = grade = None
        if misc is not None:
            sc = misc.find("stroke_count")
            if sc is not None and (sc.text or "").strip().isdigit():
                strokes = int(sc.text.strip())
            gr = misc.find("grade")
            if gr is not None and (gr.text or "").strip().isdigit():
                grade = int(gr.text.strip())

        rows.append(
            (
                literal,
                json.dumps(onyomi, ensure_ascii=False),
                json.dumps(kunyomi, ensure_ascii=False),
                json.dumps(meanings, ensure_ascii=False),
                strokes,
                grade,
            )
        )
        elem.clear()
    return rows


def parse_jmdict(path: Path):
    """Yield (word, kana, meaning) tuples. One row per keb; kana-only fallback."""
    rows = []
    for _event, elem in ET.iterparse(path, events=("end",)):
        if elem.tag != "entry":
            continue
        kebs = [
            (k.text or "").strip()
            for k in elem.findall("k_ele/keb")
            if k.text and k.text.strip()
        ]
        rebs = [
            (r.text or "").strip()
            for r in elem.findall("r_ele/reb")
            if r.text and r.text.strip()
        ]
        glosses = []
        for sense in elem.findall("sense"):
            for g in sense.findall("gloss"):
                # No lang attribute == English (g_type="expl" is still English).
                if "lang" in g.attrib:
                    continue
                text = (g.text or "").strip()
                if text:
                    glosses.append(text)
        meaning = "; ".join(glosses)
        kana = rebs[0] if rebs else ""

        if meaning and kana:
            if kebs:
                for keb in kebs:
                    rows.append((keb, kana, meaning))
            else:
                for reb in rebs:
                    rows.append((reb, reb, meaning))
        elem.clear()
    return rows


def build(
    kanjidic: Path = KANJIDIC_PATH,
    jmdict: Path = JMDICT_PATH,
    db: Path = DB_PATH,
) -> dict[str, int]:
    for p in (kanjidic, jmdict):
        if not p.exists():
            raise FileNotFoundError(
                f"Missing {p}. Download the EDRDG XML into data/ first."
            )
    if db.exists():
        db.unlink()
    conn = sqlite3.connect(db)
    try:
        conn.executescript(SCHEMA)
        kanji_rows = parse_kanjidic(kanjidic)
        conn.executemany(
            "INSERT INTO kanji VALUES (?, ?, ?, ?, ?, ?)", kanji_rows
        )
        word_rows = parse_jmdict(jmdict)
        conn.executemany(
            "INSERT INTO words VALUES (?, ?, ?)", word_rows
        )
        conn.commit()
        return {"kanji": len(kanji_rows), "words": len(word_rows)}
    finally:
        conn.close()


def main() -> None:
    counts = build()
    print(f"Built {DB_PATH}: {counts['kanji']} kanji, {counts['words']} words")


if __name__ == "__main__":
    sys.exit(main())
