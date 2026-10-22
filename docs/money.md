# Money: loans, cards, savings and live rates

"What is my mortgage for a $300k house at 1%?" gets a worked answer, a card with sliders for
the amount, the rate and the term, and a note that compares the rate with today's average:

> Note: 1% is not a realistic 30-year mortgage rate. As of Oct 16, 2026 the US average is
> 6.27% (Freddie Mac, via FRED).

The reply's numbers are the server's, never the model's arithmetic. The phone redraws the card
as a slider moves by **evaluating** the formula the server sent; it never solves anything.

## Where it lives

| Part | Path |
|------|------|
| Products, formulas, defaults, slider ranges (data, not code paths) | `apps/api/app/modules/money/catalog.py` |
| Reading a request (product, amount, rate, term, payment, currency, country) | `apps/api/app/modules/money/read.py` |
| Numbers for the asked values, the prompt block and the note | `apps/api/app/modules/money/solve.py`, `block.py`, `note.py` |
| Today's average rates: which series answers which product, cached | `apps/api/app/modules/money/rates.py` |
| FRED (Federal Reserve Economic Data) | `apps/api/app/gateways/fred_gateway.py` |
| Settings (`money_enabled`, `fred_api_key`, cache, realism ratio) | `apps/api/app/core/settings/money.py` |
| The checked formula tree (shared with physics) | `apps/api/app/services/law_binding/expression.py` (`to_tree`) |
| The card | `apps/mobile/components/rich/CalculatorBlock.tsx` |
| The evaluator twin | `apps/mobile/lib/formula/tree.ts` |
| The slider | `apps/mobile/ui/controls/Slider.tsx` |

## Products are data

A product is one catalog row: its inputs (each with a unit, a default and a range rule), its
outputs (each a formula over the inputs), the words that name it, and the rate series that
answers "what is the average rate today". Adding a product is one row; nothing else branches on
its name. Version 1 rows:

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

`rates.py` maps a product (and a term, for mortgages) to a FRED series and reads its latest
observation through `fred_gateway.py`, cached in Redis for `money_rate_cache_seconds`. Each
answer carries its value, its date and its source. With no `FRED_API_KEY`, or for a user outside
the US (their currency or their saved location says so), there is no official average: the turn
offers the reply's web search instead, and the model states the rate it finds with its date and
source, or says it could not find one.

The note compares the user's rate with the average. A rate below `average ÷ ratio` or above
`average × ratio` (`money_unrealistic_ratio`, default 2) "is not realistic"; any other rate gets
"for reference". The server writes the note, so its number and date are exact.

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
                "source": "Freddie Mac via FRED"}},
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
- `marker` is optional: today's average on the rate slider, with its date.
- Labels are i18n keys the phone translates; there is no English text in the fence.
- The server checks every tree before sending: only the closed operations and declared names,
  finite at the asked values and at every corner of the control ranges where the formula is
  defined, and equal to the server's own numbers at the asked values. A card that fails is not
  sent; the reply still has its worked numbers.

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
