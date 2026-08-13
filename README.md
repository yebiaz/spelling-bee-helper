# Spelling Bee Helper

A standalone version of the Spelling Bee project: generate a puzzle, play it, and get
hints whose strength is chosen by a logistic-regression difficulty model. It can also
reconcile its own solution set against the New York Times hint grid.

## Run it

```bash
pip install -r requirements.txt
streamlit run app.py
```

Reading NYT hint screenshots also needs the Tesseract engine itself, which is not a
Python package:

```bash
brew install tesseract              # macOS
sudo apt install tesseract-ocr      # Linux
```

Everything else works without it.

It opens in your browser at `http://localhost:8501`. Run the command from inside this
folder — `app.py` imports the other files by name, so it has to be the working directory.

`enable1.txt` is included, so nothing downloads. If the file ever goes missing,
`dictionary.py` re-fetches it from the same URL the notebook used.

To run the tests:

```bash
python tests.py
```

## What's in here

Every file sits in one folder, no subfolders. Keep them together.

```
app.py          the interface (Streamlit)
hintgrid.py     reading a NYT hint page out of a screenshot
dictionary.py   loading and filtering enable1.txt
trie.py         TrieNode, Trie, level generation
difficulty.py   word frequency + the logistic regression classifier
game.py         GameSaving: guessing, hints, NYT comparison, scoring
tests.py        the notebook's tests, plus a few more
enable1.txt     the word list
```

## Why the notebook GUI didn't work, and what changed

**Streamlit.** The original attempt failed because Streamlit was `pip install`ed inside
Colab. Streamlit isn't a notebook library — it's a web server. It has to be started from
a terminal with `streamlit run app.py`, and it needs a real `.py` file, which is why
nothing ever rendered. Nothing was wrong with the idea; it was the wrong environment.

**ipywidgets.** The fallback GUI was fighting a real limitation: `display()` calls inside
`Output` widgets that get re-created on every redraw, `global game` rebinding, and widget
state that Colab drops when the runtime disconnects. Rebuilding the roadmap on every guess
also stacked new button widgets on top of old ones.

Streamlit removes both problems. It re-runs the whole script top to bottom on every click,
so there's no widget state to keep in sync. Two rules make that work:

- Anything expensive (dictionary, trie, trained model) is wrapped in `@st.cache_resource`
  so it happens once per session instead of on every click.
- The game itself lives in `st.session_state`, so it survives the re-runs.

### Changes to the logic

The core code was ported over nearly line for line. Five deliberate changes:

1. **`enable1.txt` is cached on disk.** The notebook deleted and re-downloaded it every
   run; now it downloads only if missing, so startup is instant and works offline.
   Same file, same source: `dolph/dictionary` on GitHub. `en_US-large` (SCOWL) is not
   used, matching your decision that enable on its own was sufficient.
2. **`training()` returns metrics instead of printing them,** so the app can display the
   cross-validation scores in the sidebar. The training sample is now seeded, so the model
   is identical every launch.
3. **`level()` now targets 20-50 answers instead of 10-30,** which is closer to a real
   NYT puzzle. The sidebar slider changes the window without touching the code.
4. **The hint tracker got split in two.** `alreadyHints[word]["positions"]` used to do two
   jobs at once: remember which letters had been spent, *and* decide which blanks were
   filled in. That meant a small hint ("Random Letter: e"), which deliberately doesn't say
   *where* the letter goes, still filled in a blank. The old GUI worked around this with
   `if predictDifficulty(w) != 0`. There are now two lists — `positions` (spent) and
   `shown` (positions the player actually knows) — and `revealedSoFar` reads only `shown`.
5. **`penalty="l2"` was dropped from `LogisticRegression`.** It's the default, and recent
   scikit-learn warns about passing it explicitly. Behaviour is unchanged.

Everything else — the DFS trie search, the four
features, the three hint tiers, `nytCompare` / `filterCommon` / `restoreFromForLater`, the
scoring and rank ladder — is the notebook's logic unchanged.

## Difficulty labels

The notebook's rule could only call a word hard if it was **also 8+ letters**, so HALCYON
(zipf 2.65, and a pangram) came out middling. Frequency now leads and length is an
adjustment rather than a gate:

