MINIMUM_LIQUIDITY = 0.00000001
MAXIMUM_BALANCE = 1e14

PairCreated = LogEvent(event="PairCreated",
	params={
	"token0": {'type':str, 'idx':True},
	"token1": {'type':str, 'idx':True},
	"pair":   {'type':int}
	}
)
	
Mint = LogEvent(event="Mint",
	params={
	"pair":    {'type':int, 'idx':True},
	"amount0": {'type':(int,float,decimal)},
	"amount1": {'type':(int,float,decimal)},
	"to":      {'type':str, 'idx':True}
	}
)
	
Burn = LogEvent(event="Burn",
	params={
	"pair":    {'type':int, 'idx':True},
	"amount0": {'type':(int,float,decimal)},
	"amount1": {'type':(int,float,decimal)},
	"to":      {'type':str, 'idx':True}
	}
)

Swap = LogEvent(event="Swap",
	params={
	"pair":       {'type':int, 'idx':True},
	"amount0In":  {'type':(int,float,decimal)},
	"amount1In":  {'type':(int,float,decimal)},
	"amount0Out": {'type':(int,float,decimal)},
	"amount1Out": {'type':(int,float,decimal)},
	"to":         {'type':(str,int), 'idx':True}
	}
)

Sync = LogEvent(event="Sync",
	params={
	"pair":      {'type':int, 'idx':True},
	"reserve0":  {'type':(int,float,decimal)},
	"reserve1":  {'type':(int,float,decimal)},
	}
)

TransferLiq = LogEvent(event="TransferLiq",
	params={
	"pair": {'type':int, 'idx':True},
	"from": {'type':str, 'idx':True},
	"to":   {'type':str, 'idx':True},
	"amount":  {'type':(int,float,decimal)},
	}
)

ApproveLiq = LogEvent(event="ApproveLiq",
	params={
	"pair": {'type':int, 'idx':True},
	"from": {'type':str, 'idx':True},
	"to":   {'type':str, 'idx':True},
	"amount":  {'type':(int,float,decimal)},
	}
)
    
toks_to_pair = Hash(default_value=None)
pairs = Hash(default_value=0)
pairs_num = Variable()
feeTo = Variable()
owner = Variable()
balances = Hash(default_value=0.0)

LOCK = Variable()


token_interface = [
    importlib.Func('transfer_from', args=('amount', 'to', 'main_account')),
    importlib.Func('transfer', args=('amount', 'to')),
    importlib.Func('balance_of', args=('address',)),
    #importlib.Var('balances', Hash),
]

@construct
def constructor():
	pairs_num.set(0)
	owner.set(ctx.signer)
	feeTo.set(ctx.signer)
	LOCK.set(False)
	
@export
def enableFee(en: bool):
	assert ctx.caller == owner.get(), "SNAKX: FORBIDDEN"
	if en:
		feeTo.set(owner.get())
	else:
		feeTo.set(False)
	
#factory
@export
def createPair(tokenA: str, tokenB: str):
	assert tokenA != tokenB, 'SNAKX: IDENTICAL_ADDRESSES'
	assert tokenA < tokenB, 'SNAKX: BAD_ORDER'
	assert toks_to_pair[tokenA,tokenB] == None, 'SNAKX: PAIR_EXISTS'
	
	
	
	tA = importlib.import_module(tokenA)
	assert importlib.enforce_interface(tA, token_interface), 'SNAKX: NO_TOKA'
	
	tB = importlib.import_module(tokenB)
	assert importlib.enforce_interface(tB, token_interface), 'SNAKX: NO_TOKB'
	
	
	p_num = pairs_num.get() + 1
	pairs_num.set(p_num)
	pairs[p_num, "token0"] = tokenA
	pairs[p_num, "token1"] = tokenB
	
	pairs[p_num, "reserve0"] = 0.0
	pairs[p_num, "reserve1"] = 0.0
	
	pairs[p_num, "balance0"] = 0.0
	pairs[p_num, "balance1"] = 0.0
	
	pairs[p_num, "blockTimestampLast"] = now
	
	pairs[p_num, "totalSupply"] = 0.0
	pairs[p_num, "kLast"] = 0.0
	pairs[p_num, "creationTime"] = now
	
	toks_to_pair[tokenA,tokenB] = p_num
	
	PairCreated({"token0": tokenA, "token1": tokenB, "pair": p_num})
	return p_num
	
