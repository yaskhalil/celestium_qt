# Boolean Network State Analysis Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement a Boolean state analysis module to map system indicators into bitsets and check for attractor states, providing a formal gating mechanism for trades.

**Architecture:**
- `BooleanStateSpace` class in `src/core/boolean_network.py`.
- `map_to_bits`: Maps context features (Polars DataFrame) to a bitset integer.
- `is_in_attractor`: Evaluates if a state belongs to the target set $A \subseteq \{0, 1\}^n$.
- Formal mathematical notation used for state transition definitions: $x_{t+1} = f(x_t)$.

**Tech Stack:** Python 3.12, Polars.

---

### Task 1: Setup and Test `map_to_bits`

**Files:**
- Create: `tests/test_boolean_network.py`

- [ ] **Step 1: Write the failing test for `map_to_bits`**

```python
import pytest
import polars as pl
from src.core.boolean_network import BooleanStateSpace

def test_map_to_bits_basic():
    # Context with indicators
    # Bit 0: price > sma_20
    # Bit 1: hurst > 0.5
    # Bit 2: adx > 25
    df = pl.DataFrame({
        "close": [105.0],
        "sma_20": [100.0],
        "hurst": [0.6],
        "adx": [30.0]
    })
    
    bss = BooleanStateSpace()
    state = bss.map_to_bits(df)
    
    # Expected: 
    # price > sma_20 (105 > 100) -> Bit 0 = 1
    # hurst > 0.5 (0.6 > 0.5) -> Bit 1 = 1
    # adx > 25 (30 > 25) -> Bit 2 = 1
    # Integer = 1*2^0 + 1*2^1 + 1*2^2 = 1 + 2 + 4 = 7
    assert state == 7

def test_map_to_bits_partial():
    df = pl.DataFrame({
        "close": [95.0],
        "sma_20": [100.0],
        "hurst": [0.6],
        "adx": [20.0]
    })
    
    bss = BooleanStateSpace()
    state = bss.map_to_bits(df)
    
    # Expected: 
    # price > sma_20 (95 > 100) -> Bit 0 = 0
    # hurst > 0.5 (0.6 > 0.5) -> Bit 1 = 1
    # adx > 25 (20 > 25) -> Bit 2 = 0
    # Integer = 0 + 2 + 0 = 2
    assert state == 2
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boolean_network.py -v`
Expected: FAIL (ModuleNotFoundError or ImportError)

- [ ] **Step 3: Commit initial test**

```bash
git add tests/test_boolean_network.py
git commit -m "test: add initial tests for BooleanStateSpace.map_to_bits"
```

### Task 2: Implement `BooleanStateSpace.map_to_bits`

**Files:**
- Create: `src/core/boolean_network.py`

- [ ] **Step 1: Implement the minimal code**

```python
import polars as pl

class BooleanStateSpace:
    """
    Handles mapping of continuous/statistical states to a discrete Boolean state space.
    """
    
    def map_to_bits(self, context: pl.DataFrame) -> int:
        """
        Map indicator states into a bitset integer.
        
        Mapping:
        - Bit 0: price > sma_20
        - Bit 1: hurst > 0.5
        - Bit 2: adx > 25
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
```

- [ ] **Step 2: Run test to verify it passes**

Run: `pytest tests/test_boolean_network.py -v`
Expected: PASS

- [ ] **Step 3: Commit implementation**

```bash
git add src/core/boolean_network.py
git commit -m "feat: implement BooleanStateSpace.map_to_bits"
```

### Task 3: Implement `is_in_attractor` and Formal Comments

**Files:**
- Modify: `src/core/boolean_network.py`
- Modify: `tests/test_boolean_network.py`

- [ ] **Step 1: Add failing test for `is_in_attractor`**

In `tests/test_boolean_network.py`:
```python
def test_is_in_attractor():
    bss = BooleanStateSpace()
    # target_attractors = {1, 3, 7}
    assert bss.is_in_attractor(1) is True
    assert bss.is_in_attractor(3) is True
    assert bss.is_in_attractor(7) is True
    assert bss.is_in_attractor(0) is False
    assert bss.is_in_attractor(2) is False
    assert bss.is_in_attractor(4) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `pytest tests/test_boolean_network.py -v`
Expected: FAIL (AttributeError: 'BooleanStateSpace' object has no attribute 'is_in_attractor')

- [ ] **Step 3: Implement `is_in_attractor` and add formal comments**

In `src/core/boolean_network.py`:
```python
    def is_in_attractor(self, state: int) -> bool:
        """
        Check if state belongs to target attractor set A.
        
        Formal Definition:
        Let S = {0, 1}^n be the state space.
        Let F: S -> S be the synchronous update function.
        A subset A ⊆ S is an attractor if F(A) = A.
        
        For this implementation, we define a static target attractor set A = {1, 3, 7}.
        """
        target_attractors = {1, 3, 7}
        return state in target_attractors
```

- [ ] **Step 4: Run test to verify it passes**

Run: `pytest tests/test_boolean_network.py -v`
Expected: PASS

- [ ] **Step 5: Finalize mathematical notation in comments**

Ensure the class docstring or methods contain formal notation as requested.

```python
"""
Boolean Network State Analysis

Formally, a Boolean Network is a pair (V, F) where:
- V = {x_1, ..., x_n} is a set of Boolean variables.
- F = {f_1, ..., f_n} is a set of Boolean functions f_i: {0,1}^n -> {0,1}.

The state of the network at time t is x(t) ∈ {0,1}^n.
The transition is defined by x_i(t+1) = f_i(x_1(t), ..., x_n(t)).
"""
```

- [ ] **Step 6: Commit and Verify**

```bash
git add src/core/boolean_network.py tests/test_boolean_network.py
git commit -m "feat: implement is_in_attractor and add formal math notation"
```
