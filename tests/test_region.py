from pathlib import Path
import sys

import pytest


PROJECT_DIR = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_DIR / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from config.region import RegionError, api_base_for_region, normalize_region, resolve_region


def test_region_normalization_and_aliases():
    assert normalize_region("cn") == "cn"
    assert normalize_region("SG") == "sg"
    assert normalize_region("de") == "eu"
    assert normalize_region("cloud_region_us") == "us"
    assert normalize_region("local-dev") == "dev"


def test_unknown_region_is_rejected():
    with pytest.raises(RegionError, match="不支持的 Region"):
        normalize_region("unknown")


def test_request_region_precedes_deployment_default():
    assert resolve_region("us", "sg") == "us"
    assert resolve_region(None, "sg") == "sg"
    assert resolve_region(None, None) == "cn"


def test_standard_cloud_base_allows_request_level_region_routing():
    assert api_base_for_region("cn") == "https://api.yeelight.com"
    assert api_base_for_region("sg") == "https://api-sg.yeelight.com"
    assert api_base_for_region("us") == "https://api-us.yeelight.com"
    assert api_base_for_region("eu") == "https://api-de.yeelight.com"
    assert api_base_for_region("eu", "https://api.yeelight.com", "cn") == "https://api-de.yeelight.com"


def test_custom_base_is_fixed_to_deployment_default_region():
    assert api_base_for_region("cn", "http://127.0.0.1:8080/apis/iot", "cn") == "http://127.0.0.1:8080"
    with pytest.raises(RegionError, match="固定 Region"):
        api_base_for_region("eu", "http://127.0.0.1:8080", "cn")