@export
def pairFor(tokenA: str, tokenB: str):
	if(tokenB < tokenA):
		tokenA, tokenB = tokenB, tokenA
	return toks_to_pair[tokenA, tokenB]

@export
def liqTransfer(pair: int, amount: float, to: str):
	assert amount > 0, 'Cannot send negative balances!'
	assert pairs[pair, "balances", ctx.caller] >= amount, 'Not enough coins to send!'
	
	pairs[pair, "balances", ctx.caller] -= amount
	pairs[pair, "balances", to] += amount
	
	TransferLiq({"pair": pair, "from": ctx.caller, "to": to, "amount": amount})
    
@export
def liqApprove(pair: int, amount: float, to: str):
	assert amount > 0, 'Cannot send negative balances!'
	pairs[pair, "balances", ctx.caller, to] = amount
	
	ApproveLiq({"pair": pair, "from": ctx.caller, "to": to, "amount": amount})
	
@export
def liqTransfer_from(pair: int, amount: float, to: str, main_account: str):
	assert amount > 0, 'Cannot send negative balances!'
	assert pairs[pair, "balances", main_account, ctx.caller] >= amount, \
		'Not enough coins approved to send! You have {} and are trying to spend {}'.format(pairs[pair, "balances", main_account, ctx.caller], amount)
	assert pairs[pair, "balances", main_account] >= amount, 'Not enough coins to send!'
	
	pairs[pair, "balances", main_account, ctx.caller] -= amount
	pairs[pair, "balances", main_account] -= amount
	pairs[pair, "balances", to] += amount
	
	TransferLiq({"pair": pair, "from": main_account, "to": to, "amount": amount})


def safeTransferFromPair(pair: int, token: str, to: str, value: float):
	assert value >= 0 and value <= MAXIMUM_BALANCE, 'p2a Invalid value!'
	t = importlib.import_module(token)
	assert importlib.enforce_interface(t, token_interface)
	#tok_balances = ForeignHash(foreign_contract=token, foreign_name='balances')
	prev_balance = t.balance_of(ctx.this)
	
	if(prev_balance == None):
		prev_balance = 0
		
	
	if(token == pairs[pair, "token0"]):
		assert pairs[pair, "balance0"] >= value, 'p2a Not enough coins to send!' 
		t.transfer(value, to)
		#new_balance = tok_balances[ctx.this]
		new_balance = t.balance_of(ctx.this)
		assert new_balance >= 0, "p2a Negative balance!"
		pairs[pair, "balance0"] += new_balance - prev_balance
		assert pairs[pair, "balance0"] >= 0, "p2a Negative pair balance0!"
		return True
		
	
	elif(token == pairs[pair, "token1"]):
		assert pairs[pair, "balance1"] >= value, 'p2a Not enough coins to send!' 
		t.transfer(value, to)
		#new_balance = tok_balances[ctx.this]
		new_balance = t.balance_of(ctx.this)
		assert new_balance >= 0, "p2a Negative balance!"
		pairs[pair, "balance1"] += new_balance - prev_balance
		assert pairs[pair, "balance1"] >= 0, "p2a Negative pair balance1!"
		return True
		
	
	assert False, "p2a Wrong token!"
	
	return False


def safeTransferFromPairToPair(pair: int, token: str, to: int, value: float):
	assert value >= 0 and value <= MAXIMUM_BALANCE, 'p2p Invalid value!'
	
	if(token == pairs[pair, "token0"]):
		assert pairs[pair, "balance0"] >= value, 'p2p Not enough coins to send!'
		
		#prev_balance = pairs[pair, "balance0"]
		
		pairs[pair, "balance0"] -= value
		
		if(pairs[to, "token0"] == token):
			pairs[to, "balance0"] += value
		elif(pairs[to, "token1"] == token):
			pairs[to, "balance1"] += value
		else:
			assert False, "p2p No token in TO"
		
		new_balance = pairs[pair, "balance0"]
		
		assert new_balance >= 0, "p2p Negative balance!"
		
		return True
	elif(token == pairs[pair, "token1"]):
		assert pairs[pair, "balance1"] >= value, 'p2p Not enough coins to send!' 
		
		#prev_balance = pairs[pair, "balance1"]
		
		pairs[pair, "balance1"] -= value
		
		if(pairs[to, "token0"] == token):
			pairs[to, "balance0"] += value
		elif(pairs[to, "token1"] == token):
			pairs[to, "balance1"] += value
		else:
			assert False, "p2p No token in TO"
		
		new_balance = pairs[pair, "balance1"]
		
		assert new_balance >= 0, "p2p Negative balance!"
		
		return True
	
	assert False, "p2p Wrong token!"
	
	return False


