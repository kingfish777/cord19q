"""
LOE module
"""

from collections import Counter

import regex as re

from .vocab import Vocab

def regex(terms):
    """
    Builds a regular expression OR matched string from the terms. Each string is wrapped in
    word boundary (\b) flags to only allow complete phrase matches. Module level function used
    to allow calling from class body.

    Args:
        terms: list of terms

    Returns:
        terms regex
    """

    # Build regular expression for each term
    # Wrap term in word boundaries, escape regex special chars
    return "|".join([r"\b%s\b" % re.escape(term.lower()) for term in terms])

class LOE(object):
    """
    Methods to determine the type of level of evidence contained within an article.
    """

    # Regular expressions for full text sections
    SYSTEMATIC_REVIEW_REGEX = regex(Vocab.SYSTEMATIC_REVIEW)
    RANDOMIZED_CONTROL_TRIAL_REGEX = regex(Vocab.RANDOMIZED_CONTROL_TRIAL)
    PSEUDO_RANDOMIZED_CONTROL_TRIAL_REGEX = regex(Vocab.PSEUDO_RANDOMIZED_CONTROL_TRIAL)
    RETROSPECTIVE_COHORT_REGEX = regex(Vocab.GENERIC_L3 + Vocab.RETROSPECTIVE_COHORT)
    MATCHED_CASE_CONTROL_REGEX = regex(Vocab.GENERIC_L3 + Vocab.GENERIC_CASE_CONTROL + Vocab.MATCHED_CASE_CONTROL)
    CROSS_SECTIONAL_CASE_CONTROL_REGEX = regex(Vocab.GENERIC_L3 + Vocab.GENERIC_CASE_CONTROL + Vocab.CROSS_SECTIONAL_CASE_CONTROL)
    TIME_SERIES_ANALYSIS_REGEX = regex(Vocab.TIME_SERIES_ANALYSIS)
    PREVALENCE_STUDY_REGEX = regex(Vocab.PREVALENCE_STUDY)
    COMPUTER_MODEL_REGEX = regex(Vocab.COMPUTER_MODEL)

    # Keywords for study names in titles
    TITLE_REGEX = [(regex(["systematic review", "meta-analysis"]), 1), (regex(["randomized control"]), 2),
                   (regex(["pseudo-randomized"]), 3), (regex(["retrospective cohort"]), 4),
                   (regex(["matched case"]), 5), (r"\bcross\-?sectional\b", 6),
                   (r"\btime\-?series\b", 7), (regex(["prevalence"]), 8)]

    # List of evidence categories
    CATEGORIES = [(COMPUTER_MODEL_REGEX, 1), (PREVALENCE_STUDY_REGEX, 1), (TIME_SERIES_ANALYSIS_REGEX, 2),
                  (CROSS_SECTIONAL_CASE_CONTROL_REGEX, 2), (MATCHED_CASE_CONTROL_REGEX, 2), (RETROSPECTIVE_COHORT_REGEX, 2),
                  (PSEUDO_RANDOMIZED_CONTROL_TRIAL_REGEX, 3), (RANDOMIZED_CONTROL_TRIAL_REGEX, 3), (SYSTEMATIC_REVIEW_REGEX, 4)]

    @staticmethod
    def label(sections):
        """
        Analyzes text fields of an article to determine the level of evidence.

        Labels definitions:

        1 - I. Systematic Review
        2 - II. Randomized Controlled Trial
        3 - III-1. Pseudo-Randomized Controlled Trial
        4 - III-2. Retrospective Cohort
        5 - III-2. Matched Case Control
        6 - III-2. Cross Sectional Control
        7 - III-3. Time Series Analysis
        8 - IV. Prevalence Study
        9 - IV. Computer Model
        0 - IV. Other (Default for no match)

        Args:
            sections: list of text sections

        Returns:
            (level of evidence (int), keyword match counts)
        """

        # LOE label, keywords
        label = (0, None)

        # Search titles for exact keyword match
        title = [text for name, text, _ in sections if name and name.lower() == "title"]
        title = " ".join(title).replace("\n", " ").lower()

        for regex, loe in LOE.TITLE_REGEX:
            count, keywords = LOE.matches(regex, title)

            # Return LOE and the keywords for title matches
            if count:
                return (loe, keywords)

        # Process full-text only if text meets certain criteria
        if LOE.accept(sections):
            # Filter to allowed sections and build full text copy of sections
            text = [text for name, text, _ in sections if not name or LOE.filter(name.lower())]
            text = " ".join(text).replace("\n", " ").lower()

            if text:
                # Score text by keyword category
                matches = [LOE.matches(keywords, text) + (minimum, ) for keywords, minimum in LOE.CATEGORIES]

                # Require at least minimum matches, which is set per category
                matches = [(count, keywords) if count >= minimum else (0, None) for count, keywords, minimum in matches]

                # Derive best match
                label = LOE.top(matches)

        # Check title for mathematical/computer and label if no other labels applied (label = 0)
        if not label:
            # Allow partial matches
            count, keywords = LOE.matches(r"mathematical|computer|forecast", title)
            if count:
                # Return size of categories. Labels are inverted and computer models are first element. (1 indexed)
                label = (len(LOE.CATEGORIES), keywords)

        return label

    @staticmethod
    def accept(sections):
        """
        Requires at least one instance of the word method or result in the text of the article.

        Args:
            sections: sections

        Returns:
            True if word method or result present in text
        """

        return any([LOE.find(section, "method") or LOE.find(section, "result") for section in sections])

    @staticmethod
    def find(section, token):
        """
        Searches section for the occurance of a token. Accepts partial word matches.

        Args:
            section: input section
            token: token to search for

        Returns:
            True if token found, False otherwise
        """

        # Unpack section
        name, text, _ = section

        return (name and token in name.lower()) or (text and token in text.lower())

    @staticmethod
    def filter(name):
        """
        Filters a section name. Returns True if name is a title, method or results section.

        Args:
            name: section name

        Returns:
            True if section should be analyzed, False otherwise
        """

        # Skip introduction, background and references sections
        # Skip discussion unless it's a results and discussion
        return not re.search(r"introduction|(?<!.*?results.*?)discussion|background|reference", name)

    @staticmethod
    def matches(keywords, text):
        """
        Finds all keyword matches within a block of text. Wraps keywords in word boundaries to prevent
        partial matching of a word.

        Args:
            keywords: keywords regex
            text: text to search

        Returns:
            list of matches
        """

        if keywords:
            matches = re.findall(keywords, text, overlapped=True)
            if matches:
                # Build keyword match string
                counts = sorted(Counter(matches).items(), key=lambda x: x[1], reverse=True)

                match = ", ".join(["'%s': %d" % (key, value) for key, value in counts])

                # Return count of matches and keyword match string
                return (len(matches), match)

        return (0, None)

    @staticmethod
    def top(matches):
        """
        Searches a matches list and returns the top match by count. If no match with
        a count > 0 is found, 0 is returned.

        Args:
            matches: list of (count, keywords)

        Returns:
            top (label, keywords) match or (0, None) if no matches found
        """

        label = (0, None)

        counts = [count for count, _ in matches]
        best = max(counts)
        if best:
            # Get index of best match
            index = counts.index(best)
            match = matches[index]

            # Label is inverted index of CATEGORIES list (1 indexed)
            label = (len(matches) - index, match[1])

        return label
