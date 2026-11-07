from __future__ import annotations

from typing import Any

from cli_anything.amazon_ads_ops_workbench.core.approvals import CONFIRMATION_PROMPT


CAPABILITY_CONTRACT_VERSION = "2026-07-29"

APPROVAL_EXECUTION_PATH = (
    "Run the typed command without --dry-run to create an approval plan, ask the user "
    "the exact confirmation prompt, then run approvals execute after the user replies exactly."
)


def _read(operation: str, ad_product: str, command: str, notes: str = "") -> dict[str, Any]:
    return {
        "operation": operation,
        "adProduct": ad_product,
        "kind": "read",
        "command": command,
        "canRead": True,
        "canPlan": False,
        "canExecute": True,
        "approvalRequired": False,
        "dryRunSupported": False,
        "executionMode": "direct",
        "executionPath": "Run the listed command directly.",
        "notes": notes,
    }


def _write(
    operation: str,
    ad_product: str,
    command: str,
    notes: str = "",
    policy: str = "user_supplied_values_only",
) -> dict[str, Any]:
    return {
        "operation": operation,
        "adProduct": ad_product,
        "kind": "write",
        "command": command,
        "canRead": False,
        "canPlan": True,
        "canExecute": True,
        "approvalRequired": True,
        "confirmationPrompt": CONFIRMATION_PROMPT,
        "dryRunSupported": True,
        "executionMode": "approval-gated",
        "executionPath": APPROVAL_EXECUTION_PATH,
        "policy": policy,
        "notes": notes,
    }


def _report(operation: str, ad_product: str, command: str, notes: str = "") -> dict[str, Any]:
    return {
        "operation": operation,
        "adProduct": ad_product,
        "kind": "report",
        "command": command,
        "canRead": True,
        "canPlan": False,
        "canExecute": True,
        "approvalRequired": False,
        "dryRunSupported": False,
        "executionMode": "direct",
        "executionPath": "Creates or reads an Amazon Ads report task directly; report data may be asynchronous.",
        "notes": notes,
    }


def _raw(operation: str, ad_product: str, command: str, notes: str = "") -> dict[str, Any]:
    return {
        "operation": operation,
        "adProduct": ad_product,
        "kind": "raw",
        "command": command,
        "canRead": True,
        "canPlan": True,
        "canExecute": True,
        "approvalRequired": True,
        "confirmationPrompt": CONFIRMATION_PROMPT,
        "dryRunSupported": True,
        "executionMode": "approval-gated",
        "executionPath": APPROVAL_EXECUTION_PATH,
        "policy": "official_endpoint_only",
        "notes": notes,
    }


