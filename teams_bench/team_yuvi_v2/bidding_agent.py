"""
AGT Competition - Patient Predator Strategy v2
===============================================

Team Name: team_yuvi_v2
Strategy: Conservative early, dominate late - "Patient Predator"

KEY CHANGES FROM V1:
1. Budget reservation - always keep minimum for late rounds
2. Reduced early aggression on competitive items
3. Hard spending caps per round in early game
4. Late game dominance when others are broke

PHILOSOPHY:
- Let aggressive bidders burn their budget early on competitive items
- Pick up mid-value items at reasonable prices
- Dominate rounds 10-15 when competition has no budget left
- Never run out of gas before the finish line
"""

from typing import Dict, List


class BiddingAgent:
    """Patient predator - conserve early, dominate late."""
    
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
        
        # ===== BUDGET RESERVATION SETTINGS (KEY CHANGE!) =====
        self.min_reserve_until_round_10 = 20.0  # Keep at least 20 until round 10
        self.min_reserve_until_round_13 = 10.0  # Keep at least 10 until round 13
        
        # ===== OPPONENT TRACKING =====
        self.opponent_data = {
            opp: {
                'estimated_budget': 60.0,
                'items_won': 0,
                'total_spent': 0.0,
                'win_prices': [],
                'p_aggressive': 0.33,
                'p_truthful': 0.34,
                'p_passive': 0.33,
            }
            for opp in opponent_teams
        }
        
        # ===== MARKET TRACKING =====
        self.price_history = []
        self.my_bids = {}
        self.auction_results = []
        self.items_seen = set()
        self.high_competition_count = 0
        self.low_competition_count = 0
        
        # ===== VALUE ANALYSIS =====
        values = sorted(valuation_vector.values(), reverse=True)
        self.sorted_values = values
        self.avg_value = sum(values) / len(values)
        self.median_value = values[len(values) // 2]
        self.total_value = sum(values)
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
            for opp_id, data in self.opponent_data.items():
                data['p_passive'] = min(0.7, data['p_passive'] + 0.02)
                self._normalize_beliefs(data)
            return
        
        if winning_team not in self.opponent_data:
            return
            
        opp = self.opponent_data[winning_team]
        
        if price_paid > avg_price * 1.2:
            opp['p_aggressive'] = min(0.85, opp['p_aggressive'] * 1.3)
            opp['p_passive'] *= 0.8
        elif price_paid < avg_price * 0.7:
            opp['p_passive'] = min(0.7, opp['p_passive'] * 1.2)
        else:
            opp['p_truthful'] = min(0.7, opp['p_truthful'] * 1.15)
        
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
        
        self.price_history.append(price_paid)
        self.auction_results.append((item_id, winning_team, price_paid, my_bid, my_val))
        self.items_seen.add(item_id)
        
        if price_paid > 12:
            self.high_competition_count += 1
        elif price_paid < 6:
            self.low_competition_count += 1
        
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
        return sum(1 for d in self.opponent_data.values() if d['estimated_budget'] > 5)
    
    def _get_max_opponent_budget(self) -> float:
        if not self.opponent_data:
            return 60.0
        return max(d['estimated_budget'] for d in self.opponent_data.values())
    
    def _get_avg_opponent_aggression(self) -> float:
        active = [d for d in self.opponent_data.values() if d['estimated_budget'] > 5]
        if not active:
            return 0.3
        return sum(d['p_aggressive'] for d in active) / len(active)
    
    def _get_remaining_values(self) -> List[float]:
        return [v for item_id, v in self.valuation_vector.items() if item_id not in self.items_seen]
    
    def _get_available_budget(self, rounds_left: int) -> float:
        """
        Calculate how much budget we can ACTUALLY spend this round.
        KEY CHANGE: Enforce budget reservation!
        """
        # Determine minimum reserve based on game phase
        if rounds_left > 5:  # Rounds 1-10
            min_reserve = self.min_reserve_until_round_10
        elif rounds_left > 2:  # Rounds 11-13
            min_reserve = self.min_reserve_until_round_13
        else:  # Rounds 14-15
            min_reserve = 0  # Use everything
        
        available = max(0, self.budget - min_reserve)
        return available
    
    def _is_likely_competitive_item(self, my_valuation: float) -> bool:
        """Detect items that are probably high-value for everyone."""
        if my_valuation > 14:
            return True
        if self.high_competition_count > self.low_competition_count + 2:
            return my_valuation > 10
        return False
    
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
        PATIENT PREDATOR BIDDING LOGIC
        
        Key principles:
        1. Early game (rounds 1-7): Conservative, let others fight
        2. Mid game (rounds 8-11): Selective aggression
        3. Late game (rounds 12-15): Dominate with reserved budget
        """
        
        active_opps = self._get_active_opponents()
        max_opp_budget = self._get_max_opponent_budget()
        avg_aggression = self._get_avg_opponent_aggression()
        is_competitive = self._is_likely_competitive_item(my_valuation)
        remaining_values = self._get_remaining_values()
        available_budget = self._get_available_budget(rounds_left)
        
        # ===== PHASE DETECTION =====
        is_early_game = rounds_left > 8   # Rounds 1-7
        is_mid_game = 4 < rounds_left <= 8  # Rounds 8-11
        is_late_game = rounds_left <= 4   # Rounds 12-15
        
        # ===== EARLY GAME: CONSERVATIVE (Rounds 1-7) =====
        if is_early_game:
            # Hard cap: never spend more than 8 per round in early game
            max_early_spend = min(8.0, available_budget)
            
            if is_competitive:
                # HIGH VALUE BUT COMPETITIVE: Let others fight!
                # Bid only 60-70% - if we lose, we saved budget
                shade = 0.65
                bid = my_valuation * shade
            elif my_valuation >= self.avg_value:
                # ABOVE AVERAGE, NOT SUPER COMPETITIVE: Worth pursuing
                shade = 0.80
                bid = my_valuation * shade
            elif my_valuation >= self.avg_value * 0.5:
                # MEDIUM VALUE: Opportunistic bid
                shade = 0.70
                bid = my_valuation * shade
            else:
                # LOW VALUE: Skip in early game
                return 0.0
            
            # Apply early game spending cap
            bid = min(bid, max_early_spend)
        
        # ===== MID GAME: SELECTIVE (Rounds 8-11) =====
        elif is_mid_game:
            # More aggressive but still careful
            max_mid_spend = min(12.0, available_budget)
            
            if is_competitive:
                shade = 0.75
            elif my_valuation >= self.top_tier_threshold:
                shade = 0.88
            elif my_valuation >= self.avg_value:
                shade = 0.82
            else:
                shade = 0.70
            
            bid = my_valuation * shade
            bid = min(bid, max_mid_spend)
        
        # ===== LATE GAME: DOMINATE (Rounds 12-15) =====
        else:
            # Time to use our reserved budget!
            # Check if opponents are weakened
            opponents_weak = max_opp_budget < 25
            
            if opponents_weak:
                # Opponents running low - we can win with moderate bids
                bid = min(my_valuation * 0.85, max_opp_budget + 3)
            else:
                # Still competition - bid aggressively
                shade = 0.92
                bid = my_valuation * shade
            
            # Late game minimum spending to not waste budget
            min_late_spend = self.budget / rounds_left * 0.8
            if my_valuation > min_late_spend:
                bid = max(bid, min_late_spend)
            
            # Very late: aggressive
            if rounds_left <= 2:
                bid = max(bid, min(self.budget * 0.4, my_valuation))
            
            # Last round: use it all
            if rounds_left == 1:
                bid = min(my_valuation, self.budget)
        
        # ===== OPPONENT BUDGET EXPLOITATION =====
        if max_opp_budget < 15 and not is_early_game:
            # Opponents nearly broke - bid just enough
            bid = min(bid, max_opp_budget + 2)
        
        if max_opp_budget < 8:
            # Opponents almost dead - minimal bid to win
            bid = min(bid, max_opp_budget + 1)
        
        # ===== PRIORITY BOOST FOR EXCEPTIONAL ITEMS =====
        if remaining_values:
            expected_future = sum(remaining_values) / len(remaining_values)
            # Only boost if it's SIGNIFICANTLY better than expected
            if my_valuation > expected_future * 1.5 and is_late_game:
                bid = min(bid * 1.15, my_valuation * 0.95)
        
        # ===== FINAL CONSTRAINTS =====
        # Never exceed valuation (guarantees non-negative utility)
        # Never exceed available budget
        # Never exceed total budget
        bid = max(0.0, min(bid, available_budget, self.budget, my_valuation))
        
        return bid
