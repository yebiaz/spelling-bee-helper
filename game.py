"""The game state: guessing, hints, NYT reconciliation, scoring.

Ported from the notebook with one behaviour fix, marked FIX below: the old
hint tracker used a single "positions" list for two different jobs, so an
easy-mode "Random Letter: e" hint (which never tells you *where* the letter
goes) still filled in a blank in the revealed pattern. The tracker now keeps
"positions" (letters already spent, so hints don't repeat themselves) separate
from "shown" (positions the player actually knows), and revealedSoFar reads
only from "shown".
"""

import random

from difficulty import wordFreq


class GameSaving:  # all one class since all use solutions or letters, dont have to keep reusing

    def __init__(self, solutions, letters, center, difficulty):
        self.solutions = set(solutions)
        self.letters = set(letters)
        self.center = center
        self.wordsFound = set()
        self.alreadyHints = {}
        self.difficulty = difficulty
        self.filteredOut = []  # set aside during reconciliation, most likely first
        self.notCounted = set()  # words the player reported NYT does not count

    # user inputting and checking
    def userGuess(self, wordInput):
        word = wordInput.strip().lower()

        error = self.isValid(word)
        if error is not None:
            return error
        if word in self.wordsFound:
            return "Already found!"
        if word in self.notCounted:
            return "You marked this one as not counted by NYT."

        found = self.puzzleSpecValid(word)
        return found

    # if input is valid
    def isValid(self, word):
        if not isinstance(word, str):
            return "Must be a string of letters"
        if not word.isalpha():
            return "Must have just letters"
        if len(word) < 4:
            return "Too short"
        if len(set(word)) > 7:
            return "Must be made up of maximum 7 unique letters"
        return None

    # if word works for puzzle
    def puzzleSpecValid(self, word):
        if self.center not in word:
            return f"Must include {self.center}"
        nonValidLetters = set(word) - self.letters
        if len(nonValidLetters) > 0:
            return f"Must use {''.join(sorted(self.letters))}"
        if word in self.solutions:
            self.wordsFound.add(word)
            return "Congrats, found!"
        return "Not a valid word"

    # some helpful methods for evaluating how far in game
    def wordsLeft(self):
        return self.solutions - self.wordsFound

    def rareLeft(self):
        left = self.wordsLeft()
        if len(left) == 0:
            return False

        for word in left:
            if wordFreq(word) > 2.25:
                return False
        return True  # "Only rare words left!"

    # NYT COMPARING - nyt gives two types of hints

    # first they give prefix (first letter) & len of words and the num of them fitting these conditions
    def getPrefixLen(self, first, length, num):
        first = first.lower()
        fitLeft = []

        for word in self.wordsLeft():
            if word.startswith(first) == False or length != len(word):
                continue
            fitLeft.append(word)

        return self.nytCompare(fitLeft, num)

    # prefixTwo: the number of words that have _ _ letters
    def twoLetsGiven(self, firstTwo, num):
        fitLeft = []
        firstTwo = firstTwo.lower()

        for word in self.wordsLeft():
            if word.startswith(firstTwo) == False:
                continue
            fitLeft.append(word)

        return self.nytCompare(fitLeft, num)

    # need to compare with NYT's hints just in case we have different answers since NYT doesn't use one singular dict
    def nytCompare(self, fitLeft, num):
        if len(fitLeft) < num:  # user error or dictionary lacking
            return {
                "status": "missing",
                "msg": f"Uh oh, we have not found {num - len(fitLeft)} word(s) in our dictionary. "
                       "Recheck NYT hints or it may be our dictionary",
                "kept": fitLeft,
                "forLater": [],
            }
        elif len(fitLeft) > num:  # need to highlight most likely of our solutions
            kept, forLater = self.filterCommon(fitLeft, num)
            for word in forLater:
                self.solutions.discard(word)
                self.filteredOut.append(word)

            return {
                "status": "extra",
                "msg": f"we have found {len(fitLeft)-num} too many word(s) and will use the most common",
                "kept": kept,
                "forLater": forLater,
            }
        else:
            return {
                "status": "equal",
                "msg": "Matches NYT exactly",
                "kept": fitLeft,
                "forLater": [],
            }  # same as nyt

    def likelihood(self, word):
        """How likely NYT is to have counted this word.

        Raw corpus frequency was the old answer, but it undersells regular
        forms of common words: LOONY is rare as a string and obvious as an
        answer. familiarity() folds in the stem, so use it when the difficulty
        model is available.
        """
        if self.difficulty is not None and hasattr(self.difficulty, "familiarity"):
            return self.difficulty.familiarity(word)
        return wordFreq(word)

    # method for most common, save extra just in case it actually is that
    def filterCommon(self, fitWords, num):
        # first approach was dictionary but this was shorter as a list of tuples
        WandF = []
        for word in fitWords:
            WandF.append((self.likelihood(word), word))
        WandF.sort(reverse=True)  # easier if rev

        onlyWords = []
        for word in WandF:
            onlyWords.append(word[1])

        keep = onlyWords[0:num]
        forLater = onlyWords[num:]

        return keep, forLater

    # in case none of the ones kept worked
    def restoreFromForLater(self):
        if not self.filteredOut:
            return "No alternatives."
        word = self.filteredOut.pop(0)  # most likely one
        self.solutions.add(word)
        return f"Restored word: {word}"

    def rejectWord(self, word):
        """The player says NYT did not count this word. Swap in the next best.

        Reconciliation has to guess which of our candidates NYT kept, and it
        will sometimes guess wrong. Rather than throw the losers away, they sit
        in filteredOut in likelihood order. When a kept word turns out to be
        wrong, the best set-aside word from the same bucket takes its place, so
        the bucket count stays right and the player gets a real second guess.

        Only words from the same bucket are eligible. Promoting an unrelated
        word would put the bucket counts back out of step with NYT, which is
        the whole thing reconciliation was trying to fix.
        """
        word = word.strip().lower()
        if word not in self.solutions:
            return {"removed": None, "promoted": None, "msg": f"{word} is not in the current answer set."}

        self.solutions.discard(word)
        self.wordsFound.discard(word)
        self.notCounted.add(word)

        pools = [
            [w for w in self.filteredOut if w[:2] == word[:2]],
            [w for w in self.filteredOut if w[0] == word[0] and len(w) == len(word)],
        ]
        for pool in pools:
            candidates = [w for w in pool if w not in self.notCounted]
            if not candidates:
                continue
            replacement = max(candidates, key=self.likelihood)
            self.filteredOut.remove(replacement)
            self.solutions.add(replacement)
            return {
                "removed": word,
                "promoted": replacement,
                "msg": f"Dropped {word}, brought in {replacement} instead.",
            }

        return {
            "removed": word,
            "promoted": None,
            "msg": f"Dropped {word}. Nothing set aside fits that bucket, so it is one short now.",
        }

    ## LOGISTIC REGRESSION to leverage for hinting
    def initHint(self, word):
        if word not in self.alreadyHints:
            # FIX: "positions" = letters already spent on hints, "shown" = positions the player knows
            self.alreadyHints[word] = {"positions": [], "shown": [], "scrambled": False}

    def findPos(self, word):
        posLeft = []
        for i in range(len(word)):
            if i not in self.alreadyHints[word]["positions"]:
                posLeft.append(i)

        if len(posLeft) == 0:
            return None
        pos = random.choice(posLeft)
        self.alreadyHints[word]["positions"].append(pos)
        return pos

    def whichHint(self, word, hintType="autoDiff"):  # IMPORTANT DESIGN CHOICE
        self.initHint(word)

        difficultySpecWord = self.difficulty.predictDifficulty(word)
        if hintType == "randLetter" or (hintType == "autoDiff" and difficultySpecWord == 0):
            pos = self.findPos(word)
            if pos is None:
                return "All letters have already been revealed!"
            return f"Random letter: {word[pos]}"  # small

        elif hintType == "letterAndPos" or (hintType == "autoDiff" and difficultySpecWord == 1):
            pos = self.findPos(word)
            if pos is None:
                return "All letters have already been revealed!"
            self.alreadyHints[word]["shown"].append(pos)  # this one the player can place
            return f"Letter {pos + 1} is: {word[pos]}"  # med

        else:
            if self.alreadyHints[word]["scrambled"] == True:
                return "Already given scrambled hint for this word"
            else:
                self.alreadyHints[word]["scrambled"] = True
                scramble = list(word)
                random.shuffle(scramble)
                return f"Scrambled: {''.join(scramble)}"  # big

    # the letters a bucket gives away for free are spent, so hints never waste
    # themselves re-revealing them.
    #
    # They are deliberately NOT added to "shown". "shown" is what the player has
    # permanently earned; a bucket prefix is only true while you are looking at
    # that bucket. Marking it shown leaked across buckets: after opening AN, the
    # A-of-4-letters bucket displayed A N _ _ instead of A _ _ _. The view layer
    # adds the current bucket's prefix on top of "shown" instead.
    def applyPrefixReveal(self, word, prefix):
        self.initHint(word)

        for i in range(len(prefix)):
            if i not in self.alreadyHints[word]["positions"]:
                self.alreadyHints[word]["positions"].append(i)

    def bucketDisplay(self, word, prefixLen=0, showLength=True):
        """How a word looks inside a bucket.

        showLength=False hides the word's length entirely, which matters for the
        two-letter list: NYT tells you how many answers start with AN, not how
        long they are, and a row of blanks would give that away for free.
        """
        shown = set(range(prefixLen))
        if word in self.alreadyHints:
            shown |= set(self.alreadyHints[word]["shown"])

        if not showLength:
            revealed = [word[i].upper() for i in sorted(shown) if i < prefixLen]
            return " ".join(revealed) + " ..."

        return " ".join(word[i].upper() if i in shown else "_" for i in range(len(word)))

    def revealedSoFar(self, word):
        if word not in self.alreadyHints:
            return " ".join(["_"] * len(word))
        else:
            display = []
            for i in range(len(word)):
                if i in self.alreadyHints[word]["shown"]:
                    display.append(word[i].upper())
                else:
                    display.append("_")
            return " ".join(display)

    def roadmap(self):  # of all hints
        prefixLenCounting = {}
        twoLetterCounting = {}
        for word in self.wordsLeft():
            # one letter maps
            letter = (word[0], len(word))
            prefixLenCounting[letter] = prefixLenCounting.get(letter, 0) + 1

            # two letters prefixing
            letters2 = word[0:2]
            twoLetterCounting[letters2] = twoLetterCounting.get(letters2, 0) + 1

        return prefixLenCounting, twoLetterCounting

    # nyt scoring and ranks
    def scoreSpecWord(self, word):
        if len(word) == 4:
            points = 1
        else:
            points = len(word)
            if len(set(word)) == 7:
                points += 7  # extra if pangram
        return points

    def totalScore(self):
        totalScore = 0
        for word in self.wordsFound:
            totalScore += self.scoreSpecWord(word)
        return totalScore

    def maxPossScore(self):
        max = 0
        for word in self.solutions:
            max += self.scoreSpecWord(word)
        return max

    def percent(self):
        maxScore = self.maxPossScore()
        if maxScore == 0:
            return 0
        return (self.totalScore() / maxScore) * 100

    def ranking(self):
        percentDone = self.percent()
        if percentDone <= 10:
            return "Beginner"
        elif percentDone <= 30:
            return "Good"
        elif percentDone <= 50:
            return "Great"
        elif percentDone <= 70:
            return "Amazing"
        elif percentDone < 100:
            return "Genius"
        else:
            return "Queen Bee"
