"""Trie + puzzle generation.

Ported straight from the notebook. The only addition is `buildTrie`, which is
just the loop that used to sit at the bottom of the cell.
"""

import random


class TrieNode:
    def __init__(self):
        self.children = {}  # concept from geeks for geeks
        self.isEndOfWord = False


class Trie:
    def __init__(self):
        self.root = TrieNode()

    def insert(self, word):
        node = self.root
        for l in word:
            if l not in node.children:  # if path not alr there, then add node
                node.children[l] = TrieNode()
            node = node.children[l]  # next one is to check the next node

        node.isEndOfWord = True  # still accounts for a case where theres a word within words

    def search(self, letters, center):  # depending on len of n
        solutions = set()

        def dfs(node, wordsoFar):  # depth first search!

            # like base case, if full word
            if node.isEndOfWord:
                if center in wordsoFar:
                    solutions.add(wordsoFar)

            # only the children that have letters, also keep going incase word after full word
            for letter, child in node.children.items():  # check all children / diverging paths
                if letter in letters:  # valid next path
                    dfs(child, wordsoFar + letter)  # keep searching deeper

        dfs(self.root, "")  # start at beginning

        return solutions


def buildTrie(words):
    trie = Trie()
    for word in words:
        trie.insert(word)
    return trie


# method for making level
# make pangrams first (ones where exactly 7 and randomly choose from that, better than searching)
# NYT puzzles usually land somewhere around 20-50 answers, so that is the default
# window now. The notebook used 10-30, which was a smaller range for testing.
def level(trie, pangrams, minSolutions=20, maxSolutions=50):
    pangramList = list(pangrams)
    while True:  # keep going until find a valid one and return
        pangram = random.choice(pangramList)
        letters = set(pangram)
        possCen = list(letters)
        random.shuffle(possCen)

        for center in possCen:  # check all the centers since solutions change with them
            possSolus = trie.search(letters, center)
            # this accounts for letter combos that would have too many/little sols
            if minSolutions <= len(possSolus) <= maxSolutions:
                return letters, center, possSolus


# picking a level to suit how hard the player wants it
DIFFICULTY_RANGES = {"easy": (12, 25), "medium": (20, 45), "hard": (35, 80)}


def levelByDifficulty(trie, pangrams, familiarity=None, difficulty="medium", attempts=30):
    """Generate several candidate levels and keep the one that best fits.

    Answer count is the first lever: an easy puzzle is a short one. Beyond
    that, candidates are scored on the average familiarity of their answers,
    so an easy puzzle is not just short but made of words people know.
    """
    minSolutions, maxSolutions = DIFFICULTY_RANGES[difficulty]

    if familiarity is None:
        return level(trie, pangrams, minSolutions, maxSolutions)

    best = None
    bestScore = None
    for _ in range(attempts):
        letters, center, solutions = level(trie, pangrams, minSolutions, maxSolutions)
        average = sum(familiarity(word) for word in solutions) / len(solutions)

        if difficulty == "easy":
            score = average  # the more familiar the better
        elif difficulty == "hard":
            score = -average  # the more obscure the better
        else:
            score = -abs(average - 2.6)  # aim for the middle

        if bestScore is None or score > bestScore:
            best = (letters, center, solutions)
            bestScore = score

    return best


# method for finding the pangrams
def pangramsLeft(solutions):
    found = []
    for word in solutions:  # i mean o n
        if len(set(word)) == 7:
            found.append(word)
    return found
