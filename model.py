"""Three-cell flotation control model. Standard library only; units: cm, L/min, s."""
from dataclasses import dataclass, asdict
from collections import deque
from statistics import median
import math


@dataclass
class Config:
    duration: int = 600
    dt: float = 1.0
    plant: str = "published"
    strategy: str = "pi_ff_nominal"
    gain: float = 0.001018
    area_cm2: float = 900.0
    delays_s: tuple = (7.0, 6.0, 3.0)
    inlet_delays_s: tuple = (0.0, 0.0, 0.0)
    kc: tuple = (-62.0, -76.0, -85.0)
    ti: tuple = (56.0, 30.0, 44.0)
    kff: tuple = (0.8, 0.8, 1.0)
    initial_levels: tuple = (30.0, 34.0, 33.0)
    initial_setpoints: tuple = (30.0, 34.0, 33.0)
    feed_nominal: float = 45.0
    # Explicit simplifying assumption: no liquid overflow in the default model.
    overflow_nominal: tuple = (0.0, 0.0, 0.0)
    q_min: float = 0.0
    q_max: float = 100.0  # Assumed simulation bound, not a pump calibration.
    filter_samples: int = 10
    noise_std_cm: float = 0.0
    seed: int = 42
    level_bounds: tuple = (0.0, 45.0)
    setpoint_events: tuple = ((180.0, 0, 29.0), (180.0, 1, 33.0), (180.0, 2, 32.0))
    feed_events: tuple = ((300.0, 50.0), (450.0, 45.0))

    def validate(self):
        if self.plant not in ("published", "geometric"):
            raise ValueError("plant must be published or geometric")
        if self.strategy not in ("pi", "pi_ff_literal", "pi_ff_nominal"):
            raise ValueError("unknown strategy")
        scalars = [self.duration, self.dt, self.gain, self.area_cm2, self.feed_nominal,
                   self.q_min, self.q_max, self.noise_std_cm]
        if not all(math.isfinite(x) for x in scalars):
            raise ValueError("all parameters must be finite")
        if not 0 < self.dt <= 1 or not self.dt <= self.duration <= 7200:
            raise ValueError("require 0 < dt <= 1 and dt <= duration <= 7200")
        if self.duration / self.dt > 100000:
            raise ValueError("maximum 100000 integration steps")
        if abs(self.duration / self.dt - round(self.duration / self.dt)) > 1e-8:
            raise ValueError("duration must be an integer multiple of dt")
        if self.gain <= 0 or self.area_cm2 <= 0 or self.q_min < 0 or self.q_max <= self.q_min:
            raise ValueError("invalid gain, area or actuator bounds")
        if not isinstance(self.filter_samples, int) or not 1 <= self.filter_samples <= 1000:
            raise ValueError("filter_samples must be an integer in [1,1000]")
        if self.noise_std_cm < 0:
            raise ValueError("noise standard deviation cannot be negative")
        for name in ("delays_s", "inlet_delays_s", "kc", "ti", "kff", "initial_levels",
                     "initial_setpoints", "overflow_nominal"):
            values = getattr(self, name)
            if len(values) != 3 or not all(math.isfinite(x) for x in values):
                raise ValueError(name + " must contain three finite numbers")
        if any(x <= 0 for x in self.ti) or any(x >= 0 for x in self.kc):
            raise ValueError("ti must be positive and kc negative")
        for delay in (*self.delays_s, *self.inlet_delays_s):
            if delay < 0 or abs(delay / self.dt - round(delay / self.dt)) > 1e-8:
                raise ValueError("delays must be nonnegative multiples of dt")
        if any(x < 0 for x in self.overflow_nominal):
            raise ValueError("overflow cannot be negative")
        if len(self.level_bounds) != 2 or not all(math.isfinite(x) for x in self.level_bounds) or self.level_bounds[0] >= self.level_bounds[1]:
            raise ValueError("invalid level bounds")
        for t, cell, value in self.setpoint_events:
            if not math.isfinite(t) or not math.isfinite(value) or t < 0 or type(cell) is not int or cell not in (0, 1, 2):
                raise ValueError("invalid setpoint event")
        for t, value in self.feed_events:
            if not math.isfinite(t) or not math.isfinite(value) or t < 0 or value < 0:
                raise ValueError("invalid feed event")


def delay_value(history, index, steps, initial):
    j = index - steps
    return initial if j < 0 else history[j]


