"""Loading the word list.

Ported from the Colab notebook. Only change: the file is downloaded once and
cached on disk instead of being deleted and re-downloaded on every run, so the
app starts instantly after the first launch and works offline afterwards.
"""

import os
import urllib.request

ENABLE_URL = "https://raw.githubusercontent.com/dolph/dictionary/master/enable1.txt"
ENABLE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "enable1.txt")


def downloadDict(path=ENABLE_PATH):
    """Grab enable1.txt if we don't already have it."""
    if not os.path.exists(path):
        urllib.request.urlretrieve(ENABLE_URL, path)
    return path


def loadFile(myFile):
    words = set()
    pangrams = set()

    with open(myFile) as f:  # from stats 102 knowledge but needed to review this with open as f
        for word in f:
            word = word.strip()
            if not word.islower() or not word.isalpha() or len(word) < 4:
                continue
            if len(set(word)) > 7:
                continue
            words.add(word)
            if len(set(word)) == 7:
                pangrams.add(word)
    return words, pangrams


def loadDictionary():
    """Returns (words, pangrams)."""
    return loadFile(downloadDict())
