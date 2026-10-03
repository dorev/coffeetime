from bot_aide.ratelimit import RateLimiter


class FakeClock:
    def __init__(self):
        self.t = 0.0

    def __call__(self):
        return self.t


def test_limits_per_key_and_window():
    clock = FakeClock()
    rl = RateLimiter(2, window_seconds=60, clock=clock)
    assert rl.allow("a") and rl.allow("a")
    assert not rl.allow("a")
    assert rl.allow("b")
    clock.t = 59
    assert not rl.allow("a")
    clock.t = 60
    assert rl.allow("a")
