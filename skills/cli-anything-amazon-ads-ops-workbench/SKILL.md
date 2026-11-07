---
name: "cli-anything-amazon-ads-ops-workbench"
description: "Use when the user wants a CLI for the current Amazon Ads workbench, or needs command-line access to Amazon Ads OAuth health, profiles, portfolios, ad groups, Sponsored Products, Sponsored Brands/SBV, or Sponsored Display campaign metadata, keywords, product/category/audience/location targets, negative targets, non-creative mutations, report tasks, local report parsing, or snapshot inspection. Trigger whenever the task is about operating this repo's Amazon Ads backend without opening the web UI."
---

# cli-anything-amazon-ads-ops-workbench

Command-line interface for the Amazon Ads Ops Workbench in this repository.

## Purpose

This CLI exposes the same backend contract already present in the local workbench:

- OAuth credential health inspection
- machine-readable capability contract for agents
- profile discovery and marketplace resolution
- portfolio listing, creation, and state editing
- Sponsored Products ad group listing, creation, default bid editing, and state editing
- Sponsored Products campaign creation
- Sponsored Products campaign metadata listing
- Sponsored Products campaign state editing
- Sponsored Products campaign budget editing
- Sponsored Products campaign bidding strategy and placement bid adjustment interfaces with user-supplied values
- Sponsored Products keyword listing
- Sponsored Products keyword creation
- Sponsored Products keyword bid editing
- Sponsored Products keyword state editing
- Sponsored Products product ad listing, creation, and state editing
- Sponsored Products ASIN/category/expression target listing, creation, bid editing, and state editing
- negative keyword listing, ad group/campaign negative creation, and negative state editing
- negative product targeting listing, ad group/campaign negative creation, and negative state editing
- restricted raw `/sp/` request escape hatch for official SP endpoints not yet wrapped by typed commands
- Sponsored Brands campaign/ad group listing and non-creative creation, name, state, budget, and bidding edits
- Sponsored Brands keyword and negative keyword listing, creation, bid/state editing, and archive interfaces
- Sponsored Brands product targeting and negative targeting listing, creation, bid/state editing, and archive interfaces
- restricted raw `/sb/` request escape hatch with media/creative guardrails
- Sponsored Brands Video uses the SB non-creative command surface; creative/media upload APIs remain blocked
- Sponsored Display campaign/ad group/product ad listing and non-creative creation, name, state, bid, budget, and archive interfaces
- Sponsored Display product, audience, and location targeting listing, creation, bid/state editing, and archive interfaces
- Sponsored Display budget rule, snapshot, and restricted raw `/sd/` non-media interfaces
- Sponsored Products keyword, search term, and campaign placement report task creation
- Sponsored Brands campaign, ad group, targeting, search term, and campaign placement report task creation
- Sponsored Display campaign, ad group, product ad, and targeting report task creation
- report status inspection, file download, and local report parsing
- snapshot output aligned with the existing proxy semantics

## Install

From the harness directory:

```bash
cd agent-harness
python -m pip install -e .
```

## Environment

The CLI reads the same environment variables as the existing web proxy:

```bash
AMAZON_ADS_CLIENT_ID=
AMAZON_ADS_CLIENT_SECRET=
AMAZON_ADS_REFRESH_TOKEN=
AMAZON_ADS_PROFILE_ID=
AMAZON_ADS_REGION=NA
AMAZON_ADS_MARKETPLACE=US
AMAZON_ADS_APPROVAL_DIR=  # optional; defaults to ~/.local/state/amazon_ads_ops_workbench/approvals
```

## Command Surface

### `auth`

- `auth health`
  - Check whether the required Amazon Ads credentials are present.

### `profiles`

- `profiles list`
  - Fetch raw profile rows from Amazon Ads.
- `profiles resolve --marketplace US`
  - Resolve the preferred profile for a marketplace.

### `approvals`

- `approvals list --status awaiting_user_confirmation`
  - List local approval plans created by write commands.
- `approvals show --plan-id <PLAN_ID>`
  - Inspect the exact saved payload, payload hash, risk level, and required confirmation prompt.
- `approvals execute --plan-id <PLAN_ID> --confirm-text 确认`
  - Execute a saved write plan only after the user has replied exactly `确认`.

### `capabilities`

- `capabilities --ad-product SP --writes-only`
  - Return the machine-readable SP capability contract for agents.
- `capabilities --ad-product SP --operation campaigns.edit-budget --writes-only`
  - Check whether a specific SP write operation is executable after confirmation.
- `capabilities --ad-product SB --writes-only`
  - Return the machine-readable SB capability contract for agents.
- `capabilities --ad-product SB --operation sb-keywords.edit-bid --writes-only`
  - Check whether a specific SB write operation is executable after confirmation.
