import polars as pl

class BooleanStateSpace:
    """
    Handles mapping of continuous/statistical states to a discrete Boolean state space.
    
    Formally, a Boolean Network is a pair (V, F) where:
    - V = {x_1, ..., x_n} is a set of Boolean variables.
    - F = {f_1, ..., f_n} is a set of Boolean functions f_i: {0,1}^n -> {0,1}.

    The state of the network at time t is x(t) ∈ {0,1}^n.
    The transition is defined by x_i(t+1) = f_i(x_1(t), ..., x_n(t)).
    """
    
    def map_to_bits(self, context: pl.DataFrame) -> int:
        """
        Map indicator states into a bitset integer.
        
        Mapping:
        - Bit 0: price > sma_20 (x_0 = 1 if P > SMA_20 else 0)
        - Bit 1: hurst > 0.5    (x_1 = 1 if H > 0.5 else 0)
        - Bit 2: adx > 25       (x_2 = 1 if ADX > 25 else 0)
        
        Returns the integer representation: Σ x_i * 2^i
        """
        if context.is_empty():
            return 0
            
        row = context.row(0, named=True)
        state = 0
        
        if row.get("close", 0) > row.get("sma_20", 0):
            state |= (1 << 0)
        
        if row.get("hurst", 0) > 0.5:
            state |= (1 << 1)
            
        if row.get("adx", 0) > 25:
            state |= (1 << 2)
            
        return state
