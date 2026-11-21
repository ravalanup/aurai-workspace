import asyncio

import pytest

from functions.tier_filter import Filter, classify, decide


def run(coro):
    return asyncio.run(coro)


def body(text):
    return {"messages": [{"role": "user", "content": text}]}


def test_classify_finds_markers():
    assert classify("Strictly Confidential - Q3 plan") == ["restricted", "confidential"]
    assert classify("lunch menu") == []


@pytest.mark.parametrize(
    "tier,text,expected",
    [
        ("T0", "internal use only notes", ("allow", None)),
        ("T1", "internal use only notes", ("warn", "confidential")),
        ("T3", "internal use only notes", ("block", "confidential")),
        ("T0", "RESTRICTED figures", ("block", "restricted")),
        ("T1", "plain question", ("allow", None)),
    ],
)
def test_decide(tier, text, expected):
    assert decide(tier, text) == expected


def test_unknown_tier_is_strictest():
    assert decide("T9", "company confidential")[0] == "block"


def test_blocked_message_raises():
    f = Filter()
    with pytest.raises(Exception, match="cannot accept content marked restricted"):
        run(f.inlet(body("this is restricted")))


def test_warn_emits_status_and_passes_message():
    f = Filter()
    events = []

    async def emit(event):
        events.append(event)

    result = run(f.inlet(body("confidential draft"), __event_emitter__=emit))
    assert result == body("confidential draft")
    assert events and events[0]["type"] == "status" and "confidential" in events[0]["data"]["description"]


def test_clean_message_passes_without_events():
    f = Filter()
    events = []

    async def emit(event):
        events.append(event)

    assert run(f.inlet(body("hello"), __event_emitter__=emit)) == body("hello")
    assert events == []


def test_tier_valve_changes_behaviour():
    f = Filter()
    f.valves.tier = "T3"
    with pytest.raises(Exception, match="cannot accept content marked confidential"):
        run(f.inlet(body("company confidential")))


def test_length_limit():
    f = Filter()
    f.valves.max_message_chars = 10
    with pytest.raises(Exception, match="longer than"):
        run(f.inlet(body("x" * 11)))


def test_multipart_content_is_checked():
    f = Filter()
    parts = {"messages": [{"role": "user", "content": [{"type": "text", "text": "strictly confidential"}]}]}
    with pytest.raises(Exception, match="marked restricted"):
        run(f.inlet(parts))


def test_no_user_message_is_a_noop():
    f = Filter()
    assert run(f.inlet({"messages": []})) == {"messages": []}
