import currency

manager = Variable()
names = Hash(default_value=False)
balances = Hash(default_value=0)
approvals = Hash(default_value=0)
expiry_times = Hash(default_value=None)
owners = Hash(default_value=None)

mint_price = Variable()
royalty_fee_percentage = Variable()
registration_period = Variable()
contracts_allowlist = Variable()
enabled = Variable()

main_name_to_address = Hash(default_value=None)
address_to_main_name = Hash(default_value=None)

BLACKLIST_NAMES = ["dao", "masternodes", "rewards", "submission", "currency", "foundation"]

@construct
def seed():
    manager.set(ctx.caller)
    enabled.set(False)
    contracts_allowlist.set([])
    mint_price.set(1)
    royalty_fee_percentage.set(2)
    registration_period.set(365)


# Helper functions

def assert_is_manager():
    assert ctx.caller == manager.get(), "You are not the manager"


def assert_is_owner(address: str, name: str):
    assert balances[address, name] == 1, "You are not the owner of this name"


def assert_if_contract_is_approved(contract: str):
    if "con_" in contract:
        assert contract in contracts_allowlist.get(), "This contract is not allowed to interact with this contract"


def assert_is_approved_for_transfer(main_account: str, to: str, name: str):
    assert approvals[main_account, to, name] == 1, "Name is not approved for transfer"


def assert_is_not_blacklisted(name: str):
    assert name not in BLACKLIST_NAMES, "Name is blacklisted"


def is_expired(name: str):
    expiry = expiry_times[name]
    if expiry is None:
        return False
    return now >= expiry


def assert_is_not_expired(name: str):
    assert not is_expired(name), "Name is expired"

def assert_is_enabled():
    assert enabled.get() == True, "Contract is not enabled"


# User functions

@export
def mint_name(name: str):
    assert_is_enabled()
    assert_if_contract_is_approved(ctx.caller)
    assert_is_not_blacklisted(name)

    name = name.lower()
    assert name.isalnum() and name.isascii(), "Name must be alphanumeric and ascii"
    assert len(name) >= 3, "The minimum length is 3 characters"
    assert len(name) <= 32, "The maximum length is 32 characters"  

    if owners[name]:
        assert is_expired(name), "Name already exists and has not expired yet."
        balances[owners[name], name] = 0

    currency.transfer_from(amount=mint_price.get(), to=manager.get(), main_account=ctx.caller)

    names[name] = {} # This is a place for data to be stored by the current owner.. DNS, IPFS, etc
    expiry_times[name] = now + datetime.timedelta(days=registration_period.get())
    balances[ctx.caller, name] = 1
    owners[name] = ctx.caller


@export
def transfer(name: str, to: str):
    assert_is_not_expired(name)
    assert to != ctx.caller, "You cannot transfer to yourself"
    assert name != "", "Please specify the Name you want to transfer"
    assert_is_owner(ctx.caller, name)

    balances[ctx.caller, name] = 0
    balances[to, name] = 1

    main_name_to_address[name] = None
    if get_address_to_main_name(ctx.caller) == name:
        address_to_main_name[ctx.caller] = None
    owners[name] = to
    approvals[ctx.caller, to, name] = 0


@export
def approve(name: str, to: str):
    assert_is_not_expired(name)
    assert_is_owner(ctx.caller, name)
    approvals[ctx.caller, to, name] = 1


@export
def revoke_approval(name: str, to: str):
    assert_is_not_expired(name)
    assert_is_owner(ctx.caller, name)
    approvals[ctx.caller, to, name] = 0


@export
def transfer_from(name: str, to: str, main_account: str):
    assert_if_contract_is_approved(ctx.caller)
    assert to != main_account, "You cannot transfer to yourself"
    assert name != "", "Please specify the Name you want to transfer"
    assert_is_not_expired(name)
    assert_is_owner(main_account, name)
    assert_is_approved_for_transfer(main_account, to, name)

    approvals[main_account, to, name] = 0
    balances[main_account, name] = 0
    balances[to, name] = 1

    main_name_to_address[name] = None
    if get_address_to_main_name(main_account) == name:
        address_to_main_name[main_account] = None
    owners[name] = to


@export
def set_main_name_to_caller(name: str):
    assert_is_not_expired(name)
    assert_is_owner(ctx.caller, name)

    if get_address_to_main_name(ctx.caller):
        main_name_to_address[get_address_to_main_name(ctx.caller)] = None

    main_name_to_address[name] = ctx.caller
    address_to_main_name[ctx.caller] = name


@export
def set_data(name: str, data: dict):
    assert_is_not_expired(name)
    assert_is_owner(ctx.caller, name)

    names[name] = data


@export
def get_main_name_to_address(name: str):
    address = main_name_to_address[name]
    if address is None or is_expired(name):
        return None
    return address


@export
def get_address_to_main_name(address: str):
    name = address_to_main_name[address]
    if name is None or is_expired(name):
        return None
    return name


@export
def get_owner(name: str):
    owner = owners[name]
    if owner is None or is_expired(name):
        return None
    return owner


@export
def get_expiry_time(name: str):
    return expiry_times[name]


@export
def get_data(name: str):
    return names[name]


@export
def is_owner(name: str, address: str):
    return balances[address, name] == 1 and not is_expired(name)


@export
def renew_name(name: str):
    assert_is_not_expired(name)
    assert_is_owner(ctx.caller, name)

    currency.transfer_from(amount=mint_price.get(), to=manager.get(), main_account=ctx.caller)

    expiry_times[name] = expiry_times[name] + datetime.timedelta(days=registration_period.get())

# Manager functions

@export
def set_mint_price(price: int):
    assert_is_manager()
    mint_price.set(price)


@export
def set_royalty_fee_percentage(percentage: int):
    assert_is_manager()
    royalty_fee_percentage.set(percentage)


@export
def set_manager(new_manager: str):
    assert_is_manager()
    manager.set(new_manager)


@export
def set_contract_allowlist(contracts: list):
    assert_is_manager()
    contracts_allowlist.set(contracts)


@export
def set_registration_period(period: int):
    assert_is_manager()
    registration_period.set(period)


@export
def set_enabled(state: bool):
    assert_is_manager()
    enabled.set(state)
