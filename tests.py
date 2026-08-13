"""Tests carried over from the notebook, plus a few extras.

Run with:   python tests.py
"""

import random

from dictionary import loadDictionary
from difficulty import trainDifficulty
from difficulty import wordFreq as wordFreqOf
from game import GameSaving
from trie import buildTrie, level, pangramsLeft


def testTrieMini():
    trie = buildTrie(["album", "albumen", "lean", "lane", "blame"])
    results = trie.search(set("albumen"), "a")
    assert results == {"album", "albumen", "lean", "lane", "blame"}, results
    print("mini trie ok:", sorted(results))


def testTrieWhole(wholeTrie):
    results = wholeTrie.search(set("albumen"), "a")
    assert "albumen" in results and "album" in results
    assert all("a" in w for w in results)
    print("whole-dictionary trie ok:", len(results), "words from ALBUMEN")


def testLevel(wholeTrie, myPangrams):
    letters, center, solutions = level(wholeTrie, myPangrams)
    assert 20 <= len(solutions) <= 50
    assert center in letters and len(letters) == 7
    assert pangramsLeft(solutions), "a generated level should contain its pangram"
    print("level ok:", sorted(letters), "center", center, "->", len(solutions), "solutions")


def testGuessing(difficulty):
    letters = {"b", "n", "a", "l", "u", "e", "m"}
    solutions = {"album", "albumen", "lean", "lane", "blame"}
    game = GameSaving(solutions, letters, "a", difficulty)

    assert game.userGuess("abc123") == "Must have just letters"
    assert game.userGuess("abc") == "Too short"
    assert game.userGuess("lull") == "Must include a"
    assert game.userGuess("album") == "Congrats, found!"
    assert game.userGuess("album") == "Already found!"
    assert "album" not in game.wordsLeft()
    print("guess validation ok")


def testHints(difficulty):
    letters = {"b", "n", "a", "l", "u", "e", "m"}
    solutions = {"album", "albumen", "lean", "lane", "blame"}
    game = GameSaving(solutions, letters, "a", difficulty)

    assert game.revealedSoFar("albumen") == "_ _ _ _ _ _ _"
    # small hint gives a letter but not a position, so no blank should fill in
    game.whichHint("albumen", "randLetter")
    assert game.revealedSoFar("albumen") == "_ _ _ _ _ _ _"
    # medium hint does place a letter
    game.whichHint("albumen", "letterAndPos")
    assert game.revealedSoFar("albumen").count("_") == 6
    scrambled = game.whichHint("albumen", "scrambled")
    assert sorted(scrambled.split()[-1]) == sorted("albumen")
    assert game.whichHint("albumen", "scrambled") == "Already given scrambled hint for this word"
    print("hints ok:", game.revealedSoFar("albumen"))


def testNYTCompare(difficulty):
    letters = set("albumen")
    game = GameSaving({"album", "albumen", "lean", "lane", "blame"}, letters, "a", difficulty)

    missing = game.getPrefixLen("a", 5, 2)  # we only have one 5-letter A word
    assert missing["status"] == "missing"

    exact = game.twoLetsGiven("al", 2)
    assert exact["status"] == "equal"

    extra = GameSaving({"album", "albumen", "alum", "alumna"}, letters, "a", difficulty)
    trimmed = extra.twoLetsGiven("al", 3)
    assert trimmed["status"] == "extra"
    assert len(trimmed["kept"]) == 3
    assert len(extra.solutions) == 3
    assert extra.restoreFromForLater().startswith("Restored word:")
    assert len(extra.solutions) == 4
    print("nyt reconciliation ok:", trimmed["kept"], "set aside", trimmed["forLater"])


def testScoring(difficulty):
    letters = set("albumen")
    game = GameSaving({"album", "albumen", "lean", "lane", "blame"}, letters, "a", difficulty)
    game.wordsFound = {"album", "lean"}
    assert game.scoreSpecWord("lean") == 1  # 4 letters -> 1 point
    assert game.scoreSpecWord("albumen") == 14  # 7 letters + pangram bonus
    assert game.totalScore() == 6
    print("scoring ok:", game.totalScore(), "/", game.maxPossScore(), "->", game.ranking())


def testRare(difficulty):
    letters = set("bibelot")
    rare = GameSaving({"bibelot", "oppugn", "biennia"}, letters, "b", difficulty)
    assert rare.rareLeft() is True
    mixed = GameSaving({"album", "bibelot"}, set("albumet"), "a", difficulty)
    assert mixed.rareLeft() is False
    print("rare-words-left check ok")


