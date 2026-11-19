import unittest

from driverepair_desktop.rates import RateWindow, choose_speed


class ChooseSpeedTests(unittest.TestCase):
    def test_recent_speed_wins_when_present(self):
        value, is_average = choose_speed(5_000_000, 3_000_000, finished=False)
        self.assertEqual(value, 5_000_000)
        self.assertFalse(is_average)

    def test_unfinished_job_without_recent_sample_stays_placeholder(self):
        self.assertEqual(choose_speed(None, 3_000_000, finished=False), (None, False))

    def test_finished_job_falls_back_to_average(self):
        # A scan completing inside one rate window never produces speed_bps.
        value, is_average = choose_speed(None, 2_048_000, finished=True)
        self.assertEqual(value, 2_048_000)
        self.assertTrue(is_average)

    def test_zero_and_garbage_are_not_measurements(self):
        self.assertEqual(choose_speed(0, 0, finished=True), (None, False))
        self.assertEqual(choose_speed(None, 'n/a', finished=True), (None, False))
        self.assertEqual(choose_speed('', None, finished=True), (None, False))


class RateWindowTests(unittest.TestCase):
    def test_single_point_has_no_rate(self):
        window = RateWindow(5)
        self.assertIsNone(window.update(1024, now=100.0))

    def test_two_points_produce_a_rate(self):
        window = RateWindow(5)
        window.update(0, now=100.0)
        self.assertAlmostEqual(window.update(2_000_000, now=102.0), 1_000_000.0)


if __name__ == "__main__":
    unittest.main()