- `capabilities --ad-product SBV --writes-only`
  - Return the SBV alias contract. SBV uses SB non-creative operations; creative/media APIs remain blocked.
- `capabilities --ad-product SD --operation sd-targets.edit-bid --writes-only`
  - Check whether a specific SD write operation is executable after confirmation.

Agents must call `capabilities` before answering that an SP, SB, SBV, or SD operation has no execution capability. If a row returns `canExecute: true`, the operation is executable through the approval gate even though the initial typed command does not submit directly.

For SB/SBV, the capability contract separates executable non-creative operations from blocked creative/media work. SB campaign, ad group, keyword, negative keyword, target, negative target, and approved raw non-media requests can execute through the approval gate. SB/SBV ad, creative, image, video, logo, media, asset, and landing-page upload operations remain intentionally unsupported.

For SD, campaign, ad group, product ad, product/audience/location targeting, budget rule, snapshot, report, and approved raw non-media requests are covered. SD creative, image, video, logo, media, and asset APIs remain intentionally unsupported.

### Live mutation approval gate

Read commands and report commands run normally. SP, SB, and SD write commands do not submit directly by default.

When a write command is run without `--dry-run`, it returns `meta.mode = "approval-plan"` and this prompt:

```text
是否执行？执行请回复“确认”，不执行则无需回复！
```

The agent must ask the user with that exact prompt. If the user replies exactly `确认`, call `approvals execute --plan-id <PLAN_ID> --confirm-text 确认`. If the user does not reply exactly `确认`, do not execute.

### Agent recommendation flow

The CLI is an execution and data-access layer; it does not embed an LLM. Generate optimization recommendations in the conversation layer from read commands and reports, then translate user-approved recommendations into typed `--dry-run` commands or approval plans.

For SB, recommendations can cover campaigns, ad groups, keywords, negative keywords, product targets, negative targets, budgets, bids, and states. Recommendations must not produce SB ad, creative, image, video, logo, media, asset, or landing-page upload operations.

For SD, recommendations can cover campaigns, ad groups, product ads, product/audience/location targets, budget rules, budgets, bids, and states. Recommendations must not produce SD creative, image, video, logo, media, or asset operations.

### `campaigns`

- `campaigns list --marketplace US`
  - Fetch and normalize Sponsored Products campaign metadata.
- `campaigns create --name "T11 Manual" --targeting-type MANUAL --budget 10 --start-date 2026-07-22 --strategy MANUAL --dry-run`
  - Build one Sponsored Products campaign creation payload. Without `--dry-run`, create an approval plan.
- `campaigns set-state --campaign-id 123 --state PAUSED --dry-run`
  - Build one Sponsored Products campaign state payload. Without `--dry-run`, create an approval plan.
- `campaigns edit-budget --campaign-id 123 --budget 5.0 --budget-type DAILY --dry-run`
  - Build one Sponsored Products campaign daily budget payload. Without `--dry-run`, create an approval plan.
- `campaigns edit-bidding-strategy --campaign-id 123 --strategy AUTO_FOR_SALES --dry-run`
  - Build one campaign dynamic bidding strategy update payload. Without `--dry-run`, create an approval plan.
- `campaigns edit-placement-bids --campaign-id 123 --top-of-search 100 --product-pages 25 --rest-of-search 0 --dry-run`
  - Build one Sponsored Products campaign placement bid adjustment payload. Without `--dry-run`, create an approval plan.
  - Percentages are explicit user inputs only. Do not recommend, infer, or auto-calculate placement values inside this CLI.
  - Supported placement percentage flags are `--top-of-search`, `--product-pages`, and `--rest-of-search`, each in the 0-900 range.
  - Use `--dry-run` to inspect the exact request payload without saving an approval plan.

### `portfolios`

- `portfolios list --marketplace US`
  - Fetch and normalize portfolio rows for the selected marketplace.
- `portfolios create --name "T11" --budget 100 --currency-code USD --dry-run`
  - Build one portfolio creation payload. Without `--dry-run`, create an approval plan.
- `portfolios set-state --portfolio-id 123 --state ARCHIVED --dry-run`
  - Build one portfolio state update payload. Without `--dry-run`, create an approval plan.

### `ad-groups`

- `ad-groups list --campaign-id 123`
  - Fetch and normalize Sponsored Products ad groups.
- `ad-groups create --campaign-id 123 --name "Exact Core" --default-bid 0.72 --dry-run`
  - Build one Sponsored Products ad group creation payload. Without `--dry-run`, create an approval plan.
- `ad-groups set-state --campaign-id 123 --ad-group-id 456 --state PAUSED --dry-run`
  - Build one Sponsored Products ad group state update payload. Without `--dry-run`, create an approval plan.
