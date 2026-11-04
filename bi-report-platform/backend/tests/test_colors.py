"""Colour instructions read out of a dashboard request."""

from app.ai.colors import apply_color_rules, color_rules_from_prompt


def test_risk_ratings_listed_in_a_sentence():
    rules = color_rules_from_prompt(
        "Use appropriate colours for risk ratings: Minor - Green, Moderate - Yellow, "
        "Significant - Orange, and Major - Red.")
    assert rules == [{"match": "Minor", "color": "#2E9E5B"},
                     {"match": "Moderate", "color": "#E3B505"},
                     {"match": "Significant", "color": "#EE7B30"},
                     {"match": "Major", "color": "#D64545"}]


def test_en_dash_reads_the_same_as_a_hyphen():
    # Word and the browser turn " - " into " – ", so a pasted request arrives with en dashes.
    rules = color_rules_from_prompt("Minor – Green, Major – Red")
    assert [r["match"] for r in rules] == ["Minor", "Major"]


def test_hex_and_rgb_are_both_accepted():
    rules = color_rules_from_prompt("Open should be #d64545 and Closed should be rgb(46, 158, 91).")
    assert rules == [{"match": "Open", "color": "#D64545"},
                     {"match": "Closed", "color": "#2E9E5B"}]


def test_short_hex_is_expanded():
    assert color_rules_from_prompt("High - #f00")[0]["color"] == "#FF0000"


def test_the_words_of_the_instruction_are_not_categories():
    # "Colour High as red" is one clause: the category is High, not "Colour High".
    assert color_rules_from_prompt("Colour High as red") == [{"match": "High", "color": "#D64545"}]


def test_and_inside_a_name_is_kept():
    assert color_rules_from_prompt("Research and Development - blue")[0]["match"] == "Research and Development"


def test_a_request_about_nothing_but_charts_has_no_rules():
    assert color_rules_from_prompt("Issues by domain, and a bar chart of controls by owner") == []
    assert color_rules_from_prompt("") == []


def test_a_name_repeated_keeps_the_first_colour():
    rules = color_rules_from_prompt("Major - Red, Major - Green")
    assert rules == [{"match": "Major", "color": "#D64545"}]


def test_rules_go_on_the_charts_that_draw_categories():
    widgets = [{"chart": {"type": "bar"}}, {"chart": {"type": "kpi"}}, {"chart": {"type": "pie"}},
               {"chart": {"type": "table"}}]
    rules = [{"match": "Major", "color": "#D64545"}]
    apply_color_rules(widgets, rules)
    assert widgets[0]["style"]["colorRules"] == rules
    assert widgets[2]["style"]["colorRules"] == rules
    # A number and a table have no categories to colour.
    assert "style" not in widgets[1]
    assert "style" not in widgets[3]


def test_a_chart_that_already_has_rules_keeps_them():
    mine = [{"match": "Major", "color": "#000000"}]
    widgets = [{"chart": {"type": "bar"}, "style": {"colorRules": mine, "color": "#123456"}}]
    apply_color_rules(widgets, [{"match": "Major", "color": "#D64545"}])
    assert widgets[0]["style"] == {"colorRules": mine, "color": "#123456"}


def test_no_rules_leaves_every_chart_alone():
    widgets = [{"chart": {"type": "bar"}}]
    apply_color_rules(widgets, [])
    assert widgets == [{"chart": {"type": "bar"}}]
