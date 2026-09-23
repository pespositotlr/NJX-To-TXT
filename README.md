# NJX To TXT

Converts [NJStar](https://www.njstar.com/) word processor documents (`.NJX`)
into plain UTF-8 `.txt` files: just the text, with no formatting, the same as
opening the document in NJStar and copy-pasting everything into Notepad.

## Requirements

Python 3.10+ (standard library only, nothing to install).

## Usage

```bash
# One or more files. Each .txt is written next to its .NJX.
python njx_to_txt.py "Manga_Title 012.NJX"
python njx_to_txt.py "Manga_Title 012.NJX" "Manga_Title 013.NJX"

# Every chapter of a series: all "<prefix> <number>.NJX" files in a folder.
python njx_to_txt.py --prefix "Manga_Title" --folder "D:\Translations"

# Write the .txt files somewhere else.
python njx_to_txt.py --prefix "Manga_Title" --folder "D:\Translations" -o "D:\Translations\txt"

# No arguments: it asks for a file or a prefix.
python njx_to_txt.py
```

| Option | Meaning |
|---|---|
| `files` | `.NJX` files to convert. |
| `-p`, `--prefix` | Convert every file named `<prefix><number>…`, e.g. `Manga_Title 012.NJX`, `Manga_Title012.NJX`, `Manga_Title 14.5.NJX`. Not case-sensitive. A different series that merely starts the same way (`Manga_Title The_Sequel 01.NJX`) isn't included. |
| `-f`, `--folder` | Folder to search with `--prefix` (default: the current folder). |
| `-o`, `--output` | Folder for the `.txt` files (default: next to each `.NJX`). |
| `--overwrite` | Replace `.txt` files that already exist. Without it they're skipped, so a `.txt` you've edited is never clobbered. |

The `.txt` files are UTF-8 with Windows line endings.

## How it works

An `.NJX` file is a header, the document text, then formatting data. The tool
reads just the text:

- **Two versions of the format.** Older files store text as 8-bit EUC-JP
  (with the occasional Western character such as `é` or `©` as a single byte),
  newer ones as UTF-16. Both are handled.
- **Line breaks.** A real line break is stored as a paragraph-style code
  followed by a line break. A line break with no code before it is just where
  NJStar word-wrapped the line, so it's removed and the line joined back up,
  as copy-paste does.
- **Page header and footer** blocks at the start of newer files aren't part of
  the document body, so they're left out.

It was checked against about a thousand translations that had also been
copy-pasted out of NJStar by hand. Wherever the text itself hadn't been edited
since, the output matched exactly. In a few older files the tool is more
accurate than NJStar's own copy-paste, which garbled characters like `’`, `÷`
and `ü`.

## Limitations

- Only the text is extracted. Bold, italics, fonts and colours are dropped.
- If NJStar itself saved a character as `?` (it couldn't store it), the `.txt`
  will have `?` there too.