- `ad-groups edit-bid --campaign-id 123 --ad-group-id 456 --default-bid 0.81 --dry-run`
  - Build one Sponsored Products ad group default bid update payload. Without `--dry-run`, create an approval plan.

### `keywords`

- `keywords list --campaign-id 123 --ad-group-id 456`
  - Fetch and normalize Sponsored Products keywords.
- `keywords add --campaign-id 123 --ad-group-id 456 --keyword-text "ai recorder" --match-type EXACT --bid 0.91 --dry-run`
  - Build one Sponsored Products keyword creation payload. Without `--dry-run`, create an approval plan.
- `keywords edit-bid --campaign-id 123 --ad-group-id 456 --keyword-id 789 --bid 0.92 --dry-run`
  - Build one keyword bid update payload. The CLI does not include `state` unless explicitly supplied. Without `--dry-run`, create an approval plan.
- `keywords set-state --campaign-id 123 --ad-group-id 456 --keyword-id 789 --state PAUSED --dry-run`
  - Update one keyword state without changing its bid.

### `product-ads`

- `product-ads list --campaign-id 123`
  - Fetch and normalize Sponsored Products advertised product rows.
- `product-ads add --campaign-id 123 --ad-group-id 456 --sku SKU-1 --dry-run`
  - Build one Sponsored Products advertised product payload. Use exactly one of `--sku` or `--asin`. Without `--dry-run`, create an approval plan.
- `product-ads set-state --product-ad-id 789 --state PAUSED --dry-run`
  - Build one Sponsored Products advertised product state update payload. Without `--dry-run`, create an approval plan.

### `targets`

- `targets list --campaign-id 123`
  - Fetch and normalize Sponsored Products targeting clauses.
- `targets add-asin --campaign-id 123 --ad-group-id 456 --asin B000000001 --bid 0.88 --dry-run`
  - Build one ASIN product targeting payload. Without `--dry-run`, create an approval plan.
- `targets add-category --campaign-id 123 --ad-group-id 456 --category-id 123456 --bid 0.67 --dry-run`
  - Build one category product targeting payload. Without `--dry-run`, create an approval plan.
- `targets add-expression --campaign-id 123 --ad-group-id 456 --category-id 123456 --predicate BRAND_SAME_AS=Brand --expression-type AUTO --dry-run`
  - Build one generic product targeting expression payload. Repeat `--predicate TYPE=VALUE` for user-supplied refinements. Without `--dry-run`, create an approval plan.
- `targets edit-bid --target-id 789 --bid 0.79 --dry-run`
  - Build one product targeting bid update payload. Without `--dry-run`, create an approval plan.
- `targets set-state --target-id 789 --state ARCHIVED --dry-run`
  - Build one targeting clause state update payload. Without `--dry-run`, create an approval plan.

### `negatives`

- `negatives list --campaign-id 123 --scope both`
  - Fetch and normalize negative keywords at ad group and/or campaign scope.
- `negatives add-ad-group --campaign-id 123 --ad-group-id 456 --keyword-text "carplay wireless adapter" --match-type NEGATIVE_EXACT --dry-run`
  - Build one ad group negative keyword payload. Without `--dry-run`, create an approval plan.
- `negatives add-campaign --campaign-id 123 --keyword-text "usb c camera" --match-type NEGATIVE_EXACT --dry-run`
  - Build one campaign negative keyword payload. Without `--dry-run`, create an approval plan.
- `negatives set-state --negative-keyword-id 789 --scope adGroup --state PAUSED --dry-run`
  - Build one negative keyword state update payload at ad group or campaign scope. Without `--dry-run`, create an approval plan.

### `negative-targets`

- `negative-targets list --campaign-id 123 --scope both`
  - Fetch and normalize negative product/category targets at ad group and/or campaign scope.
- `negative-targets add-ad-group --campaign-id 123 --ad-group-id 456 --asin B000000001 --expression-type AUTO --dry-run`
  - Build one ad group negative product target payload. Without `--dry-run`, create an approval plan.
- `negative-targets add-campaign --campaign-id 123 --category-id 123456 --dry-run`
  - Build one campaign negative category target payload. Without `--dry-run`, create an approval plan.
- `negative-targets set-state --negative-target-id 789 --scope campaign --state PAUSED --dry-run`
  - Build one negative target state update payload. Without `--dry-run`, create an approval plan.

### `sb-campaigns`

- `sb-campaigns list --marketplace US`
  - Fetch and normalize Sponsored Brands campaign metadata.
- `sb-campaigns create --name "SB Brand Core" --budget 15 --start-date 2026-07-29 --smart-default MANUAL --dry-run`
  - Build one Sponsored Brands campaign creation payload without creative/media fields. Without `--dry-run`, create an approval plan.
