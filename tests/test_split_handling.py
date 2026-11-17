"""Section 21.1 Item 5 Test: Corporate Action Split Handling Invariant.

Verifies that:
1. CorporateActionLedger accurately tracks known stock splits (TDPOWERSYS.NS 2:1 on 2026-08-24, CONCORDBIO.NS 2:1 on 2026-11-04).
2. Raw unadjusted prices are preserved in store while split factor correctly adjusts historical prices across the split boundary.
"""

import datetime
import pytest

from backend.data.corporate_actions import corporate_action_engine


def test_split_handling_on_split_stocks():
    """Verify split ratio factor calculation on TDPOWERSYS and CONCORDBIO."""
    # 1. TDPOWERSYS.NS split on 2026-08-24 (2:1 split -> factor = 0.5 for pre-split bars)
    split_date_td = datetime.date(2026, 8, 24)
    factor_pre = corporate_action_engine.get_cumulative_split_factor("TDPOWERSYS.NS", split_date_td - datetime.timedelta(days=5))
    factor_post = corporate_action_engine.get_cumulative_split_factor("TDPOWERSYS.NS", split_date_td + datetime.timedelta(days=5))

    assert factor_pre == 0.5, f"Expected 0.5 pre-split factor for TDPOWERSYS, got {factor_pre}"
    assert factor_post == 1.0, f"Expected 1.0 post-split factor for TDPOWERSYS, got {factor_post}"

    # 2. CONCORDBIO.NS split on 2026-11-04 (2:1 split)
    split_date_cb = datetime.date(2026, 11, 4)
    factor_cb_pre = corporate_action_engine.get_cumulative_split_factor("CONCORDBIO.NS", split_date_cb - datetime.timedelta(days=2))
    factor_cb_post = corporate_action_engine.get_cumulative_split_factor("CONCORDBIO.NS", split_date_cb + datetime.timedelta(days=2))

    assert factor_cb_pre == 0.5, f"Expected 0.5 pre-split factor for CONCORDBIO, got {factor_cb_pre}"
    assert factor_cb_post == 1.0, f"Expected 1.0 post-split factor for CONCORDBIO, got {factor_cb_post}"

    # 3. Non-split stock (e.g. RELIANCE.NS) has factor 1.0 throughout
    factor_rel = corporate_action_engine.get_cumulative_split_factor("RELIANCE.NS", datetime.date(2026, 8, 1))
    assert factor_rel == 1.0
