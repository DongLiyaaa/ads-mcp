from concurrent.futures import ThreadPoolExecutor
import json
from unittest.mock import patch
import pytest
from cli_anything.amazon_ads_ops_workbench.control_plane.contracts import (
    public_catalog,
    invoke_contract,
    validate_arguments,
)
from cli_anything.amazon_ads_ops_workbench.control_plane.security import (
    password_hash,
    password_matches,
    redact,
    bound_hash,
    encrypt_config,
    decrypt_config,
    Problem,
)
from cli_anything.amazon_ads_ops_workbench.control_plane.worker import (
    mutation_outcome,
    validate_download_url,
)
from cli_anything.amazon_ads_ops_workbench.core.env import (
    AdsEnvironment,
    load_ads_environment,
)
from cli_anything.amazon_ads_ops_workbench.core.runtime import (
    OperationRuntime,
    operation_runtime,
    current_runtime,
)
from cli_anything.amazon_ads_ops_workbench.core.snapshot import normalize_campaign_row
from cryptography.fernet import Fernet

ENV = AdsEnvironment(
    "test-client-id", "test-client-secret", "test-refresh-token", "123", "NA", "US"
)


def test_catalog_does_not_expose_local_files_or_approval_execution():
    catalog = public_catalog()
    json.dumps(catalog, allow_nan=False)
    assert len(catalog) >= 120
    assert not any(
        r["operation"].startswith(("approvals.", "profiles.", "auth.")) for r in catalog
    )
    assert not any(
        set(r["inputSchema"]["properties"])
        & {"input_file", "output_dir", "marketplace", "confirm_submit", "dry_run"}
        for r in catalog
    )
    assert sum(r["kind"] == "report" for r in catalog) == 21


def test_plan_never_calls_upstream_or_writes_local_approval():
    with patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.create_campaign",
        side_effect=AssertionError("network write"),
    ):
        plan = invoke_contract(
            "campaigns.create",
            {
                "name": "test",
                "budget": 10,
                "targeting_type": "MANUAL",
                "start_date": "2026-10-14",
                "state": "PAUSED",
            },
            ENV,
            "plan",
        )
    assert plan["payload"]["campaigns"][0]["state"] == "PAUSED"
    assert current_runtime.get() is None


@pytest.mark.parametrize(
    "operation",
    [
        r["operation"]
        for r in public_catalog()
        if r["kind"] == "report"
        and r["operation"] not in {"reports.create-amc-query", "reports.create-full-funnel-campaigns"}
    ],
)
def test_all_report_builders_prepare_without_network(operation):
    with patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.exchange_refresh_token",
        side_effect=AssertionError("network"),
    ):
        body = invoke_contract(
            operation,
            {
                "start_date": "2026-10-01",
                "end_date": "2026-10-07",
                "time_unit": "DAILY",
            },
            ENV,
            "report_plan",
        )
    assert (
        body["startDate"] == "2026-10-01"
        and body["configuration"]["timeUnit"] == "DAILY"
    )


def test_thread_local_context_and_outputs():
    def run(number):
        env = AdsEnvironment(str(number), "s", "r", str(number), "NA", "US")
        with operation_runtime(OperationRuntime(env, "plan")):
            assert load_ads_environment().profile_id == str(number)
        return current_runtime.get()

    with ThreadPoolExecutor(max_workers=5) as pool:
        assert all(v is None for v in pool.map(run, range(30)))


@pytest.mark.parametrize("budget", [-1, 0, float("inf"), float("nan"), True, "10"])
def test_invalid_money_rejected(budget):
    with pytest.raises(Problem):
        validate_arguments("campaigns.create", {"budget": budget})


@pytest.mark.parametrize(
    "path",
    [
        "/sp/../sb/campaigns",
        "/sp/%2e%2e/a",
        "/sp//campaigns",
        "https://evil.example/sp",
        "/sp/campaigns?scope=other",
    ],
)
def test_raw_paths_cannot_escape_scope(path):
    with pytest.raises(Problem):
        validate_arguments("sp-raw.request", {"path": path})


