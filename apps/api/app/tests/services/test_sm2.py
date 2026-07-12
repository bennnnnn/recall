"""Tests for SM-2 spaced repetition helpers."""

from datetime import UTC, datetime

from app.services.sm2 import apply_sm2, quality_for_status


def test_apply_sm2_fail_resets_to_one_day():
    state = apply_sm2(
        quality=1,
        ease_factor=2.5,
        interval_days=10,
        review_count=4,
        now=datetime(2026, 7, 9, tzinfo=UTC),
    )
    assert state.review_count == 0
    assert state.interval_days == 1
    assert state.due_at.day == 10


def test_apply_sm2_fail_decreases_ease_factor():
    """BUG FIX (was silent): the EF update used to only run in the q>=3 branch, so a
    wrong answer (quality_for_status returns q=1) never applied SM-2's EF penalty —
    ease_factor only ever moved upward. It must now decrease on a failed review."""
    state = apply_sm2(
        quality=1,
        ease_factor=2.5,
        interval_days=10,
        review_count=4,
        now=datetime(2026, 7, 9, tzinfo=UTC),
    )
    assert state.ease_factor < 2.5
    assert state.ease_factor == 1.96


def test_apply_sm2_fail_ease_factor_floors_at_one_point_three():
    state = apply_sm2(
        quality=0,
        ease_factor=1.3,
        interval_days=1,
        review_count=0,
        now=datetime(2026, 7, 9, tzinfo=UTC),
    )
    assert state.ease_factor == 1.3


def test_apply_sm2_first_success_is_one_day():
    state = apply_sm2(
        quality=5,
        ease_factor=2.5,
        interval_days=0,
        review_count=0,
        now=datetime(2026, 7, 9, tzinfo=UTC),
    )
    assert state.review_count == 1
    assert state.interval_days == 1


def test_apply_sm2_second_success_is_six_days():
    state = apply_sm2(
        quality=4,
        ease_factor=2.5,
        interval_days=1,
        review_count=1,
        now=datetime(2026, 7, 9, tzinfo=UTC),
    )
    assert state.review_count == 2
    assert state.interval_days == 6


def test_quality_for_status():
    assert quality_for_status("mastered") == 5
    assert quality_for_status("learning") == 3
    assert quality_for_status("new", was_correct=False) == 1