- `sb-campaigns set-state --campaign-id 123 --state PAUSED --dry-run`
  - Build one Sponsored Brands campaign state payload. Without `--dry-run`, create an approval plan.
- `sb-campaigns edit-budget --campaign-id 123 --budget 20 --dry-run`
  - Build one Sponsored Brands campaign daily budget payload. Without `--dry-run`, create an approval plan.
- `sb-campaigns edit-name --campaign-id 123 --name "SB Brand Core Exact" --dry-run`
  - Build one Sponsored Brands campaign name update payload. Without `--dry-run`, create an approval plan.
- `sb-campaigns edit-bidding --campaign-id 123 --strategy AUTO_FOR_SALES --dry-run`
  - Build one Sponsored Brands campaign bidding strategy payload. Without `--dry-run`, create an approval plan.
- `sb-campaigns archive --campaign-id 123 --dry-run`
  - Build one Sponsored Brands campaign archive request. Without `--dry-run`, create an approval plan.

### `sb-ad-groups`

- `sb-ad-groups list --campaign-id 123`
  - Fetch and normalize Sponsored Brands ad groups.
- `sb-ad-groups create --campaign-id 123 --name "SB Core" --dry-run`
  - Build one Sponsored Brands ad group creation payload. SB ad group default bid is intentionally not exposed because bids live on keywords/targets.
- `sb-ad-groups set-state --ad-group-id 456 --state PAUSED --dry-run`
  - Build one Sponsored Brands ad group state payload. Without `--dry-run`, create an approval plan.
- `sb-ad-groups edit-name --ad-group-id 456 --name "SB Core Exact" --dry-run`
  - Build one Sponsored Brands ad group name update payload. Without `--dry-run`, create an approval plan.
- `sb-ad-groups archive --ad-group-id 456 --dry-run`
  - Build one Sponsored Brands ad group archive request. Without `--dry-run`, create an approval plan.

### `sb-keywords`

- `sb-keywords list --campaign-id 123 --ad-group-id 456`
  - Fetch and normalize Sponsored Brands keywords.
- `sb-keywords add --campaign-id 123 --ad-group-id 456 --keyword-text "carplay adapter" --match-type exact --bid 0.91 --dry-run`
  - Build one Sponsored Brands keyword creation payload. Without `--dry-run`, create an approval plan.
- `sb-keywords edit-bid --keyword-id 789 --bid 0.92 --dry-run`
  - Build one Sponsored Brands keyword bid payload. Without `--dry-run`, create an approval plan.
- `sb-keywords set-state --keyword-id 789 --state paused --dry-run`
  - Build one Sponsored Brands keyword state payload. Without `--dry-run`, create an approval plan.
- `sb-keywords archive --keyword-id 789 --dry-run`
  - Build one Sponsored Brands keyword archive payload. Without `--dry-run`, create an approval plan.

### `sb-negatives`

- `sb-negatives list --campaign-id 123 --scope both`
  - Fetch and normalize Sponsored Brands negative keywords.
- `sb-negatives add-ad-group --campaign-id 123 --ad-group-id 456 --keyword-text "free" --match-type negativeExact --dry-run`
  - Build one Sponsored Brands ad group negative keyword payload. Without `--dry-run`, create an approval plan.
- `sb-negatives add-campaign --campaign-id 123 --keyword-text "used" --match-type negativePhrase --dry-run`
  - Build one Sponsored Brands campaign negative keyword payload. Without `--dry-run`, create an approval plan.
- `sb-negatives set-state --negative-keyword-id 789 --scope campaign --state paused --dry-run`
  - Build one Sponsored Brands negative keyword state payload. Without `--dry-run`, create an approval plan.
- `sb-negatives archive --negative-keyword-id 789 --scope adGroup --dry-run`
  - Build one Sponsored Brands negative keyword archive payload. Without `--dry-run`, create an approval plan.

### `sb-targets`

- `sb-targets list --campaign-id 123 --ad-group-id 456`
  - Fetch and normalize Sponsored Brands targets.
- `sb-targets add-asin --campaign-id 123 --ad-group-id 456 --asin B000000001 --bid 0.88 --dry-run`
  - Build one Sponsored Brands ASIN target payload. Without `--dry-run`, create an approval plan.
- `sb-targets add-category --campaign-id 123 --ad-group-id 456 --category-id 123456 --bid 0.67 --dry-run`
  - Build one Sponsored Brands category target payload. Without `--dry-run`, create an approval plan.
- `sb-targets add-expression --campaign-id 123 --ad-group-id 456 --predicate asinBrandSameAs=Brand --bid 0.8 --dry-run`
  - Build one Sponsored Brands user-supplied expression target payload. Without `--dry-run`, create an approval plan.
