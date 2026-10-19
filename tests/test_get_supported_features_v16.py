"""Tests for feature-profile parsing in get_supported_features (OCPP 1.6).

Covers the truncated SupportedFeatureProfiles fallback added for #2206:
some chargers (e.g. BYD AC0207EI50) report "RemoteTrigge" instead of
"RemoteTrigger" due to a fixed-size buffer.
"""

from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from custom_components.ocpp.enums import OcppMisc as om
from custom_components.ocpp.enums import Profiles as prof
from custom_components.ocpp.ocppv16 import ChargePoint as ChargePointv16


@pytest.fixture
def cp_v16():
    """Provide a minimally-initialized v1.6 ChargePoint instance.

    We bypass __init__ and set only the attributes get_supported_features
    uses, following the pattern of test_set_charge_rate_v16.py.
    """
    cp = object.__new__(ChargePointv16)  # type: ignore[misc]
    cp.settings = SimpleNamespace(force_smart_charging=False)
    cp.call = AsyncMock()
    cp.notify_ha = AsyncMock()
    return cp


def _response_with_profiles(profiles: str):
    """Simulate a GetConfiguration response carrying SupportedFeatureProfiles."""
    return SimpleNamespace(configuration_key=[{om.value: profiles}])


async def test_exact_profiles_are_parsed(cp_v16):
    """Exact profile names keep matching as before."""
    cp_v16.call.return_value = _response_with_profiles(
        f"{om.feature_profile_core},{om.feature_profile_firmware}"
    )
    assert await cp_v16.get_supported_features() == prof.CORE | prof.FW
    cp_v16.notify_ha.assert_not_called()


async def test_truncated_remote_trigger_is_matched_by_prefix(cp_v16):
    """BYD AC0207EI50 (#2206) truncates "RemoteTrigger" to "RemoteTrigge"."""
    cp_v16.call.return_value = _response_with_profiles(
        f"{om.feature_profile_core},RemoteTrigge"
    )
    assert await cp_v16.get_supported_features() == prof.CORE | prof.REM
    cp_v16.notify_ha.assert_not_called()


async def test_unknown_profile_is_still_reported(cp_v16):
    """Genuinely unknown profiles still produce the warning path."""
    cp_v16.call.return_value = _response_with_profiles("FooBar")
    assert await cp_v16.get_supported_features() == prof.NONE
    cp_v16.notify_ha.assert_called()


async def test_empty_profile_defaults_to_core(cp_v16):
    """An empty SupportedFeatureProfiles value defaults to Core."""
    cp_v16.call.return_value = _response_with_profiles("")
    assert await cp_v16.get_supported_features() == prof.CORE


async def test_force_smart_charging_adds_smart_profile(cp_v16):
    """The force_smart_charging option ORs in the Smart profile."""
    cp_v16.settings.force_smart_charging = True
    cp_v16.call.return_value = _response_with_profiles(om.feature_profile_core)
    assert await cp_v16.get_supported_features() == prof.CORE | prof.SMART


async def test_truncated_name_matching_all_profiles_still_parses(cp_v16):
    """All six profiles with the last one truncated parse without warnings."""
    cp_v16.call.return_value = _response_with_profiles(
        "Core,FirmwareManagement,SmartCharging,Reservation,RemoteTrigge,LocalAuthListManagemen"
    )
    assert await cp_v16.get_supported_features() == (
        prof.CORE | prof.FW | prof.SMART | prof.RES | prof.REM | prof.AUTH
    )
    cp_v16.notify_ha.assert_not_called()
