import unittest
from identification import linear_fit, identify_integrator, simc_pi


class IdentificationTests(unittest.TestCase):
    def test_calibration(self):
        fit=linear_fit([0,1,2,3],[2,5,8,11])
        self.assertAlmostEqual(fit['slope'],3)
        self.assertAlmostEqual(fit['intercept'],2)
        self.assertAlmostEqual(fit['r_squared'],1)

    def test_gain_from_post_delay_data(self):
        times=list(range(31))
        levels=[30-0.001018*10*max(0,t-7)+0.002*t for t in times]
        result=identify_integrator(times,levels,10,10,30,baseline_slope_cm_s=0.002)
        self.assertAlmostEqual(result['k_prime'],-0.001018)

    def test_published_first_cell_starting_point(self):
        result=simc_pi(-0.001018,7)
        self.assertAlmostEqual(result['kc'],-70.2,delta=0.05)
        self.assertEqual(result['ti_s'],56)

    def test_bad_identification_data(self):
        with self.assertRaises(ValueError):
            identify_integrator([0,1,1],[1,2,3],10,0,5)
        with self.assertRaises(ValueError):
            simc_pi(-0.001018,7,3)