- `sb-targets edit-bid --target-id 789 --bid 0.79 --dry-run`
  - Build one Sponsored Brands target bid payload. Without `--dry-run`, create an approval plan.
- `sb-targets set-state --target-id 789 --state paused --dry-run`
  - Build one Sponsored Brands target state payload. Without `--dry-run`, create an approval plan.
- `sb-targets archive --target-id 789 --dry-run`
  - Build one Sponsored Brands target archive payload. Without `--dry-run`, create an approval plan.

### `sb-negative-targets`

- `sb-negative-targets list --campaign-id 123 --scope both`
  - Fetch and normalize Sponsored Brands negative targets.
- `sb-negative-targets add-ad-group --campaign-id 123 --ad-group-id 456 --asin B000000001 --dry-run`
  - Build one Sponsored Brands ad group negative target payload. Without `--dry-run`, create an approval plan.
- `sb-negative-targets add-campaign --campaign-id 123 --category-id 123456 --dry-run`
  - Build one Sponsored Brands campaign negative target payload. Without `--dry-run`, create an approval plan.
- `sb-negative-targets set-state --negative-target-id 789 --scope campaign --state paused --dry-run`
  - Build one Sponsored Brands negative target state payload. Without `--dry-run`, create an approval plan.
- `sb-negative-targets archive --negative-target-id 789 --scope adGroup --dry-run`
  - Build one Sponsored Brands negative target archive payload. Without `--dry-run`, create an approval plan.

### `sp-raw`

- `sp-raw request --method POST --path /sp/targets/list --payload-json '{"maxResults":10}' --dry-run`
  - Inspect one raw Sponsored Products request for official SP endpoints not yet wrapped by typed commands.
  - The path must start with `/sp/`.
  - Without `--dry-run`, raw requests create approval plans; execute them only through `approvals execute`.

### `sb-raw`

- `sb-raw request --method POST --path /sb/v4/campaigns/list --payload-json '{"maxResults":10}' --dry-run`
  - Inspect one raw Sponsored Brands request for official non-creative SB endpoints not yet wrapped by typed commands.
  - The path must start with `/sb/`.
  - Media, creative, image, video, logo, and asset paths or payload keys are blocked.
  - Without `--dry-run`, raw requests create approval plans; execute them only through `approvals execute`.

### Sponsored Display commands

- `sd-campaigns list --marketplace US`
- `ff-campaigns list --marketplace US [--state ENABLED] [--name KEYWORD] [--max-results 100]`
  - Read-only list of full-funnel campaigns (全流域广告活动) through the unified API v1. Amazon API v1 does not document creating or editing full-funnel campaigns, so there are no ff-campaigns write commands.
  - Fetch and normalize Sponsored Display campaign metadata.
- `sd-campaigns create --name "SD Retargeting" --budget 18.5 --start-date 2026-07-29 --dry-run`
  - Build one SD campaign creation payload. Without `--dry-run`, create an approval plan.
- `sd-campaigns set-state|edit-budget|edit-name|archive`
  - Build one SD campaign mutation payload. Without `--dry-run`, create an approval plan.
- `sd-ad-groups list|create|set-state|edit-bid|edit-name|archive`
  - Work with SD ad groups and default bids without creative operations.
- `sd-product-ads list|add|set-state|edit-name|archive`
  - Work with SD product ads by user-supplied SKU/ASIN and IDs.
- `sd-targets list|add-asin|add-category|add-audience|add-expression|edit-bid|set-state|archive`
  - Work with SD product and audience targets. `add-expression` accepts repeatable user-supplied `--predicate TYPE=VALUE`.
- `sd-audiences taxonomy|list`
  - Discover SD audience taxonomy and audience rows.
- `sd-locations list|add|set-state|archive`
  - Work with SD location targets.
- `sd-budget-rules list|show|create|update|associate|disassociate|campaigns|campaign-rules|usage`
  - Work with SD budget rules and campaign associations.
- `sd-snapshots request|status|download`
  - Create and inspect SD snapshot jobs.
- `sd-raw request --method POST --path /sd/campaigns --payload-json '[{"name":"x"}]' --dry-run`
  - Inspect one raw Sponsored Display request for official non-media SD endpoints not yet wrapped by typed commands.
  - The path must start with `/sd/`.
  - Creative, asset, image, video, logo, and media paths or payload keys are blocked.
  - Without `--dry-run`, raw requests create approval plans; execute them only through `approvals execute`.

### `reports`

