"""A report survives the steps that were only ever meant to improve it.

Building a detail report does four things beyond writing the charts: it asks which fields hold
values, it bounds every query to the window, it works out the filters, and it saves the lot. The
first three are worth having and none of them is worth the report. A build that has already spent
a minute writing twenty queries must not end in "Something went wrong" because the fourth filter
could not be mapped - and the person reading that sentence has nothing to act on and nothing to
tell anyone, which is the worst place this can leave them.

So each is wrapped, logged and named, and whatever happens a report comes back.
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.main import unhandled
from app.routers.assistant import _optional


def test_a_step_that_fails_does_not_take_the_report_with_it():
    def boom(_):
        raise RuntimeError("the model would not answer")
    value, problem = _optional("the report's filters", ["fallback"], boom, None)
    assert value == ["fallback"]
    assert problem.startswith("the report's filters: ")
    assert "the model would not answer" in problem


def test_a_step_that_works_says_nothing():
    """The page only mentions a step that was skipped, so a build where everything worked carries
    no note at all."""
    value, problem = _optional("the window", None, lambda n: n * 2, 21)
    assert (value, problem) == (42, "")


def test_the_fallback_keeps_the_shape_the_caller_unpacks():
    """Two of these return a pair, which the caller unpacks on the spot. A fallback of the wrong
    shape would turn a handled failure back into the 500 it was there to prevent."""
    def boom(*_):
        raise ValueError("no")
    (widgets, unbounded), problem = _optional("the window", ([{"id": "w1"}], []), boom, 1, 2)
    assert widgets == [{"id": "w1"}] and unbounded == [] and problem


# ---------- and when something gets past a route anyway ----------

@pytest.fixture
def app_that_breaks():
    app = FastAPI()
    app.add_exception_handler(Exception, unhandled)

    @app.get("/break")
    def _break():
        raise KeyError("Gross Loss")
    return app


def test_an_unexpected_error_says_what_it_was(app_that_breaks):
    """FastAPI's own answer is the plain text "Internal Server Error", which carries no detail -
    so the page falls back to "Something went wrong. Try again." and the person is told nothing.
    """
    client = TestClient(app_that_breaks, raise_server_exceptions=False)
    res = client.get("/break")
    assert res.status_code == 500
    detail = res.json()["detail"]
    assert "KeyError" in detail and "Gross Loss" in detail
    assert "GET /break" in detail, "which request failed is half of what makes this actionable"
    assert "server log" in detail
