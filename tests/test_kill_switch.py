from governor.time_kill_switch import TimeKillSwitch
from tests.helpers import FakeClock


def finish(switch, clock, count, seconds_each):
    for _ in range(count):
        clock.advance(seconds_each)
        switch.company_finished()


def test_no_projection_before_ten_companies_finish():
    clock = FakeClock()
    switch = TimeKillSwitch(clock)
    switch.begin_phase(100)
    finish(switch, clock, 9, 200)  # very slow, but too early to judge
    assert switch.projected_minutes() is None
    assert switch.check() == "ok"


def test_trips_when_projected_finish_is_above_38_minutes():
    clock = FakeClock()
    switch = TimeKillSwitch(clock)
    switch.begin_phase(15)
    finish(switch, clock, 10, 190)  # 31.7 min gone, 5 left at 0.32 per minute
    assert switch.projected_minutes() > 38
    assert switch.check() == "trip"
    assert switch.check() == "trip"  # stays tripped


def test_keeps_going_when_the_projection_is_fine():
    clock = FakeClock()
    switch = TimeKillSwitch(clock)
    switch.begin_phase(12)
    finish(switch, clock, 10, 150)  # 25 min gone, 2 left at 0.4 per minute
    assert 29 < switch.projected_minutes() < 31
    assert switch.check() == "ok"


def test_speed_uses_only_the_last_ten_completions():
    clock = FakeClock()
    switch = TimeKillSwitch(clock)
    switch.begin_phase(40)
    finish(switch, clock, 10, 100)  # slow start
    finish(switch, clock, 10, 5)  # now fast: 12 per minute
    projected = switch.projected_minutes()
    assert projected < 38
    assert switch.check() == "ok"


def test_hard_stop_at_forty_minutes():
    clock = FakeClock()
    switch = TimeKillSwitch(clock)
    switch.begin_phase(5)
    clock.advance(39 * 60 + 59)
    assert switch.check() == "ok"
    clock.advance(1)
    assert switch.check() == "hard_stop"
