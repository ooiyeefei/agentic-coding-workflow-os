from fixture import rolling_window_average


def test_rolling_window_average_keeps_final_window() -> None:
    result = rolling_window_average([2, 4, 6, 8], window=2)

    assert result == [3.0, 5.0, 7.0], "expected 3 windows, got 2"
