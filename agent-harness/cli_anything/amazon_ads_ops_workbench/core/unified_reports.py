"""Amazon Ads Reporting API v1 (unified) for ad products the v3 report types lack.

Full-funnel campaigns (console: 全流域广告活动) only report through this API. The
advertiser account is global (all marketplaces), so the worker scopes a report to
one profile by filtering on that profile's campaign IDs.
"""

from __future__ import annotations

from datetime import date
from typing import Any

from .full_funnel_fields import FULL_FUNNEL_DIMENSIONS, FULL_FUNNEL_METRICS

FULL_FUNNEL = "FULL_FUNNEL"
TIME_FIELDS = {"DAILY": "date.value", "SUMMARY": "dateRange.value"}
# Always requested: rows must map back to a campaign and its currency.
BASE_FIELDS = ["budgetCurrency.value", "campaign.id", "campaign.name"]
DEFAULT_METRICS = [
    "metric.impressions",
    "metric.viewableImpressions",
    "metric.viewableRate",
    "metric.clicks",
    "metric.ctr",
    "metric.totalCost",
    "metric.cpc",
    "metric.cpm",
    "metric.vcpm",
    "metric.sales",
    "metric.purchases",
    "metric.unitsSold",
    "metric.roas",
    "metric.costPerPurchase",
    "metric.purchaseRate",
    "metric.salesFromClicks",
    "metric.salesFromViews",
    "metric.purchasesFromClicks",
    "metric.purchasesFromViews",
    "metric.salesPromoted",
    "metric.salesHalo",
    "metric.addToCart",
    "metric.detailPageViews",
    "metric.addToList",
    "metric.brandedSearches",
    "metric.brandStorePageViews",
    "metric.newToBrandPurchases",
    "metric.newToBrandSales",
    "metric.newToBrandDetailPageViews",
    "metric.userReach",
    "metric.averageUserImpressionFrequency",
]
FULL_FUNNEL_FIELDS = [*BASE_FIELDS, *DEFAULT_METRICS]
# Impression share needs searchTerm.value and rejects campaign.id, which every
# report here includes (Amazon 400006/400004), so it is never selectable.
SELECTABLE_FIELDS = {
    field: meta
    for field, meta in {**FULL_FUNNEL_DIMENSIONS, **FULL_FUNNEL_METRICS}.items()
    if meta[0] != "Impression share"
}
# Wide reports are slow and may fail on size; keep custom picks reasonable.
MAX_CUSTOM_FIELDS = 60
# Unified field IDs to the column names the data table already labels.
RENAMES = {
    "date.value": "date",
    "dateRange.value": "dateRange",
    "budgetCurrency.value": "campaignBudgetCurrencyCode",
    "campaign.id": "campaignId",
    "campaign.name": "campaignName",
    "metric.totalCost": "cost",
}
# "roas", "metric.roas" and "METRIC.ROAS" all name the same field.
_LOOKUP = {
    alias.lower(): field
    for field in SELECTABLE_FIELDS
    for alias in (field, field.removeprefix("metric."))
}


def resolve_fields(fields: list[str] | tuple[str, ...] | None) -> list[str]:
    """Validate requested field IDs (comma-separated allowed); default metrics when empty."""
    picked: list[str] = []
    unknown: list[str] = []
    for raw in fields or []:
        for name in str(raw).split(","):
            name = name.strip()
            if not name or name in BASE_FIELDS:
                continue
            field = _LOOKUP.get(name.lower())
            if field is None:
                unknown.append(name)
            elif field not in picked:
                picked.append(field)
    if unknown:
        raise ValueError(
            "全流域报表不支持这些字段：" + "、".join(unknown[:10])
            + "；可用字段见 ff-campaigns fields"
        )
    if not picked:
        return list(DEFAULT_METRICS)
    if len(picked) > MAX_CUSTOM_FIELDS:
        raise ValueError(f"一次最多选择 {MAX_CUSTOM_FIELDS} 个字段，当前 {len(picked)} 个")
    if not any(f.startswith("metric.") for f in picked):
        raise ValueError("至少选择一个指标（metric.*）")
    return picked


