import pytest
from brownie import chain, reverts, Wei


def test_lower_target_ratio_should_take_more_debt(
    vault, strategy, token, yvault, amount, user, gov, RELATIVE_APPROX
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest({"from": gov})

    # Shares in yVault at the current target ratio
    shares_before = yvault.balanceOf(strategy)

    new_ratio_relative = 0.9

    # In default settings this will be 225 * 0.9 = 202.5
    strategy.setCollateralizationRatio(
        strategy.collateralizationRatio() * new_ratio_relative, {"from": gov}
    )

    # Adjust the position
    strategy.tend({"from": gov})

    # Because the target collateralization ratio is lower, more DAI will be minted
    # and deposited into the yvDAI vault
    assert pytest.approx(
        shares_before / new_ratio_relative, rel=RELATIVE_APPROX
    ) == yvault.balanceOf(strategy)


def test_lower_ratio_inside_rebalancing_band_should_not_take_more_debt(
    vault, strategy, token, yvault, amount, user, gov
):
    # Deposit to the vault
    assert token.balanceOf(vault) == 0
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    strategy.harvest({"from": gov})

    # Shares in yVault at the current target ratio
    shares_before = yvault.balanceOf(strategy)

    new_ratio = strategy.collateralizationRatio() - strategy.rebalanceTolerance() * 0.99
    strategy.setCollateralizationRatio(new_ratio, {"from": gov})

    # Adjust the position
    strategy.tend({"from": gov})

    # Because the current ratio is inside the rebalancing band
    # no more DAI will be minted and deposited into the yvDAI vault
    assert shares_before == yvault.balanceOf(strategy)


def test_higher_target_ratio_should_repay_debt(
    vault, strategy, token, yvault, amount, user, gov, RELATIVE_APPROX
):
    assert token.balanceOf(vault) == 0
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    harvest_tx = strategy.harvest({"from": gov})
    assert token.balanceOf(vault) == 0

    # Shares in yVault at the current target ratio
    shares_before = yvault.balanceOf(strategy)

    new_ratio_relative = 1.2

    # In default settings this will be 225 * 1.2 = 270
    strategy.setCollateralizationRatio(
        strategy.collateralizationRatio() * new_ratio_relative, {"from": gov}
    )

    # Adjust the position
    tend_tx = strategy.tend({"from": gov})

    # Because the target collateralization ratio is higher, a part of the debt
    # will be repaid to maintain a healthy ratio
    assert pytest.approx(
        shares_before / new_ratio_relative, rel=RELATIVE_APPROX
    ) == yvault.balanceOf(strategy)


def test_higher_ratio_inside_rebalancing_band_should_not_repay_debt(
    vault, test_strategy, token, yvault, amount, user, gov
):
    # Deposit to the vault
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})

    # Harvest 1: Send funds through the strategy
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Shares in yVault at the current target ratio
    shares_before = yvault.balanceOf(test_strategy)

    new_ratio = (
        test_strategy.collateralizationRatio()
        + test_strategy.rebalanceTolerance() * 0.99
    )
    test_strategy.setCollateralizationRatio(new_ratio, {"from": gov})

    assert test_strategy.tendTrigger(1) == False

    # Adjust the position
    test_strategy.tend({"from": gov})

    # Because the current ratio is inside the rebalancing band no debt will be repaid
    assert shares_before == yvault.balanceOf(test_strategy)


