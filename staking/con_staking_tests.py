import unittest
from contracting.client import ContractingClient
from contracting.stdlib.bridge.time import Datetime
from contracting.stdlib.bridge.decimal import ContractingDecimal
import os

class TestStakingContract(unittest.TestCase):

    def setUp(self):
        self.client = ContractingClient()
        self.client.flush()
        
        # Load and submit the staking contract
        with open('staking_contract.py') as f:
            contract_code = f.read()
        self.client.submit(contract_code, name='con_staking_test')
        
        # Load and submit a test token contract for testing
        test_token_code = '''
balances = Hash(default_value=0)
metadata = Hash()

@construct
def seed():
    balances[ctx.caller] = 1000000
    metadata['token_name'] = "Test Token"
    metadata['token_symbol'] = "TEST"

@export
def balance_of(address: str):
    return balances[address]

@export
def transfer(amount: float, to: str):
    assert amount > 0, 'Cannot send negative balances!'
    assert balances[ctx.caller] >= amount, 'Not enough coins to send!'
    balances[ctx.caller] -= amount
    balances[to] += amount

@export
def transfer_from(amount: float, to: str, main_account: str):
    assert amount > 0, 'Cannot send negative balances!'
    assert balances[main_account] >= amount, 'Not enough coins to send!'
    balances[main_account] -= amount
    balances[to] += amount

@export
def approve(amount: float, to: str):
    balances[ctx.caller, to] = amount
'''
        
        self.client.submit(test_token_code, name='con_stake_token')
        self.client.submit(test_token_code, name='con_reward_token')
        self.client.submit(test_token_code, name='con_fee_token')
        
        # Get contract instances
        self.staking = self.client.get_contract('con_staking_test')
        self.stake_token = self.client.get_contract('con_stake_token')
        self.reward_token = self.client.get_contract('con_reward_token')
        self.fee_token = self.client.get_contract('con_fee_token')
        
        # Set up test accounts
        self.creator = 'creator'
        self.staker1 = 'staker1'
        self.staker2 = 'staker2'
        self.owner = 'sys'  # Contract owner
        
        # Fund accounts
        self.stake_token.transfer(amount=10000, to=self.creator, signer=self.owner)
        self.stake_token.transfer(amount=10000, to=self.staker1, signer=self.owner)
        self.stake_token.transfer(amount=10000, to=self.staker2, signer=self.owner)
        
        self.reward_token.transfer(amount=10000, to=self.creator, signer=self.owner)
        self.fee_token.transfer(amount=10000, to=self.staker1, signer=self.owner)
        self.fee_token.transfer(amount=10000, to=self.staker2, signer=self.owner)
        
        # Set up approvals
        self.stake_token.approve(amount=10000, to='con_staking_test', signer=self.staker1)
        self.stake_token.approve(amount=10000, to='con_staking_test', signer=self.staker2)
        self.reward_token.approve(amount=10000, to='con_staking_test', signer=self.creator)
        self.fee_token.approve(amount=10000, to='con_staking_test', signer=self.staker1)
        self.fee_token.approve(amount=10000, to='con_staking_test', signer=self.staker2)
        
        self.environment = {"chain_id": "test-chain"}
        self.test_time = Datetime(year=2024, month=1, day=1, hour=12, minute=0, second=0)

    def tearDown(self):
        self.client.flush()

    # Constructor Tests
    def test_contract_initialization(self):
        """Test contract is properly initialized"""
        status = self.staking.get_contract_status(signer=self.creator)
        self.assertEqual(status['owner'], 'sys')
        self.assertEqual(status['paused'], False)
        self.assertEqual(status['total_pools'], 0)

    # Create Pool Tests
    def test_create_pool_success(self):
        """Test successful pool creation"""
        result = self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,  # 1 day
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time},
            return_full_output=True
        )
        
        self.assertEqual(result['result'], '0')  # First pool ID
        
        # Verify pool was created
        pool_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        self.assertEqual(pool_info['config']['creator'], self.creator)
        self.assertEqual(pool_info['config']['apy'], 10.0)
        self.assertEqual(pool_info['stats']['total_staked'], 0.0)
        
        # Verify event emission
        self.assertEqual(result['events'][0]['event'], 'PoolCreated')
        self.assertEqual(result['events'][0]['data']['pool_id'], '0')

    def test_create_pool_with_all_params(self):
        """Test pool creation with all optional parameters"""
        future_time = Datetime(year=2024, month=1, day=2, hour=12, minute=0, second=0)
        
        result = self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=15.0,
            lock_duration=172800,  # 2 days
            max_positions=50,
            stake_amount=200.0,
            start_date=int(future_time.timestamp()),
            early_withdrawal_enabled=False,
            penalty_rate=0.2,
            entry_fee_amount=10.0,
            entry_fee_token='con_fee_token',
            signer=self.creator,
            environment={"now": self.test_time},
            return_full_output=True
        )
        
        pool_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        self.assertEqual(pool_info['config']['penalty_rate'], 0.2)
        self.assertEqual(pool_info['config']['entry_fee_amount'], 10.0)
        self.assertEqual(pool_info['config']['early_withdrawal_enabled'], False)

    def test_create_pool_invalid_apy(self):
        """Test pool creation with negative APY fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=-5.0,
                lock_duration=86400,
                max_positions=100,
                stake_amount=100.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("APY must be non-negative", str(context.exception))

    def test_create_pool_invalid_lock_duration(self):
        """Test pool creation with zero lock duration fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=0,
                max_positions=100,
                stake_amount=100.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Lock duration must be positive", str(context.exception))

    def test_create_pool_invalid_max_positions(self):
        """Test pool creation with zero max positions fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=86400,
                max_positions=0,
                stake_amount=100.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Max positions must be positive", str(context.exception))

    def test_create_pool_invalid_stake_amount(self):
        """Test pool creation with zero stake amount fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=86400,
                max_positions=100,
                stake_amount=0.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Stake amount must be positive", str(context.exception))

    def test_create_pool_invalid_penalty_rate(self):
        """Test pool creation with invalid penalty rate fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=86400,
                max_positions=100,
                stake_amount=100.0,
                penalty_rate=1.5,  # > 100%
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Penalty rate must be 0-100%", str(context.exception))

    def test_create_pool_past_start_date(self):
        """Test pool creation with past start date fails"""
        past_time = Datetime(year=2023, month=12, day=31)
        
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=86400,
                max_positions=100,
                stake_amount=100.0,
                start_date=int(past_time.timestamp()),
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Start date cannot be in the past", str(context.exception))

    def test_create_pool_entry_fee_without_token(self):
        """Test pool creation with entry fee but no token fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=86400,
                max_positions=100,
                stake_amount=100.0,
                entry_fee_amount=10.0,
                entry_fee_token=None,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Entry fee token must be specified", str(context.exception))

    def test_create_pool_when_paused(self):
        """Test pool creation when contract is paused fails"""
        self.staking.emergency_pause(signer=self.owner)
        
        with self.assertRaises(AssertionError) as context:
            self.staking.create_pool(
                stake_token='con_stake_token',
                reward_token='con_reward_token',
                apy=10.0,
                lock_duration=86400,
                max_positions=100,
                stake_amount=100.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Contract is paused", str(context.exception))

    # Stake Tests
    def test_stake_success(self):
        """Test successful staking"""
        # Create pool first
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        result = self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time},
            return_full_output=True
        )
        
        # Verify stake was recorded
        stake_info = self.staking.get_stake_info(pool_id='0', staker=self.staker1, signer=self.creator)
        self.assertEqual(stake_info['amount'], 100.0)
        
        # Verify pool stats updated
        pool_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        self.assertEqual(pool_info['stats']['current_positions'], 1)
        self.assertEqual(pool_info['stats']['total_staked'], 100.0)
        
        # Verify token transfer
        self.assertEqual(self.stake_token.balance_of(address=self.staker1, signer=self.staker1), 9900.0)
        self.assertEqual(self.stake_token.balance_of(address='con_staking_test', signer=self.staker1), 100.0)
        
        # Verify event emission
        self.assertEqual(result['events'][0]['event'], 'Stake')
        self.assertEqual(result['events'][0]['data']['pool_id'], '0')
        self.assertEqual(result['events'][0]['data']['staker'], self.staker1)

    def test_stake_with_entry_fee(self):
        """Test staking with entry fee"""
        # Create pool with entry fee
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            entry_fee_amount=10.0,
            entry_fee_token='con_fee_token',
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        result = self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time},
            return_full_output=True
        )
        
        # Verify entry fee was paid
        stake_info = self.staking.get_stake_info(pool_id='0', staker=self.staker1, signer=self.creator)
        self.assertEqual(stake_info['entry_fee_paid'], 10.0)
        
        # Verify fee token transfer
        self.assertEqual(self.fee_token.balance_of(address=self.staker1, signer=self.staker1), 9990.0)
        self.assertEqual(self.fee_token.balance_of(address='con_staking_test', signer=self.staker1), 10.0)
        
        # Verify creator fees tracked
        pool_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        self.assertEqual(pool_info['config']['creator_fees_collected'], 10.0)

    def test_stake_nonexistent_pool(self):
        """Test staking in nonexistent pool fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.stake(
                pool_id='999',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Pool does not exist", str(context.exception))

    def test_stake_before_start_date(self):
        """Test staking before pool start date fails"""
        future_time = Datetime(year=2024, month=1, day=2, hour=12, minute=0, second=0)
        
        # Create pool with future start date
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            start_date=int(future_time.timestamp()),
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        with self.assertRaises(AssertionError) as context:
            self.staking.stake(
                pool_id='0',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Pool has not started yet", str(context.exception))

    def test_stake_pool_full(self):
        """Test staking when pool is full fails"""
        # Create pool with 1 position
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=1,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # First stake succeeds
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Second stake fails
        with self.assertRaises(AssertionError) as context:
            self.staking.stake(
                pool_id='0',
                signer=self.staker2,
                environment={"now": self.test_time}
            )
        self.assertIn("Pool is full", str(context.exception))

    def test_stake_already_staking(self):
        """Test staking twice in same pool fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # First stake succeeds
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Second stake by same user fails
        with self.assertRaises(AssertionError) as context:
            self.staking.stake(
                pool_id='0',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Already staking in this pool", str(context.exception))

    def test_stake_when_paused(self):
        """Test staking when contract is paused fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Pause contract
        self.staking.emergency_pause(signer=self.owner)
        
        with self.assertRaises(AssertionError) as context:
            self.staking.stake(
                pool_id='0',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Contract is paused", str(context.exception))

    # Unstake Tests
    def test_unstake_after_lock_period(self):
        """Test unstaking after lock period ends"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,  # 1 day
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Deposit rewards
        self.staking.deposit_rewards(
            pool_id='0',
            amount=1000.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Wait for lock period to end
        later_time = Datetime(year=2024, month=1, day=2, hour=12, minute=0, second=1)
        
        # Unstake
        result = self.staking.unstake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": later_time},
            return_full_output=True
        )
        
        # Verify full stake returned (no penalty)
        self.assertEqual(self.stake_token.balance_of(address=self.staker1, signer=self.staker1), 10000.0)
        
        # Verify rewards received
        self.assertEqual(self.reward_token.balance_of(address=self.staker1, signer=self.staker1), 10.0)  # 10% APY
        
        # Verify event emission
        self.assertEqual(result['events'][0]['event'], 'Unstake')
        self.assertEqual(result['events'][0]['data']['early'], False)
        self.assertEqual(result['events'][0]['data']['penalty'], 0.0)

    def test_unstake_early_with_penalty(self):
        """Test early unstaking with penalty"""
        # Create pool with penalty
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,  # 1 day
            max_positions=100,
            stake_amount=100.0,
            penalty_rate=0.1,  # 10% penalty
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Deposit rewards
        self.staking.deposit_rewards(
            pool_id='0',
            amount=1000.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Unstake early (after 12 hours = 50% of lock period)
        early_time = Datetime(year=2024, month=1, day=1, hour=24, minute=0, second=0)
        
        result = self.staking.unstake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": early_time},
            return_full_output=True
        )
        
        # Verify partial rewards (50% of time = 50% of rewards)
        expected_rewards = 10.0 * 0.5  # 5.0
        self.assertEqual(self.reward_token.balance_of(address=self.staker1, signer=self.staker1), expected_rewards)
        
        # Verify penalty applied (50% remaining time = 5% penalty on stake)
        expected_penalty = 100.0 * 0.1 * 0.5  # 5.0
        expected_return = 100.0 - expected_penalty  # 95.0
        self.assertEqual(self.stake_token.balance_of(address=self.staker1, signer=self.staker1), 9900.0 + expected_return)
        
        # Verify event data
        self.assertEqual(result['events'][0]['data']['early'], True)
        self.assertEqual(result['events'][0]['data']['penalty'], expected_penalty)

    def test_unstake_early_disabled(self):
        """Test early unstaking when disabled fails"""
        # Create pool with early withdrawal disabled
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            early_withdrawal_enabled=False,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Try to unstake early
        early_time = Datetime(year=2024, month=1, day=1, hour=18, minute=0, second=0)
        
        with self.assertRaises(AssertionError) as context:
            self.staking.unstake(
                pool_id='0',
                signer=self.staker1,
                environment={"now": early_time}
            )
        self.assertIn("Early withdrawal not allowed", str(context.exception))

    def test_unstake_nonexistent_pool(self):
        """Test unstaking from nonexistent pool fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.unstake(
                pool_id='999',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Pool does not exist", str(context.exception))

    def test_unstake_not_staking(self):
        """Test unstaking when not staking fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        with self.assertRaises(AssertionError) as context:
            self.staking.unstake(
                pool_id='0',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Not staking in this pool", str(context.exception))

    def test_unstake_when_paused(self):
        """Test unstaking when contract is paused fails"""
        # Create pool and stake
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Pause contract
        self.staking.emergency_pause(signer=self.owner)
        
        with self.assertRaises(AssertionError) as context:
            self.staking.unstake(
                pool_id='0',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Contract is paused", str(context.exception))

    # Deposit Rewards Tests
    def test_deposit_rewards_success(self):
        """Test successful reward deposit"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Deposit rewards
        self.staking.deposit_rewards(
            pool_id='0',
            amount=1000.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Verify rewards deposited
        pool_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        self.assertEqual(pool_info['config']['total_rewards_deposited'], 1000.0)
        
        # Verify token transfer
        self.assertEqual(self.reward_token.balance_of(address=self.creator, signer=self.creator), 9000.0)
        self.assertEqual(self.reward_token.balance_of(address='con_staking_test', signer=self.creator), 1000.0)

    def test_deposit_rewards_nonexistent_pool(self):
        """Test depositing rewards to nonexistent pool fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.deposit_rewards(
                pool_id='999',
                amount=1000.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Pool does not exist", str(context.exception))

    def test_deposit_rewards_not_creator(self):
        """Test depositing rewards by non-creator fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        with self.assertRaises(AssertionError) as context:
            self.staking.deposit_rewards(
                pool_id='0',
                amount=1000.0,
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Only pool creator can deposit rewards", str(context.exception))

    def test_deposit_rewards_zero_amount(self):
        """Test depositing zero rewards fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        with self.assertRaises(AssertionError) as context:
            self.staking.deposit_rewards(
                pool_id='0',
                amount=0.0,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Amount must be positive", str(context.exception))

    # Withdraw Creator Fees Tests
    def test_withdraw_creator_fees_success(self):
        """Test successful creator fee withdrawal"""
        # Create pool with entry fee
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            entry_fee_amount=10.0,
            entry_fee_token='con_fee_token',
            penalty_rate=0.1,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake to generate entry fee
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Unstake early to generate penalty
        early_time = Datetime(year=2024, month=1, day=1, hour=18, minute=0, second=0)
        self.staking.unstake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": early_time}
        )
        
        # Withdraw fees
        initial_fee_balance = self.fee_token.balance_of(address=self.creator, signer=self.creator)
        initial_stake_balance = self.stake_token.balance_of(address=self.creator, signer=self.creator)
        
        self.staking.withdraw_creator_fees(
            pool_id='0',
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Verify fee withdrawal
        final_fee_balance = self.fee_token.balance_of(address=self.creator, signer=self.creator)
        self.assertEqual(final_fee_balance, initial_fee_balance + 10.0)
        
        # Verify penalty withdrawal (should be > 0)
        final_stake_balance = self.stake_token.balance_of(address=self.creator, signer=self.creator)
        self.assertGreater(final_stake_balance, initial_stake_balance)
        
        # Verify fees reset
        pool_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        self.assertEqual(pool_info['config']['creator_fees_collected'], 0.0)
        self.assertEqual(pool_info['config']['creator_penalties_collected'], 0.0)

    def test_withdraw_creator_fees_not_creator(self):
        """Test withdrawing fees by non-creator fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        with self.assertRaises(AssertionError) as context:
            self.staking.withdraw_creator_fees(
                pool_id='0',
                signer=self.staker1,
                environment={"now": self.test_time}
            )
        self.assertIn("Only pool creator can withdraw fees", str(context.exception))

    # Calculate Rewards Tests
    def test_calculate_rewards_full_period(self):
        """Test reward calculation after full lock period"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Calculate rewards after full period
        later_time = Datetime(year=2024, month=1, day=2, hour=12, minute=0, second=1)
        rewards = self.staking.calculate_rewards(
            pool_id='0',
            staker=self.staker1,
            signer=self.creator,
            environment={"now": later_time}
        )
        
        self.assertEqual(rewards['current_reward'], 10.0)  # 10% APY
        self.assertEqual(rewards['max_reward'], 10.0)
        self.assertEqual(rewards['potential_penalty'], 0.0)
        self.assertEqual(rewards['is_early'], False)

    def test_calculate_rewards_partial_period(self):
        """Test reward calculation during lock period"""
        # Create pool with penalty
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            penalty_rate=0.1,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake
        self.staking.stake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": self.test_time}
        )
        
        # Calculate rewards after 50% of period
        partial_time = Datetime(year=2024, month=1, day=1, hour=24, minute=0, second=0)
        rewards = self.staking.calculate_rewards(
            pool_id='0',
            staker=self.staker1,
            signer=self.creator,
            environment={"now": partial_time}
        )
        
        self.assertEqual(rewards['current_reward'], 5.0)  # 50% of 10%
        self.assertEqual(rewards['max_reward'], 10.0)
        self.assertEqual(rewards['potential_penalty'], 5.0)  # 50% time remaining * 10% penalty
        self.assertEqual(rewards['is_early'], True)

    # Emergency Functions Tests
    def test_emergency_pause_unpause(self):
        """Test emergency pause and unpause"""
        # Test pause
        self.staking.emergency_pause(signer=self.owner)
        status = self.staking.get_contract_status(signer=self.creator)
        self.assertEqual(status['paused'], True)
        
        # Test unpause
        self.staking.emergency_unpause(signer=self.owner)
        status = self.staking.get_contract_status(signer=self.creator)
        self.assertEqual(status['paused'], False)

    def test_emergency_pause_not_owner(self):
        """Test emergency pause by non-owner fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.emergency_pause(signer=self.creator)
        self.assertIn("Only contract owner can pause", str(context.exception))

    def test_emergency_withdraw_token(self):
        """Test emergency token withdrawal"""
        # Transfer some tokens to contract first
        self.stake_token.transfer(amount=1000.0, to='con_staking_test', signer=self.owner)
        
        # Pause contract
        self.staking.emergency_pause(signer=self.owner)
        
        # Emergency withdraw
        initial_balance = self.stake_token.balance_of(address=self.owner, signer=self.owner)
        self.staking.emergency_withdraw_token(
            token_contract='con_stake_token',
            amount=500.0,
            signer=self.owner
        )
        
        final_balance = self.stake_token.balance_of(address=self.owner, signer=self.owner)
        self.assertEqual(final_balance, initial_balance + 500.0)

    def test_emergency_withdraw_not_owner(self):
        """Test emergency withdrawal by non-owner fails"""
        self.staking.emergency_pause(signer=self.owner)
        
        with self.assertRaises(AssertionError) as context:
            self.staking.emergency_withdraw_token(
                token_contract='con_stake_token',
                amount=500.0,
                signer=self.creator
            )
        self.assertIn("Only contract owner can emergency withdraw", str(context.exception))

    def test_emergency_withdraw_not_paused(self):
        """Test emergency withdrawal when not paused fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.emergency_withdraw_token(
                token_contract='con_stake_token',
                amount=500.0,
                signer=self.owner
            )
        self.assertIn("Contract must be paused for emergency withdrawal", str(context.exception))

    # Get Functions Tests
    def test_get_stake_info_nonexistent(self):
        """Test getting info for nonexistent stake fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.get_stake_info(
                pool_id='0',
                staker=self.staker1,
                signer=self.creator
            )
        self.assertIn("Stake not found", str(context.exception))

    def test_calculate_rewards_nonexistent_pool(self):
        """Test calculating rewards for nonexistent pool fails"""
        with self.assertRaises(AssertionError) as context:
            self.staking.calculate_rewards(
                pool_id='999',
                staker=self.staker1,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Pool does not exist", str(context.exception))

    def test_calculate_rewards_not_staking(self):
        """Test calculating rewards when not staking fails"""
        # Create pool
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        with self.assertRaises(AssertionError) as context:
            self.staking.calculate_rewards(
                pool_id='0',
                staker=self.staker1,
                signer=self.creator,
                environment={"now": self.test_time}
            )
        self.assertIn("Not staking in this pool", str(context.exception))

    # Edge Cases and Integration Tests
    def test_multiple_pools_multiple_stakers(self):
        """Test multiple pools with multiple stakers"""
        # Create two pools
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=10.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=20.0,
            lock_duration=172800,
            max_positions=50,
            stake_amount=200.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake in both pools
        self.staking.stake(pool_id='0', signer=self.staker1, environment={"now": self.test_time})
        self.staking.stake(pool_id='1', signer=self.staker1, environment={"now": self.test_time})
        self.staking.stake(pool_id='0', signer=self.staker2, environment={"now": self.test_time})
        
        # Verify independent tracking
        pool0_info = self.staking.get_pool_info(pool_id='0', signer=self.creator)
        pool1_info = self.staking.get_pool_info(pool_id='1', signer=self.creator)
        
        self.assertEqual(pool0_info['stats']['current_positions'], 2)
        self.assertEqual(pool1_info['stats']['current_positions'], 1)
        self.assertEqual(pool0_info['stats']['total_staked'], 200.0)
        self.assertEqual(pool1_info['stats']['total_staked'], 200.0)

    def test_zero_apy_pool(self):
        """Test pool with 0% APY"""
        # Create pool with 0% APY
        self.staking.create_pool(
            stake_token='con_stake_token',
            reward_token='con_reward_token',
            apy=0.0,
            lock_duration=86400,
            max_positions=100,
            stake_amount=100.0,
            signer=self.creator,
            environment={"now": self.test_time}
        )
        
        # Stake and unstake
        self.staking.stake(pool_id='0', signer=self.staker1, environment={"now": self.test_time})
        
        later_time = Datetime(year=2024, month=1, day=2, hour=12, minute=0, second=1)
        result = self.staking.unstake(
            pool_id='0',
            signer=self.staker1,
            environment={"now": later_time},
            return_full_output=True
        )
        
        # Verify no rewards
        self.assertEqual(result['events'][0]['data']['rewards'], 0.0)

if __name__ == '__main__':
    unittest.main()
