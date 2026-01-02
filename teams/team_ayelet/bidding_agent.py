"""
AGT Competition - Student Agent Template
========================================

Team Name: PacingShadow_NoImports
Members:
  - [Student 1 Name and ID]
  - [Student 2 Name and ID]
  - [Student 3 Name and ID]

Strategy Description:
Budget-paced bidding for repeated second-price auctions. We bid based on our valuation,
start aggressive early and gradually reduce aggressiveness. We adapt to observed market
prices (paid second-price) and use a pacing controller to avoid ending with leftover budget.
In the final rounds we enforce a spend-floor to burn remaining budget.

Key Features:
- Shadow-price pacing controller (keeps spending on track)
- Aggressiveness schedule: high early, lower late
- Price learning from observed second prices + endgame burn floor
"""

from typing import Dict, List


class BiddingAgent:
    def __init__(self, team_id: str, valuation_vector: Dict[str, float],
                 budget: float, opponent_teams: List[str]):

        # Required attributes (DO NOT REMOVE)
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = budget
        self.initial_budget = budget
        self.opponent_teams = opponent_teams
        self.utility = 0
        self.items_won = []

        # Game state tracking
        self.rounds_completed = 0
        self.total_rounds = 15

        # -------------------------
        # Custom state (NO imports)
        # -------------------------
        self.price_history = []  # observed second prices (length <= 15)
        self.opponent_win_count = {opp: 0 for opp in opponent_teams}

        # Aggression schedule
        self.alpha_max = 1.85
        self.alpha_min = 1.05

        # Pacing controller
        self.lambda_shadow = 0.0
        self.k_lambda = 1.10

        # Endgame burn
        self.endgame_rounds = 3
        self.burn_gamma = 1.45

        # Track spent
        self.spent_so_far = 0.0

        # Optional safety margin (set to 0.0 if you truly want to spend regardless)
        self.value_safety = 0.0

    def _update_available_budget(self, item_id: str, winning_team: str,
                                 price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)

    def _alpha_base(self) -> float:
        """Linear decay from alpha_max to alpha_min over the game."""
        if self.total_rounds <= 1:
            return self.alpha_min
        frac = self.rounds_completed / (self.total_rounds - 1)
        return self.alpha_max - (self.alpha_max - self.alpha_min) * frac

    def _avg_and_median_price(self):
        """Return (avg, median) of observed prices; if none, return (0,0)."""
        if not self.price_history:
            return 0.0, 0.0
        s = 0.0
        for p in self.price_history:
            s += p
        avg = s / len(self.price_history)

        xs = sorted(self.price_history)
        n = len(xs)
        mid = n // 2
        if n % 2 == 1:
            med = xs[mid]
        else:
            med = 0.5 * (xs[mid - 1] + xs[mid])
        return avg, med

    def update_after_each_round(self, item_id: str, winning_team: str,
                                price_paid: float):

        # System updates (DO NOT REMOVE)
        self._update_available_budget(item_id, winning_team, price_paid)

        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
            self.spent_so_far += float(price_paid)

        self.rounds_completed += 1

        # Track prices
        p = float(price_paid)
        if p > 0:
            self.price_history.append(p)

        # Track opponent wins
        if winning_team and winning_team != self.team_id:
            if winning_team in self.opponent_win_count:
                self.opponent_win_count[winning_team] += 1

        # Pacing update: compare actual spend to planned spend by now
        planned = self.initial_budget * (self.rounds_completed / self.total_rounds)
        error = planned - self.spent_so_far  # positive => underspent

        # If underspent => reduce lambda (more aggressive). If overspent => increase lambda.
        self.lambda_shadow -= self.k_lambda * (error / max(1e-9, self.initial_budget))
        if self.lambda_shadow < 0.0:
            self.lambda_shadow = 0.0

        return True

    def bidding_function(self, item_id: str) -> float:
        my_valuation = float(self.valuation_vector.get(item_id, 0.0))

        if my_valuation <= 0.0 or self.budget <= 0.0:
            return 0.0

        rounds_remaining = self.total_rounds - self.rounds_completed
        if rounds_remaining <= 0:
            return 0.0

        # 1) Base bid: value scaled by aggression and pacing pressure
        alpha = self._alpha_base()
        base_bid = alpha * my_valuation / (1.0 + self.lambda_shadow)

        # Never bid above remaining budget
        if base_bid > self.budget:
            base_bid = self.budget
        if base_bid < 0.0:
            base_bid = 0.0

        bid = base_bid

        # 2) Adapt to observed prices: if market is expensive, shade a bit;
        #    if we are much higher than typical price and value is strong, keep aggressive.
        avg_p, med_p = self._avg_and_median_price()

        # If we have some price signal, nudge bid toward "just above typical price"
        if med_p > 0:
            # Target around the median price when value supports it
            # (softly blends base bid with a market-based target)
            market_target = med_p * 1.10  # try to clear median-ish markets
            if market_target < 0.0:
                market_target = 0.0

            # Blend depending on value relative to market
            # High value -> trust base bid more; low value -> trust market target more
            if my_valuation >= 1.3 * med_p:
                w = 0.75
            elif my_valuation >= 1.0 * med_p:
                w = 0.60
            else:
                w = 0.40

            bid = w * base_bid + (1.0 - w) * market_target

        # Optional safety: don’t bid to win if expected market price > value - safety
        # (comment this out if you truly only want to spend everything regardless of value)
        if med_p > 0 and (med_p > my_valuation - self.value_safety):
            # still allow in endgame (burn), but earlier avoid negative expected utility
            if rounds_remaining > self.endgame_rounds:
                bid = min(bid, max(0.0, my_valuation - self.value_safety))

        # 3) Endgame burn: force spending remaining budget
        if rounds_remaining <= self.endgame_rounds:
            floor_bid = self.burn_gamma * (self.budget / rounds_remaining)
            if bid < floor_bid:
                bid = floor_bid

        # Clamp to [0, budget]
        if bid < 0.0:
            bid = 0.0
        if bid > self.budget:
            bid = self.budget

        bid = min(bid, max(0.0, my_valuation - 0.25))
        return float(bid)


    
    # ================================================================
    # OPTIONAL: Helper methods for your strategy
    # ================================================================
    
    # TODO: Add any helper methods you need
    # Examples:
    
    # def _classify_item_value(self, valuation: float) -> str:
    #     """Classify item as high, medium, or low value"""
    #     if valuation > self.high_value_threshold:
    #         return "high"
    #     elif valuation > self.low_value_threshold:
    #         return "medium"
    #     else:
    #         return "low"
    
    # def _estimate_competition(self, item_id: str) -> float:
    #     """Estimate how competitive this auction will be"""
    #     # Based on price history, opponent wins, etc.
    #     pass
    
    # def _calculate_budget_constraint(self) -> float:
    #     """Calculate maximum bid based on budget constraints"""
    #     rounds_remaining = self.total_rounds - self.rounds_completed
    #     return self.budget / max(1, rounds_remaining) * 2.0
    
    # def _should_bid_aggressively(self, valuation: float) -> bool:
    #     """Decide if we should bid aggressively for this item"""
    #     # Based on game state, valuation, budget, etc.
    #     pass


