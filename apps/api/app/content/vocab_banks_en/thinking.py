from app.content.vocab_catalog import CatalogDeck, _deck, _w

DOMAIN = "Thinking"


def thinking_decks() -> list[CatalogDeck]:
    return [
        _deck(
            "en",
            "conv-know-think",
            "Know and think",
            [
                _w(
                    "know",
                    "have information",
                    "I know the answer.",
                    ipa="noʊ",
                    pos="verb",
                    simple="have information",
                ),
                _w(
                    "think",
                    "use your mind",
                    "Let me think about it.",
                    ipa="θɪŋk",
                    pos="verb",
                    simple="use your mind",
                ),
                _w(
                    "believe",
                    "think something is true",
                    "I believe you.",
                    ipa="bɪˈliv",
                    pos="verb",
                    simple="think it's true",
                ),
                _w(
                    "remember",
                    "keep something in your mind",
                    "Do you remember her name?",
                    ipa="rɪˈmɛmbər",
                    pos="verb",
                    simple="keep in your mind",
                ),
                _w(
                    "forget",
                    "fail to remember",
                    "Don't forget your keys.",
                    ipa="fərˈɡɛt",
                    pos="verb",
                    simple="not remember",
                ),
                _w(
                    "understand",
                    "know what something means",
                    "I understand the question.",
                    ipa="ˌʌndərˈstænd",
                    pos="verb",
                    simple="know what it means",
                ),
            ],
            domain=DOMAIN,
            sort_order=50,
        ),
        _deck(
            "en",
            "conv-notice-decide",
            "Notice and decide",
            [
                _w(
                    "realize",
                    "suddenly understand",
                    "I realize I was wrong.",
                    ipa="ˈriəˌlaɪz",
                    pos="verb",
                    simple="suddenly understand",
                ),
                _w(
                    "notice",
                    "become aware of something",
                    "Did you notice the sign?",
                    ipa="ˈnoʊtɪs",
                    pos="verb",
                    simple="become aware",
                ),
                _w(
                    "guess",
                    "answer without being certain",
                    "Guess who called.",
                    ipa="ɡɛs",
                    pos="verb",
                    simple="answer without being sure",
                ),
                _w(
                    "decide",
                    "make a choice",
                    "We need to decide now.",
                    ipa="dɪˈsaɪd",
                    pos="verb",
                    simple="make a choice",
                ),
            ],
            domain=DOMAIN,
            sort_order=51,
        ),
    ]
