import os
import pytest
from unittest.mock import patch

os.makedirs("/home/frappe/logs", exist_ok=True)


@pytest.fixture(autouse=True)
def frappe_no_context():
    """Patch Frappe internals so unit tests run without a live site."""
    with patch("frappe.utils.data.get_system_timezone", return_value="UTC"), patch(
        "frappe.translate.get_all_translations", return_value={}
    ):
        yield
