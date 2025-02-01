balances = Hash(default_value=0)  # Reflected balances for included addresses
t_balances = Hash(default_value=0)  # True balances for excluded addresses
metadata = Hash()
excluded = Hash(default_value=False)
r_total = Variable()  # Reflected total supply
t_total = Variable()  # True total supply
approved = Hash(default_value=0)

BURN_BPS = 200  # 2% burn in basis points
REFLECTION_BPS = 300  # 3% reflection in basis points
TOTAL_BPS = 10000  # Total basis points (100%)

BURN_ADDRESS = "0" * 64

@construct
def seed():
    initial_supply = 100_000_000
    r_initial = initial_supply * 10**18  # Scale up for precision

    balances[ctx.caller] = r_initial
    r_total.set(r_initial)
    t_total.set(initial_supply)

    excluded[ctx.this] = True
    excluded[BURN_ADDRESS] = True
    t_balances[BURN_ADDRESS] = 0

    metadata['token_name'] = "REFLECT TOKEN"
    metadata['token_symbol'] = "RFT"
    metadata['token_logo_url'] = ""
    metadata['token_website'] = ""
    metadata['operator'] = ctx.caller

@export
def change_metadata(key: str, value: Any):
    assert ctx.caller == metadata['operator'], 'Only operator can change metadata!'
    metadata[key] = value

@export
def transfer(amount: int, to: str):
    assert amount > 0, 'Cannot send negative balances!'

    from_excluded = excluded[ctx.caller]
    to_excluded = excluded[to]

    rate = r_total.get() * TOTAL_BPS // t_total.get()

    if not from_excluded:
        assert balances[ctx.caller] >= amount * rate // TOTAL_BPS, 'Not enough coins to send!'
        r_amount = amount * rate // TOTAL_BPS
    else:
        assert t_balances[ctx.caller] >= amount, 'Not enough coins to send!'
        r_amount = amount * rate // TOTAL_BPS

    burn_amount = amount * BURN_BPS // TOTAL_BPS
    reflection_amount = amount * REFLECTION_BPS // TOTAL_BPS
    transfer_amount = amount - burn_amount - reflection_amount

    if from_excluded:
        if to_excluded:
            t_balances[ctx.caller] -= amount
            t_balances[to] += transfer_amount
            t_balances[BURN_ADDRESS] += burn_amount
        else:
            t_balances[ctx.caller] -= amount
            balances[to] += transfer_amount * rate // TOTAL_BPS
            t_balances[BURN_ADDRESS] += burn_amount
    else:
        if to_excluded:
            balances[ctx.caller] -= r_amount
            t_balances[to] += transfer_amount
            t_balances[BURN_ADDRESS] += burn_amount
        else:
            balances[ctx.caller] -= r_amount
            balances[to] += transfer_amount * rate // TOTAL_BPS
            t_balances[BURN_ADDRESS] += burn_amount

    t_total.set(t_total.get() - burn_amount)
    r_total.set(r_total.get() - (burn_amount + reflection_amount) * rate // TOTAL_BPS)

    return f"Transferred {amount}"

@export
def approve(amount: int, to: str):
    assert amount > 0, 'Cannot approve negative balances!'
    approved[ctx.caller, to] = amount
    return f"Approved {amount} for {to}"

@export
def transfer_from(amount: int, to: str, main_account: str):
    assert amount > 0, 'Cannot send negative balances!'
    assert approved[main_account, ctx.caller] >= amount, 'Not enough coins approved!'

    from_excluded = excluded[main_account]
    to_excluded = excluded[to]

    rate = r_total.get() * TOTAL_BPS // t_total.get()

    if not from_excluded:
        assert balances[main_account] >= amount * rate // TOTAL_BPS, 'Not enough coins!'
        r_amount = amount * rate // TOTAL_BPS
    else:
        assert t_balances[main_account] >= amount, 'Not enough coins!'
        r_amount = amount * rate // TOTAL_BPS

    burn_amount = amount * BURN_BPS // TOTAL_BPS
    reflection_amount = amount * REFLECTION_BPS // TOTAL_BPS
    transfer_amount = amount - burn_amount - reflection_amount

    approved[main_account, ctx.caller] -= amount

    if from_excluded:
        if to_excluded:
            t_balances[main_account] -= amount
            t_balances[to] += transfer_amount
            t_balances[BURN_ADDRESS] += burn_amount
        else:
            t_balances[main_account] -= amount
            balances[to] += transfer_amount * rate // TOTAL_BPS
            t_balances[BURN_ADDRESS] += burn_amount
    else:
        if to_excluded:
            balances[main_account] -= r_amount
            t_balances[to] += transfer_amount
            t_balances[BURN_ADDRESS] += burn_amount
        else:
            balances[main_account] -= r_amount
            balances[to] += transfer_amount * rate // TOTAL_BPS
            t_balances[BURN_ADDRESS] += burn_amount

    t_total.set(t_total.get() - burn_amount)
    r_total.set(r_total.get() - (burn_amount + reflection_amount) * rate // TOTAL_BPS)

    return f"Sent {amount} to {to} from {main_account}"

@export
def balance_of(address: str):
    if excluded[address]:
        return t_balances[address]
    return balances[address] * t_total.get() // r_total.get()

@export
def allowance(owner: str, spender: str):
    return approved[owner, spender]

@export
def get_total_supply():
    return t_total.get()

@export
def exclude_from_rewards(address: str):
    assert ctx.caller == metadata['operator'], 'Only operator can exclude!'
    assert not excluded[address], 'Address already excluded!'

    excluded[address] = True
    t_amount = balance_of(address)
    balances[address] = 0
    t_balances[address] = t_amount

@export
def include_in_rewards(address: str):
    assert ctx.caller == metadata['operator'], 'Only operator can include!'
    assert excluded[address], 'Address not excluded!'

    t_amount = t_balances[address]
    rate = r_total.get() * TOTAL_BPS // t_total.get()

    excluded[address] = False
    t_balances[address] = 0
    balances[address] = t_amount * rate // TOTAL_BPS
