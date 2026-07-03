"""Regex patterns for web search intent detection."""

from __future__ import annotations

import re

_EXPLICIT_SEARCH = re.compile(
    r"\b("
    r"search(?:\s+the)?\s+web"
    r"|look(?:\s+it|\s+that)?\s+up(?:\s+online)?"
    r"|google(?:\s+for|\s+this|\s+it)?"
    r"|web\s+search"
    r"|find(?:\s+me)?\s+(?:online|on\s+the\s+internet)"
    r")\b",
    re.IGNORECASE,
)

_LOOK_IT_UP = re.compile(
    r"^\s*(?:please\s+)?(?:look(?:\s+it|\s+that)\s+up|search(?:\s+for)?(?:\s+it)?)\s*[.!?]*\s*$",
    re.IGNORECASE,
)

_CLARIFICATION = re.compile(
    r"^\s*(?:"
    r"no[,!.]?\s+(?:i\s+meant|the|not)|"
    r"(?:i\s+meant|not that|the ongoing|the current|that one|this one)|"
    r"yes[,!.]?\s+(?:that|the)\b"
    r")",
    re.IGNORECASE,
)

_ONGOING = re.compile(
    r"\b(ongoing|current(?:ly)?|right now|happening now|this one|that one)\b",
    re.IGNORECASE,
)

_WORLD_CUP = re.compile(r"\b(world\s+cup|fifa|wc\s*2026|2026\s+world\s+cup)\b", re.IGNORECASE)

_SHORT_FOLLOWUP_WORDS = 12

_RECENCY = re.compile(
    r"\b("
    r"latest|breaking|today(?:'s)?|current(?:ly)?|recent(?:ly)?|right\s+now"
    r"|this\s+week|this\s+month|as\s+of|news|headline"
    r"|stock\s+price|share\s+price|market\s+cap"
    r"|who\s+won|what\s+happened|score(?:s)?"
    r"|release\s+date|when\s+did\s+.+\s+(?:happen|release|launch)"
    r"|is\s+.+\s+(?:still|currently)\s+alive"
    r")\b",
    re.IGNORECASE,
)

_NEWS = re.compile(
    r"\b("
    r"what(?:'s| is) (?:happening|going on|new|in the news)"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|in the world(?: today)?"
    r"|world news|current events"
    r"|what(?:'s| is) cookin(?:'|g)?(?: in the world)?"
    r")\b",
    re.IGNORECASE,
)

_SPORTS = re.compile(
    r"\b("
    r"game|games|match|matches|score|scores|result|results|fixture|standings|highlights|"
    r"soccer|football|nba|nfl|mlb|nhl|premier league|world cup|mls|uefa|champions league"
    r")\b",
    re.IGNORECASE,
)

_YESTERDAY = re.compile(r"\byesterday(?:'?s)?\b", re.IGNORECASE)

_SPORTS_LOOKUP = re.compile(
    r"\b("
    r"yesterday(?:'?s)?\s+(?:games?|match(?:es)?|result|score|scores)"
    r"|(?:games?|match(?:es)?|score|scores|results?)\s+(?:from\s+)?yesterday"
    r"|show me (?:the\s+)?yesterday(?:'?s)?\s+(?:games?|match(?:es)?|result|score|scores)"
    r"|show me (?:the\s+)?(?:games?|match(?:es)?|score|scores|results?)"
    r"|who won (?:the\s+)?(?:games?|match(?:es)?|yesterday|last night)"
    r"|last night(?:'s)?\s+(?:games?|match(?:es)?|score|scores)"
    r")\b",
    re.IGNORECASE,
)

_TEAM_SCORE = re.compile(
    r".{2,60}\b(?:games?|match(?:es)?)\s+score",
    re.IGNORECASE,
)

_TEAM_POSSESSIVE_SCORE = re.compile(
    r".{2,40}(?:'s|s)\s+(?:games?|match(?:es)?|score|scores|result|results)",
    re.IGNORECASE,
)

