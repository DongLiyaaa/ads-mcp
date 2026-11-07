from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
import os
import shlex
from typing import Any

import click

from cli_anything.amazon_ads_ops_workbench import __version__
from cli_anything.amazon_ads_ops_workbench.core.approvals import (
    CONFIRMATION_PROMPT,
    assert_confirmation_text,
    list_approval_plans,
    mark_approval_plan_executed,
    payload_hash,
    read_approval_plan,
    write_approval_plan,
)
from cli_anything.amazon_ads_ops_workbench.core.campaigns import (
    build_campaign_bidding_strategy_payload,
    build_campaign_budget_payload,
    build_campaign_create_payload,
    build_campaign_placement_bid_payload,
    build_campaign_state_payload,
    build_portfolio_create_payload,
    build_portfolio_state_payload,
)
from cli_anything.amazon_ads_ops_workbench.core.capabilities import (
    build_capability_contract,
)
from cli_anything.amazon_ads_ops_workbench.core.client import AmazonAdsClient
from cli_anything.amazon_ads_ops_workbench.core.dispatch import execute_approved_operation
from cli_anything.amazon_ads_ops_workbench.core.env import load_ads_environment
from cli_anything.amazon_ads_ops_workbench.core.keywords import (
    build_ad_groups_filter,
    build_ad_group_bid_payload,
    build_ad_group_create_payload,
    build_ad_group_negative_payload,
    build_ad_group_state_payload,
    build_asin_target_create_payload,
    build_campaign_negative_payload,
    build_category_target_create_payload,
    build_expression_target_create_payload,
    build_keyword_create_payload,
    build_keyword_edit_payload,
    build_keyword_state_payload,
    build_keywords_filter,
    build_negative_state_payload,
    build_negative_list_filter,
    build_negative_target_payload,
    build_negative_target_state_payload,
    build_negative_targets_filter,
    build_product_ad_create_payload,
    build_product_ad_state_payload,
    build_product_ads_filter,
    build_target_bid_payload,
    build_target_state_payload,
    build_targets_filter,
    normalize_ad_group_row,
    normalize_keyword_row,
    normalize_negative_row,
    normalize_negative_target_row,
    normalize_portfolio_row,
    normalize_product_ad_row,
    normalize_target_row,
)
from cli_anything.amazon_ads_ops_workbench.core.reports import (
    build_download_target_path,
    build_sb_ad_groups_report_body,
    build_sb_campaign_placement_report_body,
    build_sb_campaigns_report_body,
    build_sb_search_term_report_body,
    build_sb_targeting_report_body,
    build_sd_ad_groups_report_body,
    build_sd_campaigns_report_body,
    build_sd_product_ads_report_body,
    build_sd_targeting_report_body,
    build_sp_ad_groups_report_body,
    build_sp_advertised_products_report_body,
    build_sp_campaign_placement_report_body,
    build_sp_campaigns_report_body,
    build_sp_gross_and_invalids_report_body,
    build_sp_keywords_report_body,
    build_sp_purchased_products_report_body,
    build_sp_impression_share_report_body,
    build_sp_search_term_report_body,
    build_sp_targeting_report_body,
    load_report_rows,
    normalize_report_status,
    normalize_sb_report_row,
    normalize_sd_report_row,
    normalize_sp_campaign_placement_report_row,
    normalize_search_term_report_row,
    normalize_sp_keyword_report_row,
    summarize_report_rows,
)
from cli_anything.amazon_ads_ops_workbench.core.amc import (
    build_execution_body as build_amc_execution_body,
    public_templates as public_amc_templates,
    resolve_query as resolve_amc_query,
    summarize_data_sources as summarize_amc_data_sources,
    summarize_instance as summarize_amc_instance,
)
from cli_anything.amazon_ads_ops_workbench.core.sponsored_brands import (
    assert_sb_raw_allowed,
    build_sb_ad_group_archive_payload,
    build_sb_ad_group_create_payload,
    build_sb_ad_group_update_payload,
    build_sb_ad_groups_filter,
    build_sb_campaign_archive_payload,
    build_sb_campaign_create_payload,
    build_sb_campaign_update_payload,
    build_sb_campaigns_filter,
    build_sb_keyword_create_payload,
    build_sb_keyword_update_payload,
    build_sb_legacy_filter,
    build_sb_negative_keyword_payload,
    build_sb_negative_keyword_update_payload,
    build_sb_negative_target_payload,
    build_sb_negative_target_update_payload,
    build_sb_target_payload,
    build_sb_target_update_payload,
    normalize_sb_ad_group_row,
    normalize_sb_campaign_row,
    normalize_sb_keyword_row,
    normalize_sb_negative_keyword_row,
    normalize_sb_negative_target_row,
    normalize_sb_predicates,
    normalize_sb_target_row,
)
from cli_anything.amazon_ads_ops_workbench.core.sponsored_display import (
    assert_sd_raw_allowed,
    build_sd_ad_group_create_payload,
    build_sd_ad_group_update_payload,
    build_sd_audience_discovery_payload,
    build_sd_audience_taxonomy_payload,
    build_sd_budget_rule_association_payload,
    build_sd_budget_rule_create_payload,
    build_sd_budget_rule_update_payload,
    build_sd_budget_usage_payload,
    build_sd_campaign_create_payload,
    build_sd_campaign_update_payload,
    build_sd_location_payload,
    build_sd_location_update_payload,
    build_sd_product_ad_create_payload,
    build_sd_product_ad_update_payload,
    build_sd_query_filter,
    build_sd_snapshot_payload,
    build_sd_target_payload,
    build_sd_target_update_payload,
    normalize_sd_ad_group_row,
    normalize_sd_budget_rule_row,
    normalize_sd_campaign_row,
    normalize_sd_predicates,
    normalize_sd_product_ad_row,
    normalize_sd_target_row,
)
from cli_anything.amazon_ads_ops_workbench.core.snapshot import (
    build_auth_health,
    build_snapshot,
    pick_profile_id,
)


def emit(payload: Any, as_json: bool) -> None:
    from cli_anything.amazon_ads_ops_workbench.core.runtime import current_runtime
    runtime = current_runtime.get()
    if runtime is not None:
        runtime.output = payload
        return
    if as_json:
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    if isinstance(payload, dict):
        click.echo(json.dumps(payload, ensure_ascii=False, indent=2))
        return
    click.echo(str(payload))


def load_live_context(marketplace: str | None):
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    health = build_auth_health(env)
    if not health["ok"]:
        return env, target_marketplace, None, None, None, health
    client = AmazonAdsClient(env)
    from cli_anything.amazon_ads_ops_workbench.core.runtime import current_runtime
    runtime = current_runtime.get()
    if runtime is not None and runtime.mode in {'plan', 'report_plan'}:
        return env, target_marketplace, client, '', env.profile_id, health
    access_token = client.exchange_refresh_token()
    profiles = client.list_profiles(access_token)
    profile_id = env.profile_id or pick_profile_id(profiles, target_marketplace)
    return env, target_marketplace, client, access_token, profile_id, health


def build_domain_fallback(
    domain: str,
    health: dict[str, Any],
    data_key: str,
    requested: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "meta": {
            "mode": "mock",
            "status": "attention",
            "missingCredentials": health["missingCredentials"],
        },
        "data": {
            data_key: [],
            "requested": requested or {},
        },
        "domain": domain,
    }


def emit_live_rows(
    ctx: click.Context,
    marketplace: str | None,
    domain: str,
    data_key: str,
    requested: dict[str, Any],
    fetch_rows,
    normalize_row,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(domain, health, data_key, requested),
            ctx.obj["json"],
        )
        return
    if client is None or access_token is None or profile_id is None:
        raise click.UsageError("Live context is incomplete.")
    rows = fetch_rows(client, access_token, profile_id)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {data_key: [normalize_row(row) for row in rows]},
            "domain": domain,
        },
        ctx.obj["json"],
    )


def emit_live_result(
    ctx: click.Context,
    marketplace: str | None,
    domain: str,
    data_key: str,
    requested: dict[str, Any],
    fetch_result,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            {
                "meta": {
                    "mode": "mock",
                    "status": "attention",
                    "missingCredentials": health["missingCredentials"],
                },
                "data": {
                    data_key: None,
                    "requested": requested,
                },
                "domain": domain,
            },
            ctx.obj["json"],
        )
        return
    if client is None or access_token is None or profile_id is None:
        raise click.UsageError("Live context is incomplete.")
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {
                data_key: fetch_result(client, access_token, profile_id),
            },
            "domain": domain,
        },
        ctx.obj["json"],
    )


def emit_dry_run(
    ctx: click.Context,
    marketplace: str,
    payload: dict[str, Any],
    operation: str,
    policy: str = "user_supplied_values_only",
) -> None:
    data = {
        "payload": payload,
        "policy": policy,
    }
    if policy == "user_supplied_percentages_only":
        data["placementPolicy"] = policy
    emit(
        {
            "meta": {
                "mode": "dry-run",
                "status": "not_submitted",
                "marketplace": marketplace,
                "operation": operation,
            },
            "data": data,
        },
        ctx.obj["json"],
    )


def emit_approval_plan(
    ctx: click.Context,
    marketplace: str,
    payload: dict[str, Any],
    operation: str,
    policy: str = "user_supplied_values_only",
) -> None:
    plan = write_approval_plan(
        operation=operation,
        marketplace=marketplace,
        payload=payload,
        policy=policy,
    )
    data = {
        "payload": payload,
        "payloadHash": plan["payloadHash"],
        "riskLevel": plan["riskLevel"],
        "changeCount": plan["changeCount"],
        "policy": policy,
        "execution": plan["execution"],
    }
    if policy == "user_supplied_percentages_only":
        data["placementPolicy"] = policy
    emit(
        {
            "meta": {
                "mode": "approval-plan",
                "status": plan["status"],
                "marketplace": marketplace,
                "operation": operation,
                "planId": plan["planId"],
                "approvalPath": plan["_approvalPath"],
                "confirmationRequired": True,
                "confirmationPrompt": CONFIRMATION_PROMPT,
            },
            "data": data,
        },
        ctx.obj["json"],
    )


def intercept_mutation(
    ctx: click.Context,
    marketplace: str,
    payload: dict[str, Any],
    operation: str,
    dry_run: bool,
    policy: str = "user_supplied_values_only",
) -> bool:
    from cli_anything.amazon_ads_ops_workbench.core.runtime import current_runtime
    runtime = current_runtime.get()
    if runtime is not None:
        if runtime.mode != 'plan':
            raise click.UsageError('Mutation requires a server-side approval plan.')
        runtime.plan = {'operation': operation, 'payload': payload, 'policy': policy}
        return True
    if dry_run:
        emit_dry_run(ctx, marketplace, payload, operation, policy)
        return True
    emit_approval_plan(ctx, marketplace, payload, operation, policy)
    return True


def parse_predicate_options(
    predicate: tuple[str, ...],
    asin: str | None = None,
    category_id: str | None = None,
) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = []
    if asin:
        predicates.append({"type": "ASIN_SAME_AS", "value": asin})
    if category_id:
        predicates.append({"type": "CATEGORY_SAME_AS", "value": category_id})
    for raw_predicate in predicate:
        raw = raw_predicate.strip()
        if not raw:
            continue
        if "=" in raw:
            predicate_type, value = raw.split("=", 1)
        elif ":" in raw:
            predicate_type, value = raw.split(":", 1)
        else:
            predicate_type, value = raw, ""
        item: dict[str, Any] = {"type": predicate_type.strip().upper()}
        if value.strip():
            item["value"] = value.strip()
        predicates.append(item)
    if not predicates:
        raise click.BadParameter(
            "At least one of --asin, --category-id, or --predicate is required."
        )
    return predicates


def parse_json_payload(raw_payload: str | None) -> dict[str, Any] | list[Any] | None:
    if raw_payload is None or raw_payload.strip() == "":
        return None
    try:
        payload = json.loads(raw_payload)
    except json.JSONDecodeError as exc:
        raise click.BadParameter(f"payload-json is not valid JSON: {exc}") from exc
    if not isinstance(payload, (dict, list)):
        raise click.BadParameter("payload-json must decode to a JSON object or array.")
    return payload


@click.group(invoke_without_command=True)
@click.option("--json", "as_json", is_flag=True, help="Emit JSON output.")
@click.version_option(version=__version__)
@click.pass_context
def cli(ctx: click.Context, as_json: bool) -> None:
    """Amazon Ads Ops Workbench CLI."""
    ctx.ensure_object(dict)
    ctx.obj["json"] = as_json
    if ctx.invoked_subcommand is None:
        repl(as_json)


@cli.group()
def approvals() -> None:
    """Approval plans for live Amazon Ads mutations."""


@approvals.command("list")
@click.option(
    "--status",
    default=None,
    help="Optional status filter, such as awaiting_user_confirmation or executed.",
)
@click.option("--limit", default=20, type=int, help="Maximum plans to return.")
@click.pass_context
def approvals_list(ctx: click.Context, status: str | None, limit: int) -> None:
    emit(
        {
            "meta": {
                "mode": "local",
                "status": "ok",
            },
            "data": {
                "plans": list_approval_plans(status=status, limit=limit),
            },
        },
        ctx.obj["json"],
    )


@approvals.command("show")
@click.option("--plan-id", required=True, help="Approval plan id.")
@click.pass_context
def approvals_show(ctx: click.Context, plan_id: str) -> None:
    emit(read_approval_plan(plan_id), ctx.obj["json"])


