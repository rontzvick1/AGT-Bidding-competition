"""
AGT Competition - THE DOMINATOR v4
===================================

Team Name: team_yuvi_v4
Strategy: Counter-All Aggressive Domination

PHILOSOPHY: Be AGGRESSIVE, SMART, CHEEKY, and NEVER LET DOWN!

LESSONS LEARNED:
- v1 (46.7%): Near-truthful (85-92%) + budget pacing = WORKS
- v2: Too conservative = FAILS
- v3: Overthinking margins = Worse than simple v1

THE DOMINATOR PRINCIPLES:
1. AGGRESSIVE: Bid strong (87-93%), don't let others steal
2. SMART: Detect traps early, avoid overpaying
3. CHEEKY: Exploit weak opponents ruthlessly with sniper bids
4. DISCIPLINED: Perfect budget pacing, NEVER waste a cent

COUNTER-ALL STRATEGY:
- vs Truthful: Let them burn budget early, dominate late
- vs Budget-Aware: Slightly outbid them (87% vs 80%)
- vs Strategic: Our aggression crushes their shading
- vs Random: Ignore, they'll lose anyway

PHASE STRATEGY:
- Early (1-5): Learn opponents, bid 85-88%, avoid traps
- Mid (6-10): Compete hard 88-92%, build momentum  
- Late (11-15): DOMINATE - sniper mode, use all budget
"""

from typing import Dict, List