_SKIP = re.compile(
    r"\b("
    r"rewrite|proofread|debug|refactor|explain\s+this\s+code"
    r"|help\s+me\s+write|draft\s+(?:an?\s+)?(?:email|message|reply)"
    r"|remember\s+that|add\s+to\s+(?:my\s+)?(?:todo|list|memory)"
    r"|translate|summarize\s+this\s+(?:text|email|article)"
    r"|vocabulary\s+quiz|interactive\s+vocabulary|quiz\s+me\s+in\s+chat"
    r"|quick\s+quiz|begin\s+with\s+the\s+first\s+question"
    r")\b",
    re.IGNORECASE,
)

_PERSONAL_PLANNING = re.compile(
    r"\b("
    r"what\s+(?:am\s+I|are\s+we|do\s+I|should\s+I)\s+(?:trying\s+to\s+)?(?:get|have)\s+(?:done|to\s+do)"
    r"|what(?:'s| is)\s+(?:on\s+my\s+(?:plate|list|agenda)|due|still\s+open)"
    r"|what\s+(?:do\s+I|should\s+I)\s+need\s+to\s+(?:do|finish|tackle)"
    r"|(?:my|any)\s+(?:tasks?|todos?|reminders?)\s+(?:for\s+)?(?:today|tonight|this\s+week)"
    r"|how(?:'s| is)\s+my\s+day\s+looking"
    r"|how\s+did\s+my\s+day\s+go"
    r"|help\s+me\s+(?:prioriti[sz]e|plan|wrap\s+up)"
    r"|(?:show|list)\s+(?:me\s+)?(?:my\s+)?(?:tasks?|todos?|reminders?)"
    r"|what\s+(?:should\s+I|can\s+I)\s+(?:tackle|focus\s+on|work\s+on)\s+(?:today|tonight|now)?"
    r"|anything\s+(?:left|open|due)\s+(?:for\s+)?(?:me\s+)?(?:today|tonight)"
    r"|wrap\s+up\s+(?:loose\s+ends|my\s+day)"
    r"|wind\s+down"
    r")\b",
    re.IGNORECASE,
)

# Proximity intent — any "near me / nearest / closest …" ask, not a venue-type list.
_NEARBY_INTENT = re.compile(
    r"\b("
    r"near\s+me|nearby|around\s+here|in\s+(?:this\s+)?town"
    r"|close\s+(?:by|to\s+me)"
    r"|(?:the\s+)?(?:nearest|closest)\b"
    r")\b",
    re.IGNORECASE,
)

# "Nearest" used for abstract/math/social things — not a maps search.
_NON_GEOGRAPHIC_NEAREST = re.compile(
    r"\b(?:nearest|closest)\b.+\b("
    r"number|numbers|integer|prime|multiple|"
    r"match|deadline|"
    r"star|planet|galaxy|sun|moon|"
    r"approach|analogy|synonym|equivalent|"
    r"friend|relative|cousin|neighbor|neighbour|"
    r"guess|approximation|solution|competitor|rival"
    r")\b",
    re.IGNORECASE,
)

_BEST_NEAR = re.compile(
    r"\bbest\b.+\b(?:in|near|around|by)\b",
    re.IGNORECASE,
)

# Implicit nearby intent without saying "near me" (e.g. "where should I eat tonight?").
_IMPLICIT_LOCAL = re.compile(
    r"\b(?:"
    r"where\s+(?:should|can|do)\s+(?:I|we)\s+(?:eat|get|find|go|stay|park)"
    r"|where\s+to\s+(?:eat|go|get|stay|park)"
    r"|what(?:'s| is)\s+(?:good|open)\s+(?:around|near|nearby)"
    r")\b",
    re.IGNORECASE,
)

# Real-estate asks that need sale/rent/address clarified — not generic "places near me".
_AMBIGUOUS_NEARBY_SUBJECT = re.compile(
    r"\b(?:"
    r"house|houses|home|homes|property|properties|building|buildings"
    r"|apartment|apartments|condo|condos|flat|flats|unit|units"
    r")\b",
    re.IGNORECASE,
)