@pytest.mark.parametrize(
    "url",
    [
        "http://a.s3.amazonaws.com/a",
        "https://127.0.0.1/a",
        "https://s3.amazonaws.com.evil.test/a",
        "https://u:p@a.s3.amazonaws.com/a",
        "https://a.s3.amazonaws.com:123/a",
    ],
)
def test_download_url_rejects_ssrf(url):
    with pytest.raises(ValueError):
        validate_download_url(url)


def test_download_url_accepts_amazon_s3():
    assert validate_download_url(
        "https://bucket.s3.amazonaws.com/report?signature=example"
    )


def test_result_does_not_equate_partial_or_unknown_with_success():
    assert (
        mutation_outcome({"campaigns": {"success": [{"campaignId": "1"}], "error": []}})
        == "SUCCEEDED"
    )
    assert (
        mutation_outcome(
            {
                "campaigns": {
                    "success": [{"campaignId": "1"}],
                    "error": [{"message": "bad"}],
                }
            }
        )
        == "PARTIAL"
    )
    assert mutation_outcome([{"code": "INVALID_ARGUMENT"}]) == "FAILED"
    assert mutation_outcome({}) == "UNKNOWN"


def test_secrets_and_signed_urls_redacted():
    output = json.dumps(
        redact(
            {
                "refresh_token": "secret",
                "credentials_ciphertext": "cipher",
                "msg": "Atza|secret amcp_secret https://bucket.s3.amazonaws.com/a?secret=yes",
            }
        )
    )
    assert (
        "secret" not in output
        and json.loads(output)["credentials_ciphertext"] == "[REDACTED]"
    )


def test_password_and_encryption_roundtrip():
    encoded = password_hash("strong-test-password")
    assert password_matches("strong-test-password", encoded)
    assert not password_matches("wrong", encoded)
    key = Fernet.generate_key().decode()
    encrypted = encrypt_config({"refresh_token": "private"}, key)
    assert (
        "private" not in encrypted
        and decrypt_config(encrypted, key)["refresh_token"] == "private"
    )


def test_plan_binding_covers_owner_account_profile():
    base = bound_hash("u", "a", "p", "op", {"bid": 1})
    assert (
        len(
            {
                base,
                bound_hash("v", "a", "p", "op", {"bid": 1}),
                bound_hash("u", "b", "p", "op", {"bid": 1}),
                bound_hash("u", "a", "q", "op", {"bid": 1}),
            }
        )
        == 4
    )


def test_v3_budget_display_fixed():
    row = normalize_campaign_row(
        {
            "campaignId": "1",
            "name": "x",
            "state": "PAUSED",
            "budget": {"budget": 10, "budgetType": "DAILY"},
        },
        "US",
    )
    assert row["budget"] == "DAILY $10.00"


def test_post_lists_follow_all_pages_and_detect_repeated_tokens():
    from cli_anything.amazon_ads_ops_workbench.core.client import AmazonAdsClient

    client = AmazonAdsClient(ENV)
    with patch.object(
        client,
        "_send_json",
        side_effect=[
            {"campaigns": [{"campaignId": "1"}], "nextToken": "next"},
            {"campaigns": [{"campaignId": "2"}]},
        ],
    ):
        assert len(client.list_campaigns("token", "123")) == 2
    with patch.object(
        client, "_send_json", return_value={"keywords": [], "nextToken": "repeated"}
    ):
        with pytest.raises(RuntimeError, match="Repeated pagination"):
            client._post_list("/sp/keywords/list", "token", "123", {})


def _setup_service(**overrides):
    from cli_anything.amazon_ads_ops_workbench.control_plane.service import Service
    from cli_anything.amazon_ads_ops_workbench.control_plane.settings import Settings

    settings = Settings(
        "postgresql+psycopg://unused",
        Fernet.generate_key().decode(),
        "x" * 40,
        **overrides,
    )
    # db=None: every case below must be rejected before touching the database.
    return Service(None, settings)


