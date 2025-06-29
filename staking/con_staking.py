# General Multi-Token Staking Contract
# State Variables
pools = Hash()  # pool_id -> pool configuration
stakes = Hash()  # (pool_id, staker) -> stake info
pool_counter = Variable()
paused = Variable()
contract_owner = Variable()
pool_stats = Hash()  # pool_id -> stats (total_staked, current_positions)

# Events
PoolCreatedEvent = LogEvent(
    event="PoolCreated",
    params={
        "pool_id": {"type": str, "idx": True},
        "creator": {"type": str, "idx": True},
        "stake_token": {"type": str, "idx": True},
        "reward_token": {"type": str},
        "apy": {"type": (int, float)},
        "lock_duration": {"type": int},
        "max_positions": {"type": int}
    }
)

StakeEvent = LogEvent(
    event="Stake",
    params={
        "pool_id": {"type": str, "idx": True},
        "staker": {"type": str, "idx": True},
        "amount": {"type": (int, float)},
        "entry_fee": {"type": (int, float)}
    }
)

UnstakeEvent = LogEvent(
    event="Unstake",
    params={
        "pool_id": {"type": str, "idx": True},
        "staker": {"type": str, "idx": True},
        "amount": {"type": (int, float)},
        "rewards": {"type": (int, float)},
        "penalty": {"type": (int, float)},
        "early": {"type": bool}
    }
)

@construct
def init():
    pool_counter.set(0)
    paused.set(False)
    contract_owner.set(ctx.caller)

@export
def create_pool(
    stake_token: str,
    reward_token: str,
    apy: float,
    lock_duration: int,  # seconds
    max_positions: int,
    stake_amount: float,
    start_date: int = None,  # timestamp, None for immediate
    early_withdrawal_enabled: bool = True,
    penalty_rate: float = 0.1,  # 10% default penalty
    entry_fee_amount: float = 0.0,
    entry_fee_token: str = None
):
    assert not paused.get(), "Contract is paused"
    assert apy >= 0.0, "APY must be non-negative"
    assert lock_duration > 0, "Lock duration must be positive"
    assert max_positions > 0, "Max positions must be positive"
    assert stake_amount > 0.0, "Stake amount must be positive"
    assert penalty_rate >= 0.0 and penalty_rate <= 1.0, "Penalty rate must be 0-100%"
    
    if start_date is None:
        start_date = int(now.timestamp())
    else:
        assert start_date >= int(now.timestamp()), "Start date cannot be in the past"
    
    if entry_fee_amount > 0.0:
        assert entry_fee_token is not None, "Entry fee token must be specified"
    
    pool_id = str(pool_counter.get())
    pool_counter.set(pool_counter.get() + 1)
    
    pools[pool_id] = {
        "creator": ctx.caller,
        "stake_token": stake_token,
        "reward_token": reward_token,
        "apy": apy,
        "lock_duration": lock_duration,
        "max_positions": max_positions,
        "stake_amount": stake_amount,
        "start_date": start_date,
        "early_withdrawal_enabled": early_withdrawal_enabled,
        "penalty_rate": penalty_rate,
        "entry_fee_amount": entry_fee_amount,
        "entry_fee_token": entry_fee_token,
        "total_rewards_deposited": 0.0,
        "creator_fees_collected": 0.0,
        "creator_penalties_collected": 0.0
    }
    
    pool_stats[pool_id] = {
        "total_staked": 0.0,
        "current_positions": 0
    }
    
    PoolCreatedEvent({
        "pool_id": pool_id,
        "creator": ctx.caller,
        "stake_token": stake_token,
        "reward_token": reward_token,
        "apy": apy,
        "lock_duration": lock_duration,
        "max_positions": max_positions
    })
    
    return pool_id