- `reports create-sp-keywords --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Products keyword report task.
- `reports create-sp-campaign-placement --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY`
  - Create a Sponsored Products campaign placement report task.
- `reports create-search-terms --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Products search term report task.
- `reports status --report-id <REPORT_ID>`
  - Inspect one report task status.
- `reports download --report-id <REPORT_ID>`
  - Download one completed report to a local JSON file.
- `reports parse-search-terms --input-file <PATH>`
  - Parse a downloaded SP search term report into normalized JSON rows.
- `reports parse-sp-keywords --input-file <PATH>`
  - Parse a downloaded SP keyword report into normalized JSON rows.
- `reports parse-sp-campaign-placement --input-file <PATH>`
  - Parse a downloaded SP campaign placement report into normalized JSON rows.
- `reports create-sb-campaigns --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Brands campaign report task.
- `reports create-sb-ad-groups --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Brands ad group report task.
- `reports create-sb-targeting --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY`
  - Create a Sponsored Brands targeting report task.
- `reports create-sb-search-terms --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Brands search term report task.
- `reports create-sb-campaign-placement --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY`
  - Create a Sponsored Brands campaign placement report task.
- `reports parse-sb-report --input-file <PATH>`
  - Parse a downloaded SB report into normalized JSON rows.
- `reports create-sd-campaigns --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Display campaign report task.
- `reports create-sd-ad-groups --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Display ad group report task.
- `reports create-sd-product-ads --start-date 2026-07-01 --end-date 2026-07-07`
  - Create a Sponsored Display product ad report task.
- `reports create-sd-targeting --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY`
  - Create a Sponsored Display targeting report task.
- `reports create-full-funnel-campaigns --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY [--fields metric.roas --fields metric.userReach]`
  - Create a full-funnel campaign report (console: 全流域广告活动) through the unified Reporting API v1, filtered to this marketplace's full-funnel campaign IDs. Returns `campaignCount` and the unified report; when the marketplace has no full-funnel campaigns no report is created. `--time-unit` is DAILY or SUMMARY. Status and download run in the control plane worker, not `reports status`.
  - Without `--fields` the report carries 31 default metrics (delivery, cost, sales/ROAS, click vs view attribution, promoted/halo, add to cart/list, branded searches, new-to-brand, reach). `--fields` replaces the metrics with up to 60 full-funnel fields (`metric.roas` or `roas`, comma-separated allowed); the date, currency, campaign ID and campaign name are always included. Amazon rejects some combinations (for example a field that needs a companion field); the task then fails with Amazon's explanation.
- `ff-campaigns fields [--category Reach] [--search roas]`
  - Local reference of the fields `--fields` accepts (672 metrics and 10 dimensions), with category, title, data-table column and whether it is a default. Without filters it returns category counts and the default set only.
- `reports parse-sd-report --input-file <PATH>`
  - Parse a downloaded SD report into normalized JSON rows.

### root commands

- `snapshot --marketplace US`
  - Return the normalized snapshot structure used by the workbench.

## Examples

```bash
# machine-readable auth check
cli-anything-amazon-ads-ops-workbench --json auth health

# list profiles
cli-anything-amazon-ads-ops-workbench --json profiles list

# resolve one marketplace
cli-anything-amazon-ads-ops-workbench --json profiles resolve --marketplace US

# inspect SP campaign metadata
cli-anything-amazon-ads-ops-workbench --json campaigns list --marketplace US

# create one SP campaign payload without submitting
cli-anything-amazon-ads-ops-workbench --json campaigns create --name "T11 Manual" --targeting-type MANUAL --budget 10 --start-date 2026-07-22 --strategy MANUAL --dry-run

# pause one campaign payload without submitting
cli-anything-amazon-ads-ops-workbench --json campaigns set-state --campaign-id 123 --state PAUSED --dry-run

# update one campaign daily budget payload without submitting
cli-anything-amazon-ads-ops-workbench --json campaigns edit-budget --campaign-id 123 --budget 5.0 --dry-run

# update one campaign bidding strategy payload without submitting
cli-anything-amazon-ads-ops-workbench --json campaigns edit-bidding-strategy --campaign-id 123 --strategy AUTO_FOR_SALES --dry-run

# inspect one campaign placement bid adjustment payload without submitting
cli-anything-amazon-ads-ops-workbench --json campaigns edit-placement-bids --campaign-id 123 --top-of-search 100 --product-pages 25 --rest-of-search 0 --dry-run

# inspect portfolios
cli-anything-amazon-ads-ops-workbench --json portfolios list --marketplace US

# create one portfolio payload without submitting
cli-anything-amazon-ads-ops-workbench --json portfolios create --name "T11" --budget 100 --currency-code USD --dry-run

# archive one portfolio payload without submitting
cli-anything-amazon-ads-ops-workbench --json portfolios set-state --portfolio-id 123 --state ARCHIVED --dry-run