def test_vault_ratio_calculation_on_withdraw(
    vault, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0

    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 3% of the assets
    withdraw_tx = vault.withdraw(amount * 0.03, user, 100, {"from": user})

    # Strategy should restore collateralization ratio to target value on withdraw
    assert (
        pytest.approx(test_strategy.collateralizationRatio(), rel=RELATIVE_APPROX)
        == test_strategy.getCurrentMakerVaultRatio()
    )

    # Strategy has less funds to invest
    assert yvault.balanceOf(test_strategy) < shares_before
    #assert pytest.approx(yvault.balanceOf(test_strategy), rel=RELATIVE_APPROX_LOSSY) == (
    #    shares_before * 0.97
    #)



def test_vault_ratio_calculation_on_very_low_withdraw(
    vault, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0

    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 0.1% of the assets
    withdraw_tx = vault.withdraw(amount * 0.001, user, 100, {"from": user})

    # Strategy should restore collateralization ratio to target value on withdraw
    assert (
        pytest.approx(test_strategy.collateralizationRatio(), rel=RELATIVE_APPROX)
        == test_strategy.getCurrentMakerVaultRatio()
    )

    # Strategy has less funds to invest
    assert yvault.balanceOf(test_strategy) < shares_before


def test_vault_ratio_calculation_on_high_withdraw(
    vault, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0

    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 50% of the assets
    withdraw_tx = vault.withdraw(amount * 0.5, user, 100, {"from": user})

    # Strategy should restore collateralization ratio to target value on withdraw
    assert (
        pytest.approx(test_strategy.collateralizationRatio(), rel=RELATIVE_APPROX)
        == test_strategy.getCurrentMakerVaultRatio()
    )

    # Strategy has less funds to invest
    assert yvault.balanceOf(test_strategy) < shares_before

def test_vault_ratio_calculation_on_very_high_withdraw(
    dai, dai_whale, vault, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0

    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 80% of the assets
    withdraw_tx = vault.withdraw(amount * 0.8, user, 100, {"from": user})

    # Strategy should restore collateralization ratio to target value on withdraw
    #assert (
    pytest.approx(test_strategy.collateralizationRatio(), rel=0.16) == test_strategy.getCurrentMakerVaultRatio()

    # Strategy has less funds to invest
    assert yvault.balanceOf(test_strategy) < shares_before

def test_vault_ratio_calculation_on_almost_total_withdraw(
    dai, dai_whale, vault, router, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0

    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 50% of the assets
    withdraw_tx = vault.withdraw(amount * 0.95, user, 100, {"from": user})

    # Strategy should restore collateralization ratio to target value on withdraw
    #assert (
    #    pytest.approx(test_strategy.collateralizationRatio(), rel=RELATIVE_APPROX)
    #    == test_strategy.getCurrentMakerVaultRatio()
    #)

    # Strategy has less funds to invest
    assert yvault.balanceOf(test_strategy) < shares_before


def test_vault_ratio_calculation_on_total_withdraw(
    dai, dai_whale, token_whale, vault, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0
    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})

    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 100% of the assets, with 0.1% maxLoss
    withdraw_tx = vault.withdraw(amount, user, 100, {"from": user})

    # Strategy should have 0 collateralization ratio to target value on withdraw
    assert (
        pytest.approx(0, rel=RELATIVE_APPROX)
        == test_strategy.getCurrentMakerVaultRatio()
    )

    assert test_strategy.balance() == 0
    assert token.balanceOf(test_strategy) == 0
    assert steth.balanceOf(test_strategy) < 100
    assert wsteth.balanceOf(test_strategy) == 0

    assert 0 == 1


def test_vault_ratio_calculation_on_sandwiched_total_withdraw(
    token_whale, vault, wsteth, steth, test_strategy, token, yvault, amount, user, gov, RELATIVE_APPROX, RELATIVE_APPROX_LOSSY
):
    # Initial ratio is 0 because there is no collateral locked
    assert test_strategy.getCurrentMakerVaultRatio() == 0
    #sandwich:
    sandwich = "1000 ether"
    token.approve(vault.address, sandwich, {"from": token_whale})
    vault.deposit(sandwich, {"from": token_whale})
    
    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    test_strategy.harvest({"from": gov})
    withdraw_tx = vault.withdraw(vault.balanceOf(token_whale)*0.3, token_whale, 10, {"from": token_whale})
    # Collateral ratio should be the target ratio set
    assert (
        pytest.approx(test_strategy.getCurrentMakerVaultRatio(), rel=RELATIVE_APPROX)
        == test_strategy.collateralizationRatio()
    )

    shares_before = yvault.balanceOf(test_strategy)

    # Withdraw 100% of the assets, with 0.1% maxLoss
    withdraw_tx = vault.withdraw(amount, user, 10, {"from": user})
    withdraw_tx = vault.withdraw(test_strategy.estimatedTotalAssets(), token_whale, 10, {"from": token_whale})

    assert test_strategy.balance() == 0
    assert token.balanceOf(test_strategy) == 0
    assert steth.balanceOf(test_strategy) < 100
    assert wsteth.balanceOf(test_strategy) == 0



def test_tend_trigger_conditions(
    vault, strategy, token, token_whale, amount, user, gov
):
    # Initial ratio is 0 because there is no collateral locked
    assert strategy.tendTrigger(1) == False
    # Deposit to the vault and send funds through the strategy
    token.approve(vault.address, amount, {"from": user})
    vault.deposit(amount, {"from": user})
    chain.sleep(1)
    strategy.harvest({"from": gov})

    orig_target = strategy.collateralizationRatio()
    rebalance_tolerance = strategy.rebalanceTolerance()

    # Make sure we are in equilibrium
    assert strategy.tendTrigger(1) == False

    # Going under the rebalancing band should need to adjust position
    # regardless of the max acceptable base fee
    strategy.setCollateralizationRatio(
        orig_target + rebalance_tolerance * 1.001, {"from": gov}
    )

    strategy.setMaxAcceptableBaseFee(0, {"from": strategy.strategist()})
    assert strategy.tendTrigger(1) == True

    strategy.setMaxAcceptableBaseFee(1001 * 1e9, {"from": strategy.strategist()})
    assert strategy.tendTrigger(1) == True

    # Going over the target ratio but inside rebalancing band should not adjust position
    strategy.setCollateralizationRatio(
        orig_target + rebalance_tolerance * 0.999, {"from": gov}
    )
    assert strategy.tendTrigger(1) == False

    # Going over the rebalancing band should need to adjust position
    # but only if block's base fee is deemed to be acceptable
    strategy.setCollateralizationRatio(
        orig_target - rebalance_tolerance * 1.001, {"from": gov}
    )

    # Max acceptable base fee is set to 1000 gwei for testing, so go just
    # 1 gwei above and 1 gwei below to cover both sides
    strategy.setMaxAcceptableBaseFee(1001 * 1e9, {"from": strategy.strategist()})
    assert strategy.tendTrigger(1) == True

    strategy.setMaxAcceptableBaseFee(1000 * 1e9, {"from": strategy.strategist()})
    assert strategy.tendTrigger(1) == True

    strategy.setMaxAcceptableBaseFee(999 * 1e9, {"from": strategy.strategist()})
    assert strategy.tendTrigger(1) == False

    # Going over the target ratio but inside rebalancing band should not adjust position
    strategy.setCollateralizationRatio(
        orig_target - rebalance_tolerance * 0.999, {"from": gov}
    )
    strategy.setMaxAcceptableBaseFee(1001 * 1e9, {"from": strategy.strategist()})
    assert strategy.tendTrigger(1) == False



    #token.approve(vault.address, 2 ** 256 - 1, {"from": token_whale})
    #vault.deposit(Wei("10_000 ether"), {"from": token_whale})

    # Send the funds through the strategy to invest
    #chain.sleep(1)
    #strategy.harvest({"from": gov})



def test_ratio_lower_than_liquidation_should_revert(strategy, gov):
    with reverts():
        strategy.setCollateralizationRatio(1e18, {"from": gov})


def test_ratio_over_liquidation_but_with_tolerance_under_it_should_revert(
    strategy, gov
):
    strategy.setCollateralizationRatio(2e18, {"from": gov})

    with reverts():
        strategy.setRebalanceTolerance(5e17, {"from": gov})


def test_rebalance_tolerance_under_liquidation_ratio_should_revert(strategy, gov):
    with reverts():
        strategy.setRebalanceTolerance(1e18, {"from": gov})
