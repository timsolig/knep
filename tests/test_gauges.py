"""Regnmätarna till sidan: tolkning av SMHI:s svar och det rullande fönstret."""

from datetime import UTC, datetime

from knep.analys import gauges

MS = lambda s: int(datetime.fromisoformat(s).replace(tzinfo=UTC).timestamp() * 1000)  # noqa: E731


def doc(values):
    return {"station": [
        {"key": "1", "name": "A", "latitude": 59.1, "longitude": 18.2,
         "value": [{"date": MS(t), "value": v, "quality": q} for t, v, q in values]},
        {"key": "2", "name": "B", "latitude": 60.0, "longitude": 15.0, "value": None},
    ]}


def test_parse_keeps_good_values_and_only_stations_with_data():
    st, vals = gauges.parse(doc([("2026-11-03T18:15", "0.4", "G"), ("2026-11-03T18:30", "1.0", "R"),
                                 ("2026-11-03T18:45", "", "G"), ("2026-11-03T19:00", "0.2", "Y")]))
    assert st == {"1": [59.1, 18.2, "A"]}
    assert vals == {"2026-11-03T18:15:00Z": {"1": 0.4}, "2026-11-03T19:00:00Z": {"1": 0.2}}


def test_merge_rolls_window_and_drops_unused_stations():
    now = datetime(2026, 11, 3, 19, 0, tzinfo=UTC)
    old = {"stations": {"1": [59.1, 18.2, "A"], "9": [1, 1, "gammal"]},
           "15": {"2026-11-03T06:45:00Z": {"9": 1.0}, "2026-11-03T18:00:00Z": {"1": 0.1}}, "60": {}}
    fresh = {"15": ({"1": [59.1, 18.2, "A"]}, {"2026-11-03T18:15:00Z": {"1": 0.4}, "2026-11-03T18:00:00Z": {"1": 0.3}})}
    out = gauges.merge(old, fresh, now, hours=12)
    assert list(out["15"]) == ["2026-11-03T18:00:00Z", "2026-11-03T18:15:00Z"]
    assert out["15"]["2026-11-03T18:00:00Z"] == {"1": 0.3}  # nyare värde ersätter
    assert out["stations"] == {"1": [59.1, 18.2, "A"]} and out["60"] == {}
