#!/usr/bin/env python3
"""
njx_to_txt.py

Converts NJStar word processor documents (.NJX) to plain UTF-8 .txt files,
keeping just the text -- the same result as opening the document in NJStar and
copy-pasting everything into a text editor.

Usage
-----
    python njx_to_txt.py "Manga_Title 012.NJX"                 one or more files
    python njx_to_txt.py --prefix "Manga_Title"                every "Manga_Title <number>.NJX"
    python njx_to_txt.py --prefix "Manga_Title" --folder "D:\\TL" -o "D:\\TL\\txt"
    python njx_to_txt.py                                       asks what to convert

Each .txt is written next to its .NJX (or into --output) with the same name.
Existing .txt files are skipped unless --overwrite is given.

The .NJX format
---------------
    0x000   "\\x04Nj\\x0f\\x00\\x04NJStar Document\\x00" header, then a version word:
            0x0011 = older files, text stored as 8-bit EUC-JP
            0x0040 = newer files, text stored as UTF-16LE
    0x400   the document text, ending at the marker "~`!@#$%^&*()-+|=-NjxFmt"
    ...     formatting data (fonts, styles), which is ignored

Within the text, every real line break is a control character (the paragraph
style, e.g. \\x14) followed by CRLF. A CRLF with no control character before it
is just where NJStar word-wrapped the line, so it's removed, as it is when you
copy-paste out of NJStar.
"""

import argparse
import re
import sys
from pathlib import Path

HEADER_MAGIC = b'NJStar Document'
TEXT_START = 0x400
END_MARKER = '~`!@#$%^&*()-+|=-NjxFmt'
VERSION_UTF16 = b'\x40\x00'

HEADER_MARK = '\x11\r\n'
FOOTER_MARK = '\x10\r\n'

# A real line break: a control character (paragraph style or page break) then CRLF.
HARD_BREAK_RE = re.compile(r'[\x00-\x08\x0b-\x1f]\r\n')
# Control characters left over after line breaks are handled (tab is kept).
CONTROL_RE = re.compile(r'[\x00-\x08\x0b-\x1f]')


class NotNJXError(ValueError):
    pass


def decode_legacy(raw: bytes) -> str:
    """Decode older files' 8-bit text: EUC-JP (the JIS X 0213 variant, which
    also covers characters like circled numbers), with the occasional Western
    European character stored as a single Windows-1252 byte (e.g. "ö" or "©")
    wherever the bytes don't form a valid Japanese character."""
    out = []
    i, n = 0, len(raw)
    while i < n:
        b = raw[i]
        if b < 0x80:
            j = i + 1
            while j < n and raw[j] < 0x80:
                j += 1
            out.append(raw[i:j].decode('ascii'))
            i = j
            continue
        size = 3 if b == 0x8F else 2  # 0x8F starts a 3-byte character
        try:
            out.append(raw[i:i + size].decode('euc_jis_2004'))
            i += size
            continue
        except UnicodeDecodeError:
            pass
        try:
            out.append(bytes([b]).decode('cp1252'))
        except UnicodeDecodeError:
            out.append(bytes([b]).decode('latin-1'))
        i += 1
    return ''.join(out)


def extract_text(data: bytes) -> str:
    """Return the plain text of an NJX document's bytes."""
    if HEADER_MAGIC not in data[:0x20]:
        raise NotNJXError("not an NJStar document")

    if data[0x16:0x18] == VERSION_UTF16:
        end = data.find(END_MARKER.encode('utf-16-le'), TEXT_START)
        if end == -1:
            raise NotNJXError("end-of-text marker not found")
        if (end - TEXT_START) % 2:
            end -= 1
        text = data[TEXT_START:end].decode('utf-16-le', errors='replace')
    else:
        end = data.find(END_MARKER.encode('ascii'), TEXT_START)
        if end == -1:
            raise NotNJXError("end-of-text marker not found")
        text = decode_legacy(data[TEXT_START:end])

    text = strip_header_footer(text)
    text = HARD_BREAK_RE.sub('\n', text)   # real line breaks
    text = text.replace('\r\n', '')        # word-wrap points
    text = CONTROL_RE.sub('', text)
    # Like copy-paste, leave out the document's final paragraph break.
    return text[:-1] if text.endswith('\n') else text


