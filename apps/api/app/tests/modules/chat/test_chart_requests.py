"""A chart asked for in any words reaches the chart contract; a formula stays maths'.

On 2026-10-24, 15 of 30 live chart requests got no chart, a chart in a made-up format,
or maths asking which function to graph: "Show me the income in graph month by month",
"plot my test scores 72, 85, 90", "graph it" after a list of marks.
"""

from __future__ import annotations

import time

import pytest

from app.modules.chat.prompt_constants.chart import (
    chart_names_no_curve,
    chart_of_public_facts,
    is_chart_question,
)
from app.modules.math.tools.graph_followup import resolve_graph_followup
from app.modules.web_search.detection import needs_web_search
from app.services.subject_solving import detect_subject


@pytest.mark.parametrize(
    "text",
    [
        "Show me the income in graph month by month",
        "show this in a graph: Mon 5h, Tue 7h, Wed 6h, Thu 8h, Fri 4h of sleep",
        "can you put that in a chart?",
        "show that as a bar chart",
        "compare iPhone 18 Pro and Pixel 11 prices in a chart",
        "show the growth of my savings in a chart: 500, 800, 1200, 1500, 2100",
        "graph it",
        "visualize this",
        "can you visualize my sales: Q1 10k, Q2 15k, Q3 12k, Q4 20k",
        "plot my test scores 72, 85, 90, 68, 95",
        "graph the population of Ethiopia over the last 10 years",
        "graph my running distance this week: 3km, 5km, 0, 4km",
        "chart the top 5 programming languages by popularity",
        "plot temperature in Addis Ababa by month",
        "make a graph of USD to ETB exchange rate this year",
        "show me a graph of how compound interest grows on $1000 at 5% over 10 years",
        "bar graph: apples 30, bananas 45, oranges 25",
        "scatter plot of hours studied vs score: (1, 50), (2, 55), (3, 65)",
        # A language or a tool as the chart's subject, not the code that draws it.
        "bar chart of Python vs JavaScript popularity",
        "make a pie chart of my code reviews per week",
        "make a bar chart of my excel expenses: rent 1200, food 300",
        "help me visualize my spending: rent 1200, food 300",
    ],
)
def test_a_chart_asked_for_in_other_words_is_a_chart(text: str) -> None:
    assert is_chart_question(text)
    # Maths reads no curve in it, so the chart contract owns the turn.
    assert chart_names_no_curve(text)
    assert detect_subject(text) is None


@pytest.mark.parametrize(
    "text",
    [
        # A formula is maths' curve.
        "graph y = 2x + 3",
        "plot sin(x)",
        "graph x^2 - 4",
        "graph the function f(x) = 3x + 1",
        # Points on a plane, with no chart kind named, are maths' coordinate graph.
        "plot the points (1, 2), (3, 4) and (5, 6)",
        # A chart asked about, not for.
        "what's the highest value in the chart?",
        "what does the graph show",
        "I love this chart",
        "do you see the chart I sent",
        "what is a bar chart",
        # Code that draws one.
        "write python code to plot my sales",
        "make a bar chart in matplotlib",
        # A story's plot, a graph in computing, the music charts, a diagram.
        "what's the plot of Inception",
        "show me the plot of Breaking Bad season 2",
        "plot holes in the movie",
        "the plot twist was crazy",
        "explain graph theory",
        "build a knowledge graph of my notes",
        "chart topping songs this week",
        "make an org chart for my team",
        "draw a flowchart of the login process",
        # A curve or shape named in words is maths' graph.
        "graph the parabola",
        "graph a circle of radius 5",
        "graph the line through (1,2) and (3,4)",
        "show me a graph of the sine function",
        "graph the inequality x > 3",
        "graph a line with slope 2 and intercept 3",
        "graph the quadratic",
        # "Visualize" with no numbers to draw.
        "How do I visualize my goals better?",
        "I can't visualize 4D space, any tips?",
        "Help me visualize the Pythagorean theorem",
    ],
)
def test_what_is_not_a_chart_of_data_is_not_one(text: str) -> None:
    assert not is_chart_question(text)


@pytest.mark.parametrize(
    "text",
    [
        "compare iPhone 18 Pro and Pixel 11 prices in a chart",
        "chart the top 5 programming languages by popularity",
        "graph the population of Ethiopia over the last 10 years",
        "show me a chart of world population by continent",
        "make a graph of USD to ETB exchange rate this year",
    ],
)
def test_a_chart_of_facts_the_user_did_not_give_searches(text: str) -> None:
    """Drawn from memory, or refused ("those models haven't been released"), before."""
    assert chart_of_public_facts(text)
    assert needs_web_search(text)


@pytest.mark.parametrize(
    "text",
    [
        "make a bar chart of my monthly spending: rent 1200, food 450, fun 200",
        "plot my test scores 72, 85, 90, 68, 95",
        "show me a graph of how compound interest grows on $1000 at 5% over 10 years",
        "bar graph: apples 30, bananas 45, oranges 25",
        "Show me the income in graph month by month",
        "graph it",
        "show that as a bar chart",
        "show me an example bar chart",
        "draw the learning curve",
        # "In a chart" with nothing named is the chat's data.
        "put the results in a chart",
        "show the prices in a bar chart",
        "put the top three in a bar chart",
    ],
)
def test_a_chart_of_the_users_data_or_a_sample_does_not_force_a_search(text: str) -> None:
    assert not chart_of_public_facts(text)


def test_graph_it_after_data_is_a_chart_not_a_question_about_a_function() -> None:
    """ "Which function would you like me to graph?" was the reply to "graph it" after marks."""
    marks = ["Here are my exam marks: math 85, physics 78, chemistry 92, biology 88"]
    assert resolve_graph_followup("graph it", marks) == ("graph it", False)
    assert resolve_graph_followup("visualize this", ["I saved 200 in Jan, 350 in Feb"]) == (
        "visualize this",
        False,
    )
    # After a function it is still that function's graph; after nothing, maths asks.
    assert resolve_graph_followup("graph it", ["y = 2x + 3"]) == ("graph 2x + 3", False)
    assert resolve_graph_followup("graph it", ["hello there"]) == ("graph it", True)


@pytest.mark.parametrize(
    "text",
    [
        "ok  " * 40 + "hello",
        "ok\n\n" * 40,
        "please " * 300,
        "show " + "a " * 600 + "in a chart",
        # CodeQL: the formula pattern was polynomial on "=" and many spaces.
        "graph =" + " " * 20000,
    ],
)
def test_reading_a_long_message_stays_quick(text: str) -> None:
    """ "ok  ok  ok …" took seconds: the polite lead-in's spaces could be split many ways."""
    started = time.perf_counter()
    is_chart_question(text)
    chart_of_public_facts(text)
    assert time.perf_counter() - started < 0.2
