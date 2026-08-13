# Spelling Bee Helper

![Python](https://img.shields.io/badge/python-3.9+-blue)

## What this is?

A companion for the New York Times Spelling Bee, for people who play it religiously. NYT
gives you seven letters, a centre letter that every answer must use, and a grid of hints
that tells you how many answers start with each letter pair and each length.

## What we do that the NYT puzzle doesn't

**Keeps track for you.** Every answer still out there, sorted into the same buckets NYT
uses, with the words you have found ticked off. No more scribbling on a napkin.

**Tells you if a word is worth chasing.** That last stubborn answer: is it a word you
actually know, or is it LLANO? A logistic-regression model rates every remaining answer
common, middling or obscure from its frequency, length, letter pattern and whether it is a
regular form of a word you already know.

**Hints sized to the word.** Common words get a single letter with no position. Middling
ones get a letter and where it goes. Obscure ones get the whole thing scrambled, because a
letter would not have helped.

**Reconciles with NYT's answer list.** NYT does not use one fixed dictionary, so our
solver finds words they do not count and misses a few they do. Upload a screenshot of
their hint page and it works out which of our candidates they meant, and tells you what
shape the answers we are missing are.

## Running it

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
.gitignore      keeps __pycache__ and local files out of the repo
hintgrid.py     reading a NYT hint page out of a screenshot
dictionary.py   loading and filtering enable1.txt
trie.py         TrieNode, Trie, level generation
difficulty.py   word frequency + the logistic regression classifier
game.py         GameSaving: guessing, hints, NYT comparison, scoring
tests.py        the notebook's tests, plus a few more
enable1.txt     the word list
```

## Get Playing

Pick a random puzzle from the sidebar to practice, or enter today's NYT letters. Type
guesses in the box under the hive. Open a bucket on the right to see what is left and ask
for a hint.

