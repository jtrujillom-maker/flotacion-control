import unittest
from dataclasses import replace
from model import Config, simulate, delay_value


class ModelTests(unittest.TestCase):
    def test_equilibrium(self):
        for plant in ("published", "geometric"):
            r = simulate(Config(plant=plant, duration=50, feed_events=(), setpoint_events=()))
            self.assertEqual(r["status"], "completed")
            self.assertEqual(r["records"][-1]["level"], [30.0, 34.0, 33.0])
            self.assertEqual([m["iae"] for m in r["metrics"]], [0.0]*3)

    def test_integrating_slope_and_delay(self):
        # Direct plant equation: +10 L/min outlet step, 7 s effective delay.
        h = 30.0
        levels = [h]
        history = [55.0] * 20
        for k in range(20):
            h += -0.001018 * (delay_value(history, k, 7, 45.0) - 45.0)
            levels.append(h)
        self.assertAlmostEqual(levels[7], 30.0)
        self.assertAlmostEqual(levels[8], 30.0 - 0.01018)
        self.assertAlmostEqual(levels[20], 30.0 - 13*0.01018)

    def test_conservation_without_delays(self):
        c = Config(duration=20, plant="geometric", delays_s=(0,0,0),
                   feed_events=((0,50.0),), setpoint_events=(), strategy="pi")
        r = simulate(c)
        b = 1000/(60*900)
        for left, right in zip(r["records"], r["records"][1:]):
            expected = b*(left["feed"]-left["outflow"][2])*c.dt
            self.assertAlmostEqual(sum(right["level"])-sum(left["level"]), expected, places=10)

    def test_feedforward_meaning(self):
        c = Config(duration=3, feed_events=((0,50.0),), setpoint_events=(), strategy="pi_ff_literal")
        literal = simulate(c)["records"]
        nominal = simulate(replace(c, strategy="pi_ff_nominal"))["records"]
        self.assertEqual(literal[0]["feedforward"][0], 4.0)
        self.assertEqual(literal[1]["feedforward"][0], 0.0)
        self.assertEqual(nominal[1]["feedforward"][0], 4.0)

    def test_saturation_recovery(self):
        c = Config(duration=100, setpoint_events=((0,0,0.0),(20,0,30.0)), feed_events=())
        r = simulate(c)
        self.assertTrue(r["records"][0]["saturated"][0])
        self.assertTrue(all(0 <= q <= 100 for row in r["records"] for q in row["outflow"]))
        self.assertLess(r["records"][20]["raw_outflow"][0],100)

    def test_invalid_parameters(self):
        for c in (Config(dt=0), Config(gain=float("nan")), Config(ti=(0,1,1)),
                  Config(delays_s=(0.5,6,3)), Config(filter_samples=0)):
            with self.assertRaises(ValueError):
                simulate(c)

    def test_boundary_stop(self):
        r = simulate(Config(duration=50, initial_levels=(44.99,34,33),
                            initial_setpoints=(44.99,34,33), feed_events=((0,10000.0),)))
        self.assertEqual(r["status"],"level_boundary_crossed")
        self.assertIsNotNone(r["boundary_event"])


if __name__ == "__main__":
    unittest.main()
