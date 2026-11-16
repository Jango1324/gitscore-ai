"""Milestone 11-G22-R4 -- HIGH-RECALL (inverse) README evidence guards (OFFLINE research adapters).

Nothing here is imported by `src/gitscore`. Every policy uses G22-R2's `applied()` mechanism, which wraps the production
per-occurrence filter `readme.is_non_implementation_mention` (8D.3) so a policy may reject MORE occurrences. The alias
table, overlap resolution, fall-through to the next occurrence / alias, one item per concept per repository and
MODERATE confidence are unmodified production code.

INVERSE DESIGN. G22-R2 D and G22-R3 R3 required every ambiguous occurrence to carry a positive technical cue and lost
genuine use ("Pure Python", "One-line Swift API", "store in Rust"). The R4 policies DEFAULT-ACCEPT: an occurrence is
rejected only when a bounded, local, structural signal establishes that it is NOT project-use evidence. Scope is the
11 reviewed README-ambiguous aliases only (react, express, swift, rust, ruby, shell, torch, python, java, flask,
pandas); every other alias keeps readme:v4 behaviour exactly. Capitalisation is never sufficient on its own: where
case is consulted it is only an extra NECESSARY condition for a rejection, never a reason to accept or reject alone.
Rejected occurrences fall through to the next occurrence (production behaviour), so a README with one ordinary and
one genuine mention keeps the genuine one.

  P0  production readme:v4 (= G22-R2 policy A)
  P1  ordinary-English (homonym-sense) rejection only. Per alias, a homonym sense is recognised ONLY in a fixed
      structural position relative to the occurrence:
        * an adjacent homonym modifier immediately before ("ball python", "head torch", "giant pandas");
        * an adjacent homonym head noun immediately after ("rust stains", "express trains", "ruby ring");
        * a coordinated homonym sibling ("a crab, a starfish or a shell", "sapphire, ruby, emerald");
        * a bounded verb / adjective frame ("help teams react", "react with acids", "express your ...",
          "won't rust", "a swift reply");
        * a determiner-headed common noun: "a/an <alias>" (or lowercase "the/each/every <alias>") directly followed by
          punctuation, a conjunction, a preposition, a pronoun or an auxiliary -- a technology name is not a count
          noun ("a python, a corn snake", "every flask for experiments"); count-noun homonyms only;
        * a personal-name frame ("my dog, Ruby", "named after Ruby").
      No README-wide word list: words such as train, island, coffee or corrosion elsewhere in the README do nothing.
  P2  P1 + bounded negated-use rejection: a negator (no / not / without / never / nor / n't ...) at most three words
      before the alias inside the same clause, unless the gap holds an exception or causal word ("anything but",
      "other than", "thanks to"); or "<alias> is not required / used / needed ...", "<alias>-free".
  P3  P2 + project-attribution rejection: comparison / inspiration / reference frames immediately before the alias,
      bounded historical frames ("originally", "moved off", "the old"), bounded future / hypothetical frames ("plan
      to", "would like to", "<alias> bindings are planned", "can be generated", unchecked task-list items, roadmap
      sections), other-project documentation ("notes on how the", "the <alias> documentation", "maintained by another
      team"), attributed blockquotes, and third-party project lists (a linked list item under a bindings / ports /
      community heading, ATX or setext; "[project](https://...) (<alias>)").
  P4  P3 + narrowly justified POSITIVE overrides, used ONLY to resolve two known ambiguities, never to admit an
      occurrence on its own: (a) a P1 homonym rejection is withdrawn when the occurrence is in code, is followed by a
      version string, follows an explicit claim-of-use frame ("built with", "written in", "uses"), or is coordinated
      with another registry technology ("a Python or Rust backend"); (b) a P3 "like <alias>" comparison is withdrawn
      when an explicit claim-of-use verb opens the same clause ("built with modern tools like React").

Design sets (all SEEN): G22-R DEV/EVAL, G22-R2 DEV/EVAL, G22-R3 VAL-1 and VAL-2 (run once by R3; now seen), the frozen
8c fixtures and the R4 DEV near-neighbour controls. Frozen in `evaluation/m11g22r4/policy_design_freeze.json` BEFORE
the fresh validation set was opened or run.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

import m11g22r2_policies as p2
import m11g22r_policies as rpol
from gitscore.jobs.parsing.concepts import find_concept_mentions

AMBIGUOUS = p2.AMBIGUOUS  # the 11 reviewed README-ambiguous aliases (G22-R / G22-R2 / G22-R3), unchanged
_I = re.IGNORECASE
_W = r"[A-Za-z][A-Za-z'-]*"


def _words(s: str) -> list[str]:
    return [w.lower() for w in re.findall(_W, s)]


# Paragraph-aware sentence span (research-only). G22-R's `_sentence` treats EVERY newline as a sentence break, which
# cuts hard-wrapped README prose mid-sentence (torvalds/libgit2: "... platform like .NET,\nNode.js, or Ruby, then").
# Here a newline is a break only when it ends a paragraph or starts / ends a block construct (list item, heading,
# blockquote, table row, fence, setext underline); a soft-wrapped newline is whitespace. Abbreviations "e.g." /
# "i.e." / "vs." / "etc." / "cf." do not end a sentence.
_SENT_END = re.compile(r"(?<!e\.g)(?<!i\.e)(?<!\bvs)(?<!etc)(?<!\bcf)[.!?](?=\s)")
_BLOCK_LINE = re.compile(r"^[ \t]*(?:$|[-*+][ \t]|\d+[.)][ \t]|#|>|\||```|=+[ \t]*$|-{2,}[ \t]*$)")
_STANDALONE_LINE = re.compile(r"^[ \t]*(?:$|#|>|\||```|=+[ \t]*$|-{2,}[ \t]*$)")
_SENT_CACHE: dict[str, list[int]] = {}


def _breaks(text: str) -> list[int]:
    got = _SENT_CACHE.get(text)
    if got is None:
        found = {m.end() for m in _SENT_END.finditer(text)}
        pos, prev_standalone = 0, True
        for line in text.split("\n"):
            # a line starts a new sentence if it opens a block construct or follows a standalone line
            if prev_standalone or _BLOCK_LINE.match(line):
                found.add(pos)
                if pos:
                    found.add(pos - 1)
            prev_standalone = bool(_STANDALONE_LINE.match(line))
            pos += len(line) + 1
        got = sorted(found)
        if len(_SENT_CACHE) > 4096:
            _SENT_CACHE.clear()
        _SENT_CACHE[text] = got
    return got


def _occurrence(text: str, start: int, end: int) -> tuple[str, int, int]:
    br = _breaks(text)
    left = max((b for b in br if b <= start), default=0)
    right = min((b for b in br if b >= end), default=len(text))
    if right > end and text[right - 1:right] in ".!?":
        right -= 1
    sentence = text[left:right]
    return sentence, start - left, end - left


# =====================================================================================================
# P1: homonym-sense lexicon. Each set is only consulted in ONE structural position (see module docstring).
# =====================================================================================================
_PET_KIN = (r"(?:cat|dog|pet|puppy|kitten|parrot|horse|hamster|rabbit|tortoise|grandmother|grandma|grandfather|"
            r"grandpa|mother|father|mum|mom|dad|daughter|son|sister|brother|aunt|uncle|niece|nephew|wife|husband|"
            r"friend|mascot|falcon|bird|goldfish|snake)")

HOMONYM = {
    "rust": {
        "mod_before": {"underbody", "surface", "flash", "chassis", "hull", "pipe", "iron", "bolt", "frame", "deep"},
        "head_after": {"stain", "stains", "spot", "spots", "removal", "remover", "removers", "proofing", "proof",
                       "prevention", "inhibitor", "inhibitors", "converter", "treatment", "damage", "patch",
                       "patches", "hole", "holes", "mark", "marks", "belt", "streaks", "flakes"},
        "siblings": {"corrosion", "pitting", "dents", "dent", "scratches", "grime", "dirt", "wear", "rot", "mould",
                     "mold", "oxidation", "limescale", "stains", "paint", "dust"},
        "before": [r"\b(?:free\s+of|signs?\s+of|spots?\s+of|patch(?:es)?\s+of|traces?\s+of|layers?\s+of|coats?\s+of|"
                   r"flakes?\s+of|areas?\s+of|bits?\s+of|covered\s+(?:in|with)|prevents?|preventing|prevention\s+of|"
                   r"removes?|removing|removal\s+of|treats?|treating|resists?|resistant\s+to|inhibits?|"
                   r"(?:scrub|sand)(?:s|bing|ding|ed)?\s+(?:off|away))\s+(?:the\s+|any\s+|all\s+)?$"],
        "before_lower": [r"\b(?:will|won't|wouldn't|can't|cannot|doesn't|don't|didn't|never|may|might|can|could|"
                         r"not)\s+$"],
    },
    "express": {
        "head_after": {"train", "trains", "bus", "buses", "coach", "coaches", "lane", "lanes", "delivery",
                       "deliveries", "shipping", "shipment", "shipments", "post", "mail", "courier", "checkout",
                       "parcel", "parcels", "ticket", "tickets", "elevator", "elevators", "lift", "lifts", "ferry",
                       "ferries", "tram", "trams", "metro", "rail", "yourself", "yourselves", "gratitude", "thanks",
                       "interest"},
        "before": [r"\b(?:local|limited|regional|stopping|non-?stop|standard|regular|economy|overnight|priority)"
                   r"\s*(?:and|or|/|&)\s*$"],
        "after": [r"^\s*(?:and|or|/|&)\s*(?:local|standard|regular|stopping|economy|slow)\b",
                  r"^\s+(?:your|their|our|my|his|her|its|themselves|ourselves|concerns?|opinions?|ideas?|feelings?|"
                  r"emotions?|which|what|how|whether)\b"],
        "before_lower": [r"\b(?:to|can|could|will|would|should|must|may|might|cannot|can't|you|we|they|i|users?|"
                         r"students?|people|let|lets|letting|help|helps|helping|allow|allows|allowing|please|"
                         r"freely|clearly|easily|better)\s+$"],
    },
    "react": {
        "after": [r"^\s+(?:quickly|calmly|promptly|instantly|immediately|swiftly|rapidly|appropriately|accordingly|"
                  r"faster|fast|sooner|strongly|badly|differently|emotionally|positively|negatively|proactively|"
                  r"decisively|early|within|before|when|whenever|against|in\s+time)\b",
                  r"^\s+with\s+(?:acids?|bases?|metals?|water|oxygen|air|each\s+other|one\s+another|anger|surprise|"
                  r"alarm)\b",
                  r"^\s+to\s+(?:the|a|an|it|them|this|that|these|those|what|whatever|each|every|any|changes?|events?|"
                  r"alerts?|incidents?|outages?|feedback|news|failures?|errors?)\b"],
        "before_lower": [r"\b(?:can|could|will|would|should|must|may|might|cannot|can't|you|we|they|i|teams?|"
                         r"users?|people|maintainers|moderators|operators|engineers?|dispatchers|staff|help|helps|"
                         r"helping|let|lets|letting|allow|allows|allowing|(?:how|able|time|need|needs|try|tries|"
                         r"trying|learn|learning|is|was|quick|quicker|slow|slower|ready)\s+to)\s+$"],
    },
    "ruby": {
        "head_after": {"gemstone", "gemstones", "stone", "stones", "ring", "rings", "necklace", "necklaces",
                       "earring", "earrings", "slippers", "jewel", "jewels", "jewelry", "jewellery", "wedding",
                       "anniversary", "red", "throated", "pendant", "brooch"},
        "siblings": {"sapphire", "sapphires", "emerald", "emeralds", "diamond", "diamonds", "spinel", "garnet",
                     "garnets", "topaz", "amethyst", "opal", "opals", "pearl", "pearls", "jade", "onyx", "quartz"},
    },
    "java": {
        "head_after": {"island", "sea", "trench", "coffee", "beans", "bean", "roast", "blend", "sparrow", "volcano",
                       "volcanoes", "rhino"},
        "siblings": {"bali", "lombok", "sumatra", "borneo", "sulawesi", "kenyan", "kenya", "colombian", "colombia",
                     "ethiopian", "ethiopia", "brazilian", "guatemalan", "arabica", "robusta", "mocha", "espresso",
                     "latte", "yemen"},
        "before": [r"\b(?:island\s+of|isle\s+of|trip\s+to|travel(?:led|ed|ling|ing)?\s+(?:to|across|around)|"
                   r"holiday\s+in|vacation\s+in|ferry\s+to|flights?\s+to|tour\s+of|cup\s+of|mug\s+of|pot\s+of|"
                   r"coast\s+of|east|west|central)\s+$"],
        "after": [r"^\s+(?:is|was)\s+an?\s+(?:island|volcanic)\b"],
    },
    "swift": {
        "head_after": {"nest", "nests", "nesting", "chicks"},
        "siblings": {"swallow", "swallows", "martin", "martins", "wagtail", "wagtails", "sparrow", "sparrows",
                     "starling", "starlings", "warbler", "warblers", "finch", "finches", "robin", "robins", "heron",
                     "kestrel", "falcon", "tern", "terns"},
        "before_lower": [r"\b(?:a|an|very|so|too|quite|more|most|less|is|are|was|were|be|been|remarkably|"
                         r"surprisingly|relatively|reasonably)\s+$"],
        "after_lower": [r"^\s+and\s+(?:decisive|sure|painless|silent|accurate|efficient|effective|simple|easy|smooth|"
                        r"reliable|fair)\b"],
    },
    "shell": {
        "mod_before": {"sea", "egg", "nut", "snail", "turtle", "crab", "oyster", "clam", "conch", "walnut", "peanut",
                       "tortoise", "scallop", "hermit", "hard", "outer", "protective", "empty", "broken", "cracked",
                       "spiral", "mussel", "coconut", "pistachio"},
        "head_after": {"length", "collection", "collecting", "collector", "collectors", "company", "companies",
                       "corporation", "game", "casing", "fragment", "fragments", "midden", "middens", "shocked",
                       "station", "oil", "beach", "fish", "fishing"},
        "siblings": {"crab", "crabs", "anemone", "anemones", "starfish", "pebble", "pebbles", "coral", "seaweed",
                     "driftwood", "fossil", "fossils", "feather", "feathers", "urchin", "urchins", "barnacle",
                     "barnacles"},
        "after": [r"^\s+out\s+(?:for|on)\b", r"^\s+out\s+(?:\$|£|€|\d|money|cash|hundreds|thousands)"],
    },
    "torch": {
        "mod_before": {"blow", "head", "olympic", "tiki", "butane", "propane", "welding", "cutting", "plasma",
                       "flaming", "electric", "hand", "pocket", "led", "burning"},
        "head_after": {"bearer", "bearers", "relay", "light", "lit", "flame", "song", "mode", "beam"},
        "siblings": {"tent", "tents", "stove", "stoves", "lantern", "lanterns", "flashlight", "flashlights",
                     "headlamp", "headlamps", "rope", "compass", "blanket", "blankets", "batteries", "knife",
                     "whistle", "sleeping"},
        "before": [r"\b(?:pass(?:es|ed|ing)?|carr(?:y|ies|ied|ying)|light(?:s|ed|ing)?|lit|hold(?:s|ing)?|held|"
                   r"bring(?:s|ing)?|brought|pack(?:s|ed|ing)?|grab(?:s|bed)?|shine(?:s|d)?|shone)\s+(?:a|an|the|"
                   r"your|my|our|their|his|her)\s+(?:[a-z]+\s+)?$"],
    },
    "python": {
        "mod_before": {"ball", "burmese", "reticulated", "royal", "carpet", "rock", "tree", "blood", "pet", "monty",
                       "amethystine", "albino"},
        "head_after": {"sighting", "sightings", "enclosure", "enclosures", "terrarium", "vivarium", "morph",
                       "morphs", "eggs", "hatchling", "hatchlings", "skin", "skins", "shed", "bite", "bites",
                       "breeder", "breeders", "handling", "feeding", "snake"},
        "siblings": {"gecko", "geckos", "snake", "snakes", "boa", "boas", "iguana", "iguanas", "lizard", "lizards",
                     "tortoise", "tortoises", "turtle", "turtles", "dragon", "dragons", "chameleon", "chameleons",
                     "frog", "frogs", "rabbit", "rabbits", "viper", "vipers", "cobra", "cobras", "anaconda", "skink",
                     "skinks", "crocodile", "alligator"},
        "after": [r"^\s+(?:ate|eats|swallowed|swallows|coiled|coils|slithered|slithers|hissed|hisses|basked|basks|"
                  r"escaped|bit|grew|hatched)\b"],
    },
    "flask": {
        "mod_before": {"lab", "laboratory", "erlenmeyer", "conical", "volumetric", "vacuum", "thermos", "hip",
                       "glass", "round-bottom", "round-bottomed", "florence", "filter", "culture", "insulated", "steel",
                       "dewar", "drinking", "whisky", "whiskey"},
        "siblings": {"beaker", "beakers", "pipette", "pipettes", "burette", "burettes", "funnel", "funnels",
                     "thermometer", "thermometers", "vial", "vials", "condenser", "stirrer"},
        "before": [r"\b(?:shake|swirl|stopper|heat|rinse|fill|label|pour|weigh|cap|stir|clamp|warm|cool|autoclave|"
                   r"wash)(?:s|ed|ing)?\s+(?:the|a|an|each|every|your|this)\s+(?:[a-z]+\s+)?$"],
        "after": [r"^\s+(?:of|with)\s+(?:water|tea|coffee|whisky|whiskey|broth|media|medium|solution|reagent|wine|"
                  r"soup)\b"],
    },
    "pandas": {
        "mod_before": {"red", "giant", "baby", "wild", "cute", "adult", "young", "captive", "two", "three", "four"},
        "head_after": {"live", "lived", "eat", "eats", "ate", "eating", "munch", "munching", "sleep", "sleeps",
                       "sleeping", "climb", "climbs", "climbing", "roam", "roll", "rolling", "breed", "breeding",
                       "mate", "mating", "nap", "napping"},
        "window_after": {"bamboo", "cub", "cubs", "zoo", "enclosure", "enclosures", "habitat", "habitats",
                         "sanctuary", "keeper", "keepers", "plush", "plushie", "plushies"},
        "siblings": {"leopard", "leopards", "tiger", "tigers", "koala", "koalas", "meerkat", "meerkats", "bear",
                     "bears", "lemur", "lemurs", "otter", "otters", "penguin", "penguins", "elephant", "elephants",
                     "gorilla", "gorillas", "giraffe", "giraffes", "monkey", "monkeys", "lion", "lions", "wolves"},
    },
}
COUNT_NOUN_HOMONYMS = frozenset({"python", "swift", "shell", "torch", "flask", "ruby", "java"})
_NAME_BEFORE = re.compile(r"(?:\bnamed\s+(?:after\s+)?|\b" + _PET_KIN + r"\s*,\s*)$", _I)
_NAME_AFTER = re.compile(r"^(?:\s*,\s*(?:my|our|his|her|their)\s+(?:\w+\s+)?" + _PET_KIN + r"\b|\s+the\s+" + _PET_KIN
                         + r"\b)", _I)
_DET_INDEF = re.compile(r"\b(?:[Aa]n?|[Aa]nother)\s+(?:([a-z][a-z'-]*)\s+)?$")
_DET_DEF = re.compile(r"\b(?:[Tt]he|[Ee]ach|[Ee]very|[Tt]his|[Tt]hat|[Yy]our|[Mm]y|[Oo]ur|[Hh]is|[Hh]er|[Tt]heir|[Ii]ts)"
                      r"\s+(?:([a-z][a-z'-]*)\s+)?$")
_DET_GAP_STOP = {"for", "in", "with", "on", "of", "to", "using", "uses", "use", "by", "from", "via", "written",
                 "built", "and", "or", "that", "which", "pure", "plain", "modern", "new", "small", "tiny", "simple",
                 "native", "standalone"}
_NP_BOUNDARY = re.compile(
    r"^(?:\s*(?:$|[,;:.!?)\]]|—|–)|\s+(?:and|or|nor|but|in|on|at|over|under|from|with|by|near|into|onto|across|through|"
    r"behind|beside|during|before|after|until|while|for|that|which|who|whose|you|we|they|i|he|she|it|is|was|are|were|"
    r"has|had|will|can|could|should|would|must|may|might)\b)", _I)
_RUBY_ON_RAILS = re.compile(r"^\s+on\s+rails\b", _I)
_COORD_RIGHT = re.compile(r"^\s*(?:,|/|&|\band\b|\bor\b|\bnor\b)(?:\s*(?:\band\b|\bor\b))?\s*"
                          r"(?:(?:a|an|the|some|two|three|several)\s+)?((?:" + _W + r"\s*){1,3})", _I)
_COORD_LEFT = re.compile(r"((?:" + _W + r"\s+){0,2}" + _W + r")\s*(?:,|/|&|\band\b|\bor\b|\bnor\b)\s*"
                         r"(?:(?:a|an|the|some)\s+)?$", _I)
_PREV_WORD = re.compile(r"(" + _W + r")[\s-]+$")
_NEXT_WORD = re.compile(r"^[\s-]+(" + _W + r")")


def homonym_reason(text: str, start: int, end: int) -> str | None:
    """P1: the reason this ambiguous-alias occurrence is an ordinary-English (non-technology) sense, else None."""
    surface = text[start:end]
    alias = surface.lower()
    lex = HOMONYM.get(alias)
    if lex is None:
        return None
    lower = surface == alias
    sentence, s, e = _occurrence(text, start, end)
    before, after = sentence[:s], sentence[e:]
    prev = _PREV_WORD.search(before)
    nxt = _NEXT_WORD.match(after)
    if prev and prev.group(1).lower() in lex.get("mod_before", ()):
        return f"homonym modifier before: '{prev.group(1)} {surface}'"
    if nxt and nxt.group(1).lower() in lex.get("head_after", ()):
        return f"homonym head noun after: '{surface} {nxt.group(1)}'"
    window = set(_words(after)[:3])
    if window & lex.get("window_after", set()):
        return f"homonym noun within 3 words after: {sorted(window & lex['window_after'])}"
    for key, src in (("before", before), ("before_lower", before)):
        if key == "before_lower" and not lower:
            continue
        for pat in lex.get(key, ()):
            if re.search(pat, src, _I):
                return f"homonym frame before ({key})"
    for key in ("after", "after_lower"):
        if key == "after_lower" and not lower:
            continue
        for pat in lex.get(key, ()):
            if re.search(pat, after, _I):
                return f"homonym frame after ({key})"
    sib = lex.get("siblings", set())
    for m in (_COORD_RIGHT.match(after), _COORD_LEFT.search(before)):
        if m and set(_words(m.group(1))) & sib:
            return f"coordinated homonym sibling: {sorted(set(_words(m.group(1))) & sib)}"
    if _NAME_BEFORE.search(before) or _NAME_AFTER.match(after):
        return "personal / pet name frame"
    if alias in COUNT_NOUN_HOMONYMS and _NP_BOUNDARY.match(after) and not _RUBY_ON_RAILS.match(after):
        m = _DET_INDEF.search(before) or (_DET_DEF.search(before) if lower else None)
        if m and (m.group(1) is None or m.group(1).lower() not in _DET_GAP_STOP):
            return "determiner-headed common noun (a/an/the <alias> + boundary)"
    return None


# =====================================================================================================
# P2: bounded negation
# =====================================================================================================
_CLAUSE_CUT = re.compile(r"(?:[,;:()—–]|\s-\s|\b(?:but|however|although|though|whereas|while)\b)", _I)
_NEGATOR = re.compile(
    r"\b(?:no|not|without|never|nor|neither|isn't|aren't|wasn't|weren't|doesn't|don't|didn't|won't|cannot|can't)"
    r"((?:\s+[\w'.+#-]+){0,3}?)\s+$", _I)
_NEG_GAP_STOP = {"only", "just", "merely", "limited", "matter", "longer", "more", "less", "than", "but", "except",
                 "besides", "beyond", "other", "apart", "aside", "thanks", "because", "due", "powered", "courtesy",
                 "also", "even"}
_NEG_AFTER = re.compile(
    r"^(?:-free\b|(?:\s+[\w.+#-]+){0,2}?\s+(?:(?:is|are|was|were)\s+(?:not|never)|isn't|aren't|wasn't)\s+"
    r"(?:used|required|needed|necessary|involved|included|installed|supported|bundled|"
    r"an?\s+(?:hard\s+|runtime\s+)?dependency)\b)", _I)


def _clause_before(sentence: str, s: int) -> str:
    before = sentence[:s]
    cuts = list(_CLAUSE_CUT.finditer(before))
    return before[cuts[-1].end():] if cuts else before


def _clause_after(sentence: str, e: int) -> str:
    after = sentence[e:]
    m = _CLAUSE_CUT.search(after)
    return after[:m.start()] if m else after


def negation_reason(text: str, start: int, end: int) -> str | None:
    sentence, s, e = _occurrence(text, start, end)
    clause = _clause_before(sentence, s)
    m = _NEGATOR.search(clause)
    if m and not (set(_words(m.group(1))) & _NEG_GAP_STOP):
        return f"bounded negation before: '{m.group(0).strip()}'"
    if _NEG_AFTER.match(sentence[e:]):
        return "negated use after the alias"
    return None


# =====================================================================================================
# P3: project attribution (reference / comparison, historical, future, other-project docs, quotes, third-party lists)
# =====================================================================================================
_FILLER = r"(?:(?:a|an|the|its|their|our|your|plain|vanilla|standard|classic|traditional|equivalent|regular|existing|" \
          r"official|popular|upstream)\s+){0,2}"
_REF_BEFORE = re.compile(
    r"\b(?:inspired\s+by|influenced\s+by|modell?ed\s+(?:on|after)|borrow(?:ed|s)\s+from|taken\s+from|ported\s+from|"
    r"port\s+of|clone\s+of|fork\s+of|rewrite\s+of|reimplementation\s+of|alternatives?\s+to|replacement\s+for|"
    r"drop-in\s+for|counterpart\s+to|equivalent\s+of|similar\s+to|akin\s+to|à\s+la|a\s+la|"
    r"in\s+the\s+(?:style|spirit|vein)\s+of|think\s+of\s+it\s+as|comparing|than|(?:as|so)\s+\w+\s+as|compared\s+(?:to|with)|comparisons?\s+(?:to|with)|"
    r"versus|vs\.?|as\s+opposed\s+to|instead\s+of|rather\s+than|in\s+place\s+of)\s+" + _FILLER + r"$", _I)
_LIKE_BEFORE = re.compile(r"\blike\s+(?:" + _FILLER + r"|(?:[^\s,;:]+(?:\s+[^\s,;:]+)?\s*(?:,|\bor\b|\band\b)\s*)"
                          r"{1,4}(?:or\s+|and\s+)?)$", _I)
_USE_VERB_IN_CLAUSE = re.compile(r"\b(?:uses?|using|built\s+(?:with|on|in)|written\s+in|powered\s+by|based\s+on|"
                                 r"requires?|implemented\s+in|made\s+with|developed\s+(?:with|in))\b", _I)
_HIST_BEFORE = [
    re.compile(r"\b(?:originally|initially|formerly|previously)\s+(?:(?:written|built|implemented|developed|made|"
               r"prototyped|a|an|the|in|with|on|as|using|used|was|were)\s+){0,3}$", _I),
    re.compile(r"\b(?:began|begun|started)\s+(?:(?:life|out)\s+)?as\s+(?:a\s+|an\s+)?$", _I),
    re.compile(r"\b(?:moved|migrated|switched|ported|converted|transitioned|rewritten|rewrote(?:\s+it)?)\s+"
               r"(?:away\s+)?(?:off|from)\s+(?:the\s+|a\s+|an\s+|our\s+|its\s+)?$", _I),
    re.compile(r"\b(?:old|former|previous)\s+$", _I),
    re.compile(r"\b(?:until|before|prior\s+to)\s+(?:v|version\s+)?\d+(?:\.\d+)*\s*,?\s+(?:[\w'-]+\s+){0,5}$", _I),
    re.compile(r"\b(?:first|original|old|earlier|previous|early)\s+(?:prototype|version|implementation|release|"
               r"draft|iteration)s?\s+(?:(?:was|were|used|relied|depended|on|written|built|in|with|a|an)\s+){1,3}$",
               _I),
    re.compile(r"\bno\s+longer\s+(?:\w+\s+){0,2}$", _I),
    re.compile(r"\bused\s+to\s+(?:use|be|depend\s+on|rely\s+on|run\s+on)\s+(?:a\s+|an\s+|the\s+)?$", _I),
]
_FUT_STRONG = re.compile(
    r"\b(?:plan(?:s|ned|ning)?\s+to|hop(?:e|es|ed|ing)\s+to|intend(?:s|ed)?\s+to|would\s+like\s+to|'d\s+like\s+to|"
    r"aim(?:s|ing)?\s+to|going\s+to|eventually|someday|some\s+day|one\s+day|in\s+the\s+future|todo:?|to-?do:?|"
    r"wishlist:?|(?:will|would|could|might)\s+be\s+(?:ported|moved|rewritten|migrated|converted|reimplemented)\s+"
    r"(?:to|in))\s+(?:[\w'.+#-]+\s+){0,3}$", _I)
_FUT_WEAK = re.compile(r"\b(?:consider(?:s|ing)?|evaluating|investigating|migrat(?:e|es|ing)\s+(?:\w+\s+){0,3}to|"
                       r"(?:can|could|may|might)\s+be\s+(?:generated|written|added)\s+(?:for|in))\s+"
                       r"(?:a\s+|an\s+|the\s+)?$", _I)
_FUT_AFTER = re.compile(
    r"^(?:\s+(?:bindings|port|support|version|backend|frontend|client|sdk|package|implementation|rewrite|plugin|"
    r"integration|api|wrapper|module|edition))?\s+(?:(?:would|could|might|may|will)\s+be\b(?!\s+(?:installed|used|"
    r"required|needed|downloaded|built|compiled|fetched))|(?:can|could|may|might)\s+be\s+generated|"
    r"(?:is|are)\s+(?:planned|coming|on\s+the\s+roadmap|in\s+the\s+works|under\s+consideration|being\s+considered|"
    r"an?\s+(?:future|planned)|not\s+(?:yet\s+)?(?:available|implemented|supported|written|started)))", _I)
_TASK_OPEN = re.compile(r"^\s*[-*+]\s+\[ \]\s")
_DOC_BEFORE = re.compile(r"\b(?:notes|cheat\s*sheet|translation|summary|summaries|documentation|docs|reading\s+notes|"
                         r"study\s+notes|reading\s+group)\s+(?:on|about|of|for|to)\s+(?:(?:how|the|a|an|what|why|when)"
                         r"\s+){0,3}$", _I)
_DOC_THE_BEFORE = re.compile(r"\bthe\s+(?:official\s+)?$", _I)
_DOC_AFTER = re.compile(r"^\s+(?:documentation|docs|handbook|book|reference\s+manual|internals|source\s+code|"
                        r"foundation|community|conference|core\s+team)\b", _I)
_OWNED_ELSEWHERE = re.compile(r"^[^.;:]{0,40}?\b(?:maintained|written|developed|owned|published)\s+by\s+(?:another|"
                              r"other|a\s+different|a\s+separate|a\s+third|someone)\b", _I)
_QUOTE_HEADING = re.compile(r"\b(?:said|says|testimonials?|quotes?|feedback|what\s+(?:people|users)|reviews?|"
                            r"excerpts?|notices?)\b", _I)
_THIRD_PARTY_HEADING = re.compile(r"\b(?:bindings|ports|wrappers|implementations|community|third[- ]party|ecosystem|"
                                  r"used\s+by|who\s+uses|showcase|in\s+the\s+wild|projects\s+using|other\s+languages)"
                                  r"\b", _I)
_LINKED_PAREN = re.compile(r"\]\(\s*https?://[^)]*\)\s*\($")
_EXT_URL = re.compile(r"https?://|<https?://")
_LIST_ITEM = re.compile(r"^(\s*)(?:[-*+]|\d+\.)\s")
_ATX = re.compile(r"^#{1,6}\s+(.*)$", re.M)
_SETEXT = re.compile(r"^([^\n]*\S[^\n]*)\n(?:=+|-+)[ \t]*$", re.M)


def enclosing_heading(text: str, pos: int) -> str | None:
    """Nearest ATX OR setext heading before `pos` (outside code fences), normalised like readme_context does.
    Research-only: production's ReadmeContext recognises ATX headings only."""
    fences = [m.start() for m in re.finditer(r"^```", text, re.M)]
    spans = [(fences[i], fences[i + 1]) for i in range(0, len(fences) - 1, 2)]
    best = None
    for m in list(_ATX.finditer(text)) + [m for m in _SETEXT.finditer(text)
                                          if not _LIST_ITEM.match(m.group(1)) and not m.group(1).startswith("#")]:
        if m.start() <= pos and not any(a <= m.start() < b for a, b in spans):
            if best is None or m.start() > best[0]:
                best = (m.start(), m.group(1))
    if best is None:
        return None
    h = re.sub(r"[`*_]+", "", best[1]).strip().rstrip(":").strip().lower()
    return re.sub(r"\s+", " ", h)