@export
def stake(pool_id: str):
    assert not paused.get(), "Contract is paused"
    assert pool_id in pools, "Pool does not exist"
    
    pool = pools[pool_id]
    stats = pool_stats[pool_id]
    
    assert int(now.timestamp()) >= pool["start_date"], "Pool has not started yet"
    assert stats["current_positions"] < pool["max_positions"], "Pool is full"
    assert (pool_id, ctx.caller) not in stakes, "Already staking in this pool"
    
    # Handle entry fee
    entry_fee_paid = 0.0
    if pool["entry_fee_amount"] > 0.0:
        fee_token = importlib.import_module(pool["entry_fee_token"])
        fee_token.transfer_from(
            amount=pool["entry_fee_amount"],
            to=ctx.this,
            main_account=ctx.caller
        )
        entry_fee_paid = pool["entry_fee_amount"]
        
        # Track fees for creator withdrawal
        pool["creator_fees_collected"] += entry_fee_paid
        pools[pool_id] = pool
    
    # Transfer stake tokens
    stake_token = importlib.import_module(pool["stake_token"])
    stake_token.transfer_from(
        amount=pool["stake_amount"],
        to=ctx.this,
        main_account=ctx.caller
    )
    
    # Record stake
    stakes[pool_id, ctx.caller] = {
        "amount": pool["stake_amount"],
        "start_time": int(now.timestamp()),
        "entry_fee_paid": entry_fee_paid
    }
    
    # Update stats
    stats["total_staked"] += pool["stake_amount"]
    stats["current_positions"] += 1
    pool_stats[pool_id] = stats
    
    StakeEvent({
        "pool_id": pool_id,
        "staker": ctx.caller,
        "amount": pool["stake_amount"],
        "entry_fee": entry_fee_paid
    })

@export
def unstake(pool_id: str):
    assert not paused.get(), "Contract is paused"
    assert pool_id in pools, "Pool does not exist"
    assert (pool_id, ctx.caller) in stakes, "Not staking in this pool"
    
    pool = pools[pool_id]
    stake_info = stakes[pool_id, ctx.caller]
    stats = pool_stats[pool_id]
    
    current_time = int(now.timestamp())
    stake_start = stake_info["start_time"]
    time_staked = current_time - stake_start
    
    # Calculate if early withdrawal
    is_early = time_staked < pool["lock_duration"]
    
    if is_early:
        assert pool["early_withdrawal_enabled"], "Early withdrawal not allowed"
    
    # Calculate rewards (8 decimal precision)
    max_reward = round((stake_info["amount"] * pool["apy"] / 100.0), 8)
    
    if is_early:
        # Proportional rewards based on time staked
        reward_earned = round(max_reward * time_staked / pool["lock_duration"], 8)
    else:
        reward_earned = max_reward
    
    # Calculate penalty
    penalty = 0.0
    if is_early and pool["penalty_rate"] > 0.0:
        time_remaining = pool["lock_duration"] - time_staked
        penalty_factor = time_remaining / pool["lock_duration"]
        penalty = round(stake_info["amount"] * pool["penalty_rate"] * penalty_factor, 8)
        
        # Track penalty for creator withdrawal
        pool["creator_penalties_collected"] += penalty
        pools[pool_id] = pool
    
    # Calculate final amounts
    stake_return = stake_info["amount"] - penalty
    
    # Transfer stake tokens back (minus penalty)
    if stake_return > 0.0:
        stake_token = importlib.import_module(pool["stake_token"])
        stake_token.transfer(amount=stake_return, to=ctx.caller)
    
    # Transfer rewards
    if reward_earned > 0.0:
        reward_token = importlib.import_module(pool["reward_token"])
        reward_token.transfer(amount=reward_earned, to=ctx.caller)
    
    # Update stats
    stats["total_staked"] -= stake_info["amount"]
    stats["current_positions"] -= 1
    pool_stats[pool_id] = stats
    
    # Remove stake record
    del stakes[pool_id, ctx.caller]
    
    UnstakeEvent({
        "pool_id": pool_id,
        "staker": ctx.caller,
        "amount": stake_return,
        "rewards": reward_earned,
        "penalty": penalty,
        "early": is_early
    })

