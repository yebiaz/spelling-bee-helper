"""Reading a NYT hint grid out of a screenshot.

The hint page has four things worth pulling out:

    the 7 letters, with the center one in bold
    WORDS / POINTS / PANGRAMS totals
    the first-letter x word-length grid
    the two-letter list (AN-7, CA-8, CH-1, ...)

The two-letter list is plain text and OCRs cleanly. The grid does not: the
columns are separated by whitespace, and Tesseract cannot tell "2 6 8" from
"268". So the grid is read from character bounding boxes instead of from the
text output - characters are clustered into columns by their x position, which
recovers the columns exactly. The row and column totals then check the parse.

The bold center letter is not recoverable from OCR (stroke weight barely
differs at screenshot resolution), so it is inferred instead: for each of the
7 possible centers, solve the puzzle with the trie and see whose two-letter
distribution matches NYT's. The right center wins by a wide margin.

Needs Tesseract:
    macOS    brew install tesseract
    Ubuntu   sudo apt install tesseract-ocr
    Windows  https://github.com/UB-Mannheim/tesseract/wiki
"""

import re

try:
    import pytesseract
    from PIL import Image

    OCR_AVAILABLE = True
    OCR_PROBLEM = None
except ImportError as err:  # pillow or pytesseract not installed
    OCR_AVAILABLE = False
    OCR_PROBLEM = str(err)


def _charBoxes(image):
    """Every character with its centre point, in top-left origin coordinates."""
    W, H = image.size
    chars = []
    for line in pytesseract.image_to_boxes(image, config="--psm 6").splitlines():
        parts = line.split()
        if len(parts) < 5:
            continue
        ch, x1, y1, x2, y2 = parts[0], int(parts[1]), int(parts[2]), int(parts[3]), int(parts[4])
        chars.append(
            {
                "char": ch,
                "left": x1,
                "right": x2,
                "top": H - y2,
                "bottom": H - y1,
                "x": (x1 + x2) / 2,
                "y": H - (y1 + y2) / 2,
            }
        )
    return chars


def _groupLines(chars, tolerance=20):
    """Bucket characters into text lines by y position."""
    chars = sorted(chars, key=lambda c: c["y"])
    lines = []
    current = []
    last = None
    for c in chars:
        if last is not None and abs(c["y"] - last) >= tolerance:
            lines.append(sorted(current, key=lambda c: c["x"]))
            current = []
        current.append(c)
        last = c["y"]
    if current:
        lines.append(sorted(current, key=lambda c: c["x"]))
    return lines


def _cluster(values, gap):
    """Simple 1-D clustering: split wherever consecutive values jump by `gap`."""
    values = sorted(values)
    groups = []
    current = [values[0]]
    for v in values[1:]:
        if v - current[-1] < gap:
            current.append(v)
        else:
            groups.append(current)
            current = [v]
    groups.append(current)
    return [sum(g) / len(g) for g in groups]


def _readGrid(lines):
    """The first-letter x length table, read by column position.

    Returns (counts, totals) where counts maps (letter, length) -> count and
    totals maps letter -> the row total NYT printed.
    """
    rows = [ln for ln in lines if len(ln) > 2 and ln[1]["char"] == ":"]
    if not rows:
        return {}, {}, {}

    labelEdge = max(ln[1]["right"] for ln in rows)
    xs = [c["x"] for ln in rows for c in ln if c["x"] > labelEdge]
    if not xs:
        return {}, {}, {}
    centers = _cluster(xs, gap=45)

    # last column is the sigma total; the rest are word lengths starting at 4
    lengths = [4 + i for i in range(len(centers) - 1)]

    counts = {}
    rowTotals = {}
    colTotals = {}
    for ln in rows:
        label = ln[0]["char"]
        cells = [""] * len(centers)
        for c in ln[2:]:
            i = min(range(len(centers)), key=lambda k: abs(centers[k] - c["x"]))
            cells[i] += c["char"]

        isSigmaRow = not label.isalpha() or label in "xX" and len(rows) > 1 and ln is rows[-1]
        for i, cell in enumerate(cells):
            digits = re.sub(r"\D", "", cell)
            value = int(digits) if digits else 0
            if i == len(centers) - 1:
                if isSigmaRow:
                    colTotals["all"] = value
                else:
                    rowTotals[label.lower()] = value
            elif isSigmaRow:
                colTotals[lengths[i]] = value
            elif value:
                counts[(label.lower(), lengths[i])] = value

    return counts, rowTotals, colTotals