def _line(text: str, pos: int) -> tuple[int, str]:
    ls = text.rfind("\n", 0, pos) + 1
    le = text.find("\n", pos)
    return ls, text[ls:le if le != -1 else len(text)]


def _third_party_list_item(text: str, start: int) -> bool:
    ls, line = _line(text, start)
    m = _LIST_ITEM.match(line)
    if not m:
        return False
    heading = enclosing_heading(text, start) or ""
    if not _THIRD_PARTY_HEADING.search(heading):
        return False
    if _EXT_URL.search(line):
        return True
    indent = len(m.group(1).expandtabs(4))
    for nxt in text[ls + len(line) + 1:].split("\n")[:6]:  # the item's own nested sub-items
        sub = _LIST_ITEM.match(nxt)
        if not nxt.strip():
            continue
        if not sub or len(sub.group(1).expandtabs(4)) <= indent:
            break
        if _EXT_URL.search(nxt):
            return True
    return False


def _attributed_blockquote(text: str, start: int) -> bool:
    ls, line = _line(text, start)
    if not line.lstrip().startswith(">"):
        return False
    prev = [x for x in text[:ls].split("\n") if x.strip() and not x.lstrip().startswith(">")]
    intro = prev[-1].rstrip() if prev else ""
    return intro.endswith(":") or bool(_QUOTE_HEADING.search(enclosing_heading(text, start) or ""))