@pytest.mark.parametrize(
    "overrides, args, status",
    [
        (
            {"public_origin": "https://ads.example.com", "secure_cookies": True},
            ("owner", "long-password-1", ""),
            403,
        ),
        ({"setup_token": "expected-token"}, ("owner", "long-password-1", "wrong"), 403),
        ({}, ("o", "long-password-1", ""), 422),
        ({}, ("owner name", "long-password-1", ""), 422),
        ({}, ("owner", "short", ""), 422),
        ({}, ("owner-account", "OWNER-ACCOUNT", ""), 422),
    ],
)
def test_setup_admin_rejects_before_database(overrides, args, status):
    with pytest.raises(Problem) as error:
        _setup_service(**overrides).setup_admin(*args)
    assert error.value.status == status


def test_setup_availability_follows_origin_and_token():
    assert _setup_service().settings.loopback
    remote = {"public_origin": "https://ads.example.com", "secure_cookies": True}
    assert not _setup_service(**remote).settings.loopback


@pytest.mark.parametrize(
    "overrides, args, status",
    [
        (
            {"public_origin": "https://ads.example.com", "secure_cookies": True},
            ("owner", "long-password-1", ""),
            403,
        ),
        ({"setup_token": "expected-token"}, ("owner", "long-password-1", ""), 403),
        ({}, ("owner", "short", ""), 422),
        ({}, ("owner-account", "Owner-Account", ""), 422),
    ],
)
def test_reset_password_rejects_before_database(overrides, args, status):
    with pytest.raises(Problem) as error:
        _setup_service(**overrides).reset_password(*args, "127.0.0.1")
    assert error.value.status == status


def test_token_without_approve_scope_cannot_confirm():
    from cli_anything.amazon_ads_ops_workbench.control_plane.security import Actor

    actor = Actor("user", "token", frozenset({"changes:plan"}), ("account",), "t1")
    with pytest.raises(Problem) as error:
        _setup_service().approve(actor, "task", "确认", "a" * 64)
    assert error.value.status == 403


def test_full_funnel_plans_without_network():
    with patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.exchange_refresh_token",
        side_effect=AssertionError("network"),
    ):
        body = invoke_contract(
            "reports.create-full-funnel-campaigns",
            {"start_date": "2026-10-01", "end_date": "2026-10-07", "time_unit": "DAILY"},
            ENV,
            "report_plan",
        )
    assert body["unified"] is True and body["adProduct"] == "FULL_FUNNEL"
    assert (body["startDate"], body["endDate"]) == ("2026-10-01", "2026-10-07")
    assert body["fields"][:3] == ["date.value", "budgetCurrency.value", "campaign.id"]
    summary = invoke_contract(
        "reports.create-full-funnel-campaigns",
        {"start_date": "2026-10-01", "end_date": "2026-10-07", "time_unit": "SUMMARY"},
        ENV,
        "report_plan",
    )
    assert summary["fields"][0] == "dateRange.value"
    with pytest.raises(Problem):
        invoke_contract(
            "reports.create-full-funnel-campaigns",
            {"start_date": "2026-10-01", "end_date": "2026-10-07", "time_unit": "HOURLY"},
            ENV,
            "report_plan",
        )


@pytest.mark.parametrize(
    "header",
    [
        {"campaign.id": "1", "metric.totalCost": "2", "budgetCurrency.value": "USD", "date.value": "d"},
        {"Campaign ID": "1", "Total Cost": "2", "Budget Currency": "USD", "Date": "d"},
        {"campaignId": "1", "totalCost": "2", "campaignBudgetCurrencyCode": "USD", "date": "d"},
    ],
)
def test_unified_rows_normalize_any_header_spelling(header):
    from cli_anything.amazon_ads_ops_workbench.core.unified_reports import normalize_rows

    assert normalize_rows([{**header, "Extra": "x"}]) == [
        {"campaignId": "1", "cost": "2", "campaignBudgetCurrencyCode": "USD", "date": "d", "Extra": "x"}
    ]


