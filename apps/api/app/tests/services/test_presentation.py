"""Markdown boundaries and one-row calculation layout."""

from app.services.chat.calculation_layout import split_math_expression
from app.services.chat.presentation import present_assistant_markdown

CYCLIST = "A cyclist rides 12 km at 20 km/h then 8 km at 10 km/h. Find average speed."


def test_glued_bold_values_regain_a_word_space() -> None:
    train = "A train travels at**60 km/h** and returns at**40 km/h**."
    cyclist = "A cyclist rides **12 km** at**20 km/h**, then**8 km** at**10 km/h**."
    train_out = present_assistant_markdown(train)
    cyclist_out = present_assistant_markdown(cyclist)
    assert "at **60 km/h**" in train_out
    assert "at **40 km/h**" in train_out
    assert "at**" not in train_out
    assert "at **20 km/h**" in cyclist_out
    assert "then **8 km**" in cyclist_out
    assert "at **10 km/h**" in cyclist_out
    assert "at**" not in cyclist_out
    assert "then**" not in cyclist_out


def test_punctuation_and_parentheses_stay_tight() -> None:
    answer = "The answer is **48 km/h** — not **50 km/h**."
    assert present_assistant_markdown(answer) == answer
    assert present_assistant_markdown("(**important**)") == "(**important**)"
    assert present_assistant_markdown("**48 km/h**.") == "**48 km/h**."
    assert present_assistant_markdown("**48 km/h**,") == "**48 km/h**,"


def test_inline_code_link_and_math_boundaries() -> None:
    assert present_assistant_markdown("Use `yield` when appropriate.") == (
        "Use `yield` when appropriate."
    )
    assert present_assistant_markdown("Use`yield`when appropriate.") == (
        "Use `yield` when appropriate."
    )
    link = "See [the documentation](https://example.com/docs)."
    assert present_assistant_markdown(link) == link
    assert present_assistant_markdown("See[the documentation](https://example.com/docs)now") == (
        "See [the documentation](https://example.com/docs) now"
    )
    assert present_assistant_markdown("speed is $v=5$ km/h") == "speed is $v=5$ km/h"
    assert present_assistant_markdown("speed is$v=5$km/h") == "speed is $v=5$ km/h"


def test_unclosed_tokens_urls_code_and_scripts_without_spaces_stay() -> None:
    assert present_assistant_markdown("at**40") == "at**40"
    assert present_assistant_markdown("speed is $v = 5") == "speed is $v = 5"
    assert present_assistant_markdown("see https://example.com/a**b** now") == (
        "see https://example.com/a**b** now"
    )
    assert present_assistant_markdown("2*3*4") == "2*3*4"
    assert present_assistant_markdown("速度**40**米") == "速度**40**米"
    assert present_assistant_markdown("It costs $5 and $10.") == "It costs $5 and $10."
    fenced = "```python\nprint('at**40**')\n```"
    assert present_assistant_markdown(fenced) == fenced
    assert present_assistant_markdown("    at**40**") == "    at**40**"
    assert present_assistant_markdown("> at**40 km/h**") == "> at**40 km/h**"


def test_table_cell_keeps_one_line_and_a_list_keeps_its_marker() -> None:
    table = "| at**40** | **50** |\n| --- | --- |"
    presented = present_assistant_markdown(table)
    assert presented.split("\n")[0] == "| at **40** | **50** |"
    assert presented.count("\n") == table.count("\n")
    assert present_assistant_markdown("- at**40 km/h**") == "- at **40 km/h**"


def test_equals_chain_becomes_one_state_per_row() -> None:
    presented = present_assistant_markdown(r"$v = d/t = 50/10 = 5$")
    assert presented == "$v = d/t$  \n$v = 50/10$  \n$v = 5$"
    rows = split_math_expression(r"t_{\text{total}} = d/60 + d/40 = (2d+3d)/120 = 5d/120")
    assert rows == [
        r"t_{\text{total}} = d/60 + d/40",
        r"t_{\text{total}} = (2d+3d)/120",
        r"t_{\text{total}} = 5d/120",
    ]


def test_independent_equations_are_separate_rows() -> None:
    presented = present_assistant_markdown(r"$t_1=d/60,\quad t_2=d/40$")
    assert presented == "$t_1=d/60$  \n$t_2=d/40$"
    assert r"\quad" not in presented


def test_closed_paren_math_splits_and_an_open_one_stays_literal() -> None:
    source = "  \\(\n  v = d/t = 50/10 = 5\n  \\)"
    assert present_assistant_markdown(source) == ("  $v = d/t$  \n  $v = 50/10$  \n  $v = 5$")
    unfinished = "  \\(\n  \\frac{1}{2} = x"
    assert present_assistant_markdown(unfinished) == unfinished
    quoted = "> \\(v = d/t = 5\\)"
    assert present_assistant_markdown(quoted) == quoted


