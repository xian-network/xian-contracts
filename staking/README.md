# Multi-Token Staking Contract

A comprehensive, flexible staking contract that allows any token project to create customizable staking pools with time-locked rewards, penalties, and entry fees.

## Features

### Core Functionality
- **Multi-token support**: Any ERC-20 compatible token can create staking pools
- **Fixed rewards per position**: Predetermined reward amounts distributed proportionally over lock duration
- **Flexible lock periods**: Customizable staking duration in seconds
- **Capacity controls**: Set maximum number of staking positions per pool
- **Scheduled start dates**: Pools can start immediately or at future timestamps

### Economic Controls
- **Configurable APY**: Set annual percentage yield for reward calculations
- **Early withdrawal penalties**: Time-based penalties for premature unstaking
- **Entry fees**: Optional fees in any token for pool access
- **Creator revenue sharing**: Pool creators collect entry fees and penalties

### Security & Emergency Features
- **Emergency pause**: Contract owner can halt all operations
- **Emergency withdrawal**: Owner can recover tokens when paused
- **Access controls**: Role-based permissions for different operations
- **Reentrancy protection**: Secure state management patterns

## Contract Architecture

### State Variables
- `pools`: Pool configurations indexed by pool ID
- `stakes`: Individual stake records indexed by (pool_id, staker)
- `pool_stats`: Real-time statistics for each pool
- `pool_counter`: Auto-incrementing pool ID counter
- `paused`: Emergency pause state
- `contract_owner`: Emergency function access control

### Events
- `PoolCreated`: Emitted when new staking pool is created
- `Stake`: Emitted when user stakes tokens
- `Unstake`: Emitted when user withdraws stake and rewards

## Usage

### Creating a Staking Pool

```python
pool_id = staking_contract.create_pool(
    stake_token='con_my_token',          # Token users stake
    reward_token='con_reward_token',     # Token for rewards
    apy=15.0,                            # 15% annual yield
    lock_duration=2592000,               # 30 days in seconds
    max_positions=1000,                  # Maximum stakers
    stake_amount=100.0,                  # Fixed stake amount
    start_date=None,                     # Start immediately
    early_withdrawal_enabled=True,       # Allow early exit
    penalty_rate=0.1,                    # 10% penalty for early exit
    entry_fee_amount=5.0,                # Entry fee amount
    entry_fee_token='con_fee_token'      # Entry fee token
)
```

### Staking Tokens

```python
# User must approve tokens first
stake_token.approve(amount=100.0, to='con_staking_contract')
fee_token.approve(amount=5.0, to='con_staking_contract')

# Stake in pool
staking_contract.stake(pool_id='0')
```

### Withdrawing Stakes

```python
# Withdraw after lock period (no penalty)
staking_contract.unstake(pool_id='0')

# Early withdrawal (with penalty if enabled)
staking_contract.unstake(pool_id='0')  # Penalty automatically calculated
```

### Pool Management

```python
# Deposit rewards for distribution
reward_token.approve(amount=1000.0, to='con_staking_contract')
staking_contract.deposit_rewards(pool_id='0', amount=1000.0)

# Withdraw creator fees and penalties
staking_contract.withdraw_creator_fees(pool_id='0')
```

## Function Reference

### Pool Creation
- `create_pool()`: Create new staking pool with custom parameters
- `deposit_rewards()`: Add reward tokens to pool for distribution

### Staking Operations  
- `stake()`: Join staking pool with required tokens
- `unstake()`: Exit pool and claim proportional rewards
- `calculate_rewards()`: Preview potential rewards and penalties

### Information Queries
- `get_pool_info()`: Retrieve pool configuration and statistics
- `get_stake_info()`: Get individual stake details
- `get_contract_status()`: Check contract state and ownership

### Pool Creator Functions
- `withdraw_creator_fees()`: Collect entry fees and penalties

### Emergency Functions (Owner Only)
- `emergency_pause()`: Halt all contract operations
- `emergency_unpause()`: Resume normal operations  
- `emergency_withdraw_token()`: Recover tokens when paused

## Economic Model

### Reward Calculation
Rewards are calculated using time-proportional distribution:

```
max_reward = stake_amount × (apy / 100)
actual_reward = max_reward × (time_staked / lock_duration)
```

### Early Withdrawal Penalty
Penalties are calculated based on remaining lock time:

```
penalty_factor = time_remaining / lock_duration
penalty = stake_amount × penalty_rate × penalty_factor
```

### Revenue Streams for Pool Creators
1. **Entry fees**: Collected from each new staker
2. **Early withdrawal penalties**: Portion of penalized stakes
3. **Unclaimed rewards**: Rewards from early exits

## Security Considerations

### Access Controls
- Pool creation: Open to any address
- Staking: Requires token approval and available positions
- Unstaking: Only stake owner can withdraw
- Creator functions: Only pool creator
- Emergency functions: Only contract owner

### State Protection
- No compound assignment operators (prevents compilation issues)
- Explicit state updates with verification
- Hash-based key validation for multi-dimensional storage
- Event emission for all state changes

### Edge Case Handling
- Zero amounts blocked where inappropriate
- Past start dates rejected
- Capacity limits enforced
- Reentrancy protection through proper state management

## Deployment

### Prerequisites
- Contracting framework environment
- Token contracts for staking, rewards, and fees
- Sufficient gas/stamps for deployment

### Deployment Steps
1. Deploy token contracts if needed
2. Submit staking contract to network
3. Initialize with desired owner address
4. Test with small amounts before full deployment

### Environment Setup
```python
from contracting.client import ContractingClient

# Initialize client
client = ContractingClient()

# Submit contract
with open('con_staking.py') as f:
    contract_code = f.read()
client.submit(contract_code, name='con_staking')

# Get contract instance
staking = client.get_contract('con_staking')
```

## Testing

The contract includes comprehensive test coverage for:
- All core functionality paths
- Parameter validation and edge cases
- Authorization and security controls
- Multi-pool and multi-user scenarios
- Time-based reward calculations
- Emergency function behaviors

Run tests with:
```bash
python con_staking_tests.py
```

## Examples

### Basic Staking Pool
```python
# 30-day pool with 12% APY, no penalties
pool_id = contract.create_pool(
    stake_token='con_token',
    reward_token='con_token', 
    apy=12.0,
    lock_duration=2592000,
    max_positions=500,
    stake_amount=1000.0
)
```

### High-Yield Pool with Penalties
```python
# 90-day pool with 25% APY and 15% early exit penalty
pool_id = contract.create_pool(
    stake_token='con_token',
    reward_token='con_rewards',
    apy=25.0,
    lock_duration=7776000,
    max_positions=100,
    stake_amount=5000.0,
    early_withdrawal_enabled=True,
    penalty_rate=0.15
)
```

### Premium Pool with Entry Fee
```python
# Exclusive pool with entry barrier
pool_id = contract.create_pool(
    stake_token='con_premium_token',
    reward_token='con_bonus_rewards',
    apy=30.0,
    lock_duration=15552000,  # 6 months
    max_positions=50,
    stake_amount=10000.0,
    entry_fee_amount=100.0,
    entry_fee_token='con_access_token'
)
```