def attribution_reason(text: str, start: int, end: int, like_override: bool = False) -> str | None:
    sentence, s, e = _occurrence(text, start, end)
    before = sentence[:s]
    clause = _clause_before(sentence, s)
    if _REF_BEFORE.search(before):
        return "reference / comparison frame before"
    lm = _LIKE_BEFORE.search(before)
    if lm:
        clause_before_like = _clause_before(sentence, lm.start())
        if not (like_override and _USE_VERB_IN_CLAUSE.search(clause_before_like)):
            return "'like <alias>' comparison"
    for pat in _HIST_BEFORE:
        if pat.search(clause):
            return "historical frame before"
    if _FUT_STRONG.search(clause) or _FUT_WEAK.search(before):
        return "future / planned frame before"
    if _FUT_AFTER.match(sentence[e:]):
        return "future / hypothetical frame after"
    if _TASK_OPEN.match(_line(text, start)[1]):
        return "unchecked task-list item"
    if _DOC_BEFORE.search(before):
        return "other-project documentation frame"
    if _DOC_THE_BEFORE.search(before) and _DOC_AFTER.match(sentence[e:]):
        return "'the <alias> documentation / community' reference"
    if _OWNED_ELSEWHERE.match(sentence[e:]):
        return "maintained by another party"
    if _attributed_blockquote(text, start):
        return "attributed blockquote (third-party text)"
    if _LINKED_PAREN.search(text[max(0, start - 300):start]) and text[end:end + 1] == ")":
        return "'[project](https://...) (<alias>)' annotates an external project"
    if _third_party_list_item(text, start):
        return "linked list item under a third-party / bindings heading"
    return None