@approvals.command("execute")
@click.option("--plan-id", required=True, help="Approval plan id.")
@click.option(
    "--confirm-text",
    required=True,
    help='Must be exactly "确认" after the user replies with that text.',
)
@click.pass_context
def approvals_execute(ctx: click.Context, plan_id: str, confirm_text: str) -> None:
    try:
        assert_confirmation_text(confirm_text)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from exc

    plan = read_approval_plan(plan_id)
    if plan.get("status") != "awaiting_user_confirmation":
        raise click.UsageError(
            f"Approval plan {plan_id} is not awaiting confirmation: {plan.get('status')}"
        )
    payload = plan.get("payload")
    if not isinstance(payload, dict):
        raise click.UsageError("Approval plan payload must be a JSON object.")
    expected_hash = payload_hash(
        str(plan.get("operation") or ""),
        str(plan.get("marketplace") or ""),
        payload,
    )
    if expected_hash != plan.get("payloadHash"):
        raise click.UsageError("Approval plan payload hash mismatch; refuse to execute.")

    plan_marketplace = plan.get("marketplace") if isinstance(plan.get("marketplace"), str) else None
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        plan_marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "approvals",
                health,
                "execution",
                {
                    "planId": plan_id,
                    "operation": plan.get("operation"),
                    "marketplace": target_marketplace,
                    "payloadHash": plan.get("payloadHash"),
                },
            ),
            ctx.obj["json"],
        )
        return
    if client is None or access_token is None or profile_id is None:
        raise click.UsageError("Live context is incomplete; cannot execute approval plan.")

    result = execute_approved_operation(client, access_token, profile_id, plan)
    executed_plan = mark_approval_plan_executed(plan_id, result)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "submitted",
                "planId": plan_id,
                "operation": plan.get("operation"),
                "marketplace": target_marketplace,
                "payloadHash": plan.get("payloadHash"),
                "approvalPath": executed_plan["_approvalPath"],
            },
            "data": {
                "result": result,
            },
        },
        ctx.obj["json"],
    )


@cli.command("capabilities")
@click.option(
    "--ad-product",
    default="ALL",
    type=click.Choice(["ALL", "SP", "SB", "SBV", "SD", "FF"], case_sensitive=False),
    help="Filter capabilities by ad product.",
)
@click.option(
    "--operation",
    default=None,
    help="Optional substring filter such as campaigns.edit-budget.",
)
@click.option(
    "--writes-only",
    is_flag=True,
    help="Return only approval-gated write/raw operations.",
)
@click.pass_context
def capabilities_command(
    ctx: click.Context,
    ad_product: str,
    operation: str | None,
    writes_only: bool,
) -> None:
    """Machine-readable capability contract for agents."""
    emit(
        build_capability_contract(
            ad_product=ad_product,
            operation=operation,
            writes_only=writes_only,
        ),
        ctx.obj["json"],
    )


@cli.group()
def auth() -> None:
    """Authentication and credential health commands."""


@auth.command("health")
@click.pass_context
def auth_health(ctx: click.Context) -> None:
    env = load_ads_environment()
    emit(build_auth_health(env), ctx.obj["json"])


@cli.group()
def profiles() -> None:
    """Profile discovery commands."""


@profiles.command("list")
@click.pass_context
def profiles_list(ctx: click.Context) -> None:
    env = load_ads_environment()
    client = AmazonAdsClient(env)
    access_token = client.exchange_refresh_token()
    emit(client.list_profiles(access_token), ctx.obj["json"])


@profiles.command("resolve")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.pass_context
def profiles_resolve(ctx: click.Context, marketplace: str | None) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    health = build_auth_health(env)
    if not health["ok"]:
        emit(
            {
                "marketplace": target_marketplace,
                "profileId": "",
                "missingCredentials": health["missingCredentials"],
            },
            ctx.obj["json"],
        )
        return
    client = AmazonAdsClient(env)
    access_token = client.exchange_refresh_token()
    profile_rows = client.list_profiles(access_token)
    emit(
        {
            "marketplace": target_marketplace,
            "profileId": env.profile_id or pick_profile_id(profile_rows, target_marketplace),
            "profiles": profile_rows,
        },
        ctx.obj["json"],
    )


@cli.group()
def campaigns() -> None:
    """Sponsored Products campaign commands."""


@campaigns.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.pass_context
def campaigns_list(ctx: click.Context, marketplace: str | None) -> None:
    snapshot = build_snapshot(load_ads_environment(), marketplace=marketplace)
    emit(snapshot["data"].get("campaigns", []), ctx.obj["json"])


