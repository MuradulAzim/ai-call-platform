import urllib.request
import json
import time

AUTONOMY = "http://172.22.0.18:9100"

# Wait for strategic analysis to complete
print("Waiting 15s for strategic analysis to complete...")
time.sleep(15)

# Check strategy insights
try:
    r = urllib.request.urlopen(f"{AUTONOMY}/strategy/insights", timeout=10)
    data = json.loads(r.read().decode())
    print("STRATEGY_INSIGHTS:", json.dumps(data, indent=2, default=str))
except Exception as e:
    print("STRATEGY_INSIGHTS_ERROR:", str(e))

# Check strategy report
try:
    r = urllib.request.urlopen(f"{AUTONOMY}/strategy/report", timeout=10)
    data = json.loads(r.read().decode())
    print("\nSTRATEGY_REPORT_COUNT:", data.get("count", 0))
    for rpt in data.get("reports", []):
        report = rpt.get("report", {})
        print("HEALTH_SCORE:", report.get("health_score"))
        print("KEY_INSIGHT:", report.get("key_insight"))
        print("TRENDS:", len(report.get("trends", [])))
        print("ACTIONS:", len(report.get("action_plan", [])))
        print("TIMESTAMP:", rpt.get("ts"))
except Exception as e:
    print("STRATEGY_REPORT_ERROR:", str(e))
