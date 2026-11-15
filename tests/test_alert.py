from detector.alert import AlertGate, zone_of

ZONES = [{"name": "道路", "level": "警戒", "polygon": [[0, 0], [100, 0], [100, 100], [0, 100]]}]


def test_zone_of():
    assert zone_of((50, 50), ZONES)["name"] == "道路"
    assert zone_of((150, 50), ZONES) is None


def test_short_burst_is_not_confirmed():
    gate = AlertGate(window=25, min_hits=15)
    assert not any(gate.observe(1, True) for _ in range(4))  # 一瞬の誤検出


def test_flicker_does_not_reset():
    gate = AlertGate(window=10, min_hits=6)
    pattern = [True, True, False, True, True, False, True, True]  # 8フレーム中6回
    assert [gate.observe(1, f) for f in pattern][-1]


def test_cooldown_blocks_repeat():
    gate = AlertGate()
    assert gate.should_notify(1, "警戒", now=0)
    assert not gate.should_notify(1, "警戒", now=60)
    assert gate.should_notify(1, "警戒", now=400)


def test_unseen_track_is_forgotten():
    gate = AlertGate(window=10, min_hits=6)
    for _ in range(6):
        gate.observe(1, True)
    for _ in range(10):
        gate.tick(seen_ids=set())
    assert 1 not in gate.history