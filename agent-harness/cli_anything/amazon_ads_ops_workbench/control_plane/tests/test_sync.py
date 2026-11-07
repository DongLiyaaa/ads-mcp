from contextlib import nullcontext
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from cli_anything.amazon_ads_ops_workbench.control_plane.service import Service
from cli_anything.amazon_ads_ops_workbench.control_plane.security import Problem
from cli_anything.amazon_ads_ops_workbench.control_plane.contracts import validate_arguments


def service():
    svc = object.__new__(Service)
    svc.db = SimpleNamespace(sessions=lambda: nullcontext(None))
    svc.account = Mock(return_value=SimpleNamespace(profile={"timezone": "America/Los_Angeles"}))
    svc.amc_overview = Mock(return_value={"available": False, "reason": "未开通"})
    svc.create_task = Mock(side_effect=lambda actor, account, op, args, key, kind:
                           {"id": key, "operation": op, "status": "QUEUED"})
    return svc


def test_sync_dates_catalog_and_retry_identity():
    svc, actor = service(), Mock()
    result = svc.sync_reports(actor, "account-a", 7)
    from datetime import date
    assert (date.fromisoformat(result["end_date"]) - date.fromisoformat(result["start_date"])).days == 6
    assert len(result["tasks"]) == 20
    assert len(result["skipped"]) == 1
    for call in svc.create_task.call_args_list:
        _, account, op, args, key, kind = call.args
        assert account == "account-a" and kind == "report" and len(key) <= 120
        validate_arguments(op, args)
    retry = svc.sync_reports(actor, "account-a", 7)
    assert result["tasks"] == retry["tasks"]
    other = svc.sync_reports(actor, "account-b", 7)
    assert result["tasks"][0]["id"] != other["tasks"][0]["id"]


def test_sync_amc_source_filter_and_partial_failure():
    svc = service()
    svc.amc_overview.return_value = {
        "available": True, "dataSources": [{"id": "available"}],
        "templates": [
            {"id": "full-a", "category": "full", "sources": ["available"]},
            {"id": "full-b", "category": "full", "sources": ["missing"]},
            {"id": "analysis", "category": "analysis", "sources": ["available"]},
        ],
    }
    def create(actor, account, op, args, key, kind):
        if op == "reports.create-sd-campaigns":
            raise Problem(400, "不可用")
        return {"id": key, "operation": op, "arguments": args}
    svc.create_task.side_effect = create
    result = svc.sync_reports(Mock(), "account-a", 1)
    assert result["start_date"] == result["end_date"]
    assert len(result["tasks"]) == 20
    assert len(result["failures"]) == 1
    assert result["skipped"][0]["operation"] == "full-b"
    assert result["tasks"][-1]["arguments"]["time_zone"] == "America/Los_Angeles"


def test_sync_rejects_invalid_timezone_and_range_before_enqueue():
    svc = service()
    with pytest.raises(Problem):
        svc.sync_reports(Mock(), "account-a", 2)
    svc.account.return_value.profile = {}
    with pytest.raises(Problem):
        svc.sync_reports(Mock(), "account-a", 1)
    svc.create_task.assert_not_called()
