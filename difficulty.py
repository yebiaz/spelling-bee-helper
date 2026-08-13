"""Word frequency + the logistic regression difficulty classifier.

Ported from the notebook. Changes since:

  - training() returns metrics instead of printing them, and the sample is seeded.
  - logLabels was rebuilt. The old rule could only call a word hard if it was
    also 8+ letters long, so HALCYON (zipf 2.65, and a pangram) came out
    middling. Labels are now driven by frequency, with length as an adjustment
    rather than a gate. See familiarity() for the details.
  - a fifth feature, stem familiarity: how common the word you get by stripping
    a regular suffix is. LOONY is rare on its own but sits one -Y away from
    LOON, and that is genuinely easier to spot in a hive than its own
    frequency suggests.
  - familiarity() exposes the composite score used for labelling, so
    reconciliation can rank candidates by how likely a person is to know them
    rather than by raw corpus frequency.
"""

import random

import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.preprocessing import StandardScaler
from wordfreq import zipf_frequency  # the lower the score the less common, ranging from 0-7

# regular endings, longest first so -IES is tried before -S
SUFFIXES = ["ness", "iest", "ing", "ies", "ier", "est", "es", "ed", "er", "ly", "s", "d", "y"]

# how much a familiar stem is allowed to lift a rare word, in zipf points
STEM_DISCOUNT = 0.7
STEM_LIFT_CAP = 1.2


# method for finding word freq
def wordFreq(word):
    return zipf_frequency(word, "en")


# better as a class
class logDifficultyWord:
    def __init__(self, allWords=None):
        # l2 is LogisticRegression's default penalty, so passing it explicitly
        # is redundant and newer sklearn warns about the argument
        self.model = LogisticRegression(solver="lbfgs", max_iter=3000)
        self.trained = False
        # learned this needs to be included across class to be fitted and used when predicting
        self.scaler = StandardScaler()
        self.allWords = set(allWords) if allWords is not None else set()
        self.featureNames = ["length", "freq", "repeating", "vowels", "stem"]

    # ------------------------------------------------------------------
    # features
    # ------------------------------------------------------------------

    def stemFreq(self, word):
        """Frequency of the most common word this one is a regular form of.

        LOONY -> LOON, ANALLY -> ANAL, CHANCY -> CHANCE. Returns 0 when the
        word is not a regular derivative of anything, which is the case for
        HALCYON, LLANO, BIBELOT and most of the genuinely obscure answers.

        Only regular suffixes count. That matters: TOMMYROT starts with the
        common name TOMMY, but -ROT is not a suffix, so it gets no credit.
        """
        best = 0.0
        for suffix in SUFFIXES:
            if not word.endswith(suffix):
                continue
            base = word[: -len(suffix)]
            if len(base) < 4:
                continue
            # also try the spellings regular inflection hides: a dropped -E
            # (CHANCE + Y) and a doubled consonant (SLAM + M + ED)
            candidates = {base, base + "e"}
            if len(base) > 4 and base[-1] == base[-2]:
                candidates.add(base[:-1])
            for candidate in candidates:
                if candidate in self.allWords:
                    best = max(best, wordFreq(candidate))
        return best

    # have to make own features: len, word frequency, repeated letters, vowels, stem
    def features(self, word):
        length = len(word)
        freq = wordFreq(word)
        repeating = len(word) - len(set(word))
        sumVowels = 0

        for i in range(len(word)):
            if word[i] in "aeiou":
                sumVowels += 1
        vowels = abs(sumVowels / len(word) - 0.4)

        return [length, freq, repeating, vowels, self.stemFreq(word)]

    # ------------------------------------------------------------------
    # labels
    # ------------------------------------------------------------------

    def familiarity(self, word):
        """One number for how likely a player is to know this word.

        Starts from corpus frequency, then:

          - a familiar stem lifts the score, but by at most STEM_LIFT_CAP, so
            CHANCE being very common does not make CHANCY look common too
          - 8+ letters costs half a point, because long answers are harder to
            see in the hive even when the word itself is ordinary
          - 5 letters or fewer gains a quarter point, because short answers
            turn up by accident while you are trying other things
        """
        freq = wordFreq(word)
        length = len(word)

        lifted = min(self.stemFreq(word) - STEM_DISCOUNT, freq + STEM_LIFT_CAP)
        score = max(freq, lifted)

        if length >= 8:
            score -= 0.5
        if length <= 5:
            score += 0.25

        return score

    # labels: 0 common - 1 middling - 2 obscure
    def logLabels(self, word):
        score = self.familiarity(word)
        if score >= 3.9:
            return 0
        if score >= 2.9:
            return 1
        return 2

    # ------------------------------------------------------------------
    # training
    # ------------------------------------------------------------------

    def training(self, myDict, allWords=None):
        if allWords is not None:
            self.allWords = set(allWords)

        X = []
        Y = []
        for words in myDict:  # remem better than indexing
            X.append(self.features(words))
            Y.append(self.logLabels(words))

        X = pd.DataFrame(X, columns=self.featureNames)
        Y = pd.Series(Y)  # didnt process i needed this beforehand

        # need to scale the features since on different nums (remem wordfreq is 0-7)
        Xtrain, Xtest, ytrain, ytest = train_test_split(
            X.copy(), Y.copy(), test_size=0.3, random_state=43
        )  # like the split we learned in class
        Xtrain = self.scaler.fit_transform(Xtrain)
        Xtest = self.scaler.transform(Xtest)

        # cross validating
        crossVal = cross_val_score(self.model, Xtrain, ytrain, cv=5, scoring="accuracy")
        self.model.fit(Xtrain, ytrain)

        accuracy = self.model.score(Xtest, ytest)
        self.trained = True

        spread = Y.value_counts().to_dict()
        return {
            "crossVal": list(crossVal),
            "meanCrossVal": float(crossVal.mean()),
            "testAccuracy": float(accuracy),
            "trainedOn": len(X),
            "labelSpread": {int(k): int(v) for k, v in spread.items()},
        }

    def predictDifficulty(self, word):
        if self.trained == False:
            raise ValueError("Model has not been trained quite yet")

        features = self.features(word)
        scaledFeats = self.scaler.transform(pd.DataFrame([features], columns=self.featureNames))
        return self.model.predict(scaledFeats)[0]  # basically returns y: label of difficulty 0-2


def trainDifficulty(myDict, sampleSize=2000, seed=43):
    """Train on a random sample of the dictionary (same approach as the notebook).

    The full dictionary is kept on the model regardless, because stem lookups
    need it.
    """
    allWords = set(myDict)
    rng = random.Random(seed)
    pool = list(allWords)
    reducedDict = [rng.choice(pool) for _ in range(sampleSize)]

    model = logDifficultyWord(allWords)
    metrics = model.training(reducedDict)
    return model, metrics