def parseHintGrid(imageFile):
    """Read a NYT hint screenshot. Returns a dict of everything found."""
    if not OCR_AVAILABLE:
        raise RuntimeError(
            "OCR is not set up. Install the Python packages with "
            "`pip install pytesseract pillow`, and the Tesseract engine itself "
            "with `brew install tesseract` (macOS) or "
            "`sudo apt install tesseract-ocr` (Linux)."
        )

    image = Image.open(imageFile).convert("L")
    # OCR is noticeably more accurate on an upscaled image
    image = image.resize((image.width * 2, image.height * 2), Image.LANCZOS)

    text = pytesseract.image_to_string(image, config="--psm 6")
    lines = _groupLines(_charBoxes(image))

    # the 7 letters: the first line that is exactly 7 letters and nothing else
    letters = ""
    for ln in lines:
        joined = "".join(c["char"] for c in ln)
        if len(joined) == 7 and joined.isalpha():
            letters = joined.lower()
            break

    # totals line
    def grabNumber(label):
        match = re.search(label + r"\D{0,3}(\d+)", text, re.IGNORECASE)
        return int(match.group(1)) if match else None

    counts, rowTotals, colTotals = _readGrid(lines)

    # two-letter list, e.g. "CA-8 CH-1 CL-2"
    twoLetters = {}
    for prefix, count in re.findall(r"\b([A-Za-z]{2})\s*[-–—]\s*(\d+)", text):
        twoLetters[prefix.lower()] = int(count)

    return {
        "letters": set(letters),
        "words": grabNumber("WORDS"),
        "points": grabNumber("POINTS"),
        "pangrams": grabNumber("PANGRAMS"),
        "gridCounts": counts,
        "rowTotals": rowTotals,
        "colTotals": colTotals,
        "twoLetters": twoLetters,
        "rawText": text,
    }


def checkParse(parsed):
    """Cross-check the parse against the totals NYT printed. Returns warnings."""
    warnings = []

    if len(parsed["letters"]) != 7:
        warnings.append(f"Found {len(parsed['letters'])} letters, expected 7.")

    # each grid row should add up to the row total
    for letter, total in parsed["rowTotals"].items():
        rowSum = sum(v for (l, _), v in parsed["gridCounts"].items() if l == letter)
        if rowSum != total:
            warnings.append(f"Row {letter.upper()} adds to {rowSum} but the grid says {total}.")

    # the two-letter counts for a given first letter should match its row total
    for letter, total in parsed["rowTotals"].items():
        twoSum = sum(v for p, v in parsed["twoLetters"].items() if p[0] == letter)
        if twoSum and twoSum != total:
            warnings.append(
                f"Two-letter entries starting with {letter.upper()} add to {twoSum}, "
                f"but the grid row says {total}."
            )

    gridTotal = sum(parsed["gridCounts"].values())
    if parsed["words"] and gridTotal and gridTotal != parsed["words"]:
        warnings.append(f"Grid adds to {gridTotal} but the header says {parsed['words']} words.")

    return warnings


def inferCenter(trie, letters, twoLetters):
    """Work out which letter is the bold one.

    Solves the puzzle once per candidate centre and scores each against NYT's
    two-letter distribution (F1 of the shared bucket counts). Returns a list of
    (center, score, solutionCount) sorted best first.
    """
    if not twoLetters:
        return []

    nytTotal = sum(twoLetters.values())
    scored = []
    for center in sorted(letters):
        solutions = trie.search(set(letters), center)
        mine = {}
        for word in solutions:
            mine[word[:2]] = mine.get(word[:2], 0) + 1

        overlap = sum(min(count, mine.get(prefix, 0)) for prefix, count in twoLetters.items())
        recall = overlap / nytTotal if nytTotal else 0
        precision = overlap / len(solutions) if solutions else 0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0
        scored.append((center, f1, len(solutions)))

    scored.sort(key=lambda t: t[1], reverse=True)
    return scored


