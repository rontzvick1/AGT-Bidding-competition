"""
AGT Competition - Student Agent Template
========================================

Team Name: [YOUR TEAM NAME]
Members: 
  - [Student 1 Name and ID]
  - [Student 2 Name and ID]
  - [Student 3 Name and ID]

Strategy Description:
[Brief description of your bidding strategy]

Key Features:
- [Feature 1]
- [Feature 2]
- [Feature 3]
"""

from typing import Dict, List


class BiddingAgent:
    """
    Your bidding agent for the AGT Auto-Bidding Competition.
    
    This template provides the required interface and helpful structure.
    Replace the TODO sections with your own strategy implementation.
    """
    
    def __init__(self, team_id: str, valuation_vector: Dict[str, float], 
                 budget: float, opponent_teams: List[str]):
        """
        Initialize your agent at the start of each game.
        
        Args:
            team_id: Your unique team identifier (UUID string)
            valuation_vector: Dict mapping item_id to your valuation
                Example: {"item_0": 15.3, "item_1": 8.2, ..., "item_19": 12.7}
            budget: Initial budget (always 60)
            opponent_teams: List of opponent team IDs competing in the same arena
                Example: ["Team_A", "Team_B", "Team_C", "Team_D"]
                This helps you track and model each opponent's behavior separately
        
        Important:
            - This is called once at the start of each game
            - You can initialize any state variables here
            - Pre-compute anything that doesn't change during the game
            - Use opponent_teams to set up per-opponent tracking/modeling
        """
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
        self.total_rounds = 15  # Always 15 rounds per game
        
        # TODO: Add your custom state variables here
        # Examples:
        # self.price_history = []          # Track observed prices
        # self.opponent_wins = {opp: [] for opp in opponent_teams}  # Track which opponents win what
        # self.opponent_bids = {opp: [] for opp in opponent_teams}  # Infer opponent bidding patterns
        # self.beliefs = {opp: {} for opp in opponent_teams}        # Bayesian beliefs per opponent
        # self.high_value_threshold = 12.0  # Classify items
        # self.low_value_threshold = 8.0
        self.rounds_completed = 0
        self.total_rounds = 15
        
        # TODO: Pre-compute any strategy parameters
        # Examples:
        # self.avg_valuation = sum(valuation_vector.values()) / len(valuation_vector)
        # self.max_valuation = max(valuation_vector.values())
        # self.min_valuation = min(valuation_vector.values())
        self.remaining_vals = list(valuation_vector.values())
        self.opponents_budgets = {opp: 60.0 for opp in opponent_teams}
        self.high_items_seen = 0
        self.market_aggressiveness = 1.0

    def _update_available_budget(self, item_id: str, winning_team: str, 
                                 price_paid: float):
        """
        Internal method to update budget after auction.
        DO NOT MODIFY - This is called automatically by the system.
        
        Args:
            item_id: ID of the auctioned item
            winning_team: ID of the winning team
            price_paid: Price paid by winner
        """
        if winning_team == self.team_id:
            self.budget -= price_paid
            self.items_won.append(item_id)
    
    def update_after_each_round(self, item_id: str, winning_team: str, 
                                price_paid: float):
        """
        Called after each auction round with public information.
        Use this to update your beliefs, opponent models, and strategy.
        
        Args:
            item_id: The item that was just auctioned
            winning_team: Team ID of the winner (empty string if no winner)
            price_paid: Price the winner paid (second-highest bid)
        
        What you learn:
            - Which item was sold
            - Who won it
            - What price they paid (second-highest bid)
        
        What you DON'T learn:
            - All individual bids
            - Other teams' valuations
        
        Returns:
            True if update successful (required by system)
        """
        # System updates (DO NOT REMOVE)
        self._update_available_budget(item_id, winning_team, price_paid)
        
        if winning_team == self.team_id:
            self.utility += (self.valuation_vector[item_id] - price_paid)
        
        self.rounds_completed += 1
        
        # TODO: Implement your learning/adaptation logic here
        # Examples:
        if winning_team in self.opponents_budgets:
            self.opponents_budgets[winning_team] = max(0.0, self.opponents_budgets[winning_team] - price_paid)
        # Track price history
        # if price_paid > 0:
        #     self.price_history.append(price_paid)
        item_val = self.valuation_vector[item_id]
        if item_val in self.remaining_vals:
            self.remaining_vals.remove(item_val)
        # Track opponent performance
        # if winning_team and winning_team != self.team_id:
        #     self.opponent_wins[winning_team] = \
        #         self.opponent_wins.get(winning_team, 0) + 1
        if price_paid > 11:
            self.high_items_seen += 1
        # Update beliefs about market competitiveness
        # if self.price_history:
        #     self.avg_market_price = sum(self.price_history) / len(self.price_history)
        if item_val > 0:
            ratio = price_paid / item_val
            if ratio > 0.85:
                self.market_aggressiveness = 1.2
            elif ratio < 0.4:
                self.market_aggressiveness = 0.8 
        
        
        # Bayesian belief updates
        # if winning_team and price_paid > 0:
        #     # Update beliefs about winner's valuation
        #     # They bid at least price_paid + epsilon
        #     pass
        
        return True
    
    def bidding_function(self, item_id: str) -> float:
        """
        MAIN METHOD: Decide how much to bid for the current item.
        This is called once per auction round.
        
        Args:
            item_id: The item being auctioned (e.g., "item_7")
        
        Returns:
            float: Your bid amount
                - Must be >= 0
                - Should be <= your current budget
                - Bids over budget are automatically capped
                - Return 0 to not bid
        
        Important:
            - You have 2 seconds maximum to return
            - Timeout or error = bid of 0
            - This is a SECOND-PRICE auction: winner pays second-highest bid
            - Budget does NOT carry over between games
        
        Strategy Considerations:
            1. Budget Management: How much to spend now vs save for later?
            2. Item Value: Is this item worth competing for?
            3. Competition: How competitive will this auction be?
            4. Game Progress: Are we early or late in the game?
        """
        # Get your valuation for this item
        my_valuation = self.valuation_vector.get(item_id, 0)
        
        # Early exit if no value or no budget
        if my_valuation <= 0 or self.budget <= 0:
            return 0.0
        
        # Calculate rounds remaining
        rounds_remaining = self.total_rounds - self.rounds_completed
        if rounds_remaining <= 0:
            return 0.0
        
        # ============================================================
        # TODO: IMPLEMENT YOUR BIDDING STRATEGY HERE
        # ============================================================
        if my_valuation < 3 and rounds_remaining > 3:
            return my_valuation
        avg_future = sum(self.remaining_vals) / len(self.remaining_vals) if self.remaining_vals else 5
        is_good_opportunity = my_valuation > avg_future
        likely_common_high = False
        if my_valuation > 14 and self.high_items_seen < 6:
            likely_common_high = True
        bid = 0.0
        
        if likely_common_high:
            bid = my_valuation * 0.55 
            
        elif is_good_opportunity:
            base_aggression = 0.85 
            if self.market_aggressiveness < 1.0:
                base_aggression = 0.75
            
            bid = my_valuation * base_aggression
            
        else:
            bid = my_valuation * 0.4

        if self.opponents_budgets:
            richest_opponent_budget = max(self.opponents_budgets.values())
            smart_cap = richest_opponent_budget + 1.1 
            bid = min(bid, smart_cap)
        bid = min(bid, self.budget)
        bid = min(bid, my_valuation)
        # Example Strategy 1: Simple Truthful Bidding
        # bid = my_valuation
        
        # Example Strategy 2: Budget Pacing
        # budget_per_round = self.budget / rounds_remaining
        # bid = min(my_valuation, budget_per_round * 1.5)
        
        # Example Strategy 3: Value-Based Shading
        # if my_valuation > 12:
        #     bid = my_valuation * 0.9  # High value: bid aggressively
        # elif my_valuation > 8:
        #     bid = my_valuation * 0.7  # Medium value: bid moderately
        # else:
        #     bid = my_valuation * 0.5  # Low value: bid conservatively
        
        # Example Strategy 4: Adaptive Based on Observations
        # if hasattr(self, 'price_history') and self.price_history:
        #     avg_price = sum(self.price_history) / len(self.price_history)
        #     if my_valuation > avg_price * 1.2:
        #         bid = my_valuation * 0.85  # Competitive item
        #     else:
        #         bid = my_valuation * 0.6   # Less competitive
        # else:
        #     bid = my_valuation * 0.7
        
        # Example Strategy 5: End-Game Aggression
        # progress = self.rounds_completed / self.total_rounds
        # if progress > 0.7:  # Last 30% of game
        #     bid = my_valuation * 0.9  # More aggressive
        # else:
        #     bid = my_valuation * 0.7
        
        # PLACEHOLDER: Simple truthful bidding (REPLACE THIS!)
        # Bid 80% of valuation
        if rounds_remaining <= 3:
            if self.budget >= my_valuation:
                bid = my_valuation
            else:
                bid = self.budget
        # ============================================================
        # END OF STRATEGY IMPLEMENTATION
        # ============================================================
        
        # Ensure bid is valid (non-negative and within budget)
        bid = max(0.0, min(bid, self.budget))
        
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