CAPABILITIES: list[dict[str, Any]] = [
    _read("snapshot", "ALL", "snapshot --marketplace US", "High-level normalized account snapshot."),
    _read("profiles.list", "ALL", "profiles list"),
    _read("profiles.resolve", "ALL", "profiles resolve --marketplace US"),
    _read("auth.health", "ALL", "auth health"),
    _read("portfolios.list", "SP", "portfolios list --marketplace US"),
    _write("portfolios.create", "SP", "portfolios create --name NAME --budget 100 --currency-code USD"),
    _write("portfolios.set-state", "SP", "portfolios set-state --portfolio-id ID --state PAUSED"),
    _read("campaigns.list", "SP", "campaigns list --marketplace US"),
    _write("campaigns.create", "SP", "campaigns create --name NAME --targeting-type MANUAL --budget 10 --start-date YYYY-MM-DD"),
    _write("campaigns.set-state", "SP", "campaigns set-state --campaign-id ID --state PAUSED"),
    _write("campaigns.edit-budget", "SP", "campaigns edit-budget --campaign-id ID --budget 10"),
    _write(
        "campaigns.edit-bidding-strategy",
        "SP",
        "campaigns edit-bidding-strategy --campaign-id ID --strategy AUTO_FOR_SALES",
    ),
    _write(
        "campaigns.edit-placement-bids",
        "SP",
        "campaigns edit-placement-bids --campaign-id ID --top-of-search 100",
        "Only user-supplied placement percentages are accepted.",
        policy="user_supplied_percentages_only",
    ),
    _read("ad-groups.list", "SP", "ad-groups list --campaign-id ID"),
    _write("ad-groups.create", "SP", "ad-groups create --campaign-id ID --name NAME --default-bid 0.75"),
    _write("ad-groups.set-state", "SP", "ad-groups set-state --campaign-id ID --ad-group-id ID --state PAUSED"),
    _write("ad-groups.edit-bid", "SP", "ad-groups edit-bid --campaign-id ID --ad-group-id ID --default-bid 0.75"),
    _read("keywords.list", "SP", "keywords list --campaign-id ID --ad-group-id ID"),
    _write("keywords.add", "SP", "keywords add --campaign-id ID --ad-group-id ID --keyword-text TEXT --match-type EXACT --bid 0.75"),
    _write("keywords.edit-bid", "SP", "keywords edit-bid --campaign-id ID --ad-group-id ID --keyword-id ID --bid 0.75"),
    _write("keywords.set-state", "SP", "keywords set-state --campaign-id ID --ad-group-id ID --keyword-id ID --state PAUSED"),
    _read("product-ads.list", "SP", "product-ads list --campaign-id ID"),
    _write("product-ads.add", "SP", "product-ads add --campaign-id ID --ad-group-id ID --sku SKU"),
    _write("product-ads.set-state", "SP", "product-ads set-state --product-ad-id ID --state PAUSED"),
    _read("targets.list", "SP", "targets list --campaign-id ID --ad-group-id ID"),
    _write("targets.add-asin", "SP", "targets add-asin --campaign-id ID --ad-group-id ID --asin ASIN --bid 0.75"),
    _write("targets.add-category", "SP", "targets add-category --campaign-id ID --ad-group-id ID --category-id ID --bid 0.75"),
    _write("targets.add-expression", "SP", "targets add-expression --campaign-id ID --ad-group-id ID --predicate TYPE=VALUE --bid 0.75"),
    _write("targets.edit-bid", "SP", "targets edit-bid --target-id ID --bid 0.75"),
    _write("targets.set-state", "SP", "targets set-state --target-id ID --state PAUSED"),
    _read("negatives.list", "SP", "negatives list --campaign-id ID --scope both"),
    _write("negatives.add-ad-group", "SP", "negatives add-ad-group --campaign-id ID --ad-group-id ID --keyword-text TEXT --match-type NEGATIVE_EXACT"),
    _write("negatives.add-campaign", "SP", "negatives add-campaign --campaign-id ID --keyword-text TEXT --match-type NEGATIVE_EXACT"),
    _write("negatives.set-state", "SP", "negatives set-state --negative-keyword-id ID --scope adGroup --state PAUSED"),
    _read("negative-targets.list", "SP", "negative-targets list --campaign-id ID --scope both"),
    _write("negative-targets.add-ad-group", "SP", "negative-targets add-ad-group --campaign-id ID --ad-group-id ID --asin ASIN"),
    _write("negative-targets.add-campaign", "SP", "negative-targets add-campaign --campaign-id ID --category-id ID"),
    _write("negative-targets.set-state", "SP", "negative-targets set-state --negative-target-id ID --scope campaign --state PAUSED"),
    _raw("sp-raw.request", "SP", "sp-raw request --method POST --path /sp/targets/list --payload-json '{}'", "Only /sp/ paths are accepted."),
    _read("sb-campaigns.list", "SB", "sb-campaigns list --marketplace US"),
    _write("sb-campaigns.create", "SB", "sb-campaigns create --name NAME --budget 15 --start-date YYYY-MM-DD"),
    _write("sb-campaigns.set-state", "SB", "sb-campaigns set-state --campaign-id ID --state PAUSED"),
    _write("sb-campaigns.edit-budget", "SB", "sb-campaigns edit-budget --campaign-id ID --budget 15"),
    _write("sb-campaigns.edit-name", "SB", "sb-campaigns edit-name --campaign-id ID --name NAME"),
    _write("sb-campaigns.edit-bidding", "SB", "sb-campaigns edit-bidding --campaign-id ID --strategy AUTO_FOR_SALES"),
    _write("sb-campaigns.archive", "SB", "sb-campaigns archive --campaign-id ID"),
    _read("sb-ad-groups.list", "SB", "sb-ad-groups list --campaign-id ID"),
    _write("sb-ad-groups.create", "SB", "sb-ad-groups create --campaign-id ID --name NAME"),
    _write("sb-ad-groups.set-state", "SB", "sb-ad-groups set-state --ad-group-id ID --state PAUSED"),
    _write("sb-ad-groups.edit-name", "SB", "sb-ad-groups edit-name --ad-group-id ID --name NAME"),
    _write("sb-ad-groups.archive", "SB", "sb-ad-groups archive --ad-group-id ID"),
    _read("sb-keywords.list", "SB", "sb-keywords list --campaign-id ID --ad-group-id ID"),
    _write("sb-keywords.add", "SB", "sb-keywords add --campaign-id ID --ad-group-id ID --keyword-text TEXT --match-type exact --bid 0.75"),
    _write("sb-keywords.edit-bid", "SB", "sb-keywords edit-bid --keyword-id ID --bid 0.75"),
    _write("sb-keywords.set-state", "SB", "sb-keywords set-state --keyword-id ID --state paused"),
    _write("sb-keywords.archive", "SB", "sb-keywords archive --keyword-id ID"),
    _read("sb-negatives.list", "SB", "sb-negatives list --campaign-id ID --scope both"),
    _write("sb-negatives.add-ad-group", "SB", "sb-negatives add-ad-group --campaign-id ID --ad-group-id ID --keyword-text TEXT --match-type negativeExact"),
    _write("sb-negatives.add-campaign", "SB", "sb-negatives add-campaign --campaign-id ID --keyword-text TEXT --match-type negativeExact"),
    _write("sb-negatives.set-state", "SB", "sb-negatives set-state --negative-keyword-id ID --scope campaign --state paused"),
    _write("sb-negatives.archive", "SB", "sb-negatives archive --negative-keyword-id ID --scope adGroup"),
    _read("sb-targets.list", "SB", "sb-targets list --campaign-id ID --ad-group-id ID"),
    _write("sb-targets.add-asin", "SB", "sb-targets add-asin --campaign-id ID --ad-group-id ID --asin ASIN --bid 0.75"),
    _write("sb-targets.add-category", "SB", "sb-targets add-category --campaign-id ID --ad-group-id ID --category-id ID --bid 0.75"),
    _write("sb-targets.add-expression", "SB", "sb-targets add-expression --campaign-id ID --ad-group-id ID --predicate TYPE=VALUE --bid 0.75"),
    _write("sb-targets.edit-bid", "SB", "sb-targets edit-bid --target-id ID --bid 0.75"),
    _write("sb-targets.set-state", "SB", "sb-targets set-state --target-id ID --state paused"),
    _write("sb-targets.archive", "SB", "sb-targets archive --target-id ID"),
    _read("sb-negative-targets.list", "SB", "sb-negative-targets list --campaign-id ID --scope both"),
    _write("sb-negative-targets.add-ad-group", "SB", "sb-negative-targets add-ad-group --campaign-id ID --ad-group-id ID --asin ASIN"),
    _write("sb-negative-targets.add-campaign", "SB", "sb-negative-targets add-campaign --campaign-id ID --category-id ID"),
    _write("sb-negative-targets.set-state", "SB", "sb-negative-targets set-state --negative-target-id ID --scope campaign --state paused"),
    _write("sb-negative-targets.archive", "SB", "sb-negative-targets archive --negative-target-id ID --scope adGroup"),
    _raw("sb-raw.request", "SB", "sb-raw request --method POST --path /sb/v4/campaigns/list --payload-json '{}'", "Media, creative, image, video, logo, and asset paths or payload keys are blocked."),
    _read("sd-campaigns.list", "SD", "sd-campaigns list --marketplace US"),
    _read("ff-campaigns.list", "FF", "ff-campaigns list --marketplace US", "全流域广告活动只读列表；统一 API v1 query/campaigns。官方 API v1 未开放全流域活动的创建和修改。"),
    _read("ff-campaigns.fields", "FF", "ff-campaigns fields --search roas", "全流域报表可选字段（--fields）；本地字段库，不调用 Amazon。"),
    _write("sd-campaigns.create", "SD", "sd-campaigns create --name NAME --budget 15 --start-date YYYY-MM-DD"),
    _write("sd-campaigns.set-state", "SD", "sd-campaigns set-state --campaign-id ID --state paused"),
    _write("sd-campaigns.edit-budget", "SD", "sd-campaigns edit-budget --campaign-id ID --budget 15"),
    _write("sd-campaigns.edit-name", "SD", "sd-campaigns edit-name --campaign-id ID --name NAME"),
    _write("sd-campaigns.archive", "SD", "sd-campaigns archive --campaign-id ID"),
    _read("sd-ad-groups.list", "SD", "sd-ad-groups list --campaign-id ID"),
    _write("sd-ad-groups.create", "SD", "sd-ad-groups create --campaign-id ID --name NAME --default-bid 0.75"),
    _write("sd-ad-groups.set-state", "SD", "sd-ad-groups set-state --ad-group-id ID --state paused"),
    _write("sd-ad-groups.edit-bid", "SD", "sd-ad-groups edit-bid --ad-group-id ID --default-bid 0.75"),
    _write("sd-ad-groups.edit-name", "SD", "sd-ad-groups edit-name --ad-group-id ID --name NAME"),
    _write("sd-ad-groups.archive", "SD", "sd-ad-groups archive --ad-group-id ID"),
    _read("sd-product-ads.list", "SD", "sd-product-ads list --campaign-id ID --ad-group-id ID"),
    _write("sd-product-ads.add", "SD", "sd-product-ads add --campaign-id ID --ad-group-id ID --sku SKU"),
    _write("sd-product-ads.set-state", "SD", "sd-product-ads set-state --product-ad-id ID --state paused"),
    _write("sd-product-ads.edit-name", "SD", "sd-product-ads edit-name --product-ad-id ID --ad-name NAME"),
    _write("sd-product-ads.archive", "SD", "sd-product-ads archive --product-ad-id ID"),
    _read("sd-targets.list", "SD", "sd-targets list --campaign-id ID --ad-group-id ID"),
    _write("sd-targets.add-asin", "SD", "sd-targets add-asin --ad-group-id ID --asin ASIN --bid 0.75"),
    _write("sd-targets.add-category", "SD", "sd-targets add-category --ad-group-id ID --category-id ID --bid 0.75"),
    _write("sd-targets.add-audience", "SD", "sd-targets add-audience --ad-group-id ID --audience-id ID --bid 0.75"),
    _write("sd-targets.add-expression", "SD", "sd-targets add-expression --ad-group-id ID --predicate TYPE=VALUE --bid 0.75"),
    _write("sd-targets.edit-bid", "SD", "sd-targets edit-bid --target-id ID --bid 0.75"),
    _write("sd-targets.set-state", "SD", "sd-targets set-state --target-id ID --state paused"),
    _write("sd-targets.archive", "SD", "sd-targets archive --target-id ID"),
    _read("sd-audiences.taxonomy", "SD", "sd-audiences taxonomy"),
    _read("sd-audiences.list", "SD", "sd-audiences list --audience-name TEXT"),
    _read("sd-locations.list", "SD", "sd-locations list --ad-group-id ID"),
    _write("sd-locations.add", "SD", "sd-locations add --ad-group-id ID --location-id ID"),
    _write("sd-locations.set-state", "SD", "sd-locations set-state --location-target-id ID --state paused"),
    _write("sd-locations.archive", "SD", "sd-locations archive --location-target-id ID"),
    _read("sd-budget-rules.list", "SD", "sd-budget-rules list"),
    _read("sd-budget-rules.show", "SD", "sd-budget-rules show --rule-id ID"),
    _write("sd-budget-rules.create", "SD", "sd-budget-rules create --name NAME --rule-type SCHEDULE --increase-type PERCENT --increase-value 20"),
    _write("sd-budget-rules.update", "SD", "sd-budget-rules update --rule-id ID --state ENABLED"),
    _write("sd-budget-rules.associate", "SD", "sd-budget-rules associate --campaign-id ID --rule-id ID"),
    _write("sd-budget-rules.disassociate", "SD", "sd-budget-rules disassociate --campaign-id ID --rule-id ID"),
    _read("sd-budget-rules.campaigns", "SD", "sd-budget-rules campaigns --rule-id ID"),
    _read("sd-budget-rules.campaign-rules", "SD", "sd-budget-rules campaign-rules --campaign-id ID"),
    _read("sd-budget-rules.usage", "SD", "sd-budget-rules usage --campaign-id ID"),
    _report("sd-snapshots.request", "SD", "sd-snapshots request --record-type campaigns"),
    _report("sd-snapshots.status", "SD", "sd-snapshots status --snapshot-id ID"),
    _report("sd-snapshots.download", "SD", "sd-snapshots download --snapshot-id ID"),
    _raw("sd-raw.request", "SD", "sd-raw request --method POST --path /sd/campaigns --payload-json '{}'", "Creative, asset, image, video, logo, and media paths or payload keys are blocked."),
    _report("reports.create-sp-keywords", "SP", "reports create-sp-keywords --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-campaign-placement", "SP", "reports create-sp-campaign-placement --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-search-terms", "SP", "reports create-search-terms --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-campaigns", "SP", "reports create-sp-campaigns --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-ad-groups", "SP", "reports create-sp-ad-groups --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-targeting", "SP", "reports create-sp-targeting --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-advertised-products", "SP", "reports create-sp-advertised-products --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-purchased-products", "SP", "reports create-sp-purchased-products --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-impression-share", "SP", "reports create-sp-impression-share --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sp-gross-and-invalids", "SP", "reports create-sp-gross-and-invalids --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sb-campaigns", "SB", "reports create-sb-campaigns --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sb-ad-groups", "SB", "reports create-sb-ad-groups --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sb-targeting", "SB", "reports create-sb-targeting --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sb-search-terms", "SB", "reports create-sb-search-terms --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sb-campaign-placement", "SB", "reports create-sb-campaign-placement --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sd-campaigns", "SD", "reports create-sd-campaigns --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sd-ad-groups", "SD", "reports create-sd-ad-groups --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sd-product-ads", "SD", "reports create-sd-product-ads --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report("reports.create-sd-targeting", "SD", "reports create-sd-targeting --start-date YYYY-MM-DD --end-date YYYY-MM-DD"),
    _report(
        "reports.create-full-funnel-campaigns",
        "FF",
        "reports create-full-funnel-campaigns --start-date YYYY-MM-DD --end-date YYYY-MM-DD [--fields metric.roas]",
        "全流域广告活动；统一报表 API v1，按本站点的全流域活动 ID 筛选，没有活动时返回空结果。--fields 可选自定义字段（见 ff-campaigns fields），不传用默认 31 个指标。",
    ),
    _report("reports.status", "ALL", "reports status --report-id ID"),
    _report("reports.download", "ALL", "reports download --report-id ID"),
    _report("reports.parse-search-terms", "SP", "reports parse-search-terms --input-file PATH", "Local parse; no live credentials required."),
    _report("reports.parse-sp-keywords", "SP", "reports parse-sp-keywords --input-file PATH", "Local parse; no live credentials required."),
    _report("reports.parse-sp-campaign-placement", "SP", "reports parse-sp-campaign-placement --input-file PATH", "Local parse; no live credentials required."),
    _report("reports.parse-sb-report", "SB", "reports parse-sb-report --input-file PATH", "Local parse; no live credentials required."),
    _report("reports.parse-sd-report", "SD", "reports parse-sd-report --input-file PATH", "Local parse; no live credentials required."),
]


def normalize_ad_product(ad_product: str | None) -> str:
    value = (ad_product or "ALL").strip().upper()
    if value not in {"ALL", "SP", "SB", "SBV", "SD", "FF"}:
        raise ValueError("ad_product must be one of ALL, SP, SB, SBV, SD, or FF.")
    return value


def build_capability_contract(
    ad_product: str | None = None,
    operation: str | None = None,
    writes_only: bool = False,
) -> dict[str, Any]:
    selected_ad_product = normalize_ad_product(ad_product)
    selected_operation = (operation or "").strip().lower()
    rows: list[dict[str, Any]] = []
    for capability in CAPABILITIES:
        capability_ad_product = str(capability["adProduct"]).upper()
        allowed_products = {selected_ad_product, "ALL"}
        if selected_ad_product == "SBV":
            allowed_products.add("SB")
        if selected_ad_product != "ALL" and capability_ad_product not in {
            *allowed_products,
        }:
            continue
        if selected_operation and selected_operation not in str(capability["operation"]).lower():
            continue
        if writes_only and capability["kind"] not in {"write", "raw"}:
            continue
        rows.append(dict(capability))

    executable_writes = [
        row for row in rows if row["kind"] in {"write", "raw"} and row["canExecute"]
    ]
    return {
        "meta": {
            "mode": "local",
            "status": "ok",
            "contractVersion": CAPABILITY_CONTRACT_VERSION,
            "adProduct": selected_ad_product,
            "aliasOf": "SB" if selected_ad_product == "SBV" else None,
            "operationFilter": selected_operation or None,
            "writesOnly": writes_only,
            "confirmationPrompt": CONFIRMATION_PROMPT,
            "agentInstruction": (
                "Do not answer that a listed SP, SB, SBV, or SD write operation has no execution "
                "capability. It is executable after dry-run or approval-plan review and "
                "the exact user confirmation gate. SBV uses SB non-creative operations; "
                "creative, image, video, logo, asset, and media APIs are intentionally blocked."
            ),
        },
        "data": {
            "capabilities": rows,
            "summary": {
                "total": len(rows),
                "executableWrites": len(executable_writes),
                "approvalRequiredWrites": sum(
                    1 for row in executable_writes if row["approvalRequired"]
                ),
                "directInitialMutation": False,
            },
        },
    }