def testLabels(difficulty):
    """The old rule needed 8+ letters to call anything hard, which mislabelled
    short obscure words like HALCYON. Frequency now leads."""
    assert difficulty.logLabels("halcyon") == 2, "HALCYON is a hard word"
    assert difficulty.logLabels("only") == 0
    assert difficulty.logLabels("bibelot") == 2
    assert difficulty.logLabels("llano") == 2
    assert difficulty.logLabels("loan") == 0

    # a familiar stem should lift a rare form, but only so far
    assert difficulty.stemFreq("loony") > 0, "LOONY should find LOON"
    assert difficulty.stemFreq("chancy") > 0, "CHANCY should find CHANCE"
    assert difficulty.stemFreq("tommyrot") == 0, "-ROT is not a suffix"
    assert difficulty.familiarity("loony") > wordFreqOf("loony")
    assert difficulty.logLabels("chancy") != 0, "a common stem should not make CHANCY common"
    print("difficulty labels ok: halcyon obscure, loony lifted by loon, tommyrot not by tommy")


def testRejectAndReplace(difficulty):
    letters = set("albumen")
    game = GameSaving({"album", "albumen", "alum", "alumna"}, letters, "a", difficulty)
    game.twoLetsGiven("al", 3)  # trims one into filteredOut
    assert game.filteredOut

    kept = sorted(game.solutions)
    swap = game.rejectWord(kept[0])
    assert swap["removed"] == kept[0]
    assert swap["promoted"] is not None, "should have pulled a replacement in"
    assert swap["promoted"] in game.solutions
    assert kept[0] not in game.solutions
    assert kept[0] in game.notCounted
    assert len(game.solutions) == 3, "the bucket count should stay right"

    # a rejected word never comes back
    again = game.rejectWord(kept[0])
    assert again["promoted"] is None and "not in the current answer set" in again["msg"]
    print("reject and replace ok:", swap["msg"])


def testBlacklist(difficulty):
    letters = set("albumen")
    game = GameSaving({"album", "albumen", "lean"}, letters, "a", difficulty)
    game.twoLetsGiven("al", 1)  # push one into filteredOut so there is a replacement
    kept = [w for w in game.solutions if w.startswith("al")][0]
    game.rejectWord(kept)
    assert kept in game.notCounted
    assert game.userGuess(kept) == "You marked this one as not counted by NYT."
    print("blacklist ok:", kept, "cannot be found again")


def testHintGridParse(wholeTrie, difficulty):
    """Only runs if Tesseract and a sample screenshot are available."""
    import os

    from hintgrid import OCR_AVAILABLE, applyGrid, checkParse, inferCenter, parseHintGrid

    sample = "sample_hint_grid.png"
    if not OCR_AVAILABLE or not os.path.exists(sample):
        print("hint grid OCR: skipped (no tesseract or no sample_hint_grid.png)")
        return

    parsed = parseHintGrid(sample)
    assert len(parsed["letters"]) == 7, parsed["letters"]
    assert parsed["words"], "should have read a word count"
    assert parsed["twoLetters"], "should have read a two-letter list"
    assert sum(parsed["gridCounts"].values()) == parsed["words"], "grid should add to the word count"
    assert not checkParse(parsed), checkParse(parsed)

    ranking = inferCenter(wholeTrie, parsed["letters"], parsed["twoLetters"])
    center = ranking[0][0]
    assert ranking[0][1] > ranking[1][1], "the best centre should actually win"

    game = GameSaving(wholeTrie.search(parsed["letters"], center), parsed["letters"], center, difficulty)
    before = len(game.solutions)
    report = applyGrid(game, parsed["twoLetters"], parsed["gridCounts"])
    assert len(report["kept"]) <= parsed["words"], "should never keep more than NYT counted"
    assert len(game.solutions) == len(report["kept"])
    assert game.filteredOut, "dropped words should stay recoverable"
    print(
        f"hint grid OCR ok: {sorted(parsed['letters'])} centre {center}, "
        f"{before} -> {len(report['kept'])} of {parsed['words']}"
    )


if __name__ == "__main__":
    random.seed(0)
    myDict, myPangrams = loadDictionary()
    print(f"loaded {len(myDict)} words, {len(myPangrams)} pangrams")
    assert "tommyrot" in myDict, "rare word check"

    wholeTrie = buildTrie(myDict)
    difficulty, metrics = trainDifficulty(myDict)
    print("difficulty model: mean cv %.3f, test %.3f" % (metrics["meanCrossVal"], metrics["testAccuracy"]))
    assert metrics["testAccuracy"] > 0.8

    testTrieMini()
    testTrieWhole(wholeTrie)
    testLevel(wholeTrie, myPangrams)
    testGuessing(difficulty)
    testHints(difficulty)
    testNYTCompare(difficulty)
    testScoring(difficulty)
    testRare(difficulty)
    testLabels(difficulty)
    testRejectAndReplace(difficulty)
    testBlacklist(difficulty)
    testHintGridParse(wholeTrie, difficulty)
    print("\nall tests passed")
