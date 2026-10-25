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
| Reading a request (product, kind, amount, down payment, rate, term, payment, currency) | `apps/api/app/modules/money/read.py` |
| A what-if that changes the chat's last request ("what if i only do 3 years instead") | `apps/api/app/modules/money/follow_up.py` |
| The currency a request names, the card's currency and the country a rate search names | `apps/api/app/modules/money/currencies.py` |
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
branches on its name. A kind of a product priced apart is a `Variant` on its row, with its own
words and `RateLookup`: "a used car for 14000" (also pre-owned, certified pre-owned,
second-hand) is a car loan looked up at the used-car average, cached apart from the new-car one
and named in the reply ("used car loan rate"; used-car averages are published for every term at
once, so that lookup names none). A kind word used as a verb names none: "I used a calculator",
"I'm used to paying 300", "the car I used to have". New or no kind said is the row's own lookup.

The row's own lookup starts beside a variant's. When the variant's finds nothing in time, the
row's own average stands in and says so: the reply and the note name it ("today's average
60-month new car loan rate") and add the variant's `stand_in` words ("No used-car average was
found; used-car loans usually cost more."), the model is told never to call it a used-car rate,
and a rate the user gave is not called unrealistic beside it. The first live used-car ask found
no used-car average and got no numbers at all, where the new-car average had worked it. Version
1 rows:

- **Loan** (mortgage, car, personal, student, any other amortised loan): amount, annual rate,
  term → monthly payment, total interest, total paid. A rate of 0% pays amount ÷ months.
- **Card payoff**: balance, APR, monthly payment → months to pay off, total interest. A payment
  at or below the first month's interest never pays it off, and the card says so.
- **Savings**: starting amount, monthly deposit, annual rate, years → final balance, total
  deposited, interest earned.

A term the user didn't give comes from the row's default (a 30-year mortgage, a 5-year car loan),
and the reply says it assumed one. A rate they didn't give comes from today's average when there
is one; otherwise the model asks for it. "3 years ago", "20 years old", "sell after 5 years" or
"the past 3 years" is no term ("paid off after 15 years" is). "20% down" and "a down payment of
20%" are a share of the price, not the rate; a percent after a sum put down ("5000 down 6.9%")
is the rate. In "the rate went down 1% to 5.5%" the rate is 5.5%. "A 2022 car" is a model year,
not a price, and "5000 upfront" is a down payment.

## Follow-ups

"hmm what if i only do 3 years instead" right after a money reply is that request with the term
changed, and the server works it and sends the card exactly as for a first ask. The follow-up
chips under a money reply ask exactly this; before, the model did the arithmetic itself and was
off by dollars (live 2026-10-25: $340.58 a month for $340.45).

- The turn passes the user's earlier lines in its window (`turn_prep/money.py`). The request a
  line changes is the last one in the user's last three lines, and every line after it must be a
  change of it too, so changes build on each other ("3 years instead", then "and with 5000
  down?") and a line about something else ends the money conversation.
- A change line asks for one ("what if", "how about", "instead", or only the change: "36
  months?") and every number in it must be placed by its own words (`follow_up_words.py`). A
  percent is the rate only beside rate words ("at 5%", "the rate was 6.5%", "5% APR", "what if
  it's 5%") or alone. A term is the loan's by the words before it ("do 3 years", "pay it off in
  2 years"; not "wait 2 years", "keep it for 10 years" or "5% in 2 years"). A loan's sum is a
  down payment ("5000 down", "5000 upfront", "20% down"), an amount borrowed ("borrow 8000", "a
  25000 car loan") or a price ("what if the car was $18,000", "a new one for 30000", "what about
  400k?"); a card's is its payment ("pay 300") or balance ("owe 8000"); a savings plan's is a
  monthly deposit or a starting sum. A line that names something the request has no input for
  (a tax, PMI, inflation, a raise, a trade-in, cash back, insurance, a salary, rent, a
  refinance), a sum that is paid, sold, saved or earned ("what if I pay 400 instead?"), a number
  it cannot place, a change by an amount ("1% lower", "2000 more down") or another product named
  is no follow-up: the model answers as before. Reviewed 2026-10-25: looser rules had made "what
  if property tax is 1.2%" a 1.2% mortgage and "what if I pay 400 instead?" a $400 loan.
- A follow-up can change the kind either way: "what if it was a used car?", and back with "what
  if I bought a new car for 30000 instead" ("new" counts only beside what is bought: not "a new
  job").
- While the rate is today's average, the follow-up looks up the term the first ask used, so "3
  years instead" changes the term alone and keeps the rate the last reply quoted.
- The money block tells the model which inputs changed and that the numbers below are the
  answer, never to be redone from the earlier reply.

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
- `currency` is the one the request named, else the user's saved place's, else USD when no
  place is saved (`currencies.currency_for`). It is "" only for a saved place the list does not
  know; the phone then shows plain numbers, no symbol.
- Labels are i18n keys the phone translates; there is no English text in the fence.
- The server checks every tree before sending: only the closed operations and declared names,
  finite at the asked values and at every corner of the control ranges where the formula is
  defined, and equal to the server's own numbers at the asked values. A card that fails is not
  sent; the reply still has its worked numbers.

## Label keys

The fence names text by key, and the phone translates it in all nine languages. Every key starts
with `money.`; the phone refuses a fence whose `title_key` or `label_key` doesn't, and shows a
fallback (the title "Loan", an empty label, a dash) for a `money.` key it has no text for, never
the raw key. Keys the phone has (a server test, `test_money_label_keys.py`, holds the catalog to them):

| Use | Keys |
|-----|------|
| `title_key` | `money.title.mortgage`, `money.title.car`, `money.title.personal`, `money.title.student`, `money.title.loan`, `money.title.card`, `money.title.savings` |
| control `label_key` | `money.amount`, `money.rate`, `money.term_years`, `money.term_months`, `money.balance`, `money.apr`, `money.payment`, `money.start`, `money.deposit` |
| readout `label_key` | `money.monthly_payment`, `money.total_interest`, `money.total_paid`, `money.months_to_payoff`, `money.final_balance`, `money.total_deposited`, `money.interest_earned` |
| readout `never_key` | `money.never` ("Never at this payment") |
| marker `label_key` | `money.average` ("Avg {{value}} · {{date}}"); with no `as_of` the phone uses `money.average_undated` |

The phone's own keys, not sent by the server: `money.average_a11y`, `money.average_a11y_undated`,
`money.source`, `money.source_undated` (the line under the card naming the marker's source and
date), `money.reset`, `money.reset_a11y`, and the counted `money.years_count` / `money.months_count`
that print a `years` or `months` value ("30 years"; a `months` readout counts a last part-month).

On the phone: the card is `components/rich/CalculatorBlock.tsx`, its reader `lib/money/calculator.ts`,
its formatting `lib/money/format.ts` (money in the fence's `currency` and the app's language, cents
only on amounts under 10,000 that have them). Tapping the marker sets the slider to the marker's
exact value. Where the user left the sliders survives the list recycling the card and is cleared at
sign-out. Copy and Read aloud leave the card out: the reply's own text states its numbers.

Control names per product: mortgage `amount, rate, years`; car `amount, rate, months`; student `amount, rate, years`; personal `amount, rate, months`; loan `amount, rate, years`; card `balance, apr, payment`; savings `start, deposit, rate, years`. A car or personal loan's term is `months`; every other term is `years`.

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