def strip_header_footer(text: str) -> str:
    """Newer files start with the page header and footer, each wrapped in
    marker lines: "\\x11\\r\\n ... \\x11\\r\\n" (header) and "\\x10\\r\\n ...
    \\x10\\r\\n" (footer). They aren't part of the document body, so drop them."""
    for marker in (HEADER_MARK, FOOTER_MARK):
        if text.startswith(marker):
            end = text.find(marker, len(marker))
            if end != -1:
                text = text[end + len(marker):]
    return text


def convert(src: Path, out_dir: Path | None, overwrite: bool) -> str:
    """Convert one file. Returns 'converted', 'skipped' or an error message."""
    dst = (out_dir or src.parent) / (src.stem + '.txt')
    if dst.exists() and not overwrite:
        return 'skipped'
    try:
        text = extract_text(src.read_bytes())
    except (OSError, NotNJXError) as e:
        return f"error: {e}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    # UTF-8 with Windows line endings, like a text file saved from Notepad.
    with open(dst, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(text)
    return 'converted'


def files_with_prefix(folder: Path, prefix: str) -> list[Path]:
    """NJX files named <prefix><optional space><number>..., e.g. with prefix
    "Manga_Title": "Manga_Title 012.NJX", "Manga_Title012.NJX",
    "Manga_Title 14.5.NJX" -- but not "Manga_Title Rouge 01.NJX"."""
    pattern = re.compile(re.escape(prefix) + r'\s*\d', re.IGNORECASE)
    matches = [p for p in folder.iterdir()
               if p.is_file() and p.suffix.lower() == '.njx' and pattern.match(p.stem)]
    return sorted(matches, key=lambda p: natural_key(p.name))


def natural_key(name: str) -> list:
    """Sort "Manga_Title 9" before "Manga_Title 10"."""
    return [int(t) if t.isdigit() else t.lower() for t in re.split(r'(\d+)', name)]


def ask_interactively(default_folder: Path) -> tuple[list[Path], Path | None]:
    """No arguments given: ask for a file or a prefix."""
    answer = input("NJX file to convert, or a series prefix to convert all its "
                   "chapters: ").strip().strip('"')
    if not answer:
        sys.exit("Nothing to do.")
    path = Path(answer)
    if path.suffix.lower() == '.njx' or path.is_file():
        return [path], None
    folder = input(f"Folder to look in [{default_folder}]: ").strip().strip('"')
    return files_with_prefix(Path(folder) if folder else default_folder, answer), None


def main():
    ap = argparse.ArgumentParser(
        description="Convert NJStar .NJX documents to plain .txt files.")
    ap.add_argument('files', nargs='*', type=Path, help=".NJX files to convert")
    ap.add_argument('-p', '--prefix',
                    help='Convert every "<prefix> <number>.NJX" in --folder, '
                         'e.g. --prefix "Manga_Title"')
    ap.add_argument('-f', '--folder', type=Path, default=Path.cwd(),
                    help="Folder to search with --prefix (default: current folder)")
    ap.add_argument('-o', '--output', type=Path,
                    help="Folder to write .txt files to (default: next to each .NJX)")
    ap.add_argument('--overwrite', action='store_true',
                    help="Replace .txt files that already exist")
    args = ap.parse_args()

    files = list(args.files)
    if args.prefix:
        found = files_with_prefix(args.folder, args.prefix)
        if not found:
            sys.exit(f'No files named "{args.prefix} <number>.NJX" in {args.folder}')
        files += found
    if not files:
        files, _ = ask_interactively(args.folder)
        if not files:
            sys.exit("No matching .NJX files found.")

    counts = {'converted': 0, 'skipped': 0, 'failed': 0}
    for src in files:
        result = convert(src, args.output, args.overwrite)
        if result == 'converted':
            counts['converted'] += 1
            print(f"  converted  {src.name}")
        elif result == 'skipped':
            counts['skipped'] += 1
            print(f"  skipped    {src.name} (.txt already exists; use --overwrite)")
        else:
            counts['failed'] += 1
            print(f"  FAILED     {src.name}: {result}")

    print(f"\n{counts['converted']} converted, {counts['skipped']} skipped, "
          f"{counts['failed']} failed.")
    if counts['failed']:
        sys.exit(1)


if __name__ == '__main__':
    main()
