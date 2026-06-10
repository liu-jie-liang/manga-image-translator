"""集成测试配置"""
import pytest

# Hook to add --run-slow flag for integration tests
def pytest_addoption(parser):
    parser.addoption(
        "--run-slow", action="store_true", default=False,
        help="run slow integration tests (requires running services)"
    )

def pytest_configure(config):
    config.addinivalue_line(
        "markers", "slow: mark test as slow (requires running services)"
    )

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--run-slow"):
        skip_slow = pytest.mark.skip(reason="需要 --run-slow 选项")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)