def list_fields(category: str | None = None, search: str | None = None) -> list[dict[str, Any]]:
    """Selectable full-funnel fields, optionally narrowed by category or a keyword."""
    defaults = set(DEFAULT_METRICS)
    rows = []
    for field, (cat, title) in SELECTABLE_FIELDS.items():
        if category and category.lower() not in cat.lower():
            continue
        if search and search.lower() not in f"{field} {title}".lower():
            continue
        rows.append(
            {
                "field": field,
                "kind": "metric" if field.startswith("metric.") else "dimension",
                "category": cat,
                "title": title,
                "column": _column(field),
                "default": field in defaults,
            }
        )
    return rows


def build_full_funnel_plan(
    start_date: str,
    end_date: str,
    time_unit: str = "DAILY",
    fields: list[str] | tuple[str, ...] | None = None,
) -> dict[str, Any]:
    unit = (time_unit or "DAILY").upper()
    if unit not in TIME_FIELDS:
        raise ValueError("time_unit 只能是 DAILY 或 SUMMARY")
    try:
        start, end = date.fromisoformat(start_date), date.fromisoformat(end_date)
    except (TypeError, ValueError):
        raise ValueError("请提供 YYYY-MM-DD 格式的起止日期") from None
    if end < start:
        raise ValueError("结束日期不能早于开始日期")
    selected = resolve_fields(fields)
    return {
        "unified": True,
        "adProduct": FULL_FUNNEL,
        "startDate": start.isoformat(),
        "endDate": end.isoformat(),
        "fields": [TIME_FIELDS[unit], *BASE_FIELDS, *selected],
    }


def build_report_body(plan: dict[str, Any], advertiser_account_id: str, campaign_ids: list[str]) -> dict[str, Any]:
    return {
        "reports": [
            {
                "format": "CSV",
                "periods": [{"datePeriod": {"startDate": plan["startDate"], "endDate": plan["endDate"]}}],
                "query": {
                    "fields": list(plan["fields"]),
                    "filter": {
                        "on": {
                            "field": "campaign.id",
                            "comparisonOperator": "IN",
                            "not": False,
                            "values": [str(c) for c in campaign_ids],
                        }
                    },
                },
            }
        ],
        "accessRequestedAccounts": [{"advertiserAccountId": advertiser_account_id}],
    }


def pick_advertiser_account(accounts: list[dict[str, Any]], profile_id: str) -> str:
    """The global advertiser account whose alternate IDs include this profile."""
    for account in accounts:
        if any(str(alt.get("profileId")) == str(profile_id) for alt in account.get("alternateIds") or []):
            return account["advertiserAccountId"]
    raise ValueError(f"没有找到包含配置文件 {profile_id} 的广告主账户")


def _squash(name: str) -> str:
    return "".join(ch for ch in name.lower() if ch.isalnum())


def _column(field: str) -> str:
    if field in RENAMES:
        return RENAMES[field]
    if field.startswith("metric."):
        return field.removeprefix("metric.")
    # Dimensions: "dayOfWeek.value" -> dayOfWeek, "conversionSource.name" -> conversionSourceName.
    head, _, attr = field.partition(".")
    return head if attr in ("", "value") else head + attr[:1].upper() + attr[1:]


def _build_aliases() -> dict[str, str]:
    # The download's header spelling is undocumented: accept the field ID
    # ("campaign.id"), a display name ("Campaign ID") or camelCase ("campaignId").
    candidates: dict[str, set[str]] = {}
    titles = {f: t for f, (_, t) in SELECTABLE_FIELDS.items()}
    for field in [*TIME_FIELDS.values(), *BASE_FIELDS, *SELECTABLE_FIELDS]:
        names = [
            field,
            field.removeprefix("metric.").removesuffix(".value"),
            _column(field),
        ]
        if field in titles:
            names.append(titles[field])
        for alias in names:
            candidates.setdefault(_squash(alias), set()).add(_column(field))
    # A display title shared by two fields is ambiguous; leave such headers as they are.
    return {alias: next(iter(cols)) for alias, cols in candidates.items() if len(cols) == 1}


_ALIASES = _build_aliases()


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {_ALIASES.get(_squash(k), _column(k)): v for k, v in row.items()}
        for row in rows
    ]