def test_one_relationship_with_or_or_an_arrow_stays_one_row() -> None:
    roots = "$x = 2 or x = -2$"
    step = r"$2x - 1 = 0 \rightarrow x = \frac{1}{2}$"
    implied = r"$r^2 + 1 = \frac{17}{4}r \quad \Rightarrow \quad 4r^2 - 17r + 4 = 0$"
    assert present_assistant_markdown(roots) == roots
    assert present_assistant_markdown(step) == step
    assert present_assistant_markdown(implied) == implied


def test_atomic_and_wide_formulas_stay_one_row() -> None:
    atomic = r"$12 + 8 = 20\text{ km}$"
    quadratic = r"$x = \frac{-b\pm\sqrt{b^2-4ac}}{2a}$"
    factorial = r"$4! = 4 \times 3 \times 2 \times 1 = 24$"
    matrix = r"$\begin{pmatrix} 1 & 0 \\ 0 & 1 \end{pmatrix}$"
    assert present_assistant_markdown(atomic) == atomic
    assert present_assistant_markdown(quadratic) == quadratic
    assert present_assistant_markdown(factorial) == factorial
    assert present_assistant_markdown(matrix) == matrix
    assert split_math_expression("f(x, y) = 1") is None
    assert present_assistant_markdown("$20 \\div 4 = 5$") == "$20 \\div 4 = 5$"


def test_plain_symbol_chain_splits_and_an_english_sentence_does_not() -> None:
    presented = present_assistant_markdown("n = m/M = 10/18")
    assert presented == "$n = m/M$  \n$n = 10/18$"
    sentence = "Atoms of each element in water = 2"
    assert present_assistant_markdown(sentence) == sentence


def test_math_fence_chain_becomes_rows_and_other_fences_stay() -> None:
    presented = present_assistant_markdown("```math\nv = d/t = 50/10 = 5\n```")
    assert presented == "$v = d/t$  \n$v = 50/10$  \n$v = 5$"
    chart = '```chart\n{"a": "b = c = d"}\n```'
    assert present_assistant_markdown(chart) == chart


def test_adjacent_tokens_units_and_wide_statistics_stay_readable() -> None:
    assert present_assistant_markdown("**speed**$v=5$") == "**speed** $v=5$"
    assert present_assistant_markdown("about**12%**of the sample") == "about **12%** of the sample"
    assert present_assistant_markdown("dropped to$-5$ overnight") == "dropped to $-5$ overnight"
    scientific = r"$N = 6.02 \times 10^{23}$"
    assert present_assistant_markdown(scientific) == scientific
    statistic = r"$s = \sqrt{\frac{\sum (x-\bar x)^2}{n-1}}$"
    assert present_assistant_markdown(statistic) == statistic
    converted = present_assistant_markdown(r"$1\text{ km} = 1000\text{ m} = 100000\text{ cm}$")
    assert converted == "$1\\text{ km} = 1000\\text{ m}$  \n$1\\text{ km} = 100000\\text{ cm}$"
    chemistry = present_assistant_markdown(r"$n = \frac{m}{M} = \frac{10}{18}$")
    assert chemistry == "$n = \\frac{m}{M}$  \n$n = \\frac{10}{18}$"
    table = r"| $v = d/t = 5$ | **48 km/h** |"
    assert present_assistant_markdown(table) == table
    assert present_assistant_markdown("- rides **12 km** at**20 km/h**") == (
        "- rides **12 km** at **20 km/h**"
    )


def test_escaped_currency_dollar_does_not_split_the_formula() -> None:
    source = r"$\$43 \text{ per hour} \times 40 \text{ hours} = \$1{,}720 \text{ per week}$"
    assert present_assistant_markdown(source) == source
    assert present_assistant_markdown(r"$\$1,505$") == r"$\$1,505$"
    assert present_assistant_markdown(r"$\mathbf{\$3,440}$") == r"$\mathbf{\$3,440}$"


def test_presentation_is_idempotent() -> None:
    source = (
        "A cyclist rides **12 km** at**20 km/h**, then**8 km** at**10 km/h**.\n\n"
        "$v = d/t = 50/10 = 5$"
    )
    once = present_assistant_markdown(source)
    assert present_assistant_markdown(once) == once
    assert "at **20 km/h**" in once
    assert "$v = d/t$  \n$v = 50/10$  \n$v = 5$" in once