class BiddingAgent:
    """THE DOMINATOR - Aggressive counter-all strategy."""
    
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
        
        # ===== OPPONENT INTELLIGENCE =====
        self.opponent_data = {
            opp: {
                'budget': 60.0,
                'items_won': 0,
                'total_spent': 0.0,
                'is_aggressive': False,  # Bids > 90% value
                'is_passive': False,     # Bids < 70% value
                'threat_level': 1.0,     # 0-2 scale
            }
            for opp in opponent_teams
        }
        
        # ===== MARKET TRACKING =====
        self.price_history = []
        self.my_bids = {}
        self.items_seen = set()
        self.wins_at_high_price = 0  # Times we paid > 12
        self.wins_at_low_price = 0   # Times we paid < 8
        
        # ===== VALUE ANALYSIS =====
        values = sorted(valuation_vector.values(), reverse=True)
        self.sorted_values = values
        self.avg_value = sum(values) / len(values)
        self.high_value_threshold = values[int(len(values) * 0.3)] if len(values) > 3 else 15
        
    def _update_budget(self, item_id: str, winning_team: str, price_paid: float):
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
            if price_paid > 12:
                self.wins_at_high_price += 1
            elif price_paid < 8:
                self.wins_at_low_price += 1
    
    def update_after_each_round(self, item_id: str, winning_team: str, price_paid: float):
        self._update_budget(item_id, winning_team, price_paid)
        self.rounds_completed += 1
        
        my_val = self.valuation_vector.get(item_id, 0)
        my_bid = self.my_bids.get(item_id, 0)
        
        self.price_history.append(price_paid)
        self.items_seen.add(item_id)
        
        # Update opponent data
        if winning_team and winning_team != self.team_id:
            if winning_team in self.opponent_data:
                opp = self.opponent_data[winning_team]
                opp['budget'] -= price_paid
                opp['items_won'] += 1
                opp['total_spent'] += price_paid
                
                # Classify opponent behavior
                avg_price = sum(self.price_history) / len(self.price_history) if self.price_history else 10
                if price_paid > avg_price * 1.3:
                    opp['is_aggressive'] = True
                    opp['threat_level'] = min(2.0, opp['threat_level'] + 0.2)
                elif price_paid < avg_price * 0.6:
                    opp['is_passive'] = True
                    opp['threat_level'] = max(0.3, opp['threat_level'] - 0.1)
                
                # Reduce threat when budget is low
                if opp['budget'] < 20:
                    opp['threat_level'] *= 0.7
                if opp['budget'] < 10:
                    opp['threat_level'] *= 0.5
        
        return True
    
    # ========== INTELLIGENCE ==========
    
    def _get_remaining_values(self) -> List[float]:
        return [v for item_id, v in self.valuation_vector.items() 
                if item_id not in self.items_seen]
    
    def _get_max_threat_budget(self) -> float:
        """Budget of most dangerous opponent."""
        if not self.opponent_data:
            return 60.0
        threats = [(d['budget'], d['threat_level']) for d in self.opponent_data.values()]
        # Weight by threat level
        return max(b * t for b, t in threats) / max(t for _, t in threats) if threats else 60
    
    def _get_weakest_opponent_budget(self) -> float:
        """Budget of weakest active opponent."""
        active = [d['budget'] for d in self.opponent_data.values() if d['budget'] > 3]
        return min(active) if active else 0
    
    def _count_active_threats(self) -> int:
        """Count opponents who can still compete."""
        return sum(1 for d in self.opponent_data.values() 
                   if d['budget'] > 8 and d['threat_level'] > 0.5)
    
    def _is_trap_item(self, my_value: float) -> bool:
        """
        Detect if this is likely a High-for-ALL item (trap).
        High value + early game + aggressive opponents = TRAP
        """
        if my_value < 14:
            return False
        
        # Early game with high value = likely competitive trap
        if self.rounds_completed < 5:
            return True
        
        # Check if market has been competitive
        if self.price_history:
            avg_price = sum(self.price_history) / len(self.price_history)
            if avg_price > 10:
                return my_value > 15
        
        return False
    
    def _get_game_phase(self, rounds_left: int) -> str:
        """Determine current game phase."""
        if rounds_left > 10:
            return 'early'
        elif rounds_left > 5:
            return 'mid'
        else:
            return 'late'
    
    # ========== TARGET SPEND CALCULATOR (FROM V1 - PROVEN!) ==========
    
    def _get_target_spend(self, rounds_left: int, my_value: float, 
                          remaining_values: List[float]) -> float:
        """
        Calculate target spend based on v1's proven formula:
        - Even budget distribution
        - Item quality relative to future opportunities  
        - Urgency multiplier as time runs out
        """
        if rounds_left <= 0:
            return self.budget
        
        base_rate = self.budget / rounds_left
        
        # Quality multiplier - spend more on above-average items
        if remaining_values:
            avg_remaining = sum(remaining_values) / len(remaining_values)
            if my_value > avg_remaining:
                quality_mult = min(1.5, my_value / avg_remaining)
            else:
                quality_mult = max(0.7, my_value / avg_remaining)
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
    
    # ========== THE DOMINATOR BIDDING LOGIC ==========
    
    def bidding_function(self, item_id: str) -> float:
        my_value = self.valuation_vector.get(item_id, 0)
        rounds_left = self.total_rounds - self.rounds_completed
        
        if my_value <= 0 or self.budget <= 0.01 or rounds_left <= 0:
            return 0.0
        
        bid = self._dominator_bid(my_value, rounds_left)
        self.my_bids[item_id] = bid
        return float(bid)
    
    def _dominator_bid(self, my_value: float, rounds_left: int) -> float:
        """
        THE DOMINATOR v4.1 - Based on v1's proven core + smart enhancements
        
        Key insight: v1 worked because of near-truthful bidding + target spend.
        Keep that core, add light improvements.
        """
        
        remaining_values = self._get_remaining_values()
        active_threats = self._count_active_threats()
        max_opp_budget = self._get_max_threat_budget()
        
        # Budget we MUST spend per round
        min_spend_rate = self.budget / rounds_left
        
        # =========================================
        # PHASE 1: BASE SHADE (V1 PROVEN - NEAR TRUTHFUL!)
        # =========================================
        
        if my_value >= self.high_value_threshold:
            shade = 0.92  # TOP TIER - bid strong!
        elif my_value >= self.avg_value:
            shade = 0.88  # ABOVE AVERAGE
        elif my_value >= self.avg_value * 0.5:
            shade = 0.82  # BELOW AVERAGE
        else:
            shade = 0.75  # LOW VALUE
        
        bid = my_value * shade
        
        # =========================================
        # PHASE 2: COMPETITION BOOST (FROM V1)
        # =========================================
        
        is_competitive = my_value > 14  # High value likely wanted by all
        
        if is_competitive:
            # Everyone wants it - bid higher to compete
            bid = min(my_value * 0.95, bid * 1.1)
        
        # =========================================
        # PHASE 3: LIGHT OPPONENT AWARENESS (SIMPLIFIED!)
        # =========================================
        
        # Only snipe when opponents are REALLY weak
        if max_opp_budget < 10:
            bid = min(bid, max_opp_budget + 3)
        
        if active_threats <= 1:
            bid *= 0.95  # Few real threats, slight savings
        
        # =========================================
        # PHASE 4: BUDGET UTILIZATION (V1 CORE - CRITICAL!)
        # =========================================
        
        # Calculate what we SHOULD spend this round
        target_spend = self._get_target_spend(rounds_left, my_value, remaining_values)
        
        # If under-spending, boost the bid
        if bid < target_spend and my_value > target_spend * 0.8:
            bid = max(bid, target_spend)
        
        # =========================================
        # PHASE 5: LATE GAME RULES (V1 - NEVER LEAVE BUDGET!)
        # =========================================
        
        if rounds_left <= 6:
            # Getting late - ensure we're spending
            min_bid = min_spend_rate * 0.7
            if my_value > min_bid:
                bid = max(bid, min_bid)
        
        if rounds_left <= 4:
            # Late game - must spend
            forced_min = self.budget / rounds_left
            if my_value > 0:
                bid = max(bid, min(forced_min, my_value))
        
        if rounds_left <= 2:
            # Very late - aggressive spending
            if my_value > 0:
                bid = max(bid, min(self.budget * 0.4, my_value))
        
        if rounds_left == 1:
            # LAST ROUND - spend everything!
            bid = min(my_value, self.budget)
        
        # =========================================
        # PHASE 6: PRIORITY BOOST (V1)
        # =========================================
        
        if remaining_values:
            expected_future_avg = sum(remaining_values) / len(remaining_values)
            if my_value > expected_future_avg * 1.3:
                # Great opportunity - boost bid
                bid = min(bid * 1.1, my_value * 0.98)
        
        # =========================================
        # FINAL CONSTRAINTS
        # =========================================
        
        bid = max(0.0, min(bid, self.budget, my_value))
        
        return bid
