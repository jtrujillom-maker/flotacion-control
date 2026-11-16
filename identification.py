"""Linear calibration, integrating step-response identification and SIMC PI tuning.

Pure Python. Fit-window and effective delay must be chosen from experimental data;
this module does not pretend to infer an unambiguous dead time automatically.
"""
from math import isfinite, sqrt


def linear_fit(x, y, through_origin=False):
    """OLS y = slope*x + intercept; no confidence intervals are inferred."""
    x, y = list(x), list(y)
    if len(x) != len(y) or len(x) < 3:
        raise ValueError("need at least three paired observations")
    if not all(isfinite(v) for v in x + y):
        raise ValueError("observations must be finite")
    n = len(x)
    mx, my = sum(x)/n, sum(y)/n
    denominator = sum(v*v for v in x) if through_origin else sum((v-mx)**2 for v in x)
    if denominator <= 0:
        raise ValueError("independent variable has no usable spread")
    numerator = sum(a*b for a,b in zip(x,y)) if through_origin else sum((a-mx)*(b-my) for a,b in zip(x,y))
    slope = numerator/denominator
    intercept = 0.0 if through_origin else my - slope*mx
    residuals = [b-(slope*a+intercept) for a,b in zip(x,y)]
    sse = sum(v*v for v in residuals)
    sst = sum((v-my)**2 for v in y)
    return dict(slope=slope, intercept=intercept, rmse=sqrt(sse/n),
                r_squared=None if sst == 0 else 1-sse/sst,
                sample_count=n, residuals=residuals)


def identify_integrator(times_s, levels_cm, step_lpm, fit_start_s, fit_end_s,
                        baseline_slope_cm_s=0.0):
    """Fit the post-delay ramp; subtract any pre-existing level drift.

    k_prime = (post_step_slope - baseline_slope) / step_amplitude.
    Returned slope gain has units cm/s per L/min.
    """
    times, levels = list(times_s), list(levels_cm)
    if len(times) != len(levels) or not all(isfinite(v) for v in times+levels):
        raise ValueError("time and level observations must be paired and finite")
    if any(b <= a for a,b in zip(times,times[1:])):
        raise ValueError("times must be strictly increasing")
    if not all(isfinite(v) for v in (step_lpm,fit_start_s,fit_end_s,baseline_slope_cm_s)) or step_lpm == 0 or fit_end_s <= fit_start_s:
        raise ValueError("invalid step amplitude or fit interval")
    selected = [(t,h) for t,h in zip(times,levels) if fit_start_s <= t <= fit_end_s]
    fit = linear_fit([v[0] for v in selected], [v[1] for v in selected])
    return dict(k_prime=(fit["slope"]-baseline_slope_cm_s)/step_lpm,
                ramp_slope_cm_s=fit["slope"], fit=fit,
                fit_start_s=fit_start_s, fit_end_s=fit_end_s)


def simc_pi(k_prime, delay_s, tau_c_s=None):
    """SIMC starting point for a pure integrating process with effective delay.

    Kc=1/[k_prime*(tau_c+theta)], Ti=4*(tau_c+theta).
    Values are starting points, not the paper's trial-and-error final gains.
    """
    tc = delay_s if tau_c_s is None else tau_c_s
    if not all(isfinite(v) for v in (k_prime,delay_s,tc)) or k_prime == 0 or delay_s < 0 or tc <= 0:
        raise ValueError("invalid gain or time constants")
    if tc < delay_s:
        raise ValueError("use tau_c >= effective delay for this tuning workflow")
    return dict(kc=1/(k_prime*(tc+delay_s)), ti_s=4*(tc+delay_s),
                tau_c_s=tc, delay_s=delay_s)
