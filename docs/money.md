# Money: loans, cards, savings and live rates

"What is my mortgage for a $300k house at 1%?" gets a worked answer, a card with sliders for
the amount, the rate and the term, and a note that compares the rate with today's average:

> **Note:** 1% is not a realistic 30-year fixed mortgage rate. As of Oct 16, 2026, the average
> in the United States is 6.27% ([Mortgage Rates - Freddie Mac](https://www.freddiemac.com/pmms)).

The reply's numbers are the server's, never the model's arithmetic. The phone redraws the card
as a slider moves by **evaluating** the formula the server sent; it never solves anything.

## Where it lives

| Part | Path |
|------|------|
| Products, formulas, defaults, slider ranges (data, not code paths) | `apps/api/app/modules/money/catalog.py` |
| Reading a request (product, amount, rate, term, payment, currency, country) | `apps/api/app/modules/money/read.py` |
| Numbers for the asked values, the prompt block and the note | `apps/api/app/modules/money/solve.py`, `block.py`, `note.py` |
| Today's average rate: one web search, one checked structured read, cached | `apps/api/app/modules/money/rates.py` |
| The calculator fence and its self-check | `apps/api/app/modules/money/fence.py`, `schemas.py` |
| The turn: prepare beside the prompt, finish after the stream | `apps/api/app/modules/money/service.py`, `apps/api/app/modules/chat/turn_prep/money.py`, `apps/api/app/modules/chat/finalize_money.py` |
| Settings (`money_enabled`, `money_rate_cache_seconds`, `money_unrealistic_ratio`) | `apps/api/app/core/settings/money.py` |
| The checked formula tree (shared with physics) | `apps/api/app/services/law_binding/expression.py` (`to_tree`) |
| The card | `apps/mobile/components/rich/CalculatorBlock.tsx` |
| The evaluator twin | `apps/mobile/lib/formula/tree.ts` |
| The slider | `apps/mobile/ui/controls/Slider.tsx` |

## Products are data

A product is one catalog row: its inputs (each with a unit, a default and a range rule), its
outputs (each a formula over the inputs), the words that name it, and how to look up its
average rate today (`RateLookup`: what the rate is called, the terms averages are published for,
the plausible range and how recent a figure must be). Adding a product is one row; nothing else
branches on its name. Version 1 rows:

- **Loan** (mortgage, car, personal, student, any other amortised loan): amount, annual rate,
  term → monthly payment, total interest, total paid. A rate of 0% pays amount ÷ months.
- **Card payoff**: balance, APR, monthly payment → months to pay off, total interest. A payment
  at or below the first month's interest never pays it off, and the card says so.
- **Savings**: starting amount, monthly deposit, annual rate, years → final balance, total
  deposited, interest earned.

A term the user didn't give comes from the row's default (a 30-year mortgage, a 5-year car loan),
and the reply says it assumed one. A rate they didn't give comes from today's average when there
is one; otherwise the model asks for it.

## Today's rates

`rates.py` looks up today's average with one web search through the web-search module's own
cached search, for example "average 30-year fixed mortgage rate this week the United States".
One small structured read (`ROUTING.background`, validated by `RateReading`) takes the rate, the
date it describes and the URL that states it from the top results. The reading counts only when:

- the rate lies in the product's plausible range (`RateLookup.plausible`);
- the date parses and is no older than the row's `fresh_days` (and not in the future);
- the URL is one of the pages the search returned.

Anything else is no average. One answer serves every turn for the same product, term bucket
and country for `money_rate_cache_seconds`, so most turns never search. A miss spends one of the
asking user's daily searches.

The country comes from the request's currency (birr → Ethiopia), else the user's saved place,
else the United States; the query carries it, so every country takes the same path.

The lookup starts with the turn. It is waited on before the prompt only when the numbers need it
(no rate given, or "what are rates now?"), for at most a few seconds; otherwise it runs while the
reply streams and the finalize pass collects it. No average means no note and no marker; the
model is told never to state a market rate itself, and a rates question without one says it
could not find today's figure.

The note compares the user's rate with the average. A rate below `average ÷ ratio` or above
`average × ratio` (`money_unrealistic_ratio`, default 2) "is not realistic"; any other gets
"for reference"; a rate taken from the average says so. The server writes the note, with the
average's date and a link to its source.

## The `calculator` fence

The server appends it after the reply; the model never writes one. JSON, one object:

```json
{
  "v": 1,
  "product": "loan",
  "title_key": "money.title.mortgage",
  "currency": "USD",
  "controls": [
    {"name": "amount", "label_key": "money.amount", "format": "money",
     "min": 50000, "max": 1000000, "step": 5000, "value": 300000},
    {"name": "rate", "label_key": "money.rate", "format": "percent",
     "min": 0, "max": 15, "step": 0.05, "value": 1,
     "marker": {"value": 6.27, "label_key": "money.average", "as_of": "2026-10-16",
                "source": "Mortgage Rates - Freddie Mac",
                "source_url": "https://www.freddiemac.com/pmms"}},
    {"name": "years", "label_key": "money.term_years", "format": "years",
     "min": 1, "max": 40, "step": 1, "value": 30}
  ],
  "readouts": [
    {"name": "payment", "label_key": "money.monthly_payment", "format": "money",
     "primary": true, "tree": {"op": "...", "a": []}},
    {"name": "interest", "label_key": "money.total_interest", "format": "money", "tree": {}},
    {"name": "total", "label_key": "money.total_paid", "format": "money", "tree": {}}
  ]
}
```

- `format` is a closed list: `money`, `percent`, `years`, `months`, `number`.
- Each readout's `tree` is over the control names only. A value that is not finite (a card
  payment that never pays off) shows the readout's `never_key` text, or a dash.
- `marker` is optional: today's average on the rate slider, with its date, the source's title
  and, optionally, `source_url` (the page the rate came from).
- `currency` is "" when the request named none; the phone then shows its own.
- Labels are i18n keys the phone translates; there is no English text in the fence.
- The server checks every tree before sending: only the closed operations and declared names,
  finite at the asked values and at every corner of the control ranges where the formula is
  defined, and equal to the server's own numbers at the asked values. A card that fails is not
  sent; the reply still has its worked numbers.

### Keys the server sends

- Titles: `money.title.car`, `money.title.card`, `money.title.loan`, `money.title.mortgage`, `money.title.personal`, `money.title.savings`, `money.title.student`.
- Controls: `money.amount`, `money.apr`, `money.balance`, `money.deposit`, `money.monthly_payment`, `money.rate`, `money.start`, `money.term_months`, `money.term_years`.
- Readouts: `money.final_balance`, `money.interest_earned`, `money.monthly_payment`, `money.months_to_pay_off`, `money.total_deposited`, `money.total_interest`, `money.total_paid`; `never_key`: `money.never`.
- Marker: `money.average`.
- Control names per product: mortgage `amount, rate, years`; car `amount, rate, months`; student `amount, rate, years`; personal `amount, rate, months`; loan `amount, rate, years`; card `balance, apr, payment`; savings `start, deposit, rate, years`. A car or personal loan's term is `months`; every other term is `years`.

## The formula tree

The same closed language the catalog's expressions use (`expression.py`), as JSON, never as
text:

| Node | JSON |
|------|------|
| number | `{"n": 0.05}` |
| name (a control, or `pi`) | `{"v": "rate"}` |
| `+ - * / ^` | `{"op": "+", "a": [left, right]}` |
| unary minus | `{"op": "neg", "a": [x]}` |
| function (`sqrt sin cos tan asin acos atan exp log abs`) | `{"fn": "log", "a": [x]}` |
| condition | `{"op": "if", "a": [{"cmp": ">", "a": [left, right]}, then, else]}` |

`cmp` is one of `> >= < <= ==`. Division by zero, a negative base to a fractional power or a
function outside its domain gives no number (the phone shows a dash). Depth is at most 32 and a
tree at most 512 nodes.

`docs/fixtures/formula_tree_cases.json` holds trees, values and the server's result; the phone's
jest test evaluates each and must agree to 1e-9 relative (`null` means no number). The server
test that writes it runs with `UPDATE_FORMULA_TREE_FIXTURE=1`.