```
familiarity = corpus frequency
              lifted toward a familiar stem, by at most 1.2
              minus 0.5 if 8+ letters      (harder to see in the hive)
              plus 0.25 if 5 or fewer      (turn up by accident)

>= 3.9 common   >= 2.9 middling   below that obscure
```

The lift is the new fifth feature. LOONY is rare as a string but sits one -Y from LOON,
and that is genuinely easier to spot than its own frequency suggests. Only regular
suffixes count, which is why TOMMYROT gets nothing from the common name TOMMY. The lift is
capped so that CHANCE being very common does not drag CHANCY along with it.

On the NOYACHL puzzle this labels HALCYON, CANOLA, HONCHO, CLONAL, LLANO and CHANCY
obscure; LOONY, ANNOY, NYLON and CONN middling; ONLY, LOAN, CANAL and CANNON common.

One honest caveat worth knowing: because the labels are a deterministic function of the
features, the model is largely relearning the rule, which is why accuracy sits around
0.93. That is a fair measure of *fit*, not of whether the labels are right. The way to
make the model tell you something the rule doesn't is to hand-label a few hundred answers
from puzzles you have actually played and train on those.

## Reading the NYT hint page from a screenshot

Upload a screenshot of the hint page and the app fills in what the manual form used to
ask for. Three things make that work:

**The grid is read from character positions, not from OCR text.** Tesseract cannot tell
`2 6 8` from `268` — the columns are only separated by whitespace, and it merges them.
So the numeric grid is parsed from character bounding boxes: every character is clustered
into a column by its x coordinate, which recovers the columns exactly. The printed row and
column totals then check the parse, and any mismatch is shown as a warning. The two-letter
list is ordinary text and OCRs cleanly, so that part is a plain regex.

**The centre letter is inferred, not read.** It is marked only by being bold, and at
screenshot resolution the stroke weight barely differs from the other letters — measured
across the sample, the bold letter was not reliably separable. Instead each of the 7
letters is tried as the centre, the puzzle is solved with the trie, and the resulting
two-letter distribution is scored against NYT's (F1 over shared bucket counts). On the
sample the right answer won at 0.70 against 0.51 for the runner-up. The ranking is shown
so you can override it.

**Reconciliation uses both tallies at once.** NYT publishes two overlapping counts of the
same answer set. Checking one bucket at a time, as the manual form does, only ever uses
one of them, so `filterCommon` sometimes keeps a frequent word that the length grid rules
out. `applyGrid` holds both open: candidates are walked in frequency order and kept only
if their two-letter bucket *and* their letter-length cell both still have room. Leftover
quota is reported as a gap — on the sample it correctly identifies four answers NYT has
that enable does not, including a 9-letter word starting CY.

**Losing candidates are kept, not discarded.** Reconciliation has to guess which of our
candidates NYT kept, and it will sometimes guess wrong. The losers sit in `filteredOut` in
likelihood order. When a word you found turns out not to count, the ✕ beside it in the
**Found** list calls `rejectWord`, which drops it and promotes the best set-aside word
from the same two-letter bucket, falling back to the same letter-and-length cell. Nothing
outside the bucket is eligible, since promoting an unrelated word would put the counts
back out of step.
The bucket count stays right and you get a real second guess. On the sample, rejecting
ANCON brings in ANON, and rejecting CALLAN brings in CANCAN. Rejected words are remembered
so they never come back.

Ranking uses `familiarity` rather than raw frequency, so regular forms of common words are
preferred over strings that merely appear often in a corpus.

## Words NYT would not take

The ✕ beside a found word marks it as one NYT did not count. As well as swapping in a
replacement from the same bucket, the word goes on a session blacklist shown under **Not
counted** in the left panel. Blacklisted words are removed from every puzzle built
afterwards, and guessing one again returns a message saying so rather than congratulating
you a second time. **Clear this list** resets it. The list lives in the Streamlit session,
so it lasts until you stop the server.

## Notes

> The word list is [enable1](https://github.com/dolph/dictionary), the same one the notebook
used. Frequencies come from `wordfreq` (Zipf scale, 0–7).

> Not affiliated with, endorsed by, or sponsored by The New York Times.
> "The New York Times" and "Spelling Bee" are trademarks of The New York Times Company.
> This is an independent tool for personal use with puzzles you already have access to.