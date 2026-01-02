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

        self.rounds_completed = 0
        self.total_rounds = 15

        # Observations
        self.price_history = []
        self.opponent_win_count = {opp: 0 for opp in opponent_teams}

        # MORE aggressive schedule
        self.alpha_max = 2.40   # was 1.85
        self.alpha_min = 1.20   # was 1.05

        # Pacing controller (more responsive)
        self.lambda_shadow = 0.0
        self.k_lambda = 2.20     # was 1.10
        self.lambda_cap = 6.0    # prevent exploding lambda

        # Stronger endgame burn
        self.endgame_rounds = 5  # was 3
        self.burn_gamma = 2.20   # was 1.45

        self.spent_so_far = 0.0

        # Utility-safety behavior
        # If True: avoid overbidding early; still allow overbidding in endgame to spend leftovers
        self.safe_early = True
        self.safe_early_rounds = 10   # first 10 rounds be safer, last 5 spend hard
        self.value_margin = 0.25      # only used when safe_early=True

    def _update_available_budget(self, item_id: str, winning_team: str, price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)

    def _alpha_base(self) -> float:
        if self.total_rounds <= 1:
            return self.alpha_min
        frac = self.rounds_completed / (self.total_rounds - 1)
        return self.alpha_max - (self.alpha_max - self.alpha_min) * frac

    def _avg_and_median_price(self):
        if not self.price_history:
            return 0.0, 0.0
        s = 0.0
        for p in self.price_history:
            s += p
        avg = s / len(self.price_history)

        xs = sorted(self.price_history)
        n = len(xs)
        mid = n // 2
        med = xs[mid] if (n % 2 == 1) else 0.5 * (xs[mid - 1] + xs[mid])
        return avg, med

    def update_after_each_round(self, item_id: str, winning_team: str, price_paid: float):
        # System updates (DO NOT REMOVE)
        self._update_available_budget(item_id, winning_team, price_paid)

        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
            self.spent_so_far += float(price_paid)

        self.rounds_completed += 1

        p = float(price_paid)
        if p > 0:
            self.price_history.append(p)

        if winning_team and winning_team != self.team_id:
            if winning_team in self.opponent_win_count:
                self.opponent_win_count[winning_team] += 1

        # ---- Stronger pacing update ----
        # Aim to spend a bit AHEAD of linear early, to reduce end leftovers.
        # (front-load spending)
        progress = self.rounds_completed / self.total_rounds
        frontload = 0.10 * (1.0 - progress)  # up to +10% early, fades to 0
        planned = self.initial_budget * (progress + frontload)
        if planned > self.initial_budget:
            planned = self.initial_budget

        error = planned - self.spent_so_far  # positive => underspent

        # If underspent => decrease lambda (more aggressive).
        # If overspent => increase lambda (less aggressive).
        self.lambda_shadow -= self.k_lambda * (error / max(1e-9, self.initial_budget))

        if self.lambda_shadow < 0.0:
            self.lambda_shadow = 0.0
        if self.lambda_shadow > self.lambda_cap:
            self.lambda_shadow = self.lambda_cap

        return True

    def bidding_function(self, item_id: str) -> float:
        v = float(self.valuation_vector.get(item_id, 0.0))
        if v <= 0.0 or self.budget <= 0.0:
            return 0.0

        rounds_remaining = self.total_rounds - self.rounds_completed
        if rounds_remaining <= 0:
            return 0.0

        alpha = self._alpha_base()

        # Base bid (more aggressive when lambda is low)
        base_bid = alpha * v / (1.0 + self.lambda_shadow)
        if base_bid > self.budget:
            base_bid = self.budget
        if base_bid < 0.0:
            base_bid = 0.0

        bid = base_bid

        # Market nudge: be willing to clear typical prices (more aggressive than before)
        avg_p, med_p = self._avg_and_median_price()
        if med_p > 0:
            market_target = med_p * 1.35  # was 1.10
            # If we have lots of budget left relative to rounds, push harder
            pace = self.budget / max(1, rounds_remaining)
            if market_target < 0.8 * pace:
                market_target = 0.8 * pace

            # Blend more toward market_target to increase win rate/spend
            if v >= 1.2 * med_p:
                w = 0.55
            else:
                w = 0.35
            bid = w * base_bid + (1.0 - w) * market_target

        # Endgame burn: force spending remaining budget
        if rounds_remaining <= self.endgame_rounds:
            floor_bid = self.burn_gamma * (self.budget / rounds_remaining)
            if bid < floor_bid:
                bid = floor_bid

        # Optional safety only in early rounds (keeps utility decent early)
        if self.safe_early and self.rounds_completed < self.safe_early_rounds:
            cap = v - self.value_margin
            if cap < 0.0:
                cap = 0.0
            if bid > cap:
                bid = cap

        # Clamp to [0, budget]
        if bid < 0.0:
            bid = 0.0
        if bid > self.budget:
            bid = self.budget

        bid = min(bid, max(0.0, v - 0.25))
        return float(bid)
