import subprocess
import time
import json
import sys

def run_suite(run_id):
    print(f"Starting Run {run_id}...")
    t0 = time.perf_counter()
    p = subprocess.run([sys.executable, "-m", "pytest", "-q", "--tb=line"], capture_output=True, text=True)
    duration = time.perf_counter() - t0
    failed_tests = []
    summary_line = ""
    for line in p.stdout.splitlines():
        if line.startswith("FAILED "):
            failed_tests.append(line.split()[1].split(" - ")[0])
        elif "passed" in line and ("failed" in line or "error" in line or line.endswith("passed")):
            summary_line = line
    print(f"Finished Run {run_id} in {duration:.2f}s: {summary_line}")
    return {
        "run_id": run_id,
        "duration": duration,
        "summary": summary_line,
        "failed_count": len(failed_tests),
        "failed_tests": sorted(failed_tests)
    }

if __name__ == "__main__":
    r2 = run_suite(2)
    r3 = run_suite(3)
    
    # Compare r2 and r3
    diff_2_3 = set(r2["failed_tests"]) ^ set(r3["failed_tests"])
    print(f"Discrepancies between Run 2 and Run 3: {len(diff_2_3)}")
    if diff_2_3:
        for t in diff_2_3:
            print(f"  Flaky: {t}")
    
    with open("benchmark_runs.json", "w", encoding="utf-8") as f:
        json.dump({"r2": r2, "r3": r3, "flaky": list(diff_2_3)}, f, indent=2)
    print("Saved benchmark_runs.json successfully.")
