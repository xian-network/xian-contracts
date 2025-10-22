ZERO = decimal('0')
BURN_RATE = decimal('0.02')
REFLECTION_RATE = decimal('0.03')

BURN_ADDRESS = "0" * 64

balances = Hash(default_value=ZERO)  # Reflected balances for included addresses
t_balances = Hash(default_value=ZERO)  # True balances for excluded addresses
metadata = Hash()
excluded = Hash(default_value=False)
r_total = Variable(default_value=ZERO)  # Reflected total supply
t_total = Variable(default_value=ZERO)  # True total supply
approved = Hash(default_value=ZERO)
fee_exempt = Hash(default_value=False)


def to_decimal(value):
    if value is None:
        return ZERO
    if isinstance(value, str):
        return decimal(value)
    return decimal(str(value))


def get_rate():
    true_total = to_decimal(t_total.get())
    assert true_total > ZERO, 'Total supply exhausted'
    return to_decimal(r_total.get()) / true_total


@construct
def seed():
    initial_supply = decimal('100000000')
    r_total.set(initial_supply)
    t_total.set(initial_supply)
    balances[ctx.caller] = initial_supply

    excluded[ctx.this] = True
    excluded[BURN_ADDRESS] = True
    t_balances[BURN_ADDRESS] = ZERO

    fee_exempt[ctx.this] = True
    fee_exempt[BURN_ADDRESS] = True

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
def transfer(amount: float, to: str):
    amount_value = to_decimal(amount)
    assert amount_value > ZERO, 'Cannot send negative balances!'

    from_excluded = excluded[ctx.caller]
    to_excluded = excluded[to]
    skip_fees = fee_exempt[ctx.caller] or fee_exempt[to]

    rate = get_rate()
    reflected_amount = amount_value * rate

    if from_excluded:
        assert to_decimal(t_balances[ctx.caller]) >= amount_value, 'Not enough coins to send!'
        t_balances[ctx.caller] = to_decimal(t_balances[ctx.caller]) - amount_value
    else:
        assert to_decimal(balances[ctx.caller]) >= reflected_amount, 'Not enough coins to send!'
        balances[ctx.caller] = to_decimal(balances[ctx.caller]) - reflected_amount

    burn_amount = ZERO
    reflection_amount = ZERO
    transfer_amount = amount_value

    if not skip_fees:
        burn_amount = amount_value * BURN_RATE
        reflection_amount = amount_value * REFLECTION_RATE
        transfer_amount = amount_value - burn_amount - reflection_amount

    if from_excluded:
        if to_excluded:
            t_balances[to] = to_decimal(t_balances[to]) + transfer_amount
        else:
            balances[to] = to_decimal(balances[to]) + transfer_amount * rate
    else:
        if to_excluded:
            t_balances[to] = to_decimal(t_balances[to]) + transfer_amount
        else:
            balances[to] = to_decimal(balances[to]) + transfer_amount * rate

    if not skip_fees:
        t_balances[BURN_ADDRESS] = to_decimal(t_balances[BURN_ADDRESS]) + burn_amount

        true_total = to_decimal(t_total.get())
        reflected_total = to_decimal(r_total.get())

        t_total.set(true_total - burn_amount)
        r_total.set(reflected_total - (burn_amount + reflection_amount) * rate)

    return f"Transferred {amount_value}"


@export
def approve(amount: float, to: str):
    amount_value = to_decimal(amount)
    assert amount_value >= ZERO, 'Cannot approve negative balances!'
    approved[ctx.caller, to] = amount_value
    return f"Approved {amount_value} for {to}"


@export
def transfer_from(amount: float, to: str, main_account: str):
    amount_value = to_decimal(amount)
    assert amount_value > ZERO, 'Cannot send negative balances!'

    spender_allowance = to_decimal(approved[main_account, ctx.caller])
    assert spender_allowance >= amount_value, 'Not enough coins approved!'

    from_excluded = excluded[main_account]
    to_excluded = excluded[to]
    skip_fees = fee_exempt[main_account] or fee_exempt[to]

    rate = get_rate()
    reflected_amount = amount_value * rate

    if from_excluded:
        assert to_decimal(t_balances[main_account]) >= amount_value, 'Not enough coins!'
        t_balances[main_account] = to_decimal(t_balances[main_account]) - amount_value
    else:
        assert to_decimal(balances[main_account]) >= reflected_amount, 'Not enough coins!'
        balances[main_account] = to_decimal(balances[main_account]) - reflected_amount

    burn_amount = ZERO
    reflection_amount = ZERO
    transfer_amount = amount_value

    if not skip_fees:
        burn_amount = amount_value * BURN_RATE
        reflection_amount = amount_value * REFLECTION_RATE
        transfer_amount = amount_value - burn_amount - reflection_amount

    approved[main_account, ctx.caller] = spender_allowance - amount_value

    if from_excluded:
        if to_excluded:
            t_balances[to] = to_decimal(t_balances[to]) + transfer_amount
        else:
            balances[to] = to_decimal(balances[to]) + transfer_amount * rate
    else:
        if to_excluded:
            t_balances[to] = to_decimal(t_balances[to]) + transfer_amount
        else:
            balances[to] = to_decimal(balances[to]) + transfer_amount * rate

    if not skip_fees:
        t_balances[BURN_ADDRESS] = to_decimal(t_balances[BURN_ADDRESS]) + burn_amount

        true_total = to_decimal(t_total.get())
        reflected_total = to_decimal(r_total.get())

        t_total.set(true_total - burn_amount)
        r_total.set(reflected_total - (burn_amount + reflection_amount) * rate)

    return f"Sent {amount_value} to {to} from {main_account}"


@export
def balance_of(address: str):
    if excluded[address]:
        return to_decimal(t_balances[address])

    rate = get_rate()
    if rate == ZERO:
        return ZERO
    return to_decimal(balances[address]) / rate


@export
def allowance(owner: str, spender: str):
    return to_decimal(approved[owner, spender])


@export
def get_total_supply():
    return to_decimal(t_total.get())


@export
def exclude_from_rewards(address: str):
    assert ctx.caller == metadata['operator'], 'Only operator can exclude!'
    assert not excluded[address], 'Address already excluded!'

    excluded[address] = True
    token_amount = balance_of(address)
    balances[address] = ZERO
    t_balances[address] = token_amount


@export
def include_in_rewards(address: str):
    assert ctx.caller == metadata['operator'], 'Only operator can include!'
    assert excluded[address], 'Address not excluded!'

    token_amount = to_decimal(t_balances[address])
    rate = get_rate()

    excluded[address] = False
    t_balances[address] = ZERO
    balances[address] = token_amount * rate


@export
def set_fee_exempt(address: str, exempt: bool):
    assert ctx.caller == metadata['operator'], 'Only operator can change fee exemption!'
    fee_exempt[address] = exempt
