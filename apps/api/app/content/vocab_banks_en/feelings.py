from app.content.vocab_catalog import CatalogDeck, _deck, _w

DOMAIN = "Feelings"


def feelings_decks() -> list[CatalogDeck]:
    return [
        _deck(
            "en",
            "conv-feelings",
            "Feelings",
            [
                _w(
                    "happy",
                    "feeling good",
                    "She looks happy today.",
                    ipa="ˈhæpi",
                    pos="adjective",
                    simple="feeling good",
                ),
                _w(
                    "sad",
                    "feeling unhappy",
                    "He felt sad after the news.",
                    ipa="sæd",
                    pos="adjective",
                    simple="not happy",
                ),
                _w(
                    "angry",
                    "feeling mad",
                    "Don't be angry with me.",
                    ipa="ˈæŋɡri",
                    pos="adjective",
                    simple="mad",
                ),
                _w(
                    "tired",
                    "needing rest",
                    "I'm too tired to go out.",
                    ipa="ˈtaɪərd",
                    pos="adjective",
                    simple="need rest",
                ),
                _w(
                    "worried",
                    "thinking something bad may happen",
                    "She's worried about the test.",
                    ipa="ˈwɜrid",
                    pos="adjective",
                    simple="thinking something bad may happen",
                ),
                _w(
                    "excited",
                    "very happy and interested",
                    "The kids are excited about the trip.",
                    ipa="ɪkˈsaɪtɪd",
                    pos="adjective",
                    simple="very happy and interested",
                ),
                _w(
                    "annoyed",
                    "slightly angry",
                    "I'm annoyed that the bus is late.",
                    ipa="əˈnɔɪd",
                    pos="adjective",
                    simple="a little angry",
                ),
                _w(
                    "confused",
                    "not understanding",
                    "I'm confused by these instructions.",
                    ipa="kənˈfjuzd",
                    pos="adjective",
                    simple="don't understand",
                ),
            ],
            domain=DOMAIN,
            sort_order=20,
        ),
    ]