@export
def deposit_rewards(pool_id: str, amount: float):
    assert pool_id in pools, "Pool does not exist"
    
    pool = pools[pool_id]
    assert ctx.caller == pool["creator"], "Only pool creator can deposit rewards"
    assert amount > 0.0, "Amount must be positive"
    
    # Transfer reward tokens to contract
    reward_token = importlib.import_module(pool["reward_token"])
    reward_token.transfer_from(
        amount=amount,
        to=ctx.this,
        main_account=ctx.caller
    )
    
    # Update pool rewards
    pool["total_rewards_deposited"] += amount
    pools[pool_id] = pool

@export
def withdraw_creator_fees(pool_id: str):
    assert pool_id in pools, "Pool does not exist"
    
    pool = pools[pool_id]
    assert ctx.caller == pool["creator"], "Only pool creator can withdraw fees"
    
    total_fees = pool["creator_fees_collected"]
    total_penalties = pool["creator_penalties_collected"]
    
    # Withdraw entry fees
    if total_fees > 0.0 and pool["entry_fee_token"] is not None:
        fee_token = importlib.import_module(pool["entry_fee_token"])
        fee_token.transfer(amount=total_fees, to=ctx.caller)
        pool["creator_fees_collected"] = 0.0
    
    # Withdraw penalties (in stake token)
    if total_penalties > 0.0:
        stake_token = importlib.import_module(pool["stake_token"])
        stake_token.transfer(amount=total_penalties, to=ctx.caller)
        pool["creator_penalties_collected"] = 0.0
    
    pools[pool_id] = pool

@export
def get_pool_info(pool_id: str):
    assert pool_id in pools, "Pool does not exist"
    pool_info = pools[pool_id]
    stats = pool_stats[pool_id]
    
    return {
        "config": pool_info,
        "stats": stats
    }

@export
def get_stake_info(pool_id: str, staker: str):
    assert (pool_id, staker) in stakes, "Stake not found"
    return stakes[pool_id, staker]

@export
def calculate_rewards(pool_id: str, staker: str):
    assert pool_id in pools, "Pool does not exist"
    assert (pool_id, staker) in stakes, "Not staking in this pool"
    
    pool = pools[pool_id]
    stake_info = stakes[pool_id, staker]
    
    current_time = int(now.timestamp())
    time_staked = current_time - stake_info["start_time"]
    is_early = time_staked < pool["lock_duration"]
    
    # Calculate potential rewards
    max_reward = round((stake_info["amount"] * pool["apy"] / 100.0), 8)
    
    if is_early:
        current_reward = round(max_reward * time_staked / pool["lock_duration"], 8)
    else:
        current_reward = max_reward
    
    # Calculate potential penalty
    penalty = 0.0
    if is_early and pool["penalty_rate"] > 0.0:
        time_remaining = pool["lock_duration"] - time_staked
        penalty_factor = time_remaining / pool["lock_duration"]
        penalty = round(stake_info["amount"] * pool["penalty_rate"] * penalty_factor, 8)
    
    return {
        "current_reward": current_reward,
        "max_reward": max_reward,
        "potential_penalty": penalty,
        "time_staked": time_staked,
        "time_remaining": max(0, pool["lock_duration"] - time_staked),
        "is_early": is_early
    }

# Emergency functions (contract owner only)
@export
def emergency_pause():
    assert ctx.caller == contract_owner.get(), "Only contract owner can pause"
    paused.set(True)

@export
def emergency_unpause():
    assert ctx.caller == contract_owner.get(), "Only contract owner can unpause"
    paused.set(False)

@export
def emergency_withdraw_token(token_contract: str, amount: float):
    assert ctx.caller == contract_owner.get(), "Only contract owner can emergency withdraw"
    assert paused.get(), "Contract must be paused for emergency withdrawal"
    
    token = importlib.import_module(token_contract)
    token.transfer(amount=amount, to=ctx.caller)

@export
def get_contract_status():
    return {
        "paused": paused.get(),
        "owner": contract_owner.get(),
        "total_pools": pool_counter.get()
    }