# =====================================================================================================
# P4: narrow positive overrides
# =====================================================================================================
_SOFT_HEAD_AFTER = re.compile(r"^[ \t]+(?:v?\d+(?:\.\d+)*\+?[ \t]+)?(?:librar(?:y|ies)|packages?|modules?|sdks?|"
                              r"clients?|servers?|frameworks?|plugins?|extensions?|apps?|applications?|apis?|"
                              r"scripts?|code|bindings|backend|frontend|models?|tensors?|gems?|crates?|cli|ui)\b", _I)


def strong_positive(text: str, start: int, end: int) -> str | None:
    if rpol._in_code(text, start, end):
        return "code span / fence"
    if rpol._INSTALL_OR_VERSION.match(text[end:]):
        return "version string after"
    sentence, s, e = _occurrence(text, start, end)
    if p2._USE_FRAME.search(sentence[:s]):
        return "claim-of-use frame before"
    if p2._registry_list_sibling(sentence, s, e):
        return "coordinated with a registry technology"
    if _SOFT_HEAD_AFTER.match(sentence[e:]):
        return "software head noun after"
    return None


# =====================================================================================================
# policies
# =====================================================================================================
def explain(text: str, start: int, end: int, level: int) -> str | None:
    """Reason a policy at `level` (1..4) rejects this occurrence, or None (kept). Non-ambiguous aliases: always None."""
    if text[start:end].lower() not in AMBIGUOUS:
        return None
    hom = homonym_reason(text, start, end)
    if hom and level >= 4:
        pos = strong_positive(text, start, end)
        hom = None if pos else hom
    if hom:
        return "P1 " + hom
    if level >= 2:
        neg = negation_reason(text, start, end)
        if neg:
            return "P2 " + neg
    if level >= 3:
        att = attribution_reason(text, start, end, like_override=level >= 4)
        if att:
            return "P3 " + att
    return None


