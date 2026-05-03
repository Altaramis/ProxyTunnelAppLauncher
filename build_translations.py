#!/usr/bin/env python3
# Copyright (C) 2026 Altaramis
# SPDX-License-Identifier: GPL-3.0-or-later
"""
Compile .ts translation files to .qm binary files.

Usage:
    python build_translations.py [ts_file ...]

If no arguments given, compiles all .ts files in the translations/ directory.

If lrelease is available on PATH it is used; otherwise falls back to a
pure-Python minimal QM writer.
"""
import os
import shutil
import struct
import subprocess
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

# ── QM format constants ───────────────────────────────────────────────────────
_MAGIC = bytes([
    0x3c, 0xb8, 0x64, 0x18, 0xca, 0xef, 0x9c, 0x95,
    0xcd, 0x21, 0x1c, 0xbf, 0x60, 0xa1, 0xbd, 0xdd,
])

_TAG_HASHES   = 0x42   # sorted (hash, offset) pairs
_TAG_MESSAGES = 0x69   # message data

_MSG_END         = 0x01
_MSG_TRANSLATION = 0x03
_MSG_SOURCE_TEXT = 0x06   # Tag_SourceText (UTF-8)
_MSG_CONTEXT     = 0x07   # Tag_Context (UTF-8)
_MSG_COMMENT     = 0x08   # Tag_Comment / disambiguation (UTF-8)


def _elf_hash(data: bytes) -> int:
    h = 0
    for b in data:
        h = ((h << 4) + b) & 0xFFFFFFFF
        g = h & 0xF0000000
        if g:
            h ^= g >> 24
        h &= ~g & 0xFFFFFFFF
    return h


def _msg_hash(source: str, comment: str = "") -> int:
    """Qt 6 message hash: elfHash(source) ^ elfHash(comment)."""
    h = _elf_hash(source.encode("utf-8"))
    if comment:
        h ^= _elf_hash(comment.encode("utf-8"))
    return h & 0xFFFFFFFF


def _write_utf16be(text: str) -> bytes:
    encoded = text.encode("utf-16-be")
    return struct.pack(">I", len(encoded)) + encoded


def _write_utf8_tag(tag: int, text: str) -> bytes:
    encoded = text.encode("utf-8")
    return bytes([tag]) + struct.pack(">I", len(encoded)) + encoded


def _build_message(source: str, context: str, translation: str, comment: str = "") -> bytes:
    parts = bytearray()
    # Translation (UTF-16BE)
    parts.append(_MSG_TRANSLATION)
    parts += _write_utf16be(translation)
    # Comment / disambiguation (empty when not used; Qt checks *m before matching)
    parts.append(_MSG_COMMENT)
    if comment:
        cmt_b = comment.encode("utf-8")
        parts += struct.pack(">I", len(cmt_b)) + cmt_b
    else:
        parts += struct.pack(">I", 0)
    # SourceText (UTF-8)
    parts += _write_utf8_tag(_MSG_SOURCE_TEXT, source)
    # Context (UTF-8)
    parts += _write_utf8_tag(_MSG_CONTEXT, context)
    parts.append(_MSG_END)
    return bytes(parts)


def _write_section(tag: int, data: bytes) -> bytes:
    return bytes([tag]) + struct.pack(">I", len(data)) + data


def ts_to_qm(ts_path: str, qm_path: str) -> int:
    """Parse a .ts file and write a .qm binary. Returns count of translations."""
    tree = ET.parse(ts_path)
    root = tree.getroot()

    entries = []       # (hash, message_bytes) — may have duplicate hashes
    seen_hashes: dict = {}   # hash -> list of (source, context) for collision tracking

    for ctx_el in root.findall("context"):
        name_el = ctx_el.find("name")
        context = name_el.text if name_el is not None and name_el.text else ""

        for msg_el in ctx_el.findall("message"):
            src_el   = msg_el.find("source")
            trans_el = msg_el.find("translation")
            cmt_el   = msg_el.find("comment")

            if src_el is None or src_el.text is None:
                continue
            if trans_el is None or not trans_el.text:
                continue
            # Skip 'unfinished' translations
            if trans_el.get("type") == "unfinished":
                continue

            source      = src_el.text
            translation = trans_el.text
            comment     = cmt_el.text if cmt_el is not None and cmt_el.text else ""

            h = _msg_hash(source, comment)
            msg_bytes = _build_message(source, context, translation, comment)
            entries.append((h, msg_bytes))

    # Sort by hash so same-hash entries are adjacent (Qt probes neighbors for collisions)
    entries.sort(key=lambda e: e[0])

    messages_blob = bytearray()
    hash_entries = []
    for h, msg_bytes in entries:
        offset = len(messages_blob)
        messages_blob += msg_bytes
        hash_entries.append((h, offset))

    hashes_blob = bytearray()
    for h, offset in hash_entries:
        hashes_blob += struct.pack(">II", h, offset)

    n = len(hash_entries)

    qm_data = (
        _MAGIC
        + _write_section(_TAG_HASHES,   bytes(hashes_blob))
        + _write_section(_TAG_MESSAGES, bytes(messages_blob))
    )

    with open(qm_path, "wb") as f:
        f.write(qm_data)

    return n


def main():
    ts_files = sys.argv[1:]
    if not ts_files:
        ts_dir = Path(__file__).parent / "translations"
        ts_files = list(ts_dir.glob("*.ts"))
    else:
        ts_files = [Path(p) for p in ts_files]

    if not ts_files:
        print("No .ts files found.")
        sys.exit(1)

    lrelease = shutil.which("lrelease") or shutil.which("lrelease6")

    for ts in ts_files:
        qm = ts.with_suffix(".qm")
        if lrelease:
            result = subprocess.run([lrelease, str(ts), "-qm", str(qm)],
                                    capture_output=True, text=True)
            if result.returncode == 0:
                print(f"lrelease: {ts.name} → {qm.name}")
                continue
            print(f"lrelease failed, using fallback: {result.stderr.strip()}")

        count = ts_to_qm(str(ts), str(qm))
        print(f"Generated {qm.name} ({count} translations) from {ts.name}")


if __name__ == "__main__":
    main()
