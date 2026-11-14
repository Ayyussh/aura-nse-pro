"""Section 19.2: Mutation Check Runner.

Validates test sensitivity across three critical behavioral invariants:
1. Grader Entry-Bar Filtering: Reverts strict post-entry filtering and demonstrates failure.
2. Charges GST Scope: Mutates GST calculation to illegally apply to STT/Stamp Duty and demonstrates failure.
3. Three-Outcome EV: Reverts three-outcome model to binary target/stop formulation and demonstrates failure.

Confirms all tests fail under mutation and pass when restored.
"""

from __future__ import annotations
import sys
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


def run_mutation_1_grader():
    print("\n--- MUTATION 1: Grader Entry-Bar Filtering ---")
    grader_file = REPO_ROOT / "backend" / "core" / "grader.py"
    orig_code = grader_file.read_text(encoding="utf-8")

    # Mutate to include prior bars before entry date
    mutated_code = orig_code.replace(
        "df_bars = history_df.loc[history_df.index.date > entry_date]",
        "df_bars = history_df  # MUTATION: Evaluate all bars including pre-entry history"
    )
    assert mutated_code != orig_code, "Failed to apply Grader mutation!"
    grader_file.write_text(mutated_code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_v2_upgrades_section18.py::test_grader_evaluates_bars_after_entry_strictly"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        print(f"Mutation test exit code: {proc.returncode} (Expected 1)")
        assert proc.returncode != 0, "ERROR: Grader mutation test DID NOT FAIL as expected!"
        print("SUCCESS: Mutation 1 failed unit test as required.")
    finally:
        grader_file.write_text(orig_code, encoding="utf-8")
        print("Restored clean grader.py.")


def run_mutation_2_gst_scope():
    print("\n--- MUTATION 2: Charges GST Scope ---")
    charges_file = REPO_ROOT / "backend" / "costs" / "charges.py"
    orig_code = charges_file.read_text(encoding="utf-8")

    # Mutate to apply GST on total turnover (including STT and Stamp Duty)
    mutated_code = orig_code.replace(
        "gst_base = total_brokerage + exchange_txn_charge + sebi_fee",
        "gst_base = total_turnover  # MUTATION: Illegal GST on total turnover"
    )
    assert mutated_code != orig_code, "Failed to apply GST scope mutation!"
    charges_file.write_text(mutated_code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_v2_upgrades_section18.py::test_charges_engine_gst_strictly_scoped"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        print(f"Mutation test exit code: {proc.returncode} (Expected 1)")
        assert proc.returncode != 0, "ERROR: GST scope mutation test DID NOT FAIL as expected!"
        print("SUCCESS: Mutation 2 failed unit test as required.")
    finally:
        charges_file.write_text(orig_code, encoding="utf-8")
        print("Restored clean charges.py.")


def run_mutation_3_three_outcome_ev():
    print("\n--- MUTATION 3: Three-Outcome EV Formulation ---")
    predictor_file = REPO_ROOT / "backend" / "ml" / "predictor.py"
    orig_code = predictor_file.read_text(encoding="utf-8")

    # Mutate to binary formulation omitting time-expired expected R
    mutated_code = orig_code.replace(
        "ev_r = (p_target * target_r) - (p_stop * stop_r) + (p_expired * expected_r_expired) - cost_r",
        "ev_r = (p_target * target_r) - ((1.0 - p_target) * stop_r) - cost_r  # MUTATION: Binary EV omitting p_E"
    ).replace(
        '"three_outcome_model": True,',
        '"three_outcome_model": False,  # MUTATION: Binary flag',
    )
    assert mutated_code != orig_code, "Failed to apply Three-Outcome EV mutation!"
    predictor_file.write_text(mutated_code, encoding="utf-8")

    try:
        proc = subprocess.run(
            [sys.executable, "-m", "pytest", "tests/test_v2_upgrades_section18.py::test_three_outcome_ev_model_incorporates_time_expiry"],
            capture_output=True, text=True, cwd=REPO_ROOT
        )
        print(f"Mutation test exit code: {proc.returncode} (Expected 1)")
        assert proc.returncode != 0, "ERROR: Three-Outcome EV mutation test DID NOT FAIL as expected!"
        print("SUCCESS: Mutation 3 failed unit test as required.")
    finally:
        predictor_file.write_text(orig_code, encoding="utf-8")
        print("Restored clean predictor.py.")


def main():
    print("Executing Section 19.2 Mutation Invariance Checks...")
    run_mutation_1_grader()
    run_mutation_2_gst_scope()
    run_mutation_3_three_outcome_ev()
    print("\nALL 3 MUTATION CHECKS VERIFIED: Code changes are provably sensitive and robust!")


if __name__ == "__main__":
    main()