# ====================================================================
# NOTES AND TIPS
# ====================================================================

# 1. Second-Price Auction Theory:
#    - In standard Vickrey auctions, truthful bidding is optimal
#    - With budget constraints, this changes! You need strategy
#    - Winner pays second-highest bid, not their own bid

# 2. Budget Management:
#    - You have 60 units for 15 rounds
#    - Budget does NOT carry between games
#    - Spending all budget early is risky
#    - Saving too much budget is wasteful

# 3. Information Use:
#    - Learn from observed prices
#    - Track which opponents are winning
#    - Identify competitive vs non-competitive items
#    - Update your strategy as game progresses

# 4. Common Strategies:
#    - Truthful: Bid your valuation (baseline)
#    - Shading: Bid less than valuation to save budget
#    - Pacing: Limit spending per round
#    - Adaptive: Learn from observations and adjust

# 5. Testing:
#    - Use the simulator extensively: python simulator.py --your-agent ...
#    - Test with different seeds for consistency
#    - Aim for >20% win rate against examples
#    - Aim for >10 average utility

# 6. Performance:
#    - Keep computations fast (< 1 second per bid)
#    - Pre-compute what you can in __init__
#    - Avoid complex loops in bidding_function
#    - Test execution time regularly

# 7. Debugging:
#    - Add print statements (captured in logs)
#    - Use simulator with --verbose flag
#    - Check that bids are reasonable (0 to budget)
#    - Verify budget doesn't go negative (system prevents this)

# Good luck! 🏆
