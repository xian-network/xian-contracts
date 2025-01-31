random.seed()

data = Hash(default_value='')


@export
def lottery_start(lottery_id: int, token_contract: str, total_amount: float):
    assert data[lottery_id] == '', 'Lottery with this ID already exists!'

    importlib.import_module(token_contract).transfer_from(
        main_account=ctx.caller,
        amount=total_amount,
        to=ctx.this
    )

    data[lottery_id] = lottery_id
    data[lottery_id, 'creator'] = ctx.caller
    data[lottery_id, 'contract'] = token_contract
    data[lottery_id, 'amount'] = total_amount
    data[lottery_id, 'state'] = 'ACTIVE'
    data[lottery_id, 'users'] = []


@export
def lottery_register(lottery_id: int):
    assert data[lottery_id] != '', f'Lottery with ID {lottery_id} does not exist!'
    assert data[lottery_id, 'creator'] != ctx.caller, 'Creator cannot participate!'
    assert ctx.caller not in data[lottery_id, 'users'], 'You are already registered!'
    assert data[lottery_id, 'state'] == 'ACTIVE', 'This lottery already ended!'

    users = data[lottery_id, 'users']
    users.append(ctx.caller)
    data[lottery_id, 'users'] = users

    return f'Added {ctx.caller}'


@export
def lottery_end(lottery_id: int):
    assert data[lottery_id] != '', f'Lottery with ID {lottery_id} does not exist!'
    assert data[lottery_id, 'creator'] == ctx.caller, 'You are not the creator!'
    assert data[lottery_id, 'state'] == 'ACTIVE', 'This lottery already ended!'

    users = data[lottery_id, 'users']

    if len(users) < 1:
        winner = data[lottery_id, 'creator']
    else:
        index = random.randint(0, len(users) - 1)
        winner = data[lottery_id, 'users'][index]

    importlib.import_module(data[lottery_id, 'contract']).transfer(
        amount=data[lottery_id, 'amount'],
        to=winner
    )

    data[lottery_id, 'state'] = 'FINISHED'

    return f'Winner {winner}'