def _rule(level: int):
    def rule(text: str, start: int, end: int) -> bool:
        return explain(text, start, end, level) is not None
    return rule


P0 = p2.A
P1 = p2.Policy("P1_ordinary_english", rule=_rule(1), description="inverse: homonym-sense rejection only")
P2 = p2.Policy("P2_plus_negation", rule=_rule(2), description="P1 + bounded negated-use rejection")
P3 = p2.Policy("P3_plus_attribution", rule=_rule(3),
               description="P2 + reference / historical / future / third-party attribution rejection")
P4 = p2.Policy("P4_hybrid_overrides", rule=_rule(4),
               description="P3 + narrow positive overrides on P1 homonym and P3 'like' rejections")
CANDIDATES = (P1, P2, P3, P4)
LEVEL = {P1.name: 1, P2.name: 2, P3.name: 3, P4.name: 4}


@dataclass(frozen=True)
class Occurrence:
    alias: str
    start: int
    end: int


def occurrences(text: str) -> list[Occurrence]:
    """Every occurrence of an ambiguous alias (production word-boundary pattern), in text order."""
    from gitscore.concepts.matching import alias_pattern
    out = [Occurrence(a, m.start(), m.end()) for a in sorted(AMBIGUOUS) for m in alias_pattern(a).finditer(text)]
    return sorted(out, key=lambda o: o.start)


def _sanity() -> None:  # cheap self-check, no I/O
    assert find_concept_mentions("Python") is not None


_sanity()
