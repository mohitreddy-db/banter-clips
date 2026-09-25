"""Deterministic safety rules for text sent to video models.

BanterClips is a sports-banter generator, not a romantic or intimate-scene
generator. These checks run before model calls and again on model-authored
text so the product rule does not depend on one provider or model version.
"""

from __future__ import annotations

import re
from collections.abc import Mapping


PUBLIC_MESSAGE = (
    "BanterClips can't create scenes involving hugging, kissing, romantic, "
    "sexual, or other intimate contact. Please use a sports-only action."
)

# Match actions rather than broad words such as "love" or "contact", both of
# which are ordinary sports language. Include common paraphrases so the rule
# cannot be bypassed by merely avoiding the words "hug" and "kiss".
_INTIMATE_CONTACT = re.compile(
    r"(?:"
    r"\bkiss(?:es|ed|ing)?\b|"
    r"\bhug(?:s|ged|ging)?\b|"
    r"\bcuddl(?:e|es|ed|ing)\b|"
    r"\bembrac(?:e|es|ed|ing)\b|"
    r"\bcaress(?:es|ed|ing)?\b|"
    r"\bfondl(?:e|es|ed|ing)\b|"
    r"\bgrop(?:e|es|ed|ing)\b|"
    r"\b(?:make(?:s|ing)?|made)\s+out\b|"
    r"\bhold(?:s|ing)?\s+hands\b|"
    r"\b(?:wrap(?:s|ped|ping)?\s+(?:his|her|their)?\s*arms?|"
    r"arms?\s+(?:wrapped\s+)?)around\s+(?:each\s+other|him|her|them)\b|"
    r"\bsnuggl(?:e|es|ed|ing)\b|"
    r"\bnuzzl(?:e|es|ed|ing)\b|"
    r"\blap\s*danc(?:e|es|ed|ing)\b|"
    r"\bstraddl(?:e|es|ed|ing)\b|"
    r"\b(?:nude|nudity|naked|undress(?:es|ed|ing)?)\b|"
    r"\b(?:in|on)\s+(?:a\s+)?bed\s+together\b|"
    r"\bintimate(?:ly|\s+(?:contact|touch(?:ing)?|moment|scene|act))?\b|"
    r"\bromantic\s+(?:contact|touch(?:ing)?|embrace|kiss|moment|scene|act)\b|"
    r"\bsexual(?:ly|\s+(?:contact|touch(?:ing)?|act|scene|content))?\b"
    r")",
    re.IGNORECASE,
)


def contains_intimate_contact(value: object) -> bool:
    """Return True when nested request/model data contains blocked content."""
    if value is None:
        return False
    if isinstance(value, str):
        return bool(_INTIMATE_CONTACT.search(value))
    if isinstance(value, Mapping):
        return any(contains_intimate_contact(item) for item in value.values())
    if isinstance(value, (list, tuple, set, frozenset)):
        return any(contains_intimate_contact(item) for item in value)
    return False