# inspect ad groups
cli-anything-amazon-ads-ops-workbench --json ad-groups list --campaign-id 123

# create one ad group payload without submitting
cli-anything-amazon-ads-ops-workbench --json ad-groups create --campaign-id 123 --name "Exact Core" --default-bid 0.72 --dry-run

# pause one ad group payload without submitting
cli-anything-amazon-ads-ops-workbench --json ad-groups set-state --campaign-id 123 --ad-group-id 456 --state PAUSED --dry-run

# update one ad group default bid payload without submitting
cli-anything-amazon-ads-ops-workbench --json ad-groups edit-bid --campaign-id 123 --ad-group-id 456 --default-bid 0.81 --dry-run

# inspect keyword rows
cli-anything-amazon-ads-ops-workbench --json keywords list --campaign-id 123

# create one keyword payload without submitting
cli-anything-amazon-ads-ops-workbench --json keywords add --campaign-id 123 --ad-group-id 456 --keyword-text "ai recorder" --match-type EXACT --bid 0.91 --dry-run

# update one keyword bid payload without submitting
cli-anything-amazon-ads-ops-workbench --json keywords edit-bid --campaign-id 123 --ad-group-id 456 --keyword-id 789 --bid 0.92 --dry-run

# pause one keyword payload without submitting
cli-anything-amazon-ads-ops-workbench --json keywords set-state --campaign-id 123 --ad-group-id 456 --keyword-id 789 --state PAUSED --dry-run

# create one advertised product payload without submitting
cli-anything-amazon-ads-ops-workbench --json product-ads add --campaign-id 123 --ad-group-id 456 --sku SKU-1 --dry-run

# pause one advertised product payload without submitting
cli-anything-amazon-ads-ops-workbench --json product-ads set-state --product-ad-id 789 --state PAUSED --dry-run

# create one ASIN target payload without submitting
cli-anything-amazon-ads-ops-workbench --json targets add-asin --campaign-id 123 --ad-group-id 456 --asin B000000001 --bid 0.88 --dry-run

# create one category target payload without submitting
cli-anything-amazon-ads-ops-workbench --json targets add-category --campaign-id 123 --ad-group-id 456 --category-id 123456 --bid 0.67 --dry-run

# create one generic product targeting expression payload without submitting
cli-anything-amazon-ads-ops-workbench --json targets add-expression --campaign-id 123 --ad-group-id 456 --category-id 123456 --predicate BRAND_SAME_AS=Brand --expression-type AUTO --dry-run

# update one product target bid payload without submitting
cli-anything-amazon-ads-ops-workbench --json targets edit-bid --target-id 789 --bid 0.79 --dry-run

# archive one ASIN target payload without submitting
cli-anything-amazon-ads-ops-workbench --json targets set-state --target-id 789 --state ARCHIVED --dry-run

# inspect negatives
cli-anything-amazon-ads-ops-workbench --json negatives list --campaign-id 123 --scope both

# create one ad group negative payload without submitting
cli-anything-amazon-ads-ops-workbench --json negatives add-ad-group --campaign-id 123 --ad-group-id 456 --keyword-text "carplay wireless adapter" --match-type NEGATIVE_EXACT --dry-run

# create one campaign negative payload without submitting
cli-anything-amazon-ads-ops-workbench --json negatives add-campaign --campaign-id 123 --keyword-text "usb c camera" --match-type NEGATIVE_EXACT --dry-run

# pause one ad group negative keyword payload without submitting
cli-anything-amazon-ads-ops-workbench --json negatives set-state --negative-keyword-id 789 --scope adGroup --state PAUSED --dry-run

# inspect negative product/category targets
cli-anything-amazon-ads-ops-workbench --json negative-targets list --campaign-id 123 --scope both

# create one ad group negative ASIN target payload without submitting
cli-anything-amazon-ads-ops-workbench --json negative-targets add-ad-group --campaign-id 123 --ad-group-id 456 --asin B000000001 --expression-type AUTO --dry-run

# create one campaign negative category target payload without submitting
cli-anything-amazon-ads-ops-workbench --json negative-targets add-campaign --campaign-id 123 --category-id 123456 --dry-run

# pause one negative target payload without submitting
cli-anything-amazon-ads-ops-workbench --json negative-targets set-state --negative-target-id 789 --scope campaign --state PAUSED --dry-run

# inspect one raw SP request payload without submitting
cli-anything-amazon-ads-ops-workbench --json sp-raw request --method POST --path /sp/targets/list --payload-json '{"maxResults":10}' --dry-run