def sync(pair: int):
	tokenA = pairs[pair, "token0"]
	tokenB = pairs[pair, "token1"]
	
	tA = importlib.import_module(tokenA)
	assert importlib.enforce_interface(tA, token_interface)
	#hashA = ForeignHash(foreign_contract=tokenA, foreign_name='balances')
	#balA = hashA[ctx.this]
	
	balA = tA.balance_of(ctx.this)
	if balA == None:
		balA = 0.0
	
	tB = importlib.import_module(tokenB)
	assert importlib.enforce_interface(tB, token_interface)
	#hashB = ForeignHash(foreign_contract=tokenB, foreign_name='balances')
	#balB = hashB[ctx.this]
	
	balB = tB.balance_of(ctx.this)
	if balB == None:
		balB = 0.0
	
	balances[tokenA] = balA
	balances[tokenB] = balB

#noreentry
@export
def sync2(pair: int):
	assert not LOCK.get(), "SNAKX: LOCKED"
	LOCK.set(True)
	tokenA = pairs[pair, "token0"]
	tokenB = pairs[pair, "token1"]
	
	tA = importlib.import_module(tokenA)
	assert importlib.enforce_interface(tA, token_interface)
	#hashA = ForeignHash(foreign_contract=tokenA, foreign_name='balances')
	#balA = hashA[ctx.this]
	
	balA = tA.balance_of(ctx.this)
	if balA == None:
		balA = 0.0
	
	tB = importlib.import_module(tokenB)
	assert importlib.enforce_interface(tB, token_interface)
	#hashB = ForeignHash(foreign_contract=tokenB, foreign_name='balances')
	#balB = hashB[ctx.this]
	
	balB = tB.balance_of(ctx.this)
	if balB == None:
		balB = 0.0
		
	incA = balA - balances[tokenA]
	assert incA >= 0, "SNAKX: token0_neg"
	incB = balB - balances[tokenB]
	assert incB >= 0, "SNAKX: token1_neg"
	
	pairs[pair, "balance0"] += incA
	pairs[pair, "balance1"] += incB
	
	assert pairs[pair, "balance0"] <= MAXIMUM_BALANCE, "SNAKX: TokenA OVERFLOW"
	assert pairs[pair, "balance1"] <= MAXIMUM_BALANCE, "SNAKX: TokenB OVERFLOW"
	
	balances[tokenA] = balA
	balances[tokenB] = balB
	
	LOCK.set(False)


@export
def getReserves(pair: int):
	return pairs[pair, "reserve0"], pairs[pair, "reserve1"], pairs[pair, "blockTimestampLast"]
	
@export
def getSurplus(pair: int):
	return pairs[pair, "balance0"] - pairs[pair, "reserve0"], pairs[pair, "balance1"] - pairs[pair, "reserve1"]
	
#def internal_update(pair: int, balance0: float, balance1: float, UNS_reserve0: float, UNS_reserve1: float):
def internal_update(pair: int, balance0: float, balance1: float):
	assert balance0 <= MAXIMUM_BALANCE and balance1 <= MAXIMUM_BALANCE, "SNAKX: BALANCE OVERFLOW"
	pairs[pair, "reserve0"] = balance0
	pairs[pair, "reserve1"] = balance1
	pairs[pair, "blockTimestampLast"] = now
	Sync({"pair":pair,"reserve0":balance0,"reserve1":balance1});
#emit

