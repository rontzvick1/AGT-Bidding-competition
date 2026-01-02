"""
AGT Competition - Student Agent Template
========================================

Team Name: SimplePacer
Members:
  - [Student 1 Name and ID]
  - [Student 2 Name and ID]
  - [Student 3 Name and ID]

Strategy Description:
Simple budget pacing with an aggression multiplier. Start aggressive early and
linearly decay aggression. Add feedback: if we are underspending relative to a
smooth spending plan, increase aggressiveness; if overspending, decrease it.
Optionally cap bids at valuation to guarantee non-negative utility per round.

Key Features:
- Aggression schedule: high early, lower late (linear decay)
- Feedback pacing controller to avoid leftover budget
- Optional "no negative utility" guarantee via bid <= valuation cap
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
        # Strategy 1 state
        # -------------------------
        self.alpha_max = 1.80   # aggressive at start
        self.alpha_min = 1.05   # calmer near end

        self.alpha_feedback = 0.0   # adaptive adjustment term
        self.k_feedback = 0.90      # feedback strength (0.5-1.5 reasonable)
        self.feedback_clip = 0.60   # prevents extreme oscillations

        self.spent_so_far = 0.0

        # Endgame "burn" to reduce leftover budget (does NOT exceed value if cap enabled)
        self.endgame_rounds = 3
        self.burn_gamma = 1.35

        # Toggle: set True to guarantee no negative utility per round
        self.cap_at_value = True

        # Optional safety margin if cap_at_value=True (e.g., 0.0 or 0.2)
        self.value_margin = 0.0

    def _update_available_budget(self, item_id: str, winning_team: str,
                                 price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)

    def update_after_each_round(self, item_id: str, winning_team: str,
                                price_paid: float):
        # System updates (DO NOT REMOVE)
        self._update_available_budget(item_id, winning_team, price_paid)

        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
            self.spent_so_far += float(price_paid)

        self.rounds_completed += 1

        # -------------------------
        # Feedback pacing update
        # -------------------------
        # Planned smooth spend up to now:
        planned = self.initial_budget * (self.rounds_completed / self.total_rounds)
        error = planned - self.spent_so_far  # positive => underspending

        # Convert spend error into alpha adjustment:
        # underspend -> increase alpha_feedback; overspend -> decrease it
        adj = self.k_feedback * (error / max(1e-9, self.initial_budget))
        self.alpha_feedback += adj

        # Clip to keep stable
        if self.alpha_feedback > self.feedback_clip:
            self.alpha_feedback = self.feedback_clip
        elif self.alpha_feedback < -self.feedback_clip:
            self.alpha_feedback = -self.feedback_clip

        return True

    def _alpha_base(self) -> float:
        """Linear decay from alpha_max to alpha_min."""
        if self.total_rounds <= 1:
            return self.alpha_min
        frac = self.rounds_completed / (self.total_rounds - 1)
        return self.alpha_max - (self.alpha_max - self.alpha_min) * frac

    def bidding_function(self, item_id: str) -> float:
        my_valuation = float(self.valuation_vector.get(item_id, 0.0))

        if my_valuation <= 0.0 or self.budget <= 0.0:
            return 0.0

        rounds_remaining = self.total_rounds - self.rounds_completed
        if rounds_remaining <= 0:
            return 0.0

        # -------------------------
        # Strategy 1 bid:
        # bid = alpha_t * value, with alpha_t = decaying base + feedback
        # -------------------------
        alpha_t = self._alpha_base() + self.alpha_feedback

        # Keep alpha_t in a sane range
        if alpha_t < 0.10:
            alpha_t = 0.10
        if alpha_t > 2.50:
            alpha_t = 2.50

        bid = alpha_t * my_valuation

        # Endgame burn: try to spend remaining budget (soft floor)
        if rounds_remaining <= self.endgame_rounds:
            floor_bid = self.burn_gamma * (self.budget / rounds_remaining)
            if bid < floor_bid:
                bid = floor_bid

        # Guarantee no negative utility if desired (bid <= value - margin)
        if self.cap_at_value:
            cap = my_valuation - self.value_margin
            if cap < 0.0:
                cap = 0.0
            if bid > cap:
                bid = cap

        # Clamp to [0, budget]
        if bid < 0.0:
            bid = 0.0
        if bid > self.budget:
            bid = self.budget

        return float(bid)