def test_full_funnel_default_and_custom_fields():
    from cli_anything.amazon_ads_ops_workbench.core.unified_reports import (
        BASE_FIELDS,
        DEFAULT_METRICS,
        SELECTABLE_FIELDS,
    )

    assert len(DEFAULT_METRICS) == 31 and set(DEFAULT_METRICS) <= set(SELECTABLE_FIELDS)
    args = {"start_date": "2026-10-01", "end_date": "2026-10-07"}
    default = invoke_contract("reports.create-full-funnel-campaigns", args, ENV, "report_plan")
    assert default["fields"] == ["date.value", *BASE_FIELDS, *DEFAULT_METRICS]
    custom = invoke_contract(
        "reports.create-full-funnel-campaigns",
        {**args, "fields": ["roas", "METRIC.userReach, dayOfWeek.value", "metric.roas", "campaign.id"]},
        ENV,
        "report_plan",
    )
    assert custom["fields"] == [
        "date.value", *BASE_FIELDS, "metric.roas", "metric.userReach", "dayOfWeek.value"
    ]
    schema = next(
        r for r in public_catalog() if r["operation"] == "reports.create-full-funnel-campaigns"
    )["inputSchema"]["properties"]["fields"]
    assert schema["type"] == "array"


@pytest.mark.parametrize(
    "fields",
    [
        ["metric.notAMetric"],
        ["campaign.budget"],
        ["metric.impressionShare"],
        ["dayOfWeek.value"],
        ["metric.impressions," + ",".join(f"metric.x{i}" for i in range(3))],
    ],
)
def test_full_funnel_rejects_bad_fields(fields):
    with pytest.raises(Problem):
        invoke_contract(
            "reports.create-full-funnel-campaigns",
            {"start_date": "2026-10-01", "end_date": "2026-10-07", "fields": fields},
            ENV,
            "report_plan",
        )


def test_full_funnel_field_cap():
    from cli_anything.amazon_ads_ops_workbench.core.unified_reports import (
        MAX_CUSTOM_FIELDS,
        SELECTABLE_FIELDS,
        resolve_fields,
    )

    many = [f for f in SELECTABLE_FIELDS if f.startswith("metric.")]
    assert len(resolve_fields(many[:MAX_CUSTOM_FIELDS])) == MAX_CUSTOM_FIELDS
    with pytest.raises(ValueError):
        resolve_fields(many[: MAX_CUSTOM_FIELDS + 1])


def test_unified_rows_normalize_custom_fields():
    from cli_anything.amazon_ads_ops_workbench.core.unified_reports import normalize_rows

    assert normalize_rows(
        [{"metric.roas": 1, "Day of week": "MONDAY", "conversionSource.name": "x", "Purchases (new to brand)": 2}]
    ) == [{"roas": 1, "dayOfWeek": "MONDAY", "conversionSourceName": "x", "newToBrandPurchases": 2}]


def test_ff_campaign_fields_are_local_reference():
    with patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.exchange_refresh_token",
        side_effect=AssertionError("network"),
    ):
        overview = invoke_contract("ff-campaigns.fields", {}, ENV, "read")
        found = invoke_contract("ff-campaigns.fields", {"search": "roas"}, ENV, "read")
    assert overview["data"]["totalFields"] > 600 and "fields" not in overview["data"]
    assert "Reach" in overview["data"]["categories"]
    roas = {f["field"]: f for f in found["data"]["fields"]}
    assert roas["metric.roas"]["default"] is True and roas["metric.roas"]["column"] == "roas"


