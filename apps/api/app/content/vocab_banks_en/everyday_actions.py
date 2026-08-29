from app.content.vocab_catalog import CatalogDeck, _deck, _w

DOMAIN = "Everyday actions"


def everyday_actions_decks() -> list[CatalogDeck]:
    return [
        _deck(
            "en",
            "conv-get-give",
            "Get and give",
            [
                _w(
                    "get",
                    "receive or obtain",
                    "Did you get my message?",
                    ipa="ɡɛt",
                    pos="verb",
                    simple="receive or obtain",
                ),
                _w(
                    "give",
                    "hand something to someone",
                    "Give her the keys.",
                    ipa="ɡɪv",
                    pos="verb",
                    simple="hand something to someone",
                ),
                _w(
                    "take",
                    "carry or move something",
                    "Take an umbrella.",
                    ipa="teɪk",
                    pos="verb",
                    simple="carry or move something",
                ),
                _w(
                    "bring",
                    "take something toward someone or a place",
                    "Bring your laptop to class.",
                    ipa="brɪŋ",
                    pos="verb",
                    simple="take something here",
                ),
                _w(
                    "leave",
                    "go away",
                    "I leave at eight.",
                    ipa="liv",
                    pos="verb",
                    simple="go away",
                ),
                _w(
                    "stay",
                    "remain",
                    "Stay here until I come back.",
                    ipa="steɪ",
                    pos="verb",
                    simple="remain",
                ),
            ],
            domain=DOMAIN,
            sort_order=30,
        ),
        _deck(
            "en",
            "conv-put-keep",
            "Put and keep",
            [
                _w(
                    "keep",
                    "continue having",
                    "You can keep the change.",
                    ipa="kip",
                    pos="verb",
                    simple="continue having",
                ),
                _w(
                    "put",
                    "place something somewhere",
                    "Put the bag on the chair.",
                    ipa="pʊt",
                    pos="verb",
                    simple="place something somewhere",
                ),
                _w(
                    "pick",
                    "choose or take",
                    "Pick a color.",
                    ipa="pɪk",
                    pos="verb",
                    simple="choose or take",
                ),
                _w(
                    "grab",
                    "take quickly",
                    "Grab your coat.",
                    ipa="ɡræb",
                    pos="verb",
                    simple="take quickly",
                ),
                _w(
                    "hold",
                    "keep something in your hand",
                    "Hold my bag, please.",
                    ipa="hoʊld",
                    pos="verb",
                    simple="keep in your hand",
                ),
                _w(
                    "wait",
                    "stay until something happens",
                    "Wait for me outside.",
                    ipa="weɪt",
                    pos="verb",
                    simple="stay until something happens",
                ),
            ],
            domain=DOMAIN,
            sort_order=31,
        ),
    ]
