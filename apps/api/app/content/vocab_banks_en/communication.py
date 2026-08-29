from app.content.vocab_catalog import CatalogDeck, _deck, _w

DOMAIN = "Communication"


def communication_decks() -> list[CatalogDeck]:
    return [
        _deck(
            "en",
            "conv-ask-tell",
            "Ask and tell",
            [
                _w(
                    "ask",
                    "request information",
                    "Ask her what time it starts.",
                    ipa="æsk",
                    pos="verb",
                    simple="request information",
                ),
                _w(
                    "tell",
                    "give information",
                    "Tell me what happened.",
                    ipa="tɛl",
                    pos="verb",
                    simple="give information",
                ),
                _w(
                    "say",
                    "speak words",
                    "What did she say?",
                    ipa="seɪ",
                    pos="verb",
                    simple="speak words",
                ),
                _w(
                    "talk",
                    "have a conversation",
                    "We need to talk.",
                    ipa="tɔk",
                    pos="verb",
                    simple="have a conversation",
                ),
                _w(
                    "explain",
                    "make something understandable",
                    "Can you explain this again?",
                    ipa="ɪkˈspleɪn",
                    pos="verb",
                    simple="make it clear",
                ),
                _w(
                    "mention",
                    "briefly talk about something",
                    "She didn't mention the price.",
                    ipa="ˈmɛnʃən",
                    pos="verb",
                    simple="bring up briefly",
                ),
                _w(
                    "mean",
                    "intend or signify",
                    "What does this word mean?",
                    ipa="min",
                    pos="verb",
                    simple="intend or signify",
                ),
            ],
            domain=DOMAIN,
            sort_order=40,
        ),
        _deck(
            "en",
            "conv-agree",
            "Agree and suggest",
            [
                _w(
                    "agree",
                    "have the same opinion",
                    "I agree with you.",
                    ipa="əˈɡri",
                    pos="verb",
                    simple="have the same opinion",
                ),
                _w(
                    "disagree",
                    "have a different opinion",
                    "I disagree, but I hear you.",
                    ipa="ˌdɪsəˈɡri",
                    pos="verb",
                    simple="have a different opinion",
                ),
                _w(
                    "suggest",
                    "give an idea",
                    "I suggest we leave early.",
                    ipa="səɡˈdʒɛst",
                    pos="verb",
                    simple="give an idea",
                ),
                _w(
                    "promise",
                    "say you will definitely do something",
                    "I promise I'll call.",
                    ipa="ˈprɑmɪs",
                    pos="verb",
                    simple="say you will do it",
                ),
            ],
            domain=DOMAIN,
            sort_order=41,
        ),
    ]