@campaigns.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--name", required=True, help="Campaign name.")
@click.option(
    "--targeting-type",
    required=True,
    type=click.Choice(["MANUAL", "AUTO"], case_sensitive=False),
    help="Campaign targeting type.",
)
@click.option("--budget", required=True, type=float, help="Campaign daily budget.")
@click.option("--start-date", required=True, help="Start date in YYYY-MM-DD format.")
@click.option("--end-date", default=None, help="Optional end date in YYYY-MM-DD format.")
@click.option("--budget-type", default="DAILY", help="Currently only DAILY is supported.")
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial campaign state.",
)
@click.option(
    "--strategy",
    default=None,
    type=click.Choice(
        ["AUTO_FOR_SALES", "LEGACY_FOR_SALES", "MANUAL"],
        case_sensitive=False,
    ),
    help="Optional dynamic bidding strategy.",
)
@click.option("--portfolio-id", default=None, help="Optional portfolio id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def campaigns_create(
    ctx: click.Context,
    marketplace: str | None,
    name: str,
    targeting_type: str,
    budget: float,
    start_date: str,
    end_date: str | None,
    budget_type: str,
    state: str,
    strategy: str | None,
    portfolio_id: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_campaign_create_payload(
        name=name,
        targeting_type=targeting_type,
        budget=budget,
        start_date=start_date,
        budget_type=budget_type,
        state=state,
        strategy=strategy,
        portfolio_id=portfolio_id,
        end_date=end_date,
    )
    request_payload = {"campaigns": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "campaigns.create", dry_run
    ):
        return

    health = build_auth_health(env)
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "campaigns",
                health,
                "campaigns",
                {
                    "marketplace": target_marketplace,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    client = AmazonAdsClient(env)
    access_token = client.exchange_refresh_token()
    profiles = client.list_profiles(access_token)
    profile_id = env.profile_id or pick_profile_id(profiles, target_marketplace)
    result = client.create_campaign(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@campaigns.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--state", required=True, help="ENABLED, PAUSED, or ARCHIVED.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def campaigns_set_state(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_campaign_state_payload(campaign_id=campaign_id, state=state)
    request_payload = {"campaigns": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "campaigns.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "campaigns",
                health,
                "campaigns",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_campaign(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@campaigns.command("edit-budget")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--budget", required=True, type=float, help="New campaign daily budget.")
@click.option("--budget-type", default="DAILY", help="Currently only DAILY is supported.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def campaigns_edit_budget(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    budget: float,
    budget_type: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_campaign_budget_payload(
        campaign_id=campaign_id,
        budget=budget,
        budget_type=budget_type,
    )
    request_payload = {"campaigns": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "campaigns.edit-budget", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "campaigns",
                health,
                "campaigns",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "budget": budget,
                    "budgetType": budget_type,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_campaign(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@campaigns.command("edit-bidding-strategy")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option(
    "--strategy",
    required=True,
    type=click.Choice(
        ["AUTO_FOR_SALES", "LEGACY_FOR_SALES", "MANUAL"],
        case_sensitive=False,
    ),
    help="Dynamic bidding strategy.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def campaigns_edit_bidding_strategy(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    strategy: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_campaign_bidding_strategy_payload(
        campaign_id=campaign_id,
        strategy=strategy,
    )
    request_payload = {"campaigns": [payload]}
    if intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "campaigns.edit-bidding-strategy",
        dry_run,
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "campaigns",
                health,
                "campaigns",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "strategy": strategy,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_campaign(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@campaigns.command("edit-placement-bids")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option(
    "--top-of-search",
    type=click.IntRange(0, 900),
    default=None,
    help="Top of search placement bid adjustment percentage, 0-900.",
)
@click.option(
    "--product-pages",
    type=click.IntRange(0, 900),
    default=None,
    help="Product pages placement bid adjustment percentage, 0-900.",
)
@click.option(
    "--rest-of-search",
    type=click.IntRange(0, 900),
    default=None,
    help="Rest of search placement bid adjustment percentage, 0-900.",
)
@click.option(
    "--strategy",
    type=click.Choice(
        ["AUTO_FOR_SALES", "LEGACY_FOR_SALES", "MANUAL"],
        case_sensitive=False,
    ),
    default=None,
    help="Optional bidding strategy to include in the update payload.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def campaigns_edit_placement_bids(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    top_of_search: int | None,
    product_pages: int | None,
    rest_of_search: int | None,
    strategy: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    try:
        payload = build_campaign_placement_bid_payload(
            campaign_id=campaign_id,
            top_of_search=top_of_search,
            product_pages=product_pages,
            rest_of_search=rest_of_search,
            strategy=strategy,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc

    request_payload = {"campaigns": [payload]}
    if intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "campaigns.edit-placement-bids",
        dry_run,
        policy="user_supplied_percentages_only",
    ):
        return

    health = build_auth_health(env)
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "campaigns",
                health,
                "campaigns",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "topOfSearch": top_of_search,
                    "productPages": product_pages,
                    "restOfSearch": rest_of_search,
                    "strategy": strategy,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return

    client = AmazonAdsClient(env)
    access_token = client.exchange_refresh_token()
    profiles = client.list_profiles(access_token)
    profile_id = env.profile_id or pick_profile_id(profiles, target_marketplace)
    result = client.edit_campaign(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {
                "result": result,
                "payload": request_payload,
                "placementPolicy": "user_supplied_percentages_only",
            },
        },
        ctx.obj["json"],
    )


@cli.group("portfolios")
def portfolios() -> None:
    """Portfolio discovery commands."""


@portfolios.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--state", "state_filter", default=None, help="Optional portfolio state filter.")
@click.pass_context
def portfolios_list(
    ctx: click.Context,
    marketplace: str | None,
    state_filter: str | None,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "portfolios",
                health,
                "portfolios",
                {
                    "marketplace": target_marketplace,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    rows = client.list_portfolios(access_token, profile_id)
    normalized = [normalize_portfolio_row(row) for row in rows]
    if state_filter:
        normalized = [
            row for row in normalized if row["state"].upper() == state_filter.upper()
        ]
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"portfolios": normalized},
        },
        ctx.obj["json"],
    )


@portfolios.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--name", required=True, help="Portfolio name.")
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial portfolio state.",
)
@click.option("--budget", type=float, default=None, help="Optional portfolio budget amount.")
@click.option("--budget-policy", default=None, help="Optional budget policy.")
@click.option("--budget-start-date", default=None, help="Optional budget start date.")
@click.option("--budget-end-date", default=None, help="Optional budget end date.")
@click.option("--currency-code", default=None, help="Optional budget currency code.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def portfolios_create(
    ctx: click.Context,
    marketplace: str | None,
    name: str,
    state: str,
    budget: float | None,
    budget_policy: str | None,
    budget_start_date: str | None,
    budget_end_date: str | None,
    currency_code: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_portfolio_create_payload(
        name=name,
        state=state,
        budget=budget,
        budget_policy=budget_policy,
        budget_start_date=budget_start_date,
        budget_end_date=budget_end_date,
        currency_code=currency_code,
    )
    request_payload = {"portfolios": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "portfolios.create", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "portfolios",
                health,
                "portfolios",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_portfolio(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@portfolios.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--portfolio-id", required=True, help="Portfolio id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="ENABLED, PAUSED, or ARCHIVED.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def portfolios_set_state(
    ctx: click.Context,
    marketplace: str | None,
    portfolio_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_portfolio_state_payload(portfolio_id=portfolio_id, state=state)
    request_payload = {"portfolios": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "portfolios.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "portfolios",
                health,
                "portfolios",
                {
                    "marketplace": target_marketplace,
                    "portfolioId": portfolio_id,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_portfolio(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group("ad-groups")
def ad_groups() -> None:
    """Sponsored Products ad group commands."""


@ad_groups.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--state", "state_filter", default="ENABLED", help="Ad group state filter.")
@click.pass_context
def ad_groups_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    state_filter: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "ad-groups",
                health,
                "adGroups",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_ad_groups_filter(campaign_id, ad_group_id, state_filter)
    rows = client.list_ad_groups(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"adGroups": [normalize_ad_group_row(row) for row in rows]},
        },
        ctx.obj["json"],
    )


@ad_groups.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--name", required=True, help="Ad group name.")
@click.option("--default-bid", required=True, type=float, help="Default CPC bid.")
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial ad group state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def ad_groups_create(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    name: str,
    default_bid: float,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_ad_group_create_payload(
        campaign_id=campaign_id,
        name=name,
        default_bid=default_bid,
        state=state,
    )
    request_payload = {"adGroups": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "ad-groups.create", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "ad-groups",
                health,
                "adGroups",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_ad_group(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@ad_groups.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="ENABLED, PAUSED, or ARCHIVED.",
)
@click.option("--default-bid", type=float, default=None, help="Optional default bid to retain/update.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def ad_groups_set_state(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    state: str,
    default_bid: float | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_ad_group_state_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        state=state,
        default_bid=default_bid,
    )
    request_payload = {"adGroups": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "ad-groups.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "ad-groups",
                health,
                "adGroups",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_ad_group(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@ad_groups.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--default-bid", required=True, type=float, help="New ad group default CPC bid.")
@click.option(
    "--state",
    default=None,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Optional state to include if Amazon requires a full update.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def ad_groups_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    default_bid: float,
    state: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_ad_group_bid_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        default_bid=default_bid,
        state=state,
    )
    request_payload = {"adGroups": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "ad-groups.edit-bid", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "ad-groups",
                health,
                "adGroups",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "defaultBid": default_bid,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_ad_group(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group()
def keywords() -> None:
    """Sponsored Products keyword commands."""


@keywords.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--state", "state_filter", default="ENABLED", help="Keyword state filter.")
@click.pass_context
def keywords_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    state_filter: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "keywords",
                health,
                "keywords",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_keywords_filter(campaign_id, ad_group_id, state_filter)
    rows = client.list_keywords(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {
                "keywords": [normalize_keyword_row(row) for row in rows],
            },
        },
        ctx.obj["json"],
    )


@keywords.command("add")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--keyword-text", required=True, help="Keyword text.")
@click.option(
    "--match-type",
    required=True,
    type=click.Choice(["BROAD", "PHRASE", "EXACT"], case_sensitive=False),
    help="Keyword match type.",
)
@click.option("--bid", type=float, default=None, help="Optional keyword CPC bid.")
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial keyword state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def keywords_add(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    keyword_text: str,
    match_type: str,
    bid: float | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_keyword_create_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        keyword_text=keyword_text,
        match_type=match_type,
        bid=bid,
        state=state,
    )
    request_payload = {"keywords": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "keywords.add", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "keywords",
                health,
                "keywords",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_keyword(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@keywords.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--keyword-id", required=True, help="Keyword id.")
@click.option("--bid", required=True, type=float, help="New CPC bid.")
@click.option(
    "--state",
    default=None,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Optional state to include if Amazon requires a full update.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def keywords_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    keyword_id: str,
    bid: float,
    state: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_keyword_edit_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        keyword_id=keyword_id,
        bid=bid,
        state=state,
    )
    request_payload = {"keywords": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "keywords.edit-bid", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "keywords",
                health,
                "keywords",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "keywordId": keyword_id,
                    "bid": bid,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_keyword(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@keywords.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--keyword-id", required=True, help="Keyword id.")
@click.option("--state", required=True, help="ENABLED, PAUSED, or ARCHIVED.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def keywords_set_state(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    keyword_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_keyword_state_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        keyword_id=keyword_id,
        state=state,
    )
    request_payload = {"keywords": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "keywords.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "keywords",
                health,
                "keywords",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "keywordId": keyword_id,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_keyword(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group("product-ads")
def product_ads() -> None:
    """Sponsored Products advertised product commands."""


@product_ads.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--product-ad-id", default=None, help="Optional product ad id filter.")
@click.option("--state", "state_filter", default="ENABLED", help="Product ad state filter.")
@click.pass_context
def product_ads_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    product_ad_id: str | None,
    state_filter: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "product-ads",
                health,
                "productAds",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "productAdId": product_ad_id,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_product_ads_filter(campaign_id, ad_group_id, product_ad_id, state_filter)
    rows = client.list_product_ads(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"productAds": [normalize_product_ad_row(row) for row in rows]},
        },
        ctx.obj["json"],
    )


@product_ads.command("add")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--sku", default=None, help="Advertised product SKU. Use either SKU or ASIN.")
@click.option("--asin", default=None, help="Advertised product ASIN. Use either SKU or ASIN.")
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial product ad state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def product_ads_add(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    sku: str | None,
    asin: str | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    try:
        payload = build_product_ad_create_payload(
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            sku=sku,
            asin=asin,
            state=state,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"productAds": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "product-ads.add", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "product-ads",
                health,
                "productAds",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_product_ad(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@product_ads.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--product-ad-id", required=True, help="Product ad id.")
@click.option("--campaign-id", default=None, help="Optional campaign id.")
@click.option("--ad-group-id", default=None, help="Optional ad group id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="ENABLED, PAUSED, or ARCHIVED.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def product_ads_set_state(
    ctx: click.Context,
    marketplace: str | None,
    product_ad_id: str,
    campaign_id: str | None,
    ad_group_id: str | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_product_ad_state_payload(
        product_ad_id=product_ad_id,
        state=state,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
    )
    request_payload = {"productAds": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "product-ads.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "product-ads",
                health,
                "productAds",
                {
                    "marketplace": target_marketplace,
                    "productAdId": product_ad_id,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_product_ad(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group("targets")
def targets() -> None:
    """Sponsored Products product targeting commands."""


@targets.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--target-id", default=None, help="Optional target id filter.")
@click.option("--state", "state_filter", default="ENABLED", help="Targeting clause state filter.")
@click.pass_context
def targets_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    target_id: str | None,
    state_filter: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "targets",
                health,
                "targets",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "targetId": target_id,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_targets_filter(campaign_id, ad_group_id, target_id, state_filter)
    rows = client.list_targets(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"targets": [normalize_target_row(row) for row in rows]},
        },
        ctx.obj["json"],
    )


@targets.command("add-asin")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", required=True, help="Target ASIN.")
@click.option("--bid", type=float, default=None, help="Optional target CPC bid.")
@click.option(
    "--expression-type",
    default="MANUAL",
    type=click.Choice(["MANUAL", "AUTO"], case_sensitive=False),
    help="Targeting expression type.",
)
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def targets_add_asin(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    asin: str,
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_asin_target_create_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        asin=asin,
        bid=bid,
        state=state,
        expression_type=expression_type,
    )
    request_payload = {"targetingClauses": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "targets.add-asin", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "targets",
                health,
                "targets",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@targets.command("add-category")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--category-id", required=True, help="Amazon category id.")
@click.option("--bid", type=float, default=None, help="Optional target CPC bid.")
@click.option(
    "--expression-type",
    default="MANUAL",
    type=click.Choice(["MANUAL", "AUTO"], case_sensitive=False),
    help="Targeting expression type.",
)
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def targets_add_category(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    category_id: str,
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_category_target_create_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        category_id=category_id,
        bid=bid,
        state=state,
        expression_type=expression_type,
    )
    request_payload = {"targetingClauses": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "targets.add-category", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "targets",
                health,
                "targets",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@targets.command("add-expression")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", default=None, help="Shortcut predicate ASIN_SAME_AS=<asin>.")
@click.option("--category-id", default=None, help="Shortcut predicate CATEGORY_SAME_AS=<category_id>.")
@click.option(
    "--predicate",
    multiple=True,
    help="Additional predicate as TYPE=VALUE, TYPE:VALUE, or TYPE. Repeat as needed.",
)
@click.option("--bid", type=float, default=None, help="Optional target CPC bid.")
@click.option(
    "--expression-type",
    default="MANUAL",
    type=click.Choice(["MANUAL", "AUTO"], case_sensitive=False),
    help="Targeting expression type.",
)
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def targets_add_expression(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    asin: str | None,
    category_id: str | None,
    predicate: tuple[str, ...],
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    predicates = parse_predicate_options(predicate, asin=asin, category_id=category_id)
    try:
        payload = build_expression_target_create_payload(
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            predicates=predicates,
            bid=bid,
            state=state,
            expression_type=expression_type,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"targetingClauses": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "targets.add-expression", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "targets",
                health,
                "targets",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@targets.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--campaign-id", default=None, help="Optional campaign id.")
@click.option("--ad-group-id", default=None, help="Optional ad group id.")
@click.option("--bid", required=True, type=float, help="New target CPC bid.")
@click.option(
    "--state",
    default=None,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Optional state to include if Amazon requires a full update.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def targets_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    campaign_id: str | None,
    ad_group_id: str | None,
    bid: float,
    state: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_target_bid_payload(
        target_id=target_id,
        bid=bid,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        state=state,
    )
    request_payload = {"targetingClauses": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "targets.edit-bid", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "targets",
                health,
                "targets",
                {
                    "marketplace": target_marketplace,
                    "targetId": target_id,
                    "bid": bid,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@targets.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--campaign-id", default=None, help="Optional campaign id.")
@click.option("--ad-group-id", default=None, help="Optional ad group id.")
@click.option("--bid", type=float, default=None, help="Optional target bid to retain/update.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="ENABLED, PAUSED, or ARCHIVED.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def targets_set_state(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    campaign_id: str | None,
    ad_group_id: str | None,
    bid: float | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_target_state_payload(
        target_id=target_id,
        state=state,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        bid=bid,
    )
    request_payload = {"targetingClauses": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "targets.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "targets",
                health,
                "targets",
                {
                    "marketplace": target_marketplace,
                    "targetId": target_id,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.edit_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group()
def negatives() -> None:
    """Negative keyword commands."""


@negatives.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--scope", type=click.Choice(["adGroup", "campaign", "both"]), default="both")
@click.option("--state", "state_filter", default="ENABLED", help="Negative keyword state filter.")
@click.pass_context
def negatives_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    scope: str,
    state_filter: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negatives",
                health,
                "negatives",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "scope": scope,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_negative_list_filter(campaign_id, ad_group_id, state_filter)
    rows = []
    if scope in {"adGroup", "both"}:
        rows.extend(
            normalize_negative_row(item, "adGroup")
            for item in client.list_negative_keywords(access_token, profile_id, payload)
        )
    if scope in {"campaign", "both"}:
        rows.extend(
            normalize_negative_row(item, "campaign")
            for item in client.list_campaign_negative_keywords(access_token, profile_id, payload)
        )
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"negatives": rows},
        },
        ctx.obj["json"],
    )


@negatives.command("add-ad-group")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--keyword-text", required=True, help="Negative keyword text.")
@click.option("--match-type", required=True, help="NEGATIVE_EXACT or NEGATIVE_PHRASE.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def negatives_add_ad_group(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    keyword_text: str,
    match_type: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_ad_group_negative_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        keyword_text=keyword_text,
        match_type=match_type,
    )
    request_payload = {"negativeKeywords": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "negatives.add-ad-group", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negatives",
                health,
                "negatives",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "keywordText": keyword_text,
                    "matchType": match_type,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_negative_keyword(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@negatives.command("add-campaign")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--keyword-text", required=True, help="Negative keyword text.")
@click.option("--match-type", required=True, help="NEGATIVE_EXACT or NEGATIVE_PHRASE.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def negatives_add_campaign(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    keyword_text: str,
    match_type: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_campaign_negative_payload(
        campaign_id=campaign_id,
        keyword_text=keyword_text,
        match_type=match_type,
    )
    request_payload = {"campaignNegativeKeywords": [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "negatives.add-campaign", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negatives",
                health,
                "negatives",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "keywordText": keyword_text,
                    "matchType": match_type,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_campaign_negative_keyword(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@negatives.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--negative-keyword-id", required=True, help="Negative keyword id.")
@click.option("--scope", type=click.Choice(["adGroup", "campaign"]), required=True)
@click.option("--state", required=True, help="ENABLED, PAUSED, or PROPOSED.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def negatives_set_state(
    ctx: click.Context,
    marketplace: str | None,
    negative_keyword_id: str,
    scope: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_negative_state_payload(
        keyword_id=negative_keyword_id,
        state=state,
    )
    payload_key = "campaignNegativeKeywords" if scope == "campaign" else "negativeKeywords"
    request_payload = {payload_key: [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "negatives.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negatives",
                health,
                "negatives",
                {
                    "marketplace": target_marketplace,
                    "negativeKeywordId": negative_keyword_id,
                    "scope": scope,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    if scope == "campaign":
        result = client.edit_campaign_negative_keyword(access_token, profile_id, payload)
    else:
        result = client.edit_negative_keyword(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group("negative-targets")
def negative_targets() -> None:
    """Sponsored Products negative product targeting commands."""


@negative_targets.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--negative-target-id", default=None, help="Optional negative target id filter.")
@click.option("--scope", type=click.Choice(["adGroup", "campaign", "both"]), default="both")
@click.option("--state", "state_filter", default="ENABLED", help="Negative target state filter.")
@click.pass_context
def negative_targets_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    negative_target_id: str | None,
    scope: str,
    state_filter: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negative-targets",
                health,
                "negativeTargets",
                {
                    "marketplace": target_marketplace,
                    "campaignId": campaign_id,
                    "adGroupId": ad_group_id,
                    "negativeTargetId": negative_target_id,
                    "scope": scope,
                    "state": state_filter,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_negative_targets_filter(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        target_id=negative_target_id,
        state_filter=state_filter,
    )
    rows = []
    if scope in {"adGroup", "both"}:
        rows.extend(
            normalize_negative_target_row(item, "adGroup")
            for item in client.list_negative_targets(access_token, profile_id, payload)
        )
    if scope in {"campaign", "both"}:
        rows.extend(
            normalize_negative_target_row(item, "campaign")
            for item in client.list_campaign_negative_targets(
                access_token,
                profile_id,
                payload,
            )
        )
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"negativeTargets": rows},
        },
        ctx.obj["json"],
    )


@negative_targets.command("add-ad-group")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", default=None, help="Shortcut predicate ASIN_SAME_AS=<asin>.")
@click.option("--category-id", default=None, help="Shortcut predicate CATEGORY_SAME_AS=<category_id>.")
@click.option(
    "--predicate",
    multiple=True,
    help="Additional predicate as TYPE=VALUE, TYPE:VALUE, or TYPE. Repeat as needed.",
)
@click.option(
    "--expression-type",
    default="MANUAL",
    type=click.Choice(["MANUAL", "AUTO"], case_sensitive=False),
    help="Targeting expression type.",
)
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial negative target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def negative_targets_add_ad_group(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    asin: str | None,
    category_id: str | None,
    predicate: tuple[str, ...],
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    predicates = parse_predicate_options(predicate, asin=asin, category_id=category_id)
    try:
        payload = build_negative_target_payload(
            campaign_id=campaign_id,
            ad_group_id=ad_group_id,
            predicates=predicates,
            state=state,
            expression_type=expression_type,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"negativeTargetingClauses": [payload]}
    if intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "negative-targets.add-ad-group",
        dry_run,
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negative-targets",
                health,
                "negativeTargets",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_negative_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@negative_targets.command("add-campaign")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--asin", default=None, help="Shortcut predicate ASIN_SAME_AS=<asin>.")
@click.option("--category-id", default=None, help="Shortcut predicate CATEGORY_SAME_AS=<category_id>.")
@click.option(
    "--predicate",
    multiple=True,
    help="Additional predicate as TYPE=VALUE, TYPE:VALUE, or TYPE. Repeat as needed.",
)
@click.option(
    "--state",
    default="ENABLED",
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Initial negative target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def negative_targets_add_campaign(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    asin: str | None,
    category_id: str | None,
    predicate: tuple[str, ...],
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    predicates = parse_predicate_options(predicate, asin=asin, category_id=category_id)
    try:
        payload = build_negative_target_payload(
            campaign_id=campaign_id,
            predicates=predicates,
            state=state,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"campaignNegativeTargetingClauses": [payload]}
    if intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "negative-targets.add-campaign",
        dry_run,
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negative-targets",
                health,
                "negativeTargets",
                {"marketplace": target_marketplace, "payload": request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.create_campaign_negative_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@negative_targets.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--negative-target-id", required=True, help="Negative target id.")
@click.option("--scope", type=click.Choice(["adGroup", "campaign"]), required=True)
@click.option("--campaign-id", default=None, help="Optional campaign id.")
@click.option("--ad-group-id", default=None, help="Optional ad group id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="ENABLED, PAUSED, or ARCHIVED.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def negative_targets_set_state(
    ctx: click.Context,
    marketplace: str | None,
    negative_target_id: str,
    scope: str,
    campaign_id: str | None,
    ad_group_id: str | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_negative_target_state_payload(
        target_id=negative_target_id,
        state=state,
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
    )
    payload_key = (
        "campaignNegativeTargetingClauses"
        if scope == "campaign"
        else "negativeTargetingClauses"
    )
    request_payload = {payload_key: [payload]}
    if intercept_mutation(
        ctx, target_marketplace, request_payload, "negative-targets.set-state", dry_run
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "negative-targets",
                health,
                "negativeTargets",
                {
                    "marketplace": target_marketplace,
                    "negativeTargetId": negative_target_id,
                    "scope": scope,
                    "state": state,
                    "payload": request_payload,
                },
            ),
            ctx.obj["json"],
        )
        return
    if scope == "campaign":
        result = client.edit_campaign_negative_target(access_token, profile_id, payload)
    else:
        result = client.edit_negative_target(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "payload": request_payload},
        },
        ctx.obj["json"],
    )


@cli.group("sb-campaigns")
def sb_campaigns() -> None:
    """Sponsored Brands campaign commands without ads or creative operations."""


@sb_campaigns.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--portfolio-id", default=None, help="Optional portfolio id filter.")
@click.option("--name", default=None, help="Optional exact name filter.")
@click.option("--include-extended-data", is_flag=True, help="Include extended fields when supported.")
@click.pass_context
def sb_campaigns_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    state_filter: str | None,
    portfolio_id: str | None,
    name: str | None,
    include_extended_data: bool,
) -> None:
    payload = build_sb_campaigns_filter(
        campaign_id=campaign_id,
        state_filter=state_filter,
        portfolio_id=portfolio_id,
        name=name,
        include_extended_data=include_extended_data,
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sb-campaigns",
        "campaigns",
        {"payload": payload},
        lambda client, access_token, profile_id: client.list_sb_campaigns(
            access_token, profile_id, payload
        ),
        normalize_sb_campaign_row,
    )


@sb_campaigns.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--name", required=True, help="Campaign name.")
@click.option("--budget", required=True, type=float, help="Campaign budget.")
@click.option(
    "--budget-type",
    default="DAILY",
    type=click.Choice(["DAILY", "LIFETIME"], case_sensitive=False),
    help="Budget type.",
)
@click.option(
    "--state",
    default="PAUSED",
    type=click.Choice(["ENABLED", "PAUSED"], case_sensitive=False),
    help="Initial campaign state. PAUSED is safer for newly created SB campaigns.",
)
@click.option("--start-date", default=None, help="Optional start date in YYYY-MM-DD.")
@click.option("--end-date", default=None, help="Optional end date in YYYY-MM-DD.")
@click.option("--portfolio-id", default=None, help="Optional portfolio id.")
@click.option("--brand-entity-id", default=None, help="Optional Brand Entity id.")
@click.option(
    "--cost-type",
    default=None,
    type=click.Choice(["CPC", "VCPM"], case_sensitive=False),
    help="Optional cost type.",
)
@click.option(
    "--goal",
    default=None,
    type=click.Choice(["PAGE_VISIT", "BRAND_IMPRESSION_SHARE"], case_sensitive=False),
    help="Optional SB campaign goal.",
)
@click.option(
    "--product-location",
    default=None,
    type=click.Choice(["SOLD_ON_AMAZON", "NOT_SOLD_ON_AMAZON"], case_sensitive=False),
    help="Optional product location.",
)
@click.option(
    "--smart-default",
    multiple=True,
    type=click.Choice(["MANUAL", "TARGETING"], case_sensitive=False),
    help="Optional smart default value; repeat as needed.",
)
@click.option("--bid-optimization/--no-bid-optimization", default=None, help="Optional SB bid optimization flag.")
@click.option(
    "--bid-optimization-strategy",
    default=None,
    type=click.Choice(
        ["MAXIMIZE_IMMEDIATE_SALES", "MAXIMIZE_NEW_TO_BRAND_CUSTOMERS"],
        case_sensitive=False,
    ),
    help="Optional SB bid optimization strategy.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_campaigns_create(
    ctx: click.Context,
    marketplace: str | None,
    name: str,
    budget: float,
    budget_type: str,
    state: str,
    start_date: str | None,
    end_date: str | None,
    portfolio_id: str | None,
    brand_entity_id: str | None,
    cost_type: str | None,
    goal: str | None,
    product_location: str | None,
    smart_default: tuple[str, ...],
    bid_optimization: bool | None,
    bid_optimization_strategy: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sb_campaign_create_payload(
        name=name,
        budget=budget,
        budget_type=budget_type,
        state=state,
        start_date=start_date,
        end_date=end_date,
        portfolio_id=portfolio_id,
        brand_entity_id=brand_entity_id,
        cost_type=cost_type,
        goal=goal,
        product_location=product_location,
        smart_default=smart_default,
        bid_optimization=bid_optimization,
        bid_optimization_strategy=bid_optimization_strategy,
    )
    request_payload = {"campaigns": [payload]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-campaigns.create",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_campaigns.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED"], case_sensitive=False),
    help="New campaign state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_campaigns_set_state(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "campaigns": [build_sb_campaign_update_payload(campaign_id, state=state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-campaigns.set-state",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_campaigns.command("edit-budget")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--budget", required=True, type=float, help="New budget.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_campaigns_edit_budget(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    budget: float,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "campaigns": [build_sb_campaign_update_payload(campaign_id, budget=budget)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-campaigns.edit-budget",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_campaigns.command("edit-name")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--name", required=True, help="New campaign name.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_campaigns_edit_name(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    name: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "campaigns": [build_sb_campaign_update_payload(campaign_id, name=name)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-campaigns.edit-name",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_campaigns.command("edit-bidding")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--bid-optimization/--no-bid-optimization", default=None, help="SB bid optimization flag.")
@click.option(
    "--bid-optimization-strategy",
    default=None,
    type=click.Choice(
        ["MAXIMIZE_IMMEDIATE_SALES", "MAXIMIZE_NEW_TO_BRAND_CUSTOMERS"],
        case_sensitive=False,
    ),
    help="Optional SB bid optimization strategy.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_campaigns_edit_bidding(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    bid_optimization: bool | None,
    bid_optimization_strategy: str | None,
    dry_run: bool,
) -> None:
    if bid_optimization is None and not bid_optimization_strategy:
        raise click.BadParameter("At least one bidding option is required.")
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "campaigns": [
            build_sb_campaign_update_payload(
                campaign_id,
                bid_optimization=bid_optimization,
                bid_optimization_strategy=bid_optimization_strategy,
            )
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-campaigns.edit-bidding",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_campaigns.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_campaigns_archive(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = build_sb_campaign_archive_payload(campaign_id)
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-campaigns.archive",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@cli.group("sb-ad-groups")
def sb_ad_groups() -> None:
    """Sponsored Brands ad group commands without ads or creative operations."""


@sb_ad_groups.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--name", default=None, help="Optional exact name filter.")
@click.option("--include-extended-data", is_flag=True, help="Include extended fields when supported.")
@click.pass_context
def sb_ad_groups_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    state_filter: str | None,
    name: str | None,
    include_extended_data: bool,
) -> None:
    payload = build_sb_ad_groups_filter(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        state_filter=state_filter,
        name=name,
        include_extended_data=include_extended_data,
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sb-ad-groups",
        "adGroups",
        {"payload": payload},
        lambda client, access_token, profile_id: client.list_sb_ad_groups(
            access_token, profile_id, payload
        ),
        normalize_sb_ad_group_row,
    )


@sb_ad_groups.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--name", required=True, help="Ad group name.")
@click.option(
    "--state",
    default="PAUSED",
    type=click.Choice(["ENABLED", "PAUSED"], case_sensitive=False),
    help="Initial ad group state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_ad_groups_create(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    name: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "adGroups": [build_sb_ad_group_create_payload(campaign_id, name, state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-ad-groups.create",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_ad_groups.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["ENABLED", "PAUSED"], case_sensitive=False),
    help="New ad group state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_ad_groups_set_state(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "adGroups": [build_sb_ad_group_update_payload(ad_group_id, state=state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-ad-groups.set-state",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_ad_groups.command("edit-name")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--name", required=True, help="New ad group name.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_ad_groups_edit_name(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    name: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "adGroups": [build_sb_ad_group_update_payload(ad_group_id, name=name)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-ad-groups.edit-name",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_ad_groups.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_ad_groups_archive(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = build_sb_ad_group_archive_payload(ad_group_id)
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-ad-groups.archive",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@cli.group("sb-keywords")
def sb_keywords() -> None:
    """Sponsored Brands keyword commands."""


@sb_keywords.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--keyword-id", default=None, help="Optional keyword id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--locale", default=None, help="Optional locale.")
@click.pass_context
def sb_keywords_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    keyword_id: str | None,
    state_filter: str | None,
    locale: str | None,
) -> None:
    query = build_sb_legacy_filter(campaign_id, ad_group_id, keyword_id, state_filter, locale)
    emit_live_rows(
        ctx,
        marketplace,
        "sb-keywords",
        "keywords",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sb_keywords(
            access_token, profile_id, query
        ),
        normalize_sb_keyword_row,
    )


@sb_keywords.command("add")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--keyword-text", required=True, help="Keyword text.")
@click.option(
    "--match-type",
    required=True,
    type=click.Choice(["broad", "phrase", "exact"], case_sensitive=False),
    help="SB keyword match type.",
)
@click.option("--bid", default=None, type=float, help="Optional keyword bid.")
@click.option("--native-language-keyword", default=None, help="Optional native language keyword.")
@click.option("--native-language-locale", default=None, help="Optional native language locale.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_keywords_add(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    keyword_text: str,
    match_type: str,
    bid: float | None,
    native_language_keyword: str | None,
    native_language_locale: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sb_keyword_create_payload(
        campaign_id,
        ad_group_id,
        keyword_text,
        match_type,
        bid,
        native_language_keyword,
        native_language_locale,
    )
    request_payload = {"keywords": [payload]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-keywords.add",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_keywords.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--keyword-id", required=True, help="Keyword id.")
@click.option("--bid", required=True, type=float, help="New bid.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_keywords_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    keyword_id: str,
    bid: float,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"keywords": [build_sb_keyword_update_payload(keyword_id, bid=bid)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-keywords.edit-bid",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_keywords.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--keyword-id", required=True, help="Keyword id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="New keyword state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_keywords_set_state(
    ctx: click.Context,
    marketplace: str | None,
    keyword_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"keywords": [build_sb_keyword_update_payload(keyword_id, state=state)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-keywords.set-state",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_keywords.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--keyword-id", required=True, help="Keyword id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_keywords_archive(
    ctx: click.Context,
    marketplace: str | None,
    keyword_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"keywordId": keyword_id}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-keywords.archive",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@cli.group("sb-negatives")
def sb_negatives() -> None:
    """Sponsored Brands negative keyword commands."""


@sb_negatives.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--negative-keyword-id", default=None, help="Optional negative keyword id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option(
    "--scope",
    default="both",
    type=click.Choice(["adGroup", "campaign", "both"], case_sensitive=False),
    help="Fetch ad-group, campaign, or both scopes.",
)
@click.pass_context
def sb_negatives_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    negative_keyword_id: str | None,
    state_filter: str | None,
    scope: str,
) -> None:
    query = build_sb_legacy_filter(
        campaign_id, ad_group_id, negative_keyword_id, state_filter
    )

    def fetch(client, access_token, profile_id):
        rows = client.list_sb_negative_keywords(access_token, profile_id, query)
        normalized_scope = scope.lower()
        if normalized_scope == "campaign":
            return [row for row in rows if not row.get("adGroupId")]
        if normalized_scope == "adgroup":
            return [row for row in rows if row.get("adGroupId")]
        return rows

    def normalize(row):
        return normalize_sb_negative_keyword_row(
            row, "adGroup" if row.get("adGroupId") else "campaign"
        )

    emit_live_rows(
        ctx,
        marketplace,
        "sb-negatives",
        "negatives",
        {"query": query, "scope": scope},
        fetch,
        normalize,
    )


@sb_negatives.command("add-ad-group")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--keyword-text", required=True, help="Negative keyword text.")
@click.option(
    "--match-type",
    default="negativeExact",
    type=click.Choice(["negativeExact", "negativePhrase", "NEGATIVE_EXACT", "NEGATIVE_PHRASE"], case_sensitive=False),
    help="SB negative keyword match type.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negatives_add_ad_group(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    keyword_text: str,
    match_type: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "negativeKeywords": [
            build_sb_negative_keyword_payload(
                campaign_id, keyword_text, match_type, ad_group_id=ad_group_id
            )
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negatives.add",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_negatives.command("add-campaign")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--keyword-text", required=True, help="Negative keyword text.")
@click.option(
    "--match-type",
    default="negativeExact",
    type=click.Choice(["negativeExact", "negativePhrase", "NEGATIVE_EXACT", "NEGATIVE_PHRASE"], case_sensitive=False),
    help="SB negative keyword match type.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negatives_add_campaign(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    keyword_text: str,
    match_type: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "negativeKeywords": [
            build_sb_negative_keyword_payload(campaign_id, keyword_text, match_type)
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negatives.add",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_negatives.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--negative-keyword-id", required=True, help="Negative keyword id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="New negative keyword state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negatives_set_state(
    ctx: click.Context,
    marketplace: str | None,
    negative_keyword_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "negativeKeywords": [
            build_sb_negative_keyword_update_payload(negative_keyword_id, state=state)
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negatives.set-state",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_negatives.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--negative-keyword-id", required=True, help="Negative keyword id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negatives_archive(
    ctx: click.Context,
    marketplace: str | None,
    negative_keyword_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"keywordId": negative_keyword_id}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negatives.archive",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@cli.group("sb-targets")
def sb_targets() -> None:
    """Sponsored Brands product/category targeting commands."""


@sb_targets.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--target-id", default=None, help="Optional target id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.pass_context
def sb_targets_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    target_id: str | None,
    state_filter: str | None,
) -> None:
    query = build_sb_legacy_filter(
        campaign_id,
        ad_group_id,
        target_id,
        state_filter,
        entity_key="targetId",
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sb-targets",
        "targets",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sb_targets(
            access_token, profile_id, query
        ),
        normalize_sb_target_row,
    )


@sb_targets.command("add-asin")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", required=True, help="ASIN to target.")
@click.option("--bid", default=None, type=float, help="Optional target bid.")
@click.option(
    "--state",
    default="enabled",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_targets_add_asin(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    asin: str,
    bid: float | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    expression = normalize_sb_predicates((), asin=asin)
    request_payload = {
        "targets": [build_sb_target_payload(campaign_id, ad_group_id, expression, bid, state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-targets.add-asin",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_targets.command("add-category")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--category-id", required=True, help="Category refinement id to target.")
@click.option("--bid", default=None, type=float, help="Optional target bid.")
@click.option(
    "--state",
    default="enabled",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_targets_add_category(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    category_id: str,
    bid: float | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    expression = normalize_sb_predicates((), category_id=category_id)
    request_payload = {
        "targets": [build_sb_target_payload(campaign_id, ad_group_id, expression, bid, state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-targets.add-category",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_targets.command("add-expression")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", default=None, help="Optional ASIN predicate.")
@click.option("--category-id", default=None, help="Optional category refinement predicate.")
@click.option("--brand-refinement-id", default=None, help="Optional brand refinement predicate.")
@click.option("--predicate", multiple=True, help="Additional predicate as TYPE=VALUE.")
@click.option("--bid", default=None, type=float, help="Optional target bid.")
@click.option(
    "--expression-type",
    default="manual",
    type=click.Choice(["manual", "auto"], case_sensitive=False),
    help="Expression type.",
)
@click.option(
    "--state",
    default="enabled",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_targets_add_expression(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    asin: str | None,
    category_id: str | None,
    brand_refinement_id: str | None,
    predicate: tuple[str, ...],
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    try:
        expression = normalize_sb_predicates(
            predicate,
            asin=asin,
            category_id=category_id,
            brand_refinement_id=brand_refinement_id,
        )
        payload = build_sb_target_payload(
            campaign_id,
            ad_group_id,
            expression,
            bid,
            state,
            expression_type,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"targets": [payload]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-targets.add-expression",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_targets.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--bid", required=True, type=float, help="New target bid.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_targets_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    bid: float,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"targets": [build_sb_target_update_payload(target_id, bid=bid)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-targets.edit-bid",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_targets.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="New target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_targets_set_state(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"targets": [build_sb_target_update_payload(target_id, state=state)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-targets.set-state",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_targets.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_targets_archive(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"targetId": target_id}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-targets.archive",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@cli.group("sb-negative-targets")
def sb_negative_targets() -> None:
    """Sponsored Brands negative product/category targeting commands."""


@sb_negative_targets.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--target-id", default=None, help="Optional target id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option(
    "--scope",
    default="both",
    type=click.Choice(["adGroup", "campaign", "both"], case_sensitive=False),
    help="Fetch ad-group, campaign, or both scopes.",
)
@click.pass_context
def sb_negative_targets_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    target_id: str | None,
    state_filter: str | None,
    scope: str,
) -> None:
    query = build_sb_legacy_filter(
        campaign_id,
        ad_group_id,
        target_id,
        state_filter,
        entity_key="targetId",
    )

    def fetch(client, access_token, profile_id):
        rows = client.list_sb_negative_targets(access_token, profile_id, query)
        normalized_scope = scope.lower()
        if normalized_scope == "campaign":
            return [row for row in rows if not row.get("adGroupId")]
        if normalized_scope == "adgroup":
            return [row for row in rows if row.get("adGroupId")]
        return rows

    def normalize(row):
        return normalize_sb_negative_target_row(
            row, "adGroup" if row.get("adGroupId") else "campaign"
        )

    emit_live_rows(
        ctx,
        marketplace,
        "sb-negative-targets",
        "negativeTargets",
        {"query": query, "scope": scope},
        fetch,
        normalize,
    )


@sb_negative_targets.command("add-ad-group")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", default=None, help="Optional ASIN predicate.")
@click.option("--category-id", default=None, help="Optional category refinement predicate.")
@click.option("--brand-refinement-id", default=None, help="Optional brand refinement predicate.")
@click.option("--predicate", multiple=True, help="Additional predicate as TYPE=VALUE.")
@click.option(
    "--expression-type",
    default="manual",
    type=click.Choice(["manual", "auto"], case_sensitive=False),
    help="Expression type.",
)
@click.option(
    "--state",
    default="enabled",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial negative target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negative_targets_add_ad_group(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    asin: str | None,
    category_id: str | None,
    brand_refinement_id: str | None,
    predicate: tuple[str, ...],
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    try:
        expression = normalize_sb_predicates(
            predicate,
            asin=asin,
            category_id=category_id,
            brand_refinement_id=brand_refinement_id,
        )
        payload = build_sb_negative_target_payload(
            campaign_id,
            expression,
            ad_group_id=ad_group_id,
            state=state,
            expression_type=expression_type,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"negativeTargets": [payload]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negative-targets.add-ad-group",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_negative_targets.command("add-campaign")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--asin", default=None, help="Optional ASIN predicate.")
@click.option("--category-id", default=None, help="Optional category refinement predicate.")
@click.option("--brand-refinement-id", default=None, help="Optional brand refinement predicate.")
@click.option("--predicate", multiple=True, help="Additional predicate as TYPE=VALUE.")
@click.option(
    "--state",
    default="enabled",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial negative target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negative_targets_add_campaign(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    asin: str | None,
    category_id: str | None,
    brand_refinement_id: str | None,
    predicate: tuple[str, ...],
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    try:
        expression = normalize_sb_predicates(
            predicate,
            asin=asin,
            category_id=category_id,
            brand_refinement_id=brand_refinement_id,
        )
        payload = build_sb_negative_target_payload(
            campaign_id,
            expression,
            state=state,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    request_payload = {"negativeTargets": [payload]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negative-targets.add-campaign",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_negative_targets.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--negative-target-id", required=True, help="Negative target id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="New negative target state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negative_targets_set_state(
    ctx: click.Context,
    marketplace: str | None,
    negative_target_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "negativeTargets": [
            build_sb_negative_target_update_payload(negative_target_id, state=state)
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negative-targets.set-state",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@sb_negative_targets.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--negative-target-id", required=True, help="Negative target id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sb_negative_targets_archive(
    ctx: click.Context,
    marketplace: str | None,
    negative_target_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"targetId": negative_target_id}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-negative-targets.archive",
        dry_run,
        policy="no_media_creative_user_supplied_values_only",
    )


@cli.group("sd-campaigns")
def sd_campaigns() -> None:
    """Sponsored Display campaign commands without creative operations."""


@sd_campaigns.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--tactic", default=None, help="Optional SD tactic filter, such as T00030.")
@click.option("--max-results", default=100, type=int, help="Optional page size.")
@click.pass_context
def sd_campaigns_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    state_filter: str | None,
    tactic: str | None,
    max_results: int,
) -> None:
    query = build_sd_query_filter(
        campaign_id=campaign_id,
        state_filter=state_filter,
        tactic=tactic,
        max_results=max_results,
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sd-campaigns",
        "campaigns",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sd_campaigns(
            access_token, profile_id, query
        ),
        normalize_sd_campaign_row,
    )


@sd_campaigns.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--name", required=True, help="Campaign name.")
@click.option("--budget", required=True, type=float, help="Daily budget.")
@click.option("--start-date", required=True, help="Start date, YYYY-MM-DD or YYYYMMDD.")
@click.option("--end-date", default=None, help="Optional end date.")
@click.option("--tactic", default="T00030", help="Sponsored Display tactic.")
@click.option("--budget-type", default="daily", help="Budget type.")
@click.option("--cost-type", default="cpc", help="Cost type.")
@click.option(
    "--state",
    default="paused",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial campaign state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_campaigns_create(
    ctx: click.Context,
    marketplace: str | None,
    name: str,
    budget: float,
    start_date: str,
    end_date: str | None,
    tactic: str,
    budget_type: str,
    cost_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sd_campaign_create_payload(
        name=name,
        budget=budget,
        start_date=start_date,
        tactic=tactic,
        budget_type=budget_type,
        cost_type=cost_type,
        state=state,
        end_date=end_date,
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        {"campaigns": [payload]},
        "sd-campaigns.create",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_campaigns.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused", "archived"], case_sensitive=False),
    help="New campaign state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_campaigns_set_state(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"campaigns": [build_sd_campaign_update_payload(campaign_id, state=state)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-campaigns.set-state",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_campaigns.command("edit-budget")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--budget", required=True, type=float, help="New campaign budget.")
@click.option("--budget-type", default=None, help="Optional budget type.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_campaigns_edit_budget(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    budget: float,
    budget_type: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "campaigns": [
            build_sd_campaign_update_payload(
                campaign_id,
                budget=budget,
                budget_type=budget_type,
            )
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-campaigns.edit-budget",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_campaigns.command("edit-name")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--name", required=True, help="New campaign name.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_campaigns_edit_name(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    name: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"campaigns": [build_sd_campaign_update_payload(campaign_id, name=name)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-campaigns.edit-name",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_campaigns.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_campaigns_archive(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "campaigns": [build_sd_campaign_update_payload(campaign_id, state="archived")]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-campaigns.archive",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@cli.group("sd-ad-groups")
def sd_ad_groups() -> None:
    """Sponsored Display ad group commands without creative operations."""


@sd_ad_groups.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--max-results", default=100, type=int, help="Optional page size.")
@click.pass_context
def sd_ad_groups_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    state_filter: str | None,
    max_results: int,
) -> None:
    query = build_sd_query_filter(
        campaign_id=campaign_id,
        entity_id=ad_group_id,
        state_filter=state_filter,
        max_results=max_results,
        entity_key="adGroupIdFilter",
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sd-ad-groups",
        "adGroups",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sd_ad_groups(
            access_token, profile_id, query
        ),
        normalize_sd_ad_group_row,
    )


@sd_ad_groups.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--name", required=True, help="Ad group name.")
@click.option("--default-bid", required=True, type=float, help="Default bid.")
@click.option("--bid-optimization", default="clicks", help="Bid optimization mode.")
@click.option("--creative-type", default=None, help="Optional creative type; user supplied only.")
@click.option(
    "--state",
    default="paused",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial ad group state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_ad_groups_create(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    name: str,
    default_bid: float,
    bid_optimization: str,
    creative_type: str | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sd_ad_group_create_payload(
        campaign_id=campaign_id,
        name=name,
        default_bid=default_bid,
        bid_optimization=bid_optimization,
        creative_type=creative_type,
        state=state,
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        {"adGroups": [payload]},
        "sd-ad-groups.create",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_ad_groups.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused", "archived"], case_sensitive=False),
    help="New ad group state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_ad_groups_set_state(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"adGroups": [build_sd_ad_group_update_payload(ad_group_id, state=state)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-ad-groups.set-state",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_ad_groups.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--default-bid", required=True, type=float, help="New default bid.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_ad_groups_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    default_bid: float,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "adGroups": [build_sd_ad_group_update_payload(ad_group_id, default_bid=default_bid)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-ad-groups.edit-bid",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_ad_groups.command("edit-name")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--name", required=True, help="New ad group name.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_ad_groups_edit_name(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    name: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"adGroups": [build_sd_ad_group_update_payload(ad_group_id, name=name)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-ad-groups.edit-name",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_ad_groups.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_ad_groups_archive(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "adGroups": [build_sd_ad_group_update_payload(ad_group_id, state="archived")]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-ad-groups.archive",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@cli.group("sd-product-ads")
def sd_product_ads() -> None:
    """Sponsored Display product ad commands without creative uploads."""


@sd_product_ads.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--product-ad-id", default=None, help="Optional product ad id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--max-results", default=100, type=int, help="Optional page size.")
@click.pass_context
def sd_product_ads_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    product_ad_id: str | None,
    state_filter: str | None,
    max_results: int,
) -> None:
    query = build_sd_query_filter(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        entity_id=product_ad_id,
        state_filter=state_filter,
        max_results=max_results,
        entity_key="adIdFilter",
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sd-product-ads",
        "productAds",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sd_product_ads(
            access_token, profile_id, query
        ),
        normalize_sd_product_ad_row,
    )


@sd_product_ads.command("add")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--ad-name", default=None, help="Optional ad name.")
@click.option("--sku", default=None, help="Optional advertised SKU.")
@click.option("--asin", default=None, help="Optional advertised ASIN.")
@click.option("--landing-page-url", default=None, help="Optional user-supplied landing page URL.")
@click.option("--landing-page-type", default=None, help="Optional landing page type.")
@click.option(
    "--state",
    default="paused",
    type=click.Choice(["enabled", "paused"], case_sensitive=False),
    help="Initial product ad state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_product_ads_add(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    ad_group_id: str,
    ad_name: str | None,
    sku: str | None,
    asin: str | None,
    landing_page_url: str | None,
    landing_page_type: str | None,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sd_product_ad_create_payload(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        ad_name=ad_name,
        sku=sku,
        asin=asin,
        landing_page_url=landing_page_url,
        landing_page_type=landing_page_type,
        state=state,
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        {"productAds": [payload]},
        "sd-product-ads.add",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_product_ads.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--product-ad-id", required=True, help="Product ad id.")
@click.option(
    "--state",
    required=True,
    type=click.Choice(["enabled", "paused", "archived"], case_sensitive=False),
    help="New product ad state.",
)
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_product_ads_set_state(
    ctx: click.Context,
    marketplace: str | None,
    product_ad_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "productAds": [build_sd_product_ad_update_payload(product_ad_id, state=state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-product-ads.set-state",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_product_ads.command("edit-name")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--product-ad-id", required=True, help="Product ad id.")
@click.option("--ad-name", required=True, help="New ad name.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_product_ads_edit_name(
    ctx: click.Context,
    marketplace: str | None,
    product_ad_id: str,
    ad_name: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "productAds": [build_sd_product_ad_update_payload(product_ad_id, ad_name=ad_name)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-product-ads.edit-name",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_product_ads.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--product-ad-id", required=True, help="Product ad id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_product_ads_archive(
    ctx: click.Context,
    marketplace: str | None,
    product_ad_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "productAds": [build_sd_product_ad_update_payload(product_ad_id, state="archived")]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-product-ads.archive",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@cli.group("sd-targets")
def sd_targets() -> None:
    """Sponsored Display targeting commands."""


@sd_targets.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--target-id", default=None, help="Optional target id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.option("--max-results", default=100, type=int, help="Optional page size.")
@click.pass_context
def sd_targets_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    target_id: str | None,
    state_filter: str | None,
    max_results: int,
) -> None:
    query = build_sd_query_filter(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        entity_id=target_id,
        state_filter=state_filter,
        max_results=max_results,
        entity_key="targetIdFilter",
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sd-targets",
        "targets",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sd_targets(
            access_token, profile_id, query
        ),
        normalize_sd_target_row,
    )


def _build_sd_target_request(
    ad_group_id: str,
    predicate: tuple[str, ...],
    bid: float | None,
    expression_type: str,
    state: str,
    asin: str | None = None,
    category_id: str | None = None,
    audience_id: str | None = None,
) -> dict[str, Any]:
    try:
        expression = normalize_sd_predicates(
            predicate,
            asin=asin,
            category_id=category_id,
            audience_id=audience_id,
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    return {
        "targets": [
            build_sd_target_payload(
                ad_group_id,
                expression,
                bid=bid,
                expression_type=expression_type,
                state=state,
            )
        ]
    }


@sd_targets.command("add-asin")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--asin", required=True, help="Target ASIN.")
@click.option("--bid", default=None, type=float, help="Optional bid.")
@click.option("--expression-type", default="manual", help="Expression type.")
@click.option("--state", default="paused", help="Initial target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_add_asin(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    asin: str,
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = _build_sd_target_request(
        ad_group_id, (), bid, expression_type, state, asin=asin
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.add-asin",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_targets.command("add-category")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--category-id", required=True, help="Category id.")
@click.option("--bid", default=None, type=float, help="Optional bid.")
@click.option("--expression-type", default="manual", help="Expression type.")
@click.option("--state", default="paused", help="Initial target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_add_category(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    category_id: str,
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = _build_sd_target_request(
        ad_group_id, (), bid, expression_type, state, category_id=category_id
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.add-category",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_targets.command("add-audience")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--audience-id", required=True, help="Audience id.")
@click.option("--bid", default=None, type=float, help="Optional bid.")
@click.option("--expression-type", default="manual", help="Expression type.")
@click.option("--state", default="paused", help="Initial target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_add_audience(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    audience_id: str,
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = _build_sd_target_request(
        ad_group_id, (), bid, expression_type, state, audience_id=audience_id
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.add-audience",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_targets.command("add-expression")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--predicate", multiple=True, required=True, help="Predicate as TYPE=VALUE.")
@click.option("--bid", default=None, type=float, help="Optional bid.")
@click.option("--expression-type", default="manual", help="Expression type.")
@click.option("--state", default="paused", help="Initial target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_add_expression(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    predicate: tuple[str, ...],
    bid: float | None,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = _build_sd_target_request(
        ad_group_id, predicate, bid, expression_type, state
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.add-expression",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_targets.command("edit-bid")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--bid", required=True, type=float, help="New bid.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_edit_bid(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    bid: float,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"targets": [build_sd_target_update_payload(target_id, bid=bid)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.edit-bid",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_targets.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--state", required=True, help="New target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_set_state(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {"targets": [build_sd_target_update_payload(target_id, state=state)]}
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.set-state",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_targets.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--target-id", required=True, help="Target id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_targets_archive(
    ctx: click.Context,
    marketplace: str | None,
    target_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "targets": [build_sd_target_update_payload(target_id, state="archived")]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-targets.archive",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@cli.group("sd-audiences")
def sd_audiences() -> None:
    """Sponsored Display audience discovery commands."""


@sd_audiences.command("taxonomy")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--category-path", multiple=True, help="Audience category path segment.")
@click.pass_context
def sd_audiences_taxonomy(
    ctx: click.Context,
    marketplace: str | None,
    category_path: tuple[str, ...],
) -> None:
    payload = build_sd_audience_taxonomy_payload(category_path)
    emit_live_result(
        ctx,
        marketplace,
        "sd-audiences",
        "taxonomy",
        {"payload": payload},
        lambda client, access_token, profile_id: client.sd_audience_taxonomy(
            access_token, profile_id, payload
        ),
    )


@sd_audiences.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--category-path", multiple=True, help="Audience category path segment.")
@click.option("--audience-name", default="*", help="Audience name filter.")
@click.pass_context
def sd_audiences_list(
    ctx: click.Context,
    marketplace: str | None,
    category_path: tuple[str, ...],
    audience_name: str,
) -> None:
    payload = build_sd_audience_discovery_payload(
        category_path=category_path,
        audience_name=audience_name,
    )
    emit_live_result(
        ctx,
        marketplace,
        "sd-audiences",
        "audiences",
        {"payload": payload},
        lambda client, access_token, profile_id: client.sd_audience_discovery(
            access_token, profile_id, payload
        ),
    )


@cli.group("sd-locations")
def sd_locations() -> None:
    """Sponsored Display location targeting commands."""


@sd_locations.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", default=None, help="Optional campaign id filter.")
@click.option("--ad-group-id", default=None, help="Optional ad group id filter.")
@click.option("--state", "state_filter", default=None, help="Optional state filter.")
@click.pass_context
def sd_locations_list(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str | None,
    ad_group_id: str | None,
    state_filter: str | None,
) -> None:
    query = build_sd_query_filter(
        campaign_id=campaign_id,
        ad_group_id=ad_group_id,
        state_filter=state_filter,
    )
    emit_live_rows(
        ctx,
        marketplace,
        "sd-locations",
        "locations",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sd_locations(
            access_token, profile_id, query
        ),
        normalize_sd_target_row,
    )


@sd_locations.command("add")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--ad-group-id", required=True, help="Ad group id.")
@click.option("--location-id", required=True, help="Location id.")
@click.option("--expression-type", default="manual", help="Expression type.")
@click.option("--state", default="paused", help="Initial location target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_locations_add(
    ctx: click.Context,
    marketplace: str | None,
    ad_group_id: str,
    location_id: str,
    expression_type: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "locations": [
            build_sd_location_payload(
                ad_group_id,
                location_id,
                expression_type=expression_type,
                state=state,
            )
        ]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-locations.add",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_locations.command("set-state")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--location-target-id", required=True, help="Location target id.")
@click.option("--state", required=True, help="New location target state.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_locations_set_state(
    ctx: click.Context,
    marketplace: str | None,
    location_target_id: str,
    state: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "locations": [build_sd_location_update_payload(location_target_id, state)]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-locations.set-state",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@sd_locations.command("archive")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--location-target-id", required=True, help="Location target id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_locations_archive(
    ctx: click.Context,
    marketplace: str | None,
    location_target_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "locations": [build_sd_location_update_payload(location_target_id, "archived")]
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-locations.archive",
        dry_run,
        policy="sd_non_creative_user_supplied_values_only",
    )


@cli.group("sd-budget-rules")
def sd_budget_rules() -> None:
    """Sponsored Display budget rule commands."""


@sd_budget_rules.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--page-size", default=30, type=int, help="Page size.")
@click.pass_context
def sd_budget_rules_list(ctx: click.Context, marketplace: str | None, page_size: int) -> None:
    query = {"pageSize": str(page_size)}
    emit_live_rows(
        ctx,
        marketplace,
        "sd-budget-rules",
        "budgetRules",
        {"query": query},
        lambda client, access_token, profile_id: client.list_sd_budget_rules(
            access_token, profile_id, query
        ),
        normalize_sd_budget_rule_row,
    )


@sd_budget_rules.command("show")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--rule-id", required=True, help="Budget rule id.")
@click.pass_context
def sd_budget_rules_show(ctx: click.Context, marketplace: str | None, rule_id: str) -> None:
    emit_live_result(
        ctx,
        marketplace,
        "sd-budget-rules",
        "budgetRule",
        {"ruleId": rule_id},
        lambda client, access_token, profile_id: client.get_sd_budget_rule(
            access_token, profile_id, rule_id
        ),
    )


@sd_budget_rules.command("create")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--name", required=True, help="Budget rule name.")
@click.option("--rule-type", required=True, help="Rule type, such as SCHEDULE or PERFORMANCE.")
@click.option("--increase-type", required=True, help="Increase type, such as PERCENT.")
@click.option("--increase-value", required=True, type=float, help="Increase value.")
@click.option("--recurrence-type", default="DAILY", help="Recurrence type.")
@click.option("--start-date", default=None, help="Optional start date.")
@click.option("--end-date", default=None, help="Optional end date.")
@click.option("--metric-name", default=None, help="Optional performance metric.")
@click.option("--threshold", default=None, type=float, help="Optional metric threshold.")
@click.option("--comparison-operator", default=None, help="Optional comparison operator.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_budget_rules_create(
    ctx: click.Context,
    marketplace: str | None,
    name: str,
    rule_type: str,
    increase_type: str,
    increase_value: float,
    recurrence_type: str,
    start_date: str | None,
    end_date: str | None,
    metric_name: str | None,
    threshold: float | None,
    comparison_operator: str | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sd_budget_rule_create_payload(
        name=name,
        rule_type=rule_type,
        increase_type=increase_type,
        increase_value=increase_value,
        recurrence_type=recurrence_type,
        start_date=start_date,
        end_date=end_date,
        metric_name=metric_name,
        threshold=threshold,
        comparison_operator=comparison_operator,
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        payload,
        "sd-budget-rules.create",
        dry_run,
        policy="sd_budget_rule_user_supplied_values_only",
    )


@sd_budget_rules.command("update")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--rule-id", required=True, help="Budget rule id.")
@click.option("--state", default=None, help="Optional rule state.")
@click.option("--name", default=None, help="Optional new name.")
@click.option("--increase-type", default=None, help="Optional increase type.")
@click.option("--increase-value", default=None, type=float, help="Optional increase value.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_budget_rules_update(
    ctx: click.Context,
    marketplace: str | None,
    rule_id: str,
    state: str | None,
    name: str | None,
    increase_type: str | None,
    increase_value: float | None,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = build_sd_budget_rule_update_payload(
        rule_id,
        state=state,
        name=name,
        increase_type=increase_type,
        increase_value=increase_value,
    )
    intercept_mutation(
        ctx,
        target_marketplace,
        payload,
        "sd-budget-rules.update",
        dry_run,
        policy="sd_budget_rule_user_supplied_values_only",
    )


@sd_budget_rules.command("associate")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--rule-id", required=True, help="Budget rule id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_budget_rules_associate(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    rule_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = {
        "campaignId": campaign_id,
        **build_sd_budget_rule_association_payload(rule_id),
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        payload,
        "sd-budget-rules.associate",
        dry_run,
        policy="sd_budget_rule_user_supplied_values_only",
    )


@sd_budget_rules.command("disassociate")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.option("--rule-id", required=True, help="Budget rule id.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.pass_context
def sd_budget_rules_disassociate(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
    rule_id: str,
    dry_run: bool,
) -> None:
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    payload = {"campaignId": campaign_id, "budgetRuleId": rule_id}
    intercept_mutation(
        ctx,
        target_marketplace,
        payload,
        "sd-budget-rules.disassociate",
        dry_run,
        policy="sd_budget_rule_user_supplied_values_only",
    )


@sd_budget_rules.command("campaigns")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--rule-id", required=True, help="Budget rule id.")
@click.option("--page-size", default=30, type=int, help="Page size.")
@click.pass_context
def sd_budget_rules_campaigns(
    ctx: click.Context,
    marketplace: str | None,
    rule_id: str,
    page_size: int,
) -> None:
    query = {"pageSize": str(page_size)}
    emit_live_result(
        ctx,
        marketplace,
        "sd-budget-rules",
        "campaigns",
        {"ruleId": rule_id, "query": query},
        lambda client, access_token, profile_id: client.list_sd_budget_rule_campaigns(
            access_token, profile_id, rule_id, query
        ),
    )


@sd_budget_rules.command("campaign-rules")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", required=True, help="Campaign id.")
@click.pass_context
def sd_budget_rules_campaign_rules(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: str,
) -> None:
    emit_live_result(
        ctx,
        marketplace,
        "sd-budget-rules",
        "budgetRules",
        {"campaignId": campaign_id},
        lambda client, access_token, profile_id: client.list_sd_campaign_budget_rules(
            access_token, profile_id, campaign_id
        ),
    )


@sd_budget_rules.command("usage")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--campaign-id", multiple=True, required=True, help="Campaign id.")
@click.pass_context
def sd_budget_rules_usage(
    ctx: click.Context,
    marketplace: str | None,
    campaign_id: tuple[str, ...],
) -> None:
    payload = build_sd_budget_usage_payload(campaign_id)
    emit_live_result(
        ctx,
        marketplace,
        "sd-budget-rules",
        "usage",
        {"payload": payload},
        lambda client, access_token, profile_id: client.sd_budget_usage(
            access_token, profile_id, payload
        ),
    )


@cli.group("sd-snapshots")
def sd_snapshots() -> None:
    """Sponsored Display snapshot commands."""


@sd_snapshots.command("request")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--record-type", required=True, help="SD record type, such as campaigns.")
@click.option("--tactic", default=None, help="Optional tactic.")
@click.pass_context
def sd_snapshots_request(
    ctx: click.Context,
    marketplace: str | None,
    record_type: str,
    tactic: str | None,
) -> None:
    payload = build_sd_snapshot_payload(tactic)
    emit_live_result(
        ctx,
        marketplace,
        "sd-snapshots",
        "snapshot",
        {"recordType": record_type, "payload": payload},
        lambda client, access_token, profile_id: client.request_sd_snapshot(
            access_token, profile_id, record_type, payload
        ),
    )


@sd_snapshots.command("status")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--snapshot-id", required=True, help="Snapshot id.")
@click.pass_context
def sd_snapshots_status(
    ctx: click.Context,
    marketplace: str | None,
    snapshot_id: str,
) -> None:
    emit_live_result(
        ctx,
        marketplace,
        "sd-snapshots",
        "snapshot",
        {"snapshotId": snapshot_id},
        lambda client, access_token, profile_id: client.get_sd_snapshot(
            access_token, profile_id, snapshot_id
        ),
    )


@sd_snapshots.command("download")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--snapshot-id", required=True, help="Snapshot id.")
@click.pass_context
def sd_snapshots_download(
    ctx: click.Context,
    marketplace: str | None,
    snapshot_id: str,
) -> None:
    emit_live_result(
        ctx,
        marketplace,
        "sd-snapshots",
        "snapshotDownload",
        {"snapshotId": snapshot_id},
        lambda client, access_token, profile_id: client.download_sd_snapshot(
            access_token, profile_id, snapshot_id
        ),
    )


@cli.group("sd-raw")
def sd_raw() -> None:
    """Restricted raw Sponsored Display API requests; creative/media paths are blocked."""


@sd_raw.command("request")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option(
    "--method",
    required=True,
    type=click.Choice(["GET", "POST", "PUT", "DELETE"], case_sensitive=False),
    help="HTTP method.",
)
@click.option("--path", required=True, help="Sponsored Display path, must start with /sd/.")
@click.option("--payload-json", default=None, help="Optional JSON object/array request body.")
@click.option("--accept", default=None, help="Optional explicit Accept media type.")
@click.option("--content-type", default=None, help="Optional explicit Content-Type media type.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.option(
    "--confirm-submit",
    is_flag=True,
    help="Deprecated compatibility flag; live raw execution is approval-gated.",
)
@click.pass_context
def sd_raw_request(
    ctx: click.Context,
    marketplace: str | None,
    method: str,
    path: str,
    payload_json: str | None,
    accept: str | None,
    content_type: str | None,
    dry_run: bool,
    confirm_submit: bool,
) -> None:
    payload = parse_json_payload(payload_json)
    try:
        assert_sd_raw_allowed(path, payload)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "method": method.upper(),
        "path": path,
        "payload": payload,
        "accept": accept,
        "contentType": content_type,
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sd-raw.request",
        dry_run,
        policy="restricted_to_sd_non_media_paths_user_supplied_payload_only",
    )


@cli.group("sb-raw")
def sb_raw() -> None:
    """Restricted raw Sponsored Brands API requests; media and creative paths are blocked."""


@sb_raw.command("request")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option(
    "--method",
    required=True,
    type=click.Choice(["GET", "POST", "PUT", "DELETE"], case_sensitive=False),
    help="HTTP method.",
)
@click.option("--path", required=True, help="Sponsored Brands path, must start with /sb/.")
@click.option("--payload-json", default=None, help="Optional JSON object/array request body.")
@click.option("--accept", default=None, help="Optional explicit Accept media type.")
@click.option("--content-type", default=None, help="Optional explicit Content-Type media type.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.option(
    "--confirm-submit",
    is_flag=True,
    help="Deprecated compatibility flag; live raw execution is approval-gated.",
)
@click.pass_context
def sb_raw_request(
    ctx: click.Context,
    marketplace: str | None,
    method: str,
    path: str,
    payload_json: str | None,
    accept: str | None,
    content_type: str | None,
    dry_run: bool,
    confirm_submit: bool,
) -> None:
    payload = parse_json_payload(payload_json)
    try:
        assert_sb_raw_allowed(path, payload)
    except ValueError as exc:
        raise click.BadParameter(str(exc)) from exc
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "method": method.upper(),
        "path": path,
        "payload": payload,
        "accept": accept,
        "contentType": content_type,
    }
    intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sb-raw.request",
        dry_run,
        policy="restricted_to_sb_non_media_paths_user_supplied_payload_only",
    )


@cli.group("sp-raw")
def sp_raw() -> None:
    """Restricted raw Sponsored Products API requests."""


@sp_raw.command("request")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option(
    "--method",
    required=True,
    type=click.Choice(["GET", "POST", "PUT", "DELETE"], case_sensitive=False),
    help="HTTP method.",
)
@click.option("--path", required=True, help="Sponsored Products path, must start with /sp/.")
@click.option("--payload-json", default=None, help="Optional JSON object/array request body.")
@click.option("--accept", default=None, help="Optional explicit Accept media type.")
@click.option("--content-type", default=None, help="Optional explicit Content-Type media type.")
@click.option("--dry-run", is_flag=True, help="Print the request payload without submitting.")
@click.option(
    "--confirm-submit",
    is_flag=True,
    help="Deprecated compatibility flag; live raw execution is approval-gated.",
)
@click.pass_context
def sp_raw_request(
    ctx: click.Context,
    marketplace: str | None,
    method: str,
    path: str,
    payload_json: str | None,
    accept: str | None,
    content_type: str | None,
    dry_run: bool,
    confirm_submit: bool,
) -> None:
    if not path.startswith("/sp/"):
        raise click.BadParameter("Raw SP request path must start with /sp/.")
    payload = parse_json_payload(payload_json)
    env = load_ads_environment()
    target_marketplace = (marketplace or env.marketplace or "US").upper()
    request_payload = {
        "method": method.upper(),
        "path": path,
        "payload": payload,
        "accept": accept,
        "contentType": content_type,
    }
    if intercept_mutation(
        ctx,
        target_marketplace,
        request_payload,
        "sp-raw.request",
        dry_run,
        policy="restricted_to_sp_paths_user_supplied_payload_only",
    ):
        return

    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "sp-raw",
                health,
                "result",
                {"marketplace": target_marketplace, **request_payload},
            ),
            ctx.obj["json"],
        )
        return
    result = client.send_sp_raw(
        access_token=access_token,
        profile_id=profile_id,
        method=method,
        path=path,
        payload=payload,
        accept=accept,
        content_type=content_type,
    )
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"result": result, "request": request_payload},
        },
        ctx.obj["json"],
    )


FF_CAMPAIGN_KEYS = (
    "campaignId",
    "name",
    "adProduct",
    "state",
    "status",
    "startDateTime",
    "endDateTime",
    "marketplaceScope",
    "marketplaces",
    "countries",
    "budgets",
    "optimizations",
    "portfolioId",
    "creationDateTime",
    "lastUpdatedDateTime",
)


@cli.group("ff-campaigns")
def ff_campaigns() -> None:
    """Full-funnel campaigns (全流域广告活动), read-only through the unified API v1."""


@ff_campaigns.command("list")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option(
    "--state",
    "states",
    multiple=True,
    type=click.Choice(["ENABLED", "PAUSED", "ARCHIVED"], case_sensitive=False),
    help="Optional campaign state filter; repeat for several.",
)
@click.option("--campaign-id", "campaign_ids", multiple=True, help="Optional campaign id filter; repeat for several.")
@click.option("--name", default=None, help="Optional campaign name keyword (broad match).")
@click.option("--max-results", default=100, type=int, help="Maximum campaigns returned, 1-1000.")
@click.pass_context
def ff_campaigns_list(
    ctx: click.Context,
    marketplace: str | None,
    states: tuple[str, ...],
    campaign_ids: tuple[str, ...],
    name: str | None,
    max_results: int,
) -> None:
    """List this marketplace's full-funnel campaigns (全流域广告活动); read only."""
    if not 1 <= max_results <= 1000:
        raise click.UsageError("max-results 必须在 1 到 1000 之间")
    if len(campaign_ids) > 1000:
        raise click.UsageError("campaign-id 一次最多 1000 个")
    requested = {"states": [s.upper() for s in states], "campaignIds": list(campaign_ids), "name": name}
    emit_live_rows(
        ctx,
        marketplace,
        "ff-campaigns",
        "campaigns",
        requested,
        lambda client, access_token, profile_id: client.query_campaigns(
            access_token,
            profile_id,
            "FULL_FUNNEL",
            states=requested["states"],
            campaign_ids=list(campaign_ids),
            name=name,
            limit=max_results,
        ),
        lambda row: {key: row[key] for key in FF_CAMPAIGN_KEYS if key in row},
    )


@ff_campaigns.command("fields")
@click.option("--category", default=None, help="Category keyword, such as Delivery, Reach or retail.")
@click.option("--search", default=None, help="Keyword matched against field IDs and titles, such as roas.")
@click.pass_context
def ff_campaigns_fields(ctx: click.Context, category: str | None, search: str | None) -> None:
    """Fields the full-funnel report accepts in --fields; filter by category or search to list them."""
    from collections import Counter

    from cli_anything.amazon_ads_ops_workbench.core.unified_reports import (
        BASE_FIELDS,
        DEFAULT_METRICS,
        MAX_CUSTOM_FIELDS,
        list_fields,
    )

    everything = list_fields()
    data: dict[str, Any] = {
        "alwaysIncluded": ["date.value | dateRange.value", *BASE_FIELDS],
        "defaultMetrics": list(DEFAULT_METRICS),
        "maxCustomFields": MAX_CUSTOM_FIELDS,
        "categories": dict(Counter(f["category"] for f in everything)),
        "totalFields": len(everything),
    }
    if category or search:
        data["fields"] = list_fields(category, search)
    else:
        # The whole library is ~700 rows; ask for a category or keyword instead.
        data["hint"] = "传 category 或 search 查看具体字段，例如 search=roas 或 category=Reach"
    emit({"meta": {"mode": "reference", "status": "ok"}, "data": data}, ctx.obj["json"])


@cli.group()
def reports() -> None:
    """Reporting commands."""


@reports.command("create-sp-keywords")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="DAILY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_keywords(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports",
                health,
                "reports",
                {
                    "marketplace": target_marketplace,
                    "startDate": start_date,
                    "endDate": end_date,
                    "timeUnit": time_unit,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_sp_keywords_report_body(start_date, end_date, time_unit)
    result = client.create_report(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"report": normalize_report_status(result)},
        },
        ctx.obj["json"],
    )


@reports.command("create-sp-campaign-placement")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_campaign_placement(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports",
                health,
                "reports",
                {
                    "marketplace": target_marketplace,
                    "startDate": start_date,
                    "endDate": end_date,
                    "timeUnit": time_unit,
                    "reportTypeId": "spCampaigns",
                    "groupBy": ["campaignPlacement"],
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_sp_campaign_placement_report_body(start_date, end_date, time_unit)
    result = client.create_report(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"report": normalize_report_status(result)},
        },
        ctx.obj["json"],
    )


@reports.command("create-search-terms")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_search_terms(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports",
                health,
                "reports",
                {
                    "marketplace": target_marketplace,
                    "startDate": start_date,
                    "endDate": end_date,
                    "timeUnit": time_unit,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = build_sp_search_term_report_body(start_date, end_date, time_unit)
    result = client.create_report(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"report": normalize_report_status(result)},
        },
        ctx.obj["json"],
    )


def create_report_from_builder(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
    builder,
    report_type_id: str,
    group_by: list[str],
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports",
                health,
                "reports",
                {
                    "marketplace": target_marketplace,
                    "startDate": start_date,
                    "endDate": end_date,
                    "timeUnit": time_unit,
                    "reportTypeId": report_type_id,
                    "groupBy": group_by,
                },
            ),
            ctx.obj["json"],
        )
        return
    payload = builder(start_date, end_date, time_unit)
    result = client.create_report(access_token, profile_id, payload)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"report": normalize_report_status(result)},
        },
        ctx.obj["json"],
    )


@reports.command("create-sp-campaigns")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_campaigns(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP campaign performance report."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_campaigns_report_body,
        "spCampaigns",
        ["campaign"],
    )


@reports.command("create-sp-ad-groups")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_ad_groups(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP ad group performance report."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_ad_groups_report_body,
        "spCampaigns",
        ["adGroup"],
    )


@reports.command("create-sp-targeting")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_targeting(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP keyword and product targeting report."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_targeting_report_body,
        "spTargeting",
        ["targeting"],
    )


@reports.command("create-sp-advertised-products")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_advertised_products(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP advertised product report."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_advertised_products_report_body,
        "spAdvertisedProduct",
        ["advertiser"],
    )


@reports.command("create-sp-purchased-products")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_purchased_products(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP purchased product report (sales of other ASINs)."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_purchased_products_report_body,
        "spPurchasedProduct",
        ["asin"],
    )


@reports.command("create-sp-impression-share")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_impression_share(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP top-of-search impression share per keyword/target."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_impression_share_report_body,
        "spTargeting",
        ["targeting"],
    )


@reports.command("create-sp-gross-and-invalids")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sp_gross_and_invalids(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    """SP gross and invalid traffic report."""
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sp_gross_and_invalids_report_body,
        "spGrossAndInvalids",
        ["campaign"],
    )


@reports.command("create-amc-query")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Query window start date in YYYY-MM-DD (advertiser time zone).")
@click.option("--end-date", required=True, help="Query window end date in YYYY-MM-DD, inclusive. AMC data lags about 48 hours.")
@click.option("--template", default=None, help="Built-in AMC template id; see `amc templates`. Use either --template or --sql.")
@click.option("--sql", default=None, help="Custom AMC SQL (aggregate SELECT; no LIMIT, top-level ORDER BY or SELECT *).")
@click.option("--time-zone", default=None, help="IANA time zone for the window, e.g. America/Los_Angeles.")
@click.option("--instance-id", default=None, help="AMC instance id; defaults to the account's first ready instance.")
@click.pass_context
def reports_create_amc_query(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    template: str | None,
    sql: str | None,
    time_zone: str | None,
    instance_id: str | None,
) -> None:
    """Run an Amazon Marketing Cloud SQL query; results arrive as rows asynchronously."""
    try:
        query, template_id = resolve_amc_query(template, sql)
        body = build_amc_execution_body(query, start_date, end_date, time_zone)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from None
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "amc", health, "execution", {"template": template_id, "startDate": start_date, "endDate": end_date}
            ),
            ctx.obj["json"],
        )
        return
    from cli_anything.amazon_ads_ops_workbench.core.runtime import current_runtime

    runtime = current_runtime.get()
    if runtime is not None and runtime.mode == "report_plan":
        client.amc_create_execution("", "", instance_id, body)
        return
    entity, instance = client.amc_context(access_token, instance_id)
    result = client.amc_create_execution(access_token, entity, instance["instanceId"], body)
    emit(
        {
            "meta": {"mode": "live", "status": "connected", "marketplace": target_marketplace},
            "data": {"instanceId": instance["instanceId"], "execution": result, "template": template_id},
        },
        ctx.obj["json"],
    )


@reports.command("create-full-funnel-campaigns")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="DAILY", help="DAILY or SUMMARY.")
@click.option(
    "--fields",
    multiple=True,
    help="Optional metric/dimension field IDs (e.g. metric.roas or roas); empty uses the default set. See ff-campaigns fields.",
)
@click.pass_context
def reports_create_full_funnel_campaigns(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
    fields: tuple[str, ...],
) -> None:
    """Full-funnel campaigns (全流域广告活动) report via the unified Reporting API v1."""
    from cli_anything.amazon_ads_ops_workbench.core.runtime import current_runtime
    from cli_anything.amazon_ads_ops_workbench.core.unified_reports import (
        build_full_funnel_plan,
        build_report_body,
    )

    try:
        plan = build_full_funnel_plan(start_date, end_date, time_unit, fields)
    except ValueError as exc:
        raise click.UsageError(str(exc)) from None
    runtime = current_runtime.get()
    if runtime is not None and runtime.mode == "report_plan":
        # The worker resolves campaigns and the advertiser account when it submits.
        runtime.report = plan
        return
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports", health, "full-funnel", {"startDate": start_date, "endDate": end_date}
            ),
            ctx.obj["json"],
        )
        return
    campaign_ids = client.query_campaign_ids(access_token, profile_id, plan["adProduct"])
    report = None
    if campaign_ids:
        account_id = client.advertiser_account_id(access_token, profile_id)
        report = client.unified_create_report(
            access_token, build_report_body(plan, account_id, campaign_ids)
        )
    emit(
        {
            "meta": {"mode": "live", "status": "connected", "marketplace": target_marketplace},
            "data": {"campaignCount": len(campaign_ids), "report": report},
        },
        ctx.obj["json"],
    )


@reports.command("create-sb-campaigns")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sb_campaigns(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sb_campaigns_report_body,
        "sbCampaigns",
        ["campaign"],
    )


@reports.command("create-sb-ad-groups")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sb_ad_groups(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sb_ad_groups_report_body,
        "sbAdGroups",
        ["adGroup"],
    )


@reports.command("create-sb-targeting")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sb_targeting(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sb_targeting_report_body,
        "sbTargeting",
        ["targeting"],
    )


@reports.command("create-sb-search-terms")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sb_search_terms(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sb_search_term_report_body,
        "sbSearchTerm",
        ["searchTerm"],
    )


@reports.command("create-sb-campaign-placement")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sb_campaign_placement(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sb_campaign_placement_report_body,
        "sbCampaigns",
        ["campaignPlacement"],
    )


@reports.command("create-sd-campaigns")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sd_campaigns(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sd_campaigns_report_body,
        "sdCampaigns",
        ["campaign"],
    )


@reports.command("create-sd-ad-groups")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sd_ad_groups(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sd_ad_groups_report_body,
        "sdAdGroups",
        ["adGroup"],
    )


@reports.command("create-sd-product-ads")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sd_product_ads(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sd_product_ads_report_body,
        "sdProductAds",
        ["productAd"],
    )


@reports.command("create-sd-targeting")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--start-date", required=True, help="Report start date in YYYY-MM-DD.")
@click.option("--end-date", required=True, help="Report end date in YYYY-MM-DD.")
@click.option("--time-unit", default="SUMMARY", help="SUMMARY or DAILY.")
@click.pass_context
def reports_create_sd_targeting(
    ctx: click.Context,
    marketplace: str | None,
    start_date: str,
    end_date: str,
    time_unit: str,
) -> None:
    create_report_from_builder(
        ctx,
        marketplace,
        start_date,
        end_date,
        time_unit,
        build_sd_targeting_report_body,
        "sdTargeting",
        ["targeting"],
    )


@reports.command("status")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--report-id", required=True, help="Report id.")
@click.pass_context
def reports_status(
    ctx: click.Context,
    marketplace: str | None,
    report_id: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports",
                health,
                "reports",
                {
                    "marketplace": target_marketplace,
                    "reportId": report_id,
                },
            ),
            ctx.obj["json"],
        )
        return
    result = client.get_report(access_token, profile_id, report_id)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {"report": normalize_report_status(result)},
        },
        ctx.obj["json"],
    )


@reports.command("download")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--report-id", required=True, help="Report id.")
@click.option(
    "--output-dir",
    default=os.path.expanduser("~/Downloads"),
    help="Directory for the downloaded report file.",
)
@click.pass_context
def reports_download(
    ctx: click.Context,
    marketplace: str | None,
    report_id: str,
    output_dir: str,
) -> None:
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(
        marketplace
    )
    if not health["ok"]:
        emit(
            build_domain_fallback(
                "reports",
                health,
                "reports",
                {
                    "marketplace": target_marketplace,
                    "reportId": report_id,
                    "outputDir": output_dir,
                },
            ),
            ctx.obj["json"],
        )
        return
    status = client.get_report(access_token, profile_id, report_id)
    normalized = normalize_report_status(status)
    if not normalized["url"]:
        emit(
            {
                "meta": {
                    "mode": "live",
                    "status": "attention",
                    "profileId": profile_id,
                    "marketplace": target_marketplace,
                },
                "data": {"report": normalized},
            },
            ctx.obj["json"],
        )
        return
    report_type = normalized["reportTypeId"] or "report"
    output_path = build_download_target_path(output_dir, report_id, report_type)
    download_meta = client.download_report_file(normalized["url"], output_path)
    emit(
        {
            "meta": {
                "mode": "live",
                "status": "connected",
                "profileId": profile_id,
                "marketplace": target_marketplace,
            },
            "data": {
                "report": normalized,
                "download": download_meta,
            },
        },
        ctx.obj["json"],
    )


@reports.command("parse-search-terms")
@click.option("--input-file", required=True, help="Downloaded search term report JSON path.")
@click.pass_context
def reports_parse_search_terms(ctx: click.Context, input_file: str) -> None:
    rows = [normalize_search_term_report_row(row) for row in load_report_rows(input_file)]
    emit(
        {
            "meta": {
                "mode": "local",
                "status": "parsed",
                "inputFile": input_file,
            },
            "data": {
                "summary": summarize_report_rows(rows),
                "rows": rows,
            },
        },
        ctx.obj["json"],
    )


@reports.command("parse-sp-keywords")
@click.option("--input-file", required=True, help="Downloaded SP keyword report JSON path.")
@click.pass_context
def reports_parse_sp_keywords(ctx: click.Context, input_file: str) -> None:
    rows = [normalize_sp_keyword_report_row(row) for row in load_report_rows(input_file)]
    emit(
        {
            "meta": {
                "mode": "local",
                "status": "parsed",
                "inputFile": input_file,
            },
            "data": {
                "summary": summarize_report_rows(rows),
                "rows": rows,
            },
        },
        ctx.obj["json"],
    )


@reports.command("parse-sp-campaign-placement")
@click.option("--input-file", required=True, help="Downloaded SP campaign placement report JSON path.")
@click.pass_context
def reports_parse_sp_campaign_placement(ctx: click.Context, input_file: str) -> None:
    rows = [
        normalize_sp_campaign_placement_report_row(row)
        for row in load_report_rows(input_file)
    ]
    emit(
        {
            "meta": {
                "mode": "local",
                "status": "parsed",
                "inputFile": input_file,
            },
            "data": {
                "summary": summarize_report_rows(rows),
                "rows": rows,
            },
        },
        ctx.obj["json"],
    )


@reports.command("parse-sb-report")
@click.option("--input-file", required=True, help="Downloaded SB report JSON path.")
@click.pass_context
def reports_parse_sb_report(ctx: click.Context, input_file: str) -> None:
    rows = [normalize_sb_report_row(row) for row in load_report_rows(input_file)]
    emit(
        {
            "meta": {
                "mode": "local",
                "status": "parsed",
                "inputFile": input_file,
            },
            "data": {
                "summary": summarize_report_rows(rows),
                "rows": rows,
            },
        },
        ctx.obj["json"],
    )


@reports.command("parse-sd-report")
@click.option("--input-file", required=True, help="Downloaded SD report JSON path.")
@click.pass_context
def reports_parse_sd_report(ctx: click.Context, input_file: str) -> None:
    rows = [normalize_sd_report_row(row) for row in load_report_rows(input_file)]
    emit(
        {
            "meta": {
                "mode": "local",
                "status": "parsed",
                "inputFile": input_file,
            },
            "data": {
                "summary": summarize_report_rows(rows),
                "rows": rows,
            },
        },
        ctx.obj["json"],
    )


@cli.group()
def amc() -> None:
    """Amazon Marketing Cloud discovery commands; queries run via `reports create-amc-query`."""


@amc.command("templates")
def amc_templates() -> None:
    """List built-in AMC query templates (local; no API call)."""
    emit({"meta": {"mode": "local"}, "data": {"templates": public_amc_templates()}}, True)


@amc.command("instances")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.pass_context
def amc_instances(ctx: click.Context, marketplace: str | None) -> None:
    """Show the AMC instance linked to this advertiser (entity resolved automatically)."""
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(marketplace)
    if not health["ok"]:
        emit(build_domain_fallback("amc", health, "instances"), ctx.obj["json"])
        return
    entity, instance = client.amc_context(access_token)
    emit(
        {
            "meta": {"mode": "live", "status": "connected", "marketplace": target_marketplace},
            "data": {"instances": [summarize_amc_instance(instance)]},
        },
        ctx.obj["json"],
    )


@amc.command("data-sources")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--source", default=None, help="Return full columns for one data source, e.g. sponsored_ads_traffic.")
@click.option("--instance-id", default=None, help="AMC instance id; defaults to the first ready instance.")
@click.pass_context
def amc_data_sources(
    ctx: click.Context, marketplace: str | None, source: str | None, instance_id: str | None
) -> None:
    """List AMC tables usable in SQL; pass --source for its columns."""
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(marketplace)
    if not health["ok"]:
        emit(build_domain_fallback("amc", health, "dataSources"), ctx.obj["json"])
        return
    entity, instance = client.amc_context(access_token, instance_id)
    sources = summarize_amc_data_sources(
        client.amc_data_sources(access_token, entity, instance["instanceId"])
    )
    if source:
        sources = [s for s in sources if s["id"] == source]
        if not sources:
            raise click.UsageError("AMC 数据表不存在: " + source)
    else:
        sources = [{**{k: v for k, v in s.items() if k != "columns"}, "columnCount": len(s["columns"])} for s in sources]
    emit(
        {
            "meta": {"mode": "live", "status": "connected", "marketplace": target_marketplace},
            "data": {"instanceId": instance["instanceId"], "dataSources": sources},
        },
        ctx.obj["json"],
    )


@amc.command("executions")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.option("--days", default=7, type=click.IntRange(1, 90), help="Look back this many days.")
@click.option("--instance-id", default=None, help="AMC instance id; defaults to the first ready instance.")
@click.pass_context
def amc_executions(ctx: click.Context, marketplace: str | None, days: int, instance_id: str | None) -> None:
    """List recent AMC query executions, including ones started outside this tool."""
    env, target_marketplace, client, access_token, profile_id, health = load_live_context(marketplace)
    if not health["ok"]:
        emit(build_domain_fallback("amc", health, "executions"), ctx.obj["json"])
        return
    since = (datetime.now(timezone.utc) - timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%S")
    entity, instance = client.amc_context(access_token, instance_id)
    rows = client.amc_list_executions(access_token, entity, instance["instanceId"], since)
    keep = ("workflowExecutionId", "workflowId", "status", "statusReason", "createTime", "timeWindowStart", "timeWindowEnd")
    emit(
        {
            "meta": {"mode": "live", "status": "connected", "marketplace": target_marketplace},
            "data": {"instanceId": instance["instanceId"], "executions": [{k: r.get(k) for k in keep} for r in rows]},
        },
        ctx.obj["json"],
    )


@cli.command("snapshot")
@click.option("--marketplace", default=None, help="Marketplace such as US, CA, or MX.")
@click.pass_context
def snapshot_command(ctx: click.Context, marketplace: str | None) -> None:
    emit(build_snapshot(load_ads_environment(), marketplace=marketplace), ctx.obj["json"])


def repl(as_json: bool) -> None:
    skin = None
    prompt_session = None
    try:
        from cli_anything.amazon_ads_ops_workbench.utils.repl_skin import ReplSkin

        skin = ReplSkin("amazon_ads_ops_workbench", version=__version__)
        skin.print_banner()
        prompt_session = skin.create_prompt_session()
    except Exception:
        click.echo("Amazon Ads Ops Workbench REPL. 输入 exit 退出。")

    while True:
        try:
            if skin and prompt_session:
                line = skin.get_input(
                    prompt_session,
                    project_name="amazon-ads",
                    modified=False,
                ).strip()
            else:
                line = input("amazon-ads> ").strip()
        except EOFError:
            click.echo()
            break
        if not line:
            continue
        if line in {"exit", "quit"}:
            if skin:
                skin.print_goodbye()
            break
        if line == "help":
            help_text = "可用命令: capabilities --ad-product SP|SB|SBV|SD --writes-only | auth health | profiles list | profiles resolve --marketplace US | approvals list/show/execute | portfolios list/create/set-state | campaigns list/create/set-state/edit-budget/edit-bidding-strategy/edit-placement-bids | ad-groups list/create/set-state/edit-bid | keywords list/add/edit-bid/set-state | product-ads list/add/set-state | targets list/add-asin/add-category/add-expression/edit-bid/set-state | negatives list/add-ad-group/add-campaign/set-state | negative-targets list/add-ad-group/add-campaign/set-state | sb-campaigns list/create/set-state/edit-budget/edit-name/edit-bidding/archive | sb-ad-groups list/create/set-state/edit-name/archive | sb-keywords list/add/edit-bid/set-state/archive | sb-negatives list/add-ad-group/add-campaign/set-state/archive | sb-targets list/add-asin/add-category/add-expression/edit-bid/set-state/archive | sb-negative-targets list/add-ad-group/add-campaign/set-state/archive | sd-campaigns list/create/set-state/edit-budget/edit-name/archive | sd-ad-groups list/create/set-state/edit-bid/edit-name/archive | sd-product-ads list/add/set-state/edit-name/archive | sd-targets list/add-asin/add-category/add-audience/add-expression/edit-bid/set-state/archive | sd-audiences taxonomy/list | sd-locations list/add/set-state/archive | sd-budget-rules list/show/create/update/associate/disassociate/campaigns/campaign-rules/usage | sp-raw request | sb-raw request | sd-raw request | reports create-sp-keywords/create-sp-campaign-placement/create-search-terms/create-sb-campaigns/create-sb-ad-groups/create-sb-targeting/create-sb-search-terms/create-sb-campaign-placement/create-sd-campaigns/create-sd-ad-groups/create-sd-product-ads/create-sd-targeting/status/download/parse-search-terms/parse-sp-keywords/parse-sp-campaign-placement/parse-sb-report/parse-sd-report | snapshot"
            if skin:
                skin.info(help_text)
            else:
                click.echo(help_text)
            continue
        args = ["--json"] + shlex.split(line) if as_json else shlex.split(line)
        try:
            cli.main(args=args, prog_name="cli-anything-amazon-ads-ops-workbench", standalone_mode=False)
        except SystemExit:
            continue
        except Exception as exc:  # pragma: no cover
            if skin:
                skin.error(str(exc))
            else:
                click.echo(f"error: {exc}", err=True)


if __name__ == "__main__":
    cli()