def applyGrid(game, twoLetters, gridCounts=None):
    """Reconcile the whole puzzle at once against everything NYT published.

    NYT gives two overlapping tallies of the same answer set: how many answers
    start with each two-letter pair, and how many start with each letter at each
    length. Checking them one bucket at a time (what the manual form does) uses
    only one tally at a time, so filterCommon sometimes keeps a common word that
    the length table rules out.

    This keeps both tallies open at once. Candidate words are walked in order of
    frequency, and a word is kept only if its two-letter bucket AND its
    letter-length cell both still have room. Whatever quota is left over at the
    end is real signal: those are answers NYT has that enable does not.

    Words that get dropped go into game.filteredOut in likelihood order, so
    restoreFromForLater and rejectWord can pull the next best one back in when
    the player reports that a kept word was not counted.
    """
    twoLeft = dict(twoLetters)
    gridLeft = dict(gridCounts) if gridCounts else None

    candidates = sorted(game.wordsLeft(), key=lambda w: (-game.likelihood(w), w))
    kept = []
    dropped = []

    for word in candidates:
        twoKey = word[:2]
        gridKey = (word[0], len(word))

        roomTwo = twoLeft.get(twoKey, 0) > 0
        roomGrid = True if gridLeft is None else gridLeft.get(gridKey, 0) > 0

        if roomTwo and roomGrid:
            twoLeft[twoKey] -= 1
            if gridLeft is not None:
                gridLeft[gridKey] -= 1
            kept.append(word)
        else:
            dropped.append(word)

    for word in dropped:
        game.solutions.discard(word)
        game.filteredOut.append(word)

    # leftover quota = answers NYT counted that we could not find.
    # The two tallies describe the same missing words from different angles, so
    # pair them up where the first letters agree: "1 starting AN" plus "1 A word
    # of 6 letters" is almost certainly one word, AN + four more letters.
    twoGaps = {p: n for p, n in twoLeft.items() if n > 0}
    gridGaps = {}
    if gridLeft is not None:
        gridGaps = {k: n for k, n in gridLeft.items() if n > 0}

    gaps = []
    for prefix in sorted(twoGaps):
        for (letter, length) in sorted(gridGaps):
            if letter != prefix[0]:
                continue
            paired = min(twoGaps[prefix], gridGaps[(letter, length)])
            while paired > 0:
                gaps.append({"prefix": prefix, "length": length, "count": 1})
                twoGaps[prefix] -= 1
                gridGaps[(letter, length)] -= 1
                paired -= 1
            if twoGaps[prefix] == 0:
                break
    gridGaps = {k: n for k, n in gridGaps.items() if n > 0}

    for prefix, remaining in sorted(twoGaps.items()):
        if remaining > 0:
            gaps.append({"prefix": prefix, "length": None, "count": remaining})
    for (letter, length), remaining in sorted(gridGaps.items()):
        if remaining > 0:
            gaps.append({"prefix": letter, "length": length, "count": remaining})

    return {
        "kept": kept,
        "dropped": dropped,
        "gaps": gaps,
        "target": sum(twoLetters.values()) if twoLetters else None,
    }


def describeGap(gap):
    """One readable line for a missing answer."""
    prefix = gap["prefix"].upper()
    plural = "s" if gap["count"] > 1 else ""

    if gap["length"]:
        blanks = " ".join(["_"] * (gap["length"] - len(gap["prefix"])))
        return f"{gap['count']} word{plural}: {' '.join(prefix)} {blanks}  ({gap['length']} letters)"
    return f"{gap['count']} word{plural} starting {' '.join(prefix)}, length unknown"