def test_ff_campaigns_list_is_read_only_query():
    calls = []

    def send(self, token, path, label, body=None, profile_id=None):
        calls.append((path, json.loads(json.dumps(body)), profile_id))
        if "nextToken" in body:
            return {"campaigns": [{"campaignId": "2", "name": "b", "state": "PAUSED", "extra": 1}]}
        return {"campaigns": [{"campaignId": "1", "name": "a", "state": "ENABLED"}], "nextToken": "t"}

    entry = next(r for r in public_catalog() if r["operation"] == "ff-campaigns.list")
    assert entry["kind"] == "read"
    with patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.exchange_refresh_token",
        return_value="tok",
    ), patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.list_profiles",
        return_value=[],
    ), patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient._ads_api_send", send
    ):
        out = invoke_contract(
            "ff-campaigns.list", {"states": ["enabled", "PAUSED"], "name": "brand"}, ENV, "read"
        )
    assert out["data"]["campaigns"] == [
        {"campaignId": "1", "name": "a", "state": "ENABLED"},
        {"campaignId": "2", "name": "b", "state": "PAUSED"},
    ]
    assert {c[0] for c in calls} == {"/adsApi/v1/query/campaigns"} and calls[0][2] == "123"
    assert calls[0][1]["adProductFilter"] == {"include": ["FULL_FUNNEL"]}
    assert calls[0][1]["stateFilter"] == {"include": ["ENABLED", "PAUSED"]}
    assert calls[0][1]["nameFilter"] == {"include": ["brand"], "queryTermMatchType": "BROAD_MATCH"}
    assert calls[1][1]["nextToken"] == "t"
    with pytest.raises(Problem):
        invoke_contract("ff-campaigns.list", {"max_results": 0}, ENV, "read")


def test_amc_query_plans_without_network():
    with patch(
        "cli_anything.amazon_ads_ops_workbench.core.client.AmazonAdsClient.exchange_refresh_token",
        side_effect=AssertionError("network"),
    ):
        body = invoke_contract(
            "reports.create-amc-query",
            {"template": "hour-of-day", "start_date": "2026-07-01", "end_date": "2026-09-28"},
            ENV,
            "report_plan",
        )
    assert body["amc"] is True and body["instanceId"] is None
    execution = body["execution"]
    assert "\n" not in execution["workflow"]["sqlQuery"]
    assert execution["timeWindowEnd"] == "2026-09-29T00:00:00"


@pytest.mark.parametrize(
    "arguments",
    [
        {"start_date": "2026-07-01", "end_date": "2026-07-07"},
        {"template": "hour-of-day", "sql": "SELECT 1", "start_date": "2026-07-01", "end_date": "2026-07-07"},
        {"template": "nope", "start_date": "2026-07-01", "end_date": "2026-07-07"},
        {"sql": "SELECT 1; SELECT 2", "start_date": "2026-07-01", "end_date": "2026-07-07"},
        {"template": "hour-of-day", "start_date": "2025-01-01", "end_date": "2026-07-07"},
    ],
)
def test_amc_query_rejects_bad_arguments(arguments):
    with pytest.raises(Problem) as error:
        validate_arguments("reports.create-amc-query", arguments)
    assert error.value.status == 400


def test_amc_query_allows_windows_beyond_31_days():
    validate_arguments(
        "reports.create-amc-query",
        {"template": "frequency-vs-conversion", "start_date": "2026-01-01", "end_date": "2026-09-30"},
    )


def test_worker_waits_out_database_outage():
    from sqlalchemy.exc import OperationalError
    from cli_anything.amazon_ads_ops_workbench.control_plane.worker import Worker

    worker = Worker.__new__(Worker)
    calls = iter([OperationalError("SELECT 1", {}, Exception("in recovery mode")), True, False])

    def run_one():
        value = next(calls)
        if isinstance(value, Exception):
            raise value
        return value

    worker.run_one = run_one
    assert [worker.step(), worker.step(), worker.step()] == [5, 0, 2]