def internal_mintFee(pair: int, reserve0: float, reserve1: float):
	feeOn = feeTo.get() != False
	kLast = pairs[pair, "kLast"]
	if (feeOn):
		if (kLast != 0):
			rootK = (reserve0 * reserve1) ** 0.5;
			rootKLast = kLast ** 0.5;
			if (rootK > rootKLast):
				numerator = pairs[pair, "totalSupply"] * (rootK - rootKLast);
				denominator = rootK * 5 + rootKLast;
				liquidity = numerator / denominator;
				if (liquidity > 0):
					internal_mint(pair, feeTo.get(), liquidity);
	elif(kLast != 0): 
		pairs[pair, "kLast"] = 0.0
	return feeOn

def internal_burn(pair: int, src: str, value: float):
	pairs[pair, "totalSupply"] -= value
	assert pairs[pair, "totalSupply"] >= 0, "Negative supply!"
	pairs[pair, "balances", src] -= value
	assert pairs[pair, "balances", src] >= 0, "Negative balance!"

#noreentry
@export
def burn(pair: int, to: str):
	assert not LOCK.get(), "SNAKX: LOCKED"
	LOCK.set(True)
	
	reserve0, reserve1, ignore = getReserves(pair)
	
	token0 = pairs[pair, "token0"]
	token1 = pairs[pair, "token1"]
	balance0 = pairs[pair, "balance0"]
	balance1 = pairs[pair, "balance1"]

	liquidity = pairs[pair, "balances", ctx.this]
	
	feeOn = internal_mintFee(pair, reserve0, reserve1);
	totalSupply = pairs[pair, "totalSupply"]
	amount0 = (liquidity * balance0) / totalSupply
	amount1 = (liquidity * balance1) / totalSupply
	assert amount0 > 0 and amount1 > 0, 'SNAKX: INSUFFICIENT_LIQUIDITY_BURNED'
	internal_burn(pair, ctx.this, liquidity)
	safeTransferFromPair(pair, token0, to, amount0);
	safeTransferFromPair(pair, token1, to, amount1);
	
	balance0 = pairs[pair, "balance0"]
	balance1 = pairs[pair, "balance1"]
	

	#internal_update(pair, balance0, balance1, UNS_reserve0, UNS_reserve1);
	internal_update(pair, balance0, balance1);
	sync(pair)
	if (feeOn):
		pairs[pair, "kLast"] = balance0 * balance1
		
	Burn({"pair": pair, "amount0": amount0, "amount1": amount1, "to": to})
	
	LOCK.set(False)
	return amount0, amount1


def internal_mint(pair: int, to: str, value: float):
	pairs[pair, "totalSupply"] += value
	pairs[pair, "balances", to] += value

#noreentry
@export
def mint(pair: int, to: str):
	assert not LOCK.get(), "SNAKX: LOCKED"
	LOCK.set(True)
	
	reserve0, reserve1, ignore = getReserves(pair)
	balance0 = pairs[pair, "balance0"]
	balance1 = pairs[pair, "balance1"]
	
	amount0 = balance0 - reserve0
	amount1 = balance1 - reserve1
	
	feeOn = internal_mintFee(pair, reserve0, reserve1)
	totalSupply = pairs[pair, "totalSupply"]
	
	liquidity = 0
	if (totalSupply == 0):
		liquidity = ((amount0 * amount1) ** 0.5) - MINIMUM_LIQUIDITY;
		internal_mint(pair, "DEAD", MINIMUM_LIQUIDITY) # permanently lock the first MINIMUM_LIQUIDITY tokens
	else:
		liquidity = min((amount0 * totalSupply) / reserve0, (amount1 * totalSupply) / reserve1)
	assert liquidity > 0, 'SNAKX: INSUFFICIENT_LIQUIDITY_MINTED'
	internal_mint(pair, to, liquidity)
	
	#internal_update(pair, balance0, balance1, UNS_reserve0, UNS_reserve1);
	internal_update(pair, balance0, balance1)
	sync(pair)
	if (feeOn):
		pairs[pair, "kLast"] = balance0 * balance1
	
	Mint({"pair": pair, "amount0": amount0, "amount1": amount1, "to": to})
	
	LOCK.set(False)
	return liquidity
	
			
