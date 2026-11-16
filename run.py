"""Run: python run.py --output results [--plant published|geometric]."""
import argparse
import csv
import json
from pathlib import Path
from model import Config, compare


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--output", default="results")
    p.add_argument("--plant", choices=["published", "geometric"], default="published")
    args = p.parse_args()
    dest = Path(args.output)
    dest.mkdir(parents=True, exist_ok=True)
    results = compare(Config(plant=args.plant))
    summary = {}
    for name, result in results.items():
        (dest / (name + ".json")).write_text(json.dumps(result, indent=2, allow_nan=False), encoding="utf-8")
        summary[name] = {k: result[k] for k in ("status", "metrics", "effective_gain", "assumptions")}
        with (dest / (name + ".csv")).open("w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["time_s", "feed_lpm"] + [f"{v}_{i+1}" for v in
                            ("level_cm", "filtered_cm", "setpoint_cm", "outflow_lpm", "ff_lpm") for i in range(3)])
            for row in result["records"]:
                writer.writerow([row["time"], row["feed"]] + [x for v in
                                ("level", "filtered", "setpoint", "outflow", "feedforward") for x in row[v]])
        print(name, result["status"], "IAE:", [round(m["iae"], 3) for m in result["metrics"]])
    (dest / "summary.json").write_text(json.dumps(summary, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
