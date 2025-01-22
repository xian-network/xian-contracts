I = importlib

@export
def is_XSC001(contract: str):
    # Import the contract to validate
    token = I.import_module(contract)
    
    # Check required state variables exist
    required_variables = [
        I.Var('balances', Hash),
        I.Var('metadata', Hash)
    ]

    # Check required functions with correct signatures exist
    required_functions = [
        I.Func('seed'),
        I.Func('change_metadata', args=('key', 'value')),
        I.Func('transfer', args=('amount', 'to')), 
        I.Func('approve', args=('amount', 'to')),
        I.Func('transfer_from', args=('amount', 'to', 'main_account')),
        I.Func('balance_of', args=('account',))
    ]
    
    # Basic interface check
    interface_valid = I.enforce_interface(token, required_variables + required_functions)
    if not interface_valid:
        return False

    # Check metadata fields exist by trying to read them
    required_metadata = [
        'token_name',
        'token_symbol',
        'token_logo_url', 
        'token_website',
        'operator'
    ]

    for field in required_metadata:
        if token.metadata[field] is None:
            return False

    return True