#noreentry
@export
def swap(pair: int, amount0Out: float, amount1Out: float, to: str):
	assert not LOCK.get(), "SNAKX: LOCKED"
	LOCK.set(True)
	
	assert amount0Out > 0 or amount1Out > 0, 'SNAKX: INSUFFICIENT_OUTPUT_AMOUNT'
	reserve0, reserve1, ignore = getReserves(pair)
	assert amount0Out < reserve0 and amount1Out < reserve1, 'SNAKX: INSUFFICIENT_LIQUIDITY'
	token0 = pairs[pair, "token0"]
	token1 = pairs[pair, "token1"]
	assert to != token0 and to != token1, 'SNAKX: INVALID_TO'
	
	if (amount0Out > 0):
		safeTransferFromPair(pair, token0, to, amount0Out)
	if (amount1Out > 0):
		safeTransferFromPair(pair, token1, to, amount1Out)
	balance0 = pairs[pair, "balance0"]
	balance1 = pairs[pair, "balance1"]
	amount0In = balance0 - (reserve0 - amount0Out) if balance0 > reserve0 - amount0Out else 0
	amount1In = balance1 - (reserve1 - amount1Out) if balance1 > reserve1 - amount1Out else 0
	assert amount0In > 0 or amount1In > 0, 'SNAKX: INSUFFICIENT_INPUT_AMOUNT'
	balance0Adjusted = (balance0) - (amount0In * 0.003)
	balance1Adjusted = (balance1) - (amount1In * 0.003)
	assert (balance0Adjusted * balance1Adjusted) >= (reserve0 * reserve1), 'SNAKX: K'
#		or abs((balance0Adjusted * balance1Adjusted) - (reserve0 * reserve1)) < MINIMUM_LIQUIDITY, 'SNAKX: K'

	#internal_update(pair, balance0, balance1, reserve0, reserve1);
	internal_update(pair, balance0, balance1)
	sync(pair)
	
	Swap({"pair": pair,
		"amount0In": amount0In, "amount1In": amount1In,
		"amount0Out": amount0Out, "amount1Out": amount1Out,
		"to": to})
		
	LOCK.set(False)
	#emit Swap(msg.sender, amount0In, amount1In, amount0Out, amount1Out, to);
	
#noreentry
@export
def swapToPair(pair: int, amount0Out: float, amount1Out: float, to: int):
	assert not LOCK.get(), "SNAKX: LOCKED"
	LOCK.set(True)
	
	assert amount0Out > 0 or amount1Out > 0, 'SNAKX: INSUFFICIENT_OUTPUT_AMOUNT'
	reserve0, reserve1, ignore = getReserves(pair)
	assert amount0Out < reserve0 and amount1Out < reserve1, 'SNAKX: INSUFFICIENT_LIQUIDITY'
	token0 = pairs[pair, "token0"]
	token1 = pairs[pair, "token1"]

	if (amount0Out > 0):
		safeTransferFromPairToPair(pair, token0, to, amount0Out)
	if (amount1Out > 0):
		safeTransferFromPairToPair(pair, token1, to, amount1Out)
	balance0 = pairs[pair, "balance0"]
	balance1 = pairs[pair, "balance1"]
	amount0In = balance0 - (reserve0 - amount0Out) if balance0 > reserve0 - amount0Out else 0
	amount1In = balance1 - (reserve1 - amount1Out) if balance1 > reserve1 - amount1Out else 0
	assert amount0In > 0 or amount1In > 0, 'SNAKX: INSUFFICIENT_INPUT_AMOUNT'
	balance0Adjusted = (balance0) - (amount0In * 0.003)
	balance1Adjusted = (balance1) - (amount1In * 0.003)
	assert (balance0Adjusted * balance1Adjusted) >= (reserve0 * reserve1), 'SNAKX: K'
#		or abs((balance0Adjusted * balance1Adjusted) - (reserve0 * reserve1)) < MINIMUM_LIQUIDITY, 'SNAKX: K'

	#internal_update(pair, balance0, balance1, reserve0, reserve1);
	internal_update(pair, balance0, balance1);
	
	Swap({"pair": pair,
		"amount0In": amount0In, "amount1In": amount1In,
		"amount0Out": amount0Out, "amount1Out": amount1Out,
		"to": to})
		
	LOCK.set(False)
	#emit Swap(msg.sender, amount0In, amount1In, amount0Out, amount1Out, to);