# inspect SD capability and create non-submitted SD payloads
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SD --operation sd-targets.edit-bid --writes-only
cli-anything-amazon-ads-ops-workbench --json sd-campaigns create --name "SD Retargeting" --budget 18.5 --start-date 2026-07-29 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-ad-groups create --campaign-id 123 --name "SD Core" --default-bid 0.72 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-product-ads add --campaign-id 123 --ad-group-id 456 --sku SKU-1 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-targets add-audience --ad-group-id 456 --audience-id aud-1 --bid 0.88 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-raw request --method POST --path /sd/campaigns --payload-json '[{"name":"x"}]' --dry-run

# create an SP keyword report
cli-anything-amazon-ads-ops-workbench --json reports create-sp-keywords --start-date 2026-07-01 --end-date 2026-07-07

# create an SP campaign placement report
cli-anything-amazon-ads-ops-workbench --json reports create-sp-campaign-placement --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY

# create an SP search term report
cli-anything-amazon-ads-ops-workbench --json reports create-search-terms --start-date 2026-07-01 --end-date 2026-07-07

# create an SD targeting report
cli-anything-amazon-ads-ops-workbench --json reports create-sd-targeting --start-date 2026-07-01 --end-date 2026-07-07

# inspect report status
cli-anything-amazon-ads-ops-workbench --json reports status --report-id <REPORT_ID>

# download one completed report
cli-anything-amazon-ads-ops-workbench --json reports download --report-id <REPORT_ID>

# parse one downloaded search term report
cli-anything-amazon-ads-ops-workbench --json reports parse-search-terms --input-file ~/Downloads/spSearchTerm.json

# parse one downloaded SP keyword report
cli-anything-amazon-ads-ops-workbench --json reports parse-sp-keywords --input-file ~/Downloads/spKeywords.json

# parse one downloaded SP campaign placement report
cli-anything-amazon-ads-ops-workbench --json reports parse-sp-campaign-placement --input-file ~/Downloads/spCampaignPlacement.json

# inspect the full normalized snapshot
cli-anything-amazon-ads-ops-workbench --json snapshot --marketplace US
```

## REPL

Running the command without a subcommand enters the interactive REPL:

```bash
cli-anything-amazon-ads-ops-workbench
```

Type `help` to see the short command list and `exit` to leave.

## For Agents

- Prefer `--json` for all programmatic use.
- Treat missing credentials as a valid fallback response, not a transport failure.
- Before saying an SP/SB/SBV/SD operation cannot be executed, call `capabilities --ad-product SP --writes-only`, `capabilities --ad-product SB --writes-only`, `capabilities --ad-product SBV --writes-only`, `capabilities --ad-product SD --writes-only`, or `capabilities --operation <operation> --writes-only`.
- `snapshot` is the best high-level command when you want one stable response envelope.
- `campaigns list` is the narrower command when you only need campaign rows.
- Generate SP/SB/SBV/SD optimization recommendations in the conversation layer from read/report outputs; do not treat recommendation generation as permission to execute.
- `campaigns edit-budget` currently validates against the Amazon Ads v3 daily budget shape.
- `campaigns edit-placement-bids` is an interface only. Agents must not infer placement percentages; pass only values supplied by the user and prefer `--dry-run` before creating an approval plan.
- All SP, SB, and SD write commands support `--dry-run`. Without `--dry-run`, they create approval plans and do not submit live mutations.
- Before executing an approval plan, ask the user exactly: `是否执行？执行请回复“确认”，不执行则无需回复！`
- Only call `approvals execute --plan-id <PLAN_ID> --confirm-text 确认` after the user replies exactly `确认`.
- `targets add-expression` and `negative-targets add-*` accept user-supplied predicates as `TYPE=VALUE`; positive targets and ad group negative targets also accept explicit `--expression-type MANUAL|AUTO`.
- Use typed commands first. Use `sp-raw request` or `sb-raw request` only for official endpoints not yet wrapped here; raw requests are also approval-gated.
- Do not add SB ad, creative, image, video, logo, or asset upload commands in this CLI; `sb-raw` blocks those paths and payload keys.
- `portfolios list`, `ad-groups list`, `keywords list`, `product-ads list`, `targets list`, `negatives list`, `negative-targets list`, `sb-campaigns list`, `sb-ad-groups list`, `sb-keywords list`, `sb-negatives list`, `sb-targets list`, `sb-negative-targets list`, and `reports ...` all return a stable `meta + data` envelope.
- `negatives set-state` accepts the live Amazon Ads negative keyword states, which are narrower than campaign states.
- `reports download` defaults to `~/Downloads` unless `--output-dir` is supplied.
- `reports parse-search-terms`, `reports parse-sp-keywords`, `reports parse-sp-campaign-placement`, and `reports parse-sb-report` are local-only commands and do not require live credentials.
