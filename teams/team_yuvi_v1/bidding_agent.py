"""
AGT Competition - Advanced Adaptive Strategy v2
================================================

Team Name: team_yuvi
Strategy: Bayesian opponent modeling + guaranteed budget utilization + adaptive aggression

DESIGN PRINCIPLES:
1. NEVER leave budget unspent - budget = 0 at end
2. Near-truthful bidding (85-100%) - Vickrey rewards truthfulness
3. Prioritize high-value items but don't skip opportunities
4. Track market conditions to detect "high-value-for-all" vs "unique value" items
5. Adapt aggression based on opponent behavior AND remaining budget

KEY INSIGHT: In multi-player sequential Vickrey:
- Too conservative = lose items AND waste budget
- Too aggressive = burn budget early, lose late items
- Optimal: Spend budget evenly, bid near-truthfully, prioritize high-margin items
"""

from typing import Dict, List


class BiddingAgent:
    """Advanced adaptive agent - v2 with guaranteed budget spend."""
    
    def __init__(self, team_id: str, valuation_vector: Dict[str, float], 
                 budget: float, opponent_teams: List[str]):
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
                'estimated_budget': 60.0,
                'items_won': 0,
                'total_spent': 0.0,
                'win_prices': [],
                # Bayesian: aggressive/truthful/passive
                'p_aggressive': 0.33,
                'p_truthful': 0.34,
                'p_passive': 0.33,
            }
            for opp in opponent_teams
        }
        
        # ===== MARKET TRACKING =====
        self.price_history = []
        self.my_bids = {}
        self.auction_results = []  # (item_id, winner, price, my_bid, my_val, did_we_win)
        self.items_seen = set()
        
        # Track competitive vs non-competitive items
        self.high_competition_count = 0  # Items where price > 12
        self.low_competition_count = 0   # Items where price < 6
        
        # ===== VALUE ANALYSIS =====
        values = sorted(valuation_vector.values(), reverse=True)
        self.sorted_values = values
        self.avg_value = sum(values) / len(values)
        self.median_value = values[len(values) // 2]
        self.total_value = sum(values)
        
        # Top 30% threshold (items we REALLY want)
        self.top_tier_threshold = values[int(len(values) * 0.3)] if len(values) > 3 else values[0]
        
    def _update_available_budget(self, item_id: str, winning_team: str, 
                                 price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
    
    def _bayesian_update(self, winning_team: str, price_paid: float, my_bid: float):
        """Update beliefs about opponent types."""
        avg_price = sum(self.price_history) / len(self.price_history) if self.price_history else 10
        
        if not winning_team or winning_team == self.team_id:
            # We won or no winner - opponents are weaker than expected
            for opp_id, data in self.opponent_data.items():
                shift = 0.02
                data['p_passive'] = min(0.7, data['p_passive'] + shift)
                self._normalize_beliefs(data)
            return
        
        if winning_team not in self.opponent_data:
            return
            
        opp = self.opponent_data[winning_team]
        
        # Update based on price level
        if price_paid > avg_price * 1.2:
            opp['p_aggressive'] = min(0.85, opp['p_aggressive'] * 1.3)
            opp['p_passive'] *= 0.8
        elif price_paid < avg_price * 0.7:
            opp['p_passive'] = min(0.7, opp['p_passive'] * 1.2)
        else:
            opp['p_truthful'] = min(0.7, opp['p_truthful'] * 1.15)
        
        # Strong signal: they outbid us significantly
        if my_bid > 0 and price_paid > my_bid:
            opp['p_aggressive'] = min(0.85, opp['p_aggressive'] * 1.2)
        
        self._normalize_beliefs(opp)
    
    def _normalize_beliefs(self, opp_data: dict):
        total = opp_data['p_aggressive'] + opp_data['p_truthful'] + opp_data['p_passive']
        if total > 0:
            opp_data['p_aggressive'] /= total
            opp_data['p_truthful'] /= total
            opp_data['p_passive'] /= total
    
    def update_after_each_round(self, item_id: str, winning_team: str, 
                                price_paid: float):
        self._update_available_budget(item_id, winning_team, price_paid)
        self.rounds_completed += 1
        
        my_val = self.valuation_vector.get(item_id, 0)
        my_bid = self.my_bids.get(item_id, 0)
        did_win = (winning_team == self.team_id)
        
        # Record history
        self.price_history.append(price_paid)
        self.auction_results.append((item_id, winning_team, price_paid, my_bid, my_val, did_win))
        self.items_seen.add(item_id)
        
        # Track market competitiveness
        if price_paid > 12:
            self.high_competition_count += 1
        elif price_paid < 6:
            self.low_competition_count += 1
        
        # Update opponent data
        if winning_team and winning_team != self.team_id:
            if winning_team in self.opponent_data:
                opp = self.opponent_data[winning_team]
                opp['estimated_budget'] -= price_paid
                opp['items_won'] += 1
                opp['total_spent'] += price_paid
                opp['win_prices'].append(price_paid)
        
        self._bayesian_update(winning_team, price_paid, my_bid)
        return True
    
    # ========== HELPER METHODS ==========
    
    def _get_active_opponents(self) -> int:
        """Count opponents with budget > 5."""
        return sum(1 for d in self.opponent_data.values() if d['estimated_budget'] > 5)
    
    def _get_max_opponent_budget(self) -> float:
        if not self.opponent_data:
            return 60.0
        return max(d['estimated_budget'] for d in self.opponent_data.values())
    
    def _get_avg_opponent_aggression(self) -> float:
        """Average aggression probability across active opponents."""
        active = [d for d in self.opponent_data.values() if d['estimated_budget'] > 5]
        if not active:
            return 0.3
        return sum(d['p_aggressive'] for d in active) / len(active)
    
    def _get_remaining_values(self) -> List[float]:
        """Get list of our values for unseen items."""
        return [v for item_id, v in self.valuation_vector.items() if item_id not in self.items_seen]
    
    def _is_likely_competitive_item(self, my_valuation: float) -> bool:
        """
        Estimate if this item is "high-value-for-all" (competitive) or "mixed" (might be unique to us).
        Use our valuation as signal + market history.
        """
        # High values (>14) often come from "high-value-for-all" category
        if my_valuation > 14:
            return True
        
        # If we've seen many high-price auctions, market is competitive
        if self.high_competition_count > self.low_competition_count + 2:
            return my_valuation > 10
        
        return False
    
    # ========== CORE BIDDING LOGIC ==========
    
    def bidding_function(self, item_id: str) -> float:
        my_valuation = self.valuation_vector.get(item_id, 0)
        rounds_left = self.total_rounds - self.rounds_completed
        
        # Edge cases
        if my_valuation <= 0:
            return 0.0
        if self.budget <= 0.01:
            return 0.0
        if rounds_left <= 0:
            return 0.0
        
        bid = self._calculate_bid(my_valuation, rounds_left)
        self.my_bids[item_id] = bid
        return float(bid)
    
    def _calculate_bid(self, my_valuation: float, rounds_left: int) -> float:
        """
        IMPROVED BIDDING LOGIC v2
        
        Key changes:
        1. Higher base shading (85-95% instead of 55-85%)
        2. Guaranteed minimum spend per round
        3. Never skip items in late game
        4. Aggressive budget utilization
        """
        
        active_opps = self._get_active_opponents()
        max_opp_budget = self._get_max_opponent_budget()
        avg_aggression = self._get_avg_opponent_aggression()
        is_competitive = self._is_likely_competitive_item(my_valuation)
        remaining_values = self._get_remaining_values()
        
        # Budget we MUST spend per round to not waste it
        min_spend_rate = self.budget / rounds_left
        
        # ===== PHASE 1: DETERMINE BASE SHADE =====
        # Much less shading than before! Near-truthful is better in Vickrey
        
        if my_valuation >= self.top_tier_threshold:
            # TOP TIER ITEM: We really want this
            shade = 0.92
        elif my_valuation >= self.avg_value:
            # ABOVE AVERAGE: Worth competing for
            shade = 0.88
        elif my_valuation >= self.avg_value * 0.5:
            # BELOW AVERAGE but not trash
            shade = 0.82
        else:
            # LOW VALUE
            shade = 0.75
        
        bid = my_valuation * shade
        
        # ===== PHASE 2: COMPETITION ADJUSTMENT =====
        
        if is_competitive:
            # Likely "high-value-for-all" - everyone wants it
            # Bid higher to compete, but cap at valuation
            bid = min(my_valuation * 0.95, bid * 1.1)
        
        if avg_aggression > 0.5:
            # Aggressive field - need to bid higher
            bid *= 1.05
        elif avg_aggression < 0.25:
            # Passive field - can shade more
            bid *= 0.95
        
        # ===== PHASE 3: OPPONENT BUDGET AWARENESS =====
        
        if active_opps <= 1:
            # Few threats - we can relax a bit
            bid *= 0.92
        
        if max_opp_budget < 20:
            # Opponents running low
            bid = min(bid, max_opp_budget + 5)
        
        if max_opp_budget < 10:
            # Opponents nearly broke - bid just enough to win
            bid = min(bid, max_opp_budget + 2)
        
        # ===== PHASE 4: BUDGET UTILIZATION (CRITICAL!) =====
        # This is where v1 failed - we must spend our budget!
        
        # Calculate what we SHOULD spend this round
        target_spend = self._get_target_spend(rounds_left, my_valuation, remaining_values)
        
        # If we're under-spending, boost the bid
        if bid < target_spend and my_valuation > target_spend * 0.8:
            bid = max(bid, target_spend)
        
        # ===== PHASE 5: LATE GAME RULES (NEVER LEAVE BUDGET!) =====
        
        if rounds_left <= 6:
            # Getting late - ensure we're spending
            min_bid = min_spend_rate * 0.7
            if my_valuation > min_bid:
                bid = max(bid, min_bid)
        
        if rounds_left <= 4:
            # Late game - bid on ANY positive value item
            if my_valuation > 0:
                # Must spend at least 1/rounds_left of budget
                forced_min = self.budget / rounds_left
                bid = max(bid, min(forced_min, my_valuation))
        
        if rounds_left <= 2:
            # Very late - aggressive spending
            if my_valuation > 0:
                # Spend at least 40% of remaining budget
                bid = max(bid, min(self.budget * 0.4, my_valuation))
        
        if rounds_left == 1:
            # LAST ROUND - spend everything (up to valuation)
            bid = min(my_valuation, self.budget)
        
        # ===== PHASE 6: PRIORITY BOOST =====
        
        # Is this item better than what we expect to see?
        if remaining_values:
            expected_future_avg = sum(remaining_values) / len(remaining_values)
            if my_valuation > expected_future_avg * 1.3:
                # This is a great opportunity - boost bid
                bid = min(bid * 1.1, my_valuation * 0.98)
        
        # ===== FINAL CONSTRAINTS =====
        # Never bid more than valuation (guarantees non-negative utility if we win)
        # Never bid more than budget
        bid = max(0.0, min(bid, self.budget, my_valuation))
        
        return bid
    
    def _get_target_spend(self, rounds_left: int, current_val: float, 
                          remaining_values: List[float]) -> float:
        """
        Calculate target spend for this round based on:
        - Even budget distribution
        - Item quality relative to future opportunities
        - Urgency (rounds remaining)
        """
        if rounds_left <= 0:
            return self.budget
        
        base_rate = self.budget / rounds_left
        
        # If current item is above average of remaining, spend more
        if remaining_values:
            avg_remaining = sum(remaining_values) / len(remaining_values)
            if current_val > avg_remaining:
                quality_mult = min(1.5, current_val / avg_remaining)
            else:
                quality_mult = max(0.7, current_val / avg_remaining)
        else:
            quality_mult = 1.0
        
        # Urgency multiplier - spend more as time runs out
        if rounds_left <= 3:
            urgency = 1.3
        elif rounds_left <= 5:
            urgency = 1.15
        else:
            urgency = 1.0
        
        return base_rate * quality_mult * urgency