_QUALIFIED_NEARBY = re.compile(
    r"\b(?:"
    r"for\s+sale|to\s+(?:buy|rent|lease)|for\s+rent|rentals?|buying|leasing"
    r"|open\s+(?:now|today)|24\s*hours?"
    r"|near\s+\d|at\s+\d|from\s+\d|\d+\s+\w+\s+(?:st|street|ave|avenue|rd|road|blvd|dr|drive|way|ln|lane)\b"
    r")\b",
    re.IGNORECASE,
)

_PROXIMITY_PHRASES = (
    r"\bnear\s+me\b",
    r"\bnearby\b",
    r"\baround\s+here\b",
    r"\bin(?:\s+this)?\s+town\b",
    r"\bclose\s+(?:by|to\s+me)\b",
    r"\b(?:the\s+)?(?:nearest|closest)\b",
    r"\bbest\b",
)

_QUIZ_ANSWER = re.compile(r"^[A-D]\.?$", re.IGNORECASE)

# Distance / travel from the user's location — venue-agnostic.
_DISTANCE_INTENT = re.compile(
    r"\b("
    r"how\s+far"
    r"|how\s+many\s+(?:miles|kilometers|kilometres|km|minutes|mins)"
    r"|(?:walking|driving|drive|travel|commute)\s+(?:distance|time)"
    r"|distance\s+(?:to|from)"
    r"|how\s+long\s+(?:to\s+get|does\s+it\s+take|is\s+the\s+(?:drive|trip|walk))"
    r"|(?:miles|km|kilometers?|kilometres?|minutes?)\s+(?:away|from\s+(?:me|here))"
    r"|directions?\s+to"
    r")\b",
    re.IGNORECASE,
)

_FROM_USER = re.compile(
    r"\b(?:from\s+(?:me|here|my\s+(?:location|place))|to\s+me|where\s+i\s+am)\b",
    re.IGNORECASE,
)

_DISTANCE_BETWEEN = re.compile(r"\bdistance\b.+\bbetween\b", re.IGNORECASE)

_QUERY_PREFIX = re.compile(
    r"^\s*(?:"
    r"(?:can\s+you\s+)?(?:please\s+)?"
    r"(?:search(?:\s+the)?\s+web(?:\s+for)?|"
    r"look\s+up(?:\s+online)?(?:\s+for)?|"
    r"google(?:\s+for)?|"
    r"find(?:\s+online)?(?:\s+for)?)"
    r")\s*",
    re.IGNORECASE,
)

_STREET_SUFFIX = (
    r"(?:St|Street|Ave|Avenue|Rd|Road|Blvd|Boulevard|Dr|Drive|Ln|Lane|Way|Pl|Place|"
    r"Ct|Court|Sq|Square|Pkwy|Parkway)"
)
_ADDRESS_RE = re.compile(
    rf"\b(\d+\s+[\w\s.'#-]{{2,40}}{_STREET_SUFFIX}\b(?:,\s*[\w\s.'-]{{2,30}})?)",
    re.IGNORECASE,
)
_PRICE_RE = re.compile(r"(?<![\w$])(\$\$\$|\$\$|\$)(?![\w$])")

_GENERIC_NEWS_QUERY = re.compile(
    r"^(?:"
    r"what(?:'s| is) (?:happening|going on|new)(?: in the world(?: today)?| in the news)?"
    r"|top (?:news|stories|headlines)"
    r"|news (?:today|this week|stories)"
    r"|(?:what(?:'s| is) )?(?:cookin(?:'|g)?(?: in the world)?|in the world(?: today)?)"
    r"|world news|current events"
    r")\s*[.!?]*$",
    re.IGNORECASE,
)

_NUMBERED_VENUE_LINE = re.compile(r"^\s*\d+\.\s+")
