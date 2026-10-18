"""Each real function must keep the frozen signature from contracts/interfaces.py. Missing modules are skipped until their phase lands."""
import importlib
import inspect

import pytest

from contracts import interfaces


@pytest.mark.parametrize("name", sorted(interfaces.IMPLEMENTATIONS))
def test_signature_matches_the_contract(name):
    module_name, func_name = interfaces.IMPLEMENTATIONS[name].split(":")
    try:
        module = importlib.import_module(module_name)
    except ModuleNotFoundError:
        pytest.skip(f"{module_name} not built yet")
    real = getattr(module, func_name, None)
    assert real is not None, f"{module_name} has no {func_name}"
    want = list(inspect.signature(getattr(interfaces, name)).parameters)
    have = list(inspect.signature(real).parameters)
    assert have == want, f"{name}: parameters {have} != contract {want}"
    assert inspect.iscoroutinefunction(real) == inspect.iscoroutinefunction(getattr(interfaces, name)), f"{name}: async mismatch"
