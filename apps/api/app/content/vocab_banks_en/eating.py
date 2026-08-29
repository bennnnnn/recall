from app.content.vocab_catalog import CatalogDeck, _deck, _w

DOMAIN = "Eating and drinking"


def eating_decks() -> list[CatalogDeck]:
    return [
        _deck(
            "en",
            "conv-chew-sip",
            "Chew and sip",
            [
                _w(
                    "bite",
                    "cut food with your teeth",
                    "Don't bite your lip.",
                    ipa="baɪt",
                    pos="verb",
                    simple="cut food with your teeth",
                ),
                _w(
                    "chew",
                    "crush food with your teeth",
                    "Chew slowly.",
                    ipa="tʃu",
                    pos="verb",
                    simple="crush food with your teeth",
                ),
                _w(
                    "swallow",
                    "move food or drink down your throat",
                    "Swallow the pill with water.",
                    ipa="ˈswɑloʊ",
                    pos="verb",
                    simple="send food down your throat",
                ),
                _w(
                    "gulp",
                    "swallow quickly or loudly",
                    "He gulped the water.",
                    ipa="ɡʌlp",
                    pos="verb",
                    simple="swallow quickly",
                ),
                _w(
                    "sip",
                    "drink a small amount",
                    "She sipped her tea.",
                    ipa="sɪp",
                    pos="verb",
                    simple="drink a little",
                ),
                _w(
                    "slurp",
                    "eat or drink with a sucking sound",
                    "Don't slurp your soup.",
                    ipa="slɜrp",
                    pos="verb",
                    simple="eat or drink with a sucking sound",
                ),
                _w(
                    "lick",
                    "move your tongue over something",
                    "The dog licked my hand.",
                    ipa="lɪk",
                    pos="verb",
                    simple="use your tongue",
                ),
                _w(
                    "suck",
                    "pull something using your mouth",
                    "The baby sucked the bottle.",
                    ipa="sʌk",
                    pos="verb",
                    simple="pull with your mouth",
                ),
            ],
            domain=DOMAIN,
            sort_order=100,
        ),
        _deck(
            "en",
            "conv-spit-choke",
            "Spit and choke",
            [
                _w(
                    "spit",
                    "force saliva out of your mouth",
                    "Don't spit on the sidewalk.",
                    ipa="spɪt",
                    pos="verb",
                    simple="force something out of your mouth",
                ),
                _w(
                    "drool",
                    "let saliva come out of your mouth",
                    "The baby drooled on the toy.",
                    ipa="drul",
                    pos="verb",
                    simple="let saliva run out",
                ),
                _w(
                    "choke",
                    "have trouble breathing because something blocks your throat",
                    "He choked on a piece of bread.",
                    ipa="tʃoʊk",
                    pos="verb",
                    simple="can't breathe because something is stuck",
                ),
            ],
            domain=DOMAIN,
            sort_order=101,
        ),
    ]
