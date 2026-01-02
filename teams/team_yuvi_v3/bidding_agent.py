"""
AGT Competition - Ultimate Margin-Maximizing Strategy v3
=========================================================

Team Name: team_yuvi_v3
Strategy: MARGIN-FOCUSED bidding with trap avoidance and opportunity detection

CORE INSIGHT: Utility = Value - Price
    → Maximize MARGIN, not just value!
    → A 10-value item won at price 4 (margin=6) beats
      an 18-value item won at price 16 (margin=2)

KEY PRINCIPLES:
1. MARGIN FOCUS: Bid based on expected profit margin, not raw value
2. TRAP AVOIDANCE: High-for-ALL items = everyone bids high = low margin = SKIP
3. OPPORTUNITY HUNTING: Mixed items where WE have high value = high margin = BID STRONG
4. BUDGET DISCIPLINE: Never waste budget, never run out early
5. SNIPER MODE: When opponents are weak, bid just enough to beat them

BASED ON: v1 (46.7% win rate) with strategic improvements
"""

from typing import Dict, List, Tuple


class BiddingAgent:
    """Ultimate margin-maximizing bidder."""
    
    def __init__(self, team_id: str, valuation_vector: Dict[str, float], 
                 budget: float, opponent_teams: List[str]):
        self.team_id = team_id
        self.valuation_vector = valuation_vector
        self.budget = budget
        self.initial_budget = budget
        self.opponent_teams = opponent_teams
        self.items_won = []
        
        self.rounds_completed = 0
        self.total_rounds = 15
        
        # ===== OPPONENT TRACKING =====
        self.opponent_data = {
            opp: {
                'budget': 60.0,
                'items_won': 0,
                'total_spent': 0.0,
                'avg_win_price': 0.0,
                'aggression': 0.5,  # 0=passive, 1=aggressive
            }
            for opp in opponent_teams
        }
        
        # ===== MARKET INTELLIGENCE =====
        self.price_history = []
        self.my_bids = {}
        self.items_seen = set()
        
        # Track margin patterns: (my_value, price_paid, margin)
        self.margin_history = []
        
        # Competition detection
        self.high_value_high_price_count = 0  # Likely High-for-ALL
        self.high_value_low_price_count = 0   # Likely unique opportunity
        
        # ===== VALUE ANALYSIS =====
        values = sorted(valuation_vector.values(), reverse=True)
        self.sorted_values = values
        self.avg_value = sum(values) / len(values)
        self.total_value = sum(values)
        self.top_25_pct = values[int(len(values) * 0.25)] if len(values) > 4 else values[0]
        self.top_50_pct = values[int(len(values) * 0.50)] if len(values) > 2 else values[0]
        
    def _update_budget(self, item_id: str, winning_team: str, price_paid: float):
        """Track our budget after each round."""
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
    
    def update_after_each_round(self, item_id: str, winning_team: str, price_paid: float):
        """Learn from each auction result."""
        self._update_budget(item_id, winning_team, price_paid)
        self.rounds_completed += 1
        
        my_val = self.valuation_vector.get(item_id, 0)
        my_bid = self.my_bids.get(item_id, 0)
        margin = my_val - price_paid
        
        # Record price and margin history
        self.price_history.append(price_paid)
        self.margin_history.append((my_val, price_paid, margin))
        self.items_seen.add(item_id)
        
        # Detect competition patterns
        if my_val > 12:
            if price_paid > 10:
                self.high_value_high_price_count += 1  # Competitive item
            else:
                self.high_value_low_price_count += 1   # Unique opportunity
        
        # Update opponent data
        if winning_team and winning_team != self.team_id:
            if winning_team in self.opponent_data:
                opp = self.opponent_data[winning_team]
                opp['budget'] -= price_paid
                opp['items_won'] += 1
                opp['total_spent'] += price_paid
                
                # Update aggression estimate
                avg_price = sum(self.price_history) / len(self.price_history)
                if price_paid > avg_price * 1.2:
                    opp['aggression'] = min(1.0, opp['aggression'] + 0.1)
                elif price_paid < avg_price * 0.8:
                    opp['aggression'] = max(0.0, opp['aggression'] - 0.05)
        
        return True
    
    # ========== INTELLIGENCE GATHERING ==========
    
    def _get_active_opponents(self) -> int:
        """Count opponents with meaningful budget."""
        return sum(1 for d in self.opponent_data.values() if d['budget'] > 5)
    
    def _get_max_opponent_budget(self) -> float:
        """Get the highest opponent budget."""
        if not self.opponent_data:
            return 60.0
        return max(d['budget'] for d in self.opponent_data.values())
    
    def _get_min_opponent_budget(self) -> float:
        """Get the lowest opponent budget."""
        if not self.opponent_data:
            return 60.0
        return min(d['budget'] for d in self.opponent_data.values())
    
    def _get_avg_opponent_aggression(self) -> float:
        """Average aggression of active opponents."""
        active = [d for d in self.opponent_data.values() if d['budget'] > 5]
        if not active:
            return 0.5
        return sum(d['aggression'] for d in active) / len(active)
    
    def _get_remaining_values(self) -> List[float]:
        """Our values for items not yet auctioned."""
        return [v for item_id, v in self.valuation_vector.items() 
                if item_id not in self.items_seen]
    
    # ========== MARGIN ESTIMATION ==========
    
    def _estimate_competition(self, my_value: float) -> str:
        """
        Estimate competition level for current item.
        Returns: 'high', 'medium', 'low'
        """
        rounds_done = self.rounds_completed
        
        # Early game: use value as proxy
        if rounds_done < 3:
            if my_value > 15:
                return 'high'  # Likely High-for-ALL
            elif my_value < 6:
                return 'low'   # Likely Low-for-ALL
            else:
                return 'medium'
        
        # After some rounds: use learned patterns
        if self.high_value_high_price_count > self.high_value_low_price_count + 2:
            # Market is competitive
            if my_value > 14:
                return 'high'
            elif my_value > 8:
                return 'medium'
            else:
                return 'low'
        elif self.high_value_low_price_count > self.high_value_high_price_count:
            # We're getting unique opportunities
            if my_value > 12:
                return 'low'  # Others probably don't want it
            else:
                return 'medium'
        else:
            # Mixed signals
            if my_value > 15:
                return 'high'
            elif my_value > 7:
                return 'medium'
            else:
                return 'low'
    
    def _estimate_price(self, my_value: float, competition: str) -> float:
        """
        Estimate what price this item will sell for.
        """
        if competition == 'high':
            # Everyone wants it → price will be high
            return my_value * 0.75
        elif competition == 'low':
            # Few competitors → price will be low
            return my_value * 0.35
        else:
            return my_value * 0.55
    
    def _estimate_margin(self, my_value: float) -> Tuple[float, str]:
        """
        Estimate expected margin (profit) if we win this item.
        Returns: (expected_margin, competition_level)
        """
        competition = self._estimate_competition(my_value)
        expected_price = self._estimate_price(my_value, competition)
        expected_margin = my_value - expected_price
        return expected_margin, competition
    
    # ========== CORE BIDDING LOGIC ==========
    
    def bidding_function(self, item_id: str) -> float:
        my_value = self.valuation_vector.get(item_id, 0)
        rounds_left = self.total_rounds - self.rounds_completed
        
        if my_value <= 0 or self.budget <= 0.01 or rounds_left <= 0:
            return 0.0
        
        bid = self._calculate_ultimate_bid(my_value, rounds_left)
        self.my_bids[item_id] = bid
        return float(bid)
    
    def _calculate_ultimate_bid(self, my_value: float, rounds_left: int) -> float:
        """
        THE ULTIMATE BIDDING ALGORITHM
        
        Strategy: Maximize margin while maintaining budget discipline
        """
        
        # Gather intelligence
        expected_margin, competition = self._estimate_margin(my_value)
        max_opp_budget = self._get_max_opponent_budget()
        min_opp_budget = self._get_min_opponent_budget()
        avg_aggression = self._get_avg_opponent_aggression()
        remaining_values = self._get_remaining_values()
        active_opps = self._get_active_opponents()
        
        # Budget discipline
        budget_per_round = self.budget / rounds_left
        spent_so_far = self.initial_budget - self.budget
        rounds_done = self.total_rounds - rounds_left
        expected_spent = (rounds_done / self.total_rounds) * self.initial_budget
        budget_status = "under" if spent_so_far < expected_spent * 0.8 else "over" if spent_so_far > expected_spent * 1.2 else "on_track"
        
        # ===== PHASE 1: MARGIN-BASED BASE BID =====
        
        if expected_margin > 5:
            # EXCELLENT opportunity - bid strong
            shade = 0.92
        elif expected_margin > 3:
            # GOOD opportunity
            shade = 0.88
        elif expected_margin > 1:
            # MARGINAL opportunity
            shade = 0.82
        else:
            # POOR opportunity (likely trap)
            shade = 0.70
        
        bid = my_value * shade
        
        # ===== PHASE 2: TRAP AVOIDANCE =====
        
        if competition == 'high':
            # This is likely a High-for-ALL item
            # Everyone wants it → expensive to win → low margin
            
            if rounds_left > 10:
                # Early game: let aggressive players burn budget
                bid = min(bid, my_value * 0.75)
            elif rounds_left > 5:
                # Mid game: compete but carefully
                bid = min(bid, my_value * 0.85)
            # Late game: compete normally
            
            # Extra caution if we already have items
            if len(self.items_won) >= 3:
                bid *= 0.90
        
        # ===== PHASE 3: OPPORTUNITY BOOSTING =====
        
        if competition == 'low' and my_value > 10:
            # We likely have UNIQUE high value (Mixed category luck!)
            # Others probably value this low → we can win cheap
            # But bid enough to secure it
            bid = max(bid, my_value * 0.80)
        
        # ===== PHASE 4: OPPONENT EXPLOITATION =====
        
        # Sniper mode: when opponents are weak, bid just enough
        if max_opp_budget < 20:
            bid = min(bid, max_opp_budget + 4)
        
        if max_opp_budget < 12:
            bid = min(bid, max_opp_budget + 2)
        
        if max_opp_budget < 6:
            # Opponents nearly dead - minimal bid
            bid = min(bid, max_opp_budget + 1)
        
        # If only 1-2 active opponents, we can relax
        if active_opps <= 1:
            bid *= 0.90
        
        # Adjust for opponent aggression
        if avg_aggression > 0.7:
            bid *= 1.05  # Aggressive field, bid higher
        elif avg_aggression < 0.3:
            bid *= 0.92  # Passive field, save budget
        
        # ===== PHASE 5: BUDGET DISCIPLINE =====
        
        # Minimum spend to not waste budget
        min_reasonable_spend = budget_per_round * 0.6
        
        if my_value > min_reasonable_spend:
            bid = max(bid, min_reasonable_spend)
        
        # If underspending, be more aggressive
        if budget_status == "under" and my_value > 5:
            boost = min(1.15, 1 + (expected_spent - spent_so_far) / 30)
            bid *= boost
        
        # ===== PHASE 6: LATE GAME FORCE =====
        
        if rounds_left <= 5:
            # Must start spending
            min_late_spend = budget_per_round * 0.7
            if my_value > min_late_spend * 0.8:
                bid = max(bid, min_late_spend)
        
        if rounds_left <= 3:
            # Urgent spending
            force_spend = self.budget / rounds_left * 0.8
            if my_value > force_spend * 0.7:
                bid = max(bid, min(force_spend, my_value))
        
        if rounds_left <= 2:
            # Very late
            bid = max(bid, min(self.budget * 0.45, my_value))
        
        if rounds_left == 1:
            # Last round - use all budget if item is worth it
            bid = min(my_value, self.budget)
        
        # ===== PHASE 7: QUALITY PRIORITY =====
        
        # If this item is much better than remaining items, prioritize
        if remaining_values:
            avg_remaining = sum(remaining_values) / len(remaining_values)
            max_remaining = max(remaining_values)
            
            if my_value > avg_remaining * 1.4:
                # Significantly above average - boost
                bid = min(bid * 1.12, my_value * 0.95)
            
            if my_value >= max_remaining * 0.95:
                # This might be our best remaining item
                bid = min(bid * 1.08, my_value * 0.96)
        
        # ===== FINAL CONSTRAINTS =====
        bid = max(0.0, min(bid, self.budget, my_value))
        
        return bid