def simulate(config=None):
    """Fixed-step causal simulation. Stops on a physical level boundary crossing.

    published: empirical integrating gain for inlet AND outlet (inlet gain assumed).
    geometric: liquid-volume balance with constant prescribed liquid overflow.
    Delays are effective path delays, not explicit transport-volume inventories.
    Controller sees commanded upstream pump flow, not an independent flow sensor.
    """
    import random
    c = config or Config()
    c.validate()
    rng = random.Random(c.seed)
    b = c.gain if c.plant == "published" else 1000.0 / (60.0 * c.area_cm2)
    qstar = []
    q = c.feed_nominal
    for overflow in c.overflow_nominal:
        q -= overflow
        qstar.append(q)
    if any(not c.q_min <= q <= c.q_max for q in qstar):
        raise ValueError("nominal outflow is outside actuator bounds")
    if any(not c.level_bounds[0] <= h <= c.level_bounds[1] for h in c.initial_levels):
        raise ValueError("initial levels outside physical bounds")
    inletstar = [c.feed_nominal, qstar[0], qstar[1]]
    h = list(c.initial_levels)
    integral = [0.0] * 3
    last_inlet = inletstar.copy()
    windows = [deque([x] * c.filter_samples, maxlen=c.filter_samples) for x in h]
    qhist = [[], [], []]
    inhist = [[], [], []]
    records = []
    metrics = [dict(iae=0.0, iae_filtered=0.0, ise=0.0, itae=0.0,
                    total_variation=0.0, saturation_s=0.0, max_abs_error=0.0) for _ in range(3)]
    status = "completed"
    crossing = None
    sp_events = sorted(c.setpoint_events)
    feed_events = sorted(c.feed_events)
    steps = int(round(c.duration / c.dt))
    for k in range(steps + 1):
        t = k * c.dt
        sp = list(c.initial_setpoints)
        feed = c.feed_nominal
        for when, cell, value in sp_events:
            if when <= t + 1e-9:
                sp[cell] = value
        for when, value in feed_events:
            if when <= t + 1e-9:
                feed = value
        hf = []
        measured = []
        for i in range(3):
            measured.append(h[i] + rng.gauss(0.0, c.noise_std_cm))
            windows[i].append(measured[i])
            hf.append(median(windows[i]))
        commands, raw_commands, inlets, ffs, saturated = [], [], [], [], []
        for i in range(3):
            inlet = feed if i == 0 else commands[i - 1]
            e = sp[i] - hf[i]
            ff = 0.0
            if c.strategy == "pi_ff_literal":
                ff = c.kff[i] * (inlet - last_inlet[i])
            elif c.strategy == "pi_ff_nominal":
                ff = c.kff[i] * (inlet - inletstar[i])
            raw = qstar[i] + c.kc[i] * e + integral[i] + ff
            applied = max(c.q_min, min(c.q_max, raw))
            saturated.append(raw != applied)
            commands.append(applied)
            raw_commands.append(raw)
            inlets.append(inlet)
            ffs.append(ff)
            if k < steps:
                di = c.kc[i] * c.dt * e / c.ti[i]
                if not ((raw >= c.q_max and di > 0) or (raw <= c.q_min and di < 0)):
                    integral[i] += di
            last_inlet[i] = inlet
            qhist[i].append(applied)
            inhist[i].append(inlet)
        records.append(dict(time=t, level=h.copy(), measured=measured, filtered=hf,
                            setpoint=sp, feed=feed, inlet=inlets, outflow=commands,
                            raw_outflow=raw_commands, feedforward=ffs, saturated=saturated))
        if k == steps:
            break
        new_h = []
        for i in range(3):
            m = metrics[i]
            err = sp[i] - h[i]
            m["iae"] += abs(err) * c.dt
            m["iae_filtered"] += abs(sp[i] - hf[i]) * c.dt
            m["ise"] += err * err * c.dt
            m["itae"] += t * abs(err) * c.dt
            m["max_abs_error"] = max(m["max_abs_error"], abs(err))
            m["saturation_s"] += c.dt if saturated[i] else 0.0
            prior = qstar[i] if k == 0 else qhist[i][k - 1]
            m["total_variation"] += abs(commands[i] - prior)
            qi = delay_value(inhist[i], k, round(c.inlet_delays_s[i] / c.dt), inletstar[i])
            qo = delay_value(qhist[i], k, round(c.delays_s[i] / c.dt), qstar[i])
            dh = b * ((qi - inletstar[i]) - (qo - qstar[i]))
            new_h.append(h[i] + c.dt * dh)
        if any(x < c.level_bounds[0] or x > c.level_bounds[1] for x in new_h):
            status = "level_boundary_crossed"
            crossing = dict(time=t + c.dt, attempted_levels=new_h)
            break
        h = new_h
    return dict(config=asdict(c), status=status, boundary_event=crossing,
                effective_gain=b, nominal_outflows=qstar, metrics=metrics,
                records=records,
                assumptions=["Default schedules are illustrative, not digitized paper data.",
                             "Inlet sensitivity is assumed equal to outlet sensitivity.",
                             "Upstream commanded flows are proxies for disturbance measurements.",
                             "Constant liquid overflow; no gas or froth dynamics.",
                             "Actuator limits are assumptions pending calibration."])


def compare(config=None):
    from dataclasses import replace
    c = config or Config()
    return {s: simulate(replace(c, strategy=s)) for s in
            ("pi", "pi_ff_literal", "pi_ff_nominal")}
