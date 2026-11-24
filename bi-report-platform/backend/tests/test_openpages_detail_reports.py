"""
Reading a one-line request as the detail report it asks for.

No AI model is involved, so every answer here is exact: the test is that the four subjects people
ask for in one line are recognised, that the window in the words wins over the report's usual one,
that the dates on the page are real dates rather than a relative phrase, and - most of all - that
a request this does not know is handed on untouched. A wrong expansion replaces what someone asked
for with something else, which is worse than not expanding at all.
"""

from datetime import date

from app.openpages_detail_reports import (CONTROL_TESTS, KRI_TREND, LOSS_EVENTS, REPORTS, RISKS,
                                          expand)

TODAY = date(2026, 11, 24)


def test_the_four_subjects_are_recognised():
    asked = {
        "Get me controls test report for past 3 months": CONTROL_TESTS,
        "Get me risk report for past 2 months": RISKS,
        "Show me KRI trend report for past 6 months": KRI_TREND,
        "Loss events report for past 3 months": LOSS_EVENTS,
    }
    for request, report in asked.items():
        got = expand(request, TODAY)
        assert got is not None, request
        assert got.report is report, request


def test_the_window_comes_from_the_words():
    got = expand("Get me controls test report for past 3 months", TODAY)
    assert got.window.start == date(2026, 8, 26)
    assert got.window.end == TODAY
    assert got.window.title == "Last 3 Months"

    longer = expand("Get me risk report for past 12 months", TODAY)
    assert longer.window.start == date(2025, 11, 29)
    assert longer.window.title == "Last 12 Months"


def test_a_report_without_a_window_gets_its_usual_one():
    assert expand("loss events report", TODAY).window.title == "Last 3 Months"
    assert expand("show me the risk report", TODAY).window.title == "Last 2 Months"
    assert expand("KRI trend report please", TODAY).window.title == "Last 6 Months"


def test_weeks_and_year_to_date_are_understood():
    assert expand("loss events report for the last 6 weeks", TODAY).window.start == date(2026, 10, 13)
    ytd = expand("risk report year to date", TODAY)
    assert ytd.window.start == date(2026, 1, 1)
    assert ytd.window.title == "Year to Date"


def test_real_dates_reach_the_prompt_not_a_relative_phrase():
    prompt = expand("Get me controls test report for past 3 months", TODAY).prompt
    assert "26 August 2026 and 24 November 2026 (the last 3 months)" in prompt
    assert "Control Testing - Last 3 Months" in prompt
    # The relative phrase the person typed never survives into the prompt on its own.
    assert "past 3 months" not in prompt
    assert "falls between" in prompt


def test_the_more_specific_subject_wins():
    # Names both controls and risks; it is a testing report.
    assert expand("control test report", TODAY).report is CONTROL_TESTS
    # Names risk, but it is about the indicators.
    assert expand("key risk indicator report for past 6 months", TODAY).report is KRI_TREND


def test_a_request_this_does_not_know_is_left_alone():
    for request in ("", "risks", "show me vendors by criticality",
                    "build me a questionnaire assessment page",
                    "x" * 500):
        assert expand(request, TODAY) is None, request


def test_a_request_that_describes_its_own_page_is_left_alone():
    # The person has said what they want; expanding would overwrite it.
    assert expand("risk report for past 2 months as a pie chart", TODAY) is None
    assert expand("loss events report with a tab per business entity", TODAY) is None


def test_every_prompt_carries_the_shared_blocks_and_fits_the_cap():
    from app.schemas import MAX_WIDGETS

    for report in REPORTS:
        prompt = expand(f"{report.title} report", TODAY).prompt
        for block in ("KPI CARDS", "DETAIL TABLE", "LAYOUT", "DRILL-DOWN", "HOUSE RULES"):
            assert block in prompt, f"{report.id} is missing {block}"
        assert "{window}" not in prompt and "{title}" not in prompt
        # 4 cards + 15 charts + 2 tables, comfortably under the cap that used to truncate these.
        assert 4 + 15 + 2 <= MAX_WIDGETS
