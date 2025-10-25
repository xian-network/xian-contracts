# Reflection Token (con_reflection_token)

A decimal‑native reflection token designed for Xian’s Python smart contract stack. Holders accrue reflections on every trade that touches a designated “fee target” (e.g., DEX pairs), while
wallet‑to‑wallet transfers remain fee-free.

## How It Works

- **Reflected vs. true balances**: Included addresses store “reflected” balances; excluded addresses hold true balances. `balance_of` converts automatically.
- **Fee routing**: Burn and reflection rates (default 2% + 3%) only apply when either party in `transfer` or `transfer_from` is marked as a fee target via `set_fee_target(address, enabled=True)`. Wallet
transfers bypass fees.
- **Reward exclusion**: `exclude_from_rewards(address)` moves an address to true-balance tracking (used for DEX pools). `include_in_rewards` reverses it.
- **Operator controls**: `metadata['operator']` (set in `seed`) can update metadata, toggle fee targets, and manage reward status.

## Deployment & Integration Steps

1. **Deploy the contract**  
Submit the content of `con_reflection_token.py` under your desired name (e.g., `con_refl`). The constructor mints the full supply to `ctx.caller`.

2. **Create the DEX pair (no liquidity yet)**  
Call `con_pairs.createPair(tokenA='currency', tokenB='con_refl_v2')` and record the returned pair ID.

3. **Configure the token before any liquidity touches the pair**  
Repeat for every new pair/router you add.
```python
con_refl_v2.exclude_from_rewards('con_pairs')          # keeps pools out of reflections
con_refl_v2.set_fee_target('con_pairs', True)          # charges fees on pool interactions
con_refl_v2.set_fee_target('con_dex_v2', True)         # optional but covers router legs
```

4. **Approve the router and add liquidity**  
```python
con_refl_v2.approve(amount=..., to='con_dex_v2')
currency.approve(amount=..., to='con_dex_v2')

deadline = to_contract_time(datetime.utcnow() + timedelta(minutes=10))

con_dex_v2.addLiquidity(
    tokenA='currency',
    tokenB='con_refl_v2',
    amountADesired=...,
    amountBDesired=...,
    amountAMin=...,
    amountBMin=...,
    to='lp',
    deadline=deadline,
    signer=lp
)
```
5. **Trade with realistic slippage**  
Because the pool uses fee-on-transfer logic, the slippage on the DEX contract `con_dex_v2` needs to be set to at least 5% (if you stay with the default burn and reflection values) to avoid the DEX error `SNAKX: INSUFFICIENT_OUTPUT_AMOUNT`.

## Customizing for Your Token

- Supply & metadata: Edit seed() (initial_supply, symbol/name/logo fields) to match your project.
- Fee rates: Adjust BURN_RATE and REFLECTION_RATE (Contracting decimals). Ensure sum <= 1.
- Distribution logic: Modify seed() to split initial supply across addresses if desired.
- Additional fee targets: Call set_fee_target(<address>, True) for any contract that should trigger reflections (OTC escrows, other routers, etc.).

When cloning the pattern, keep the workflow order intact: deploy → create pair → configure fee targets/exclusions → approve → add liquidity. That guarantees the pool never records taxed transfers before it’s protected, preventing the token0_neg invariant errors.

## Troubleshooting

- SNAKX: token0_neg: Means the pool saw fees before configuration. Spin up a new pair (fresh token name), apply steps 2–4 before adding liquidity.
- SNAKX: INSUFFICIENT_OUTPUT_AMOUNT: Your amountOutMin is higher than the quoted output. Re-read reserves (getReserves or getAmountsOut) and lower the minimum or increase slippage.
- Wallet transfers not accruing reflections: Reflections only accrue when a fee target participates. Regular holders need trades (buys/sells) to see balances change.

With that order and configuration, the contract trades flawlessly on the Xian DEX while preserving reflection rewards for actual market activity.
