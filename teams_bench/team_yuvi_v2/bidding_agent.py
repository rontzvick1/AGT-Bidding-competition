"""
AGT Competition - Category-Aware Adaptive Strategy v2
======================================================

Team Name: team_yuvi_v2
Strategy: v1 base + Category inference + Remaining item estimation

BASED ON v1 (46.7% win rate, 16.35 avg utility) with NEW FEATURES:
1. Infer item categories from price signals (High-for-ALL, Low-for-ALL, Mixed)
2. Track remaining items per category
3. Detect "unique value" opportunities (Mixed items where we have high value)
4. Adjust strategy based on what's likely left

ITEM DISTRIBUTION (known):
- 6 items: High-value for ALL teams (each gets U[10,20]) → COMPETITIVE
- 4 items: Low-value for ALL teams (each gets U[1,10]) → LESS COMPETITIVE
- 10 items: Mixed values (each gets U[1,20]) → UNPREDICTABLE

KEY INSIGHT: If our value is HIGH but price is LOW → we have UNIQUE value (Mixed category)
            This is a golden opportunity for high profit margin!
"""

from typing import Dict, List, Tuple


class BiddingAgent:
    """Category-aware adaptive agent with remaining item estimation."""

    def __init__(
        self,
        team_id: str,
        valuation_vector: Dict[str, float],
        budget: float,
        opponent_teams: List[str],
    ):
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = budget
        self.initial_budget = budget
        self.opponent_teams = opponent_teams
        self.utility = 0
        self.items_won = []

        self.rounds_completed = 0
        self.total_rounds = 15

        # ===== OPPONENT TRACKING =====
        self.opponent_data = {
            opp: {
                "estimated_budget": 60.0,
                "items_won": 0,
                "total_spent": 0.0,
                "win_prices": [],
                "p_aggressive": 0.33,
                "p_truthful": 0.34,
                "p_passive": 0.33,
            }
            for opp in opponent_teams
        }

        # ===== MARKET & HISTORY TRACKING =====
        self.price_history = []
        self.my_bids = {}
        self.auction_results = (
            []
        )  # (item_id, winner, price, my_bid, my_val, inferred_category)
        self.items_seen = set()

        # ===== CATEGORY INFERENCE (NEW!) =====
        # Expected counts: 6 High-for-ALL, 4 Low-for-ALL, 10 Mixed
        self.category_counts = {
            "high_for_all": 0,  # Items where price > 10 AND our_val > 10
            "low_for_all": 0,  # Items where price < 7 AND our_val < 8
            "mixed_competitive": 0,  # Mixed items that sold high
            "mixed_cheap": 0,  # Mixed items that sold low (opportunity!)
        }

        # Track per-item inferred categories
        self.item_categories = {}  # item_id -> inferred category

        # Track "golden opportunities" - items where we had unique high value
        self.unique_value_wins = 0

        # ===== VALUE ANALYSIS =====
        values = sorted(valuation_vector.values(), reverse=True)
        self.sorted_values = values
        self.avg_value = sum(values) / len(values)
        self.median_value = values[len(values) // 2]
        self.total_value = sum(values)
        self.top_tier_threshold = (
            values[int(len(values) * 0.3)] if len(values) > 3 else values[0]
        )

    def _update_available_budget(
        self, item_id: str, winning_team: str, price_paid: float
    ):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)

    def _infer_category(self, my_val: float, price_paid: float, i_won: bool) -> str:
        """
        Infer the likely category of an item based on signals.

        Logic:
        - High price (>10) + High our_val (>10) → likely "High-for-ALL"
        - Low price (<7) + Low our_val (<8) → likely "Low-for-ALL"
        - High our_val + Low price → "Mixed" where we got lucky (OPPORTUNITY!)
        - Low our_val + High price → "Mixed" where others got lucky
        """
        if my_val > 10 and price_paid > 10:
            return "high_for_all"
        elif my_val < 8 and price_paid < 7:
            return "low_for_all"
        elif my_val > 12 and price_paid < 8:
            # We had high value but it sold cheap - UNIQUE VALUE opportunity
            return "mixed_unique_to_us"
        elif my_val < 8 and price_paid > 10:
            # We had low value but it sold high - others wanted it
            return "mixed_unique_to_others"
        else:
            return "mixed_neutral"

    def _bayesian_update(self, winning_team: str, price_paid: float, my_bid: float):
        """Update beliefs about opponent types."""
        avg_price = (
            sum(self.price_history) / len(self.price_history)
            if self.price_history
            else 10
        )

        if not winning_team or winning_team == self.team_id:
            for opp_id, data in self.opponent_data.items():
                data["p_passive"] = min(0.7, data["p_passive"] + 0.02)
                self._normalize_beliefs(data)
            return

        if winning_team not in self.opponent_data:
            return

        opp = self.opponent_data[winning_team]

        if price_paid > avg_price * 1.2:
            opp["p_aggressive"] = min(0.85, opp["p_aggressive"] * 1.3)
            opp["p_passive"] *= 0.8
        elif price_paid < avg_price * 0.7:
            opp["p_passive"] = min(0.7, opp["p_passive"] * 1.2)
        else:
            opp["p_truthful"] = min(0.7, opp["p_truthful"] * 1.15)

        if my_bid > 0 and price_paid > my_bid:
            opp["p_aggressive"] = min(0.85, opp["p_aggressive"] * 1.2)

        self._normalize_beliefs(opp)

    def _normalize_beliefs(self, opp_data: dict):
        total = (
            opp_data["p_aggressive"] + opp_data["p_truthful"] + opp_data["p_passive"]
        )
        if total > 0:
            opp_data["p_aggressive"] /= total
            opp_data["p_truthful"] /= total
            opp_data["p_passive"] /= total

    def update_after_each_round(
        self, item_id: str, winning_team: str, price_paid: float
    ):
        self._update_available_budget(item_id, winning_team, price_paid)
        self.rounds_completed += 1

        my_val = self.valuation_vector.get(item_id, 0)
        my_bid = self.my_bids.get(item_id, 0)
        i_won = winning_team == self.team_id

        # ===== INFER CATEGORY (NEW!) =====
        inferred_cat = self._infer_category(my_val, price_paid, i_won)
        self.item_categories[item_id] = inferred_cat

        # Update category counts
        if inferred_cat == "high_for_all":
            self.category_counts["high_for_all"] += 1
        elif inferred_cat == "low_for_all":
            self.category_counts["low_for_all"] += 1
        elif inferred_cat == "mixed_unique_to_us":
            self.category_counts["mixed_cheap"] += 1
            if i_won:
                self.unique_value_wins += 1
        else:
            self.category_counts["mixed_competitive"] += 1

        # Record history
        self.price_history.append(price_paid)
        self.auction_results.append(
            (item_id, winning_team, price_paid, my_bid, my_val, inferred_cat)
        )
        self.items_seen.add(item_id)

        # Update opponent data
        if winning_team and winning_team != self.team_id:
            if winning_team in self.opponent_data:
                opp = self.opponent_data[winning_team]
                opp["estimated_budget"] -= price_paid
                opp["items_won"] += 1
                opp["total_spent"] += price_paid
                opp["win_prices"].append(price_paid)

        self._bayesian_update(winning_team, price_paid, my_bid)
        return True

    # ========== HELPER METHODS ==========

    def _get_active_opponents(self) -> int:
        return sum(1 for d in self.opponent_data.values() if d["estimated_budget"] > 5)

    def _get_max_opponent_budget(self) -> float:
        if not self.opponent_data:
            return 60.0
        return max(d["estimated_budget"] for d in self.opponent_data.values())

    def _get_avg_opponent_aggression(self) -> float:
        active = [d for d in self.opponent_data.values() if d["estimated_budget"] > 5]
        if not active:
            return 0.3
        return sum(d["p_aggressive"] for d in active) / len(active)

    def _get_remaining_values(self) -> List[float]:
        return [
            v
            for item_id, v in self.valuation_vector.items()
            if item_id not in self.items_seen
        ]

    def _estimate_remaining_categories(self) -> Dict[str, float]:
        """
        Estimate how many items of each category are likely remaining.
        Based on: 6 High-for-ALL, 4 Low-for-ALL, 10 Mixed (of which 15 total auctioned)

        Returns expected counts with fractional estimates.
        """
        # How many of each we've likely seen
        seen_high = self.category_counts["high_for_all"]
        seen_low = self.category_counts["low_for_all"]
        seen_mixed = (
            self.category_counts["mixed_cheap"]
            + self.category_counts["mixed_competitive"]
        )

        # Expected remaining (can't go below 0)
        # Note: 5 items won't be auctioned at all
        remaining_high = max(0, 6 - seen_high)
        remaining_low = max(0, 4 - seen_low)
        remaining_mixed = max(0, 10 - seen_mixed)

        # Total items remaining in auction
        total_remaining = self.total_rounds - self.rounds_completed

        # Probability distribution of what we'll see
        total_unseen = remaining_high + remaining_low + remaining_mixed
        if total_unseen > 0:
            prob_high = remaining_high / total_unseen
            prob_low = remaining_low / total_unseen
            prob_mixed = remaining_mixed / total_unseen
        else:
            prob_high = prob_low = prob_mixed = 0.33

        return {
            "high_for_all": remaining_high,
            "low_for_all": remaining_low,
            "mixed": remaining_mixed,
            "expected_remaining": total_remaining,
            "prob_next_high": prob_high,
            "prob_next_low": prob_low,
            "prob_next_mixed": prob_mixed,
        }

    def _estimate_remaining_value_stats(self) -> Dict[str, float]:
        """
        Estimate statistics about remaining item values.
        Uses category estimates to predict what's coming.
        """
        remaining_cats = self._estimate_remaining_categories()
        remaining_own_values = self._get_remaining_values()

        if not remaining_own_values:
            return {"avg": 10, "max": 15, "expected_competitive": 5}

        # Our remaining average
        our_remaining_avg = sum(remaining_own_values) / len(remaining_own_values)
        our_remaining_max = max(remaining_own_values)

        # Estimate competition level
        # High-for-all items are guaranteed competitive (everyone values 10-20)
        expected_competitive = remaining_cats["high_for_all"]

        # Mixed items have ~50% chance of being competitive (when others also high)
        expected_competitive += remaining_cats["mixed"] * 0.3

        return {
            "our_avg": our_remaining_avg,
            "our_max": our_remaining_max,
            "expected_competitive_items": expected_competitive,
            "expected_low_competition_items": remaining_cats["low_for_all"]
            + remaining_cats["mixed"] * 0.5,
        }

    def _predict_item_category(self, my_valuation: float) -> str:
        """
        Predict the likely category of the current item based on our valuation.

        Returns: 'likely_high_for_all', 'likely_low_for_all', 'likely_mixed', 'unknown'
        """
        remaining = self._estimate_remaining_categories()

        if my_valuation >= 15:
            # Very high value - could be High-for-ALL or lucky Mixed
            if remaining["high_for_all"] >= 2:
                return "likely_high_for_all"  # Still many competitive items left
            else:
                return "likely_mixed"  # Most competitive items passed

        elif my_valuation <= 5:
            # Very low value - could be Low-for-ALL or unlucky Mixed
            if remaining["low_for_all"] >= 2:
                return "likely_low_for_all"
            else:
                return "likely_mixed"

        else:
            # Mid-range value - hard to tell
            return "likely_mixed"

    def _is_likely_unique_opportunity(self, my_valuation: float) -> bool:
        """
        Detect if this item might be a "unique value" opportunity for us.
        If we have high value and market pattern suggests Mixed category.
        """
        remaining = self._estimate_remaining_categories()

        if my_valuation >= 14:
            # High value for us
            # If most High-for-ALL items have passed, this might be Mixed where we're lucky
            if self.category_counts["high_for_all"] >= 4:
                return True
            # If we've seen price patterns where our high values didn't correlate with high prices
            if self.unique_value_wins >= 1:
                return True  # We've gotten lucky before, might happen again

        return False

    def _get_competition_score(self, my_valuation: float) -> float:
        """
        Calculate expected competition score (0-1) for this item.
        Higher = more competition expected.
        """
        prediction = self._predict_item_category(my_valuation)
        remaining = self._estimate_remaining_categories()

        if prediction == "likely_high_for_all":
            return 0.9  # Very competitive
        elif prediction == "likely_low_for_all":
            return 0.3  # Low competition
        else:
            # Mixed - estimate based on our value
            if my_valuation >= 15:
                return 0.6  # We want it, others might too
            elif my_valuation <= 8:
                return 0.4  # We don't want it much
            else:
                return 0.5

    # ========== CORE BIDDING LOGIC ==========

    def bidding_function(self, item_id: str) -> float:
        my_valuation = self.valuation_vector.get(item_id, 0)
        rounds_left = self.total_rounds - self.rounds_completed

        if my_valuation <= 0 or self.budget <= 0.01 or rounds_left <= 0:
            return 0.0

        bid = self._calculate_bid(my_valuation, rounds_left)
        self.my_bids[item_id] = bid
        return float(bid)

    def _calculate_bid(self, my_valuation: float, rounds_left: int) -> float:
        """
        CATEGORY-AWARE BIDDING WITH BUDGET PACING

        KEY FIX: Don't spend more than 4-6 budget/round average!
        Budget = 60, Rounds = 15, Target avg = 4/round
        """

        active_opps = self._get_active_opponents()
        max_opp_budget = self._get_max_opponent_budget()
        avg_aggression = self._get_avg_opponent_aggression()
        remaining_values = self._get_remaining_values()
        remaining_cats = self._estimate_remaining_categories()
        remaining_stats = self._estimate_remaining_value_stats()
        is_unique_opportunity = self._is_likely_unique_opportunity(my_valuation)
        predicted_category = self._predict_item_category(my_valuation)

        # ===== BUDGET PACING (CRITICAL FIX!) =====
        # Target: spend ~4/round on average (60/15 = 4)
        # Allow bursts but cap maximum per-round spend based on phase

        budget_per_round_target = self.budget / rounds_left
        spent_so_far = self.initial_budget - self.budget
        rounds_done = self.total_rounds - rounds_left

        # How much SHOULD we have spent by now?
        expected_spent = (rounds_done / self.total_rounds) * self.initial_budget
        budget_surplus = expected_spent - spent_so_far  # positive = underspent

        # Max we're ALLOWED to spend this round based on pacing
        if rounds_left > 8:  # Early game: conservative
            max_round_spend = 6.0 + max(0, budget_surplus * 0.3)
        elif rounds_left > 4:  # Mid game: moderate
            max_round_spend = 8.0 + max(0, budget_surplus * 0.5)
        else:  # Late game: aggressive
            max_round_spend = budget_per_round_target * 1.5

        # ===== PHASE 1: BASE SHADE =====
        if my_valuation >= self.top_tier_threshold:
            shade = 0.88
        elif my_valuation >= self.avg_value:
            shade = 0.84
        elif my_valuation >= self.avg_value * 0.5:
            shade = 0.78
        else:
            shade = 0.70

        bid = my_valuation * shade

        # ===== PHASE 2: CATEGORY-BASED ADJUSTMENT =====

        if is_unique_opportunity:
            # GOLDEN OPPORTUNITY: High value for us, likely Mixed category
            # Others probably don't want it - bid confidently but paced
            bid = my_valuation * 0.85

        elif predicted_category == "likely_high_for_all":
            # Likely High-for-ALL item - TRAP! Everyone wants it
            # Be MORE conservative - these are expensive to win
            bid = min(my_valuation * 0.80, bid)

            # If we've already won items, definitely let competitive ones go
            if len(self.items_won) >= 2:
                bid *= 0.85

        elif predicted_category == "likely_low_for_all":
            # Low competition expected - good value opportunity
            bid = min(my_valuation * 0.75, bid)

        # ===== PHASE 3: REMAINING ITEMS STRATEGY =====

        # If few good items remain, be more aggressive
        if remaining_cats["high_for_all"] <= 1 and my_valuation > 12:
            bid = max(bid, my_valuation * 0.85)

        # If many competitive items remain, be patient
        if remaining_stats["expected_competitive_items"] > 4:
            bid = min(bid, my_valuation * 0.80)

        # ===== PHASE 4: OPPONENT AWARENESS =====

        if avg_aggression > 0.5:
            bid *= 1.03
        elif avg_aggression < 0.25:
            bid *= 0.95

        if active_opps <= 1:
            bid *= 0.90

        # Exploit weak opponents
        if max_opp_budget < 15:
            bid = min(bid, max_opp_budget + 3)

        if max_opp_budget < 8:
            bid = min(bid, max_opp_budget + 1)

        # ===== PHASE 5: BUDGET PACING ENFORCEMENT =====
        # Cap bid to maintain budget for later rounds

        if rounds_left > 4:
            # Not late game yet - enforce spending cap
            bid = min(bid, max_round_spend)

        # ===== PHASE 6: LATE GAME SPENDING =====

        if rounds_left <= 4:
            # Late game - need to spend remaining budget
            min_spend = self.budget / rounds_left * 0.7
            if my_valuation > min_spend:
                bid = max(bid, min(min_spend, my_valuation))

        if rounds_left <= 2:
            # Very late - be aggressive
            if my_valuation > 0:
                bid = max(bid, min(self.budget * 0.45, my_valuation))

        if rounds_left == 1:
            # Last round - spend it all if item is worth it
            bid = min(my_valuation, self.budget)

        # ===== PHASE 7: OPPORTUNITY BOOST =====

        # If this item is significantly better than remaining expected items
        if remaining_values:
            expected_future_avg = sum(remaining_values) / len(remaining_values)
            if my_valuation > expected_future_avg * 1.3:
                bid = min(bid * 1.1, my_valuation * 0.98)

        # ===== FINAL CONSTRAINTS =====
        bid = max(0.0, min(bid, self.budget, my_valuation))

        return bid
