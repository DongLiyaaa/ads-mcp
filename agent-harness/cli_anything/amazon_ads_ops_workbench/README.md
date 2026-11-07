# Amazon Ads Ops Workbench CLI

This CLI gives agents a direct command-line interface to the Amazon Ads workbench backend capabilities already present in this repository.

## Covered now

- OAuth health inspection
- Machine-readable capability contract for agents
- Profile listing and marketplace resolution
- Portfolio listing, creation, and state editing
- Sponsored Products ad group listing
- Sponsored Products ad group creation, default bid editing, and state editing
- Sponsored Products campaign metadata listing
- Sponsored Products campaign creation
- Sponsored Products campaign state editing
- Sponsored Products campaign budget editing
- Sponsored Products campaign bidding strategy and placement bid adjustment interfaces with user-supplied values
- Sponsored Products keyword listing
- Sponsored Products keyword creation
- Sponsored Products keyword bid editing
- Sponsored Products keyword state editing
- Sponsored Products product ad listing, creation, and state editing
- Sponsored Products ASIN/category/expression target listing, creation, bid editing, and state editing
- Negative keyword listing, ad group/campaign negative creation, and negative state editing
- Negative product targeting listing, ad group/campaign negative creation, and negative state editing
- Restricted raw `/sp/` request escape hatch for SP endpoints not yet wrapped by typed commands
- Sponsored Products keyword, search term, and campaign placement report task creation
- Sponsored Brands campaign listing, creation, budget/name/bidding/state editing, and archive approval plans
- Sponsored Brands ad group listing, creation, name/state editing, and archive approval plans
- Sponsored Brands keyword listing, creation, bid/state editing, and archive approval plans
- Sponsored Brands negative keyword listing, ad group/campaign negative creation, state editing, and archive approval plans
- Sponsored Brands ASIN/category/expression target listing, creation, bid/state editing, and archive approval plans
- Sponsored Brands negative target listing, ad group/campaign negative creation, state editing, and archive approval plans
- Restricted raw `/sb/` request escape hatch for non-media SB endpoints not yet wrapped by typed commands
- Sponsored Brands campaign, ad group, targeting, search term, and campaign placement report task creation
- Sponsored Brands Video uses the SB non-creative command surface; creative/media upload APIs remain blocked
- Sponsored Display campaign listing, creation, budget/name/state editing, and archive approval plans
- Sponsored Display ad group listing, creation, default bid/name/state editing, and archive approval plans
- Sponsored Display product ad listing, creation, name/state editing, and archive approval plans
- Sponsored Display ASIN/category/audience/expression target listing, creation, bid/state editing, and archive approval plans
- Sponsored Display audience discovery, location targeting, budget rules, and snapshots
- Restricted raw `/sd/` request escape hatch for non-media SD endpoints not yet wrapped by typed commands
- Sponsored Display campaign, ad group, product ad, and targeting report task creation
- Report status inspection, file download, and local report parsing
- Snapshot output aligned with the web proxy

## Environment variables

Set the same variables used by the web proxy:

```bash
export AMAZON_ADS_CLIENT_ID=...
export AMAZON_ADS_CLIENT_SECRET=...
export AMAZON_ADS_REFRESH_TOKEN=...
export AMAZON_ADS_PROFILE_ID=
export AMAZON_ADS_REGION=NA
export AMAZON_ADS_MARKETPLACE=US
```

## Install

```bash
cd agent-harness
pip install -e .
```

## Command examples

```bash
cli-anything-amazon-ads-ops-workbench --json auth health
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SP --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SP --operation campaigns.edit-budget --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SB --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SB --operation sb-keywords.edit-bid --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SBV --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SD --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SD --operation sd-targets.edit-bid --writes-only
cli-anything-amazon-ads-ops-workbench --json profiles list
cli-anything-amazon-ads-ops-workbench --json profiles resolve --marketplace US
cli-anything-amazon-ads-ops-workbench --json portfolios create --name "T11" --budget 100 --currency-code USD --dry-run
cli-anything-amazon-ads-ops-workbench --json portfolios set-state --portfolio-id 123 --state ARCHIVED --dry-run
cli-anything-amazon-ads-ops-workbench --json campaigns list --marketplace US
cli-anything-amazon-ads-ops-workbench --json campaigns create --name "T11 Manual" --targeting-type MANUAL --budget 10 --start-date 2026-07-22 --strategy MANUAL --dry-run
cli-anything-amazon-ads-ops-workbench --json campaigns set-state --campaign-id 123 --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json campaigns edit-budget --campaign-id 123 --budget 5.0 --dry-run
cli-anything-amazon-ads-ops-workbench --json campaigns edit-bidding-strategy --campaign-id 123 --strategy AUTO_FOR_SALES --dry-run
cli-anything-amazon-ads-ops-workbench --json campaigns edit-placement-bids --campaign-id 123 --top-of-search 100 --product-pages 25 --rest-of-search 0 --dry-run
cli-anything-amazon-ads-ops-workbench --json portfolios list --marketplace US
cli-anything-amazon-ads-ops-workbench --json ad-groups list --campaign-id 123
cli-anything-amazon-ads-ops-workbench --json ad-groups create --campaign-id 123 --name "Exact Core" --default-bid 0.72 --dry-run
cli-anything-amazon-ads-ops-workbench --json ad-groups set-state --campaign-id 123 --ad-group-id 456 --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json ad-groups edit-bid --campaign-id 123 --ad-group-id 456 --default-bid 0.81 --dry-run
cli-anything-amazon-ads-ops-workbench --json keywords list --campaign-id 123
cli-anything-amazon-ads-ops-workbench --json keywords add --campaign-id 123 --ad-group-id 456 --keyword-text "ai recorder" --match-type EXACT --bid 0.91 --dry-run
cli-anything-amazon-ads-ops-workbench --json keywords edit-bid --campaign-id 123 --ad-group-id 456 --keyword-id 789 --bid 0.92 --dry-run
cli-anything-amazon-ads-ops-workbench --json keywords set-state --campaign-id 123 --ad-group-id 456 --keyword-id 789 --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json product-ads list --campaign-id 123
cli-anything-amazon-ads-ops-workbench --json product-ads add --campaign-id 123 --ad-group-id 456 --sku SKU-1 --dry-run
cli-anything-amazon-ads-ops-workbench --json product-ads set-state --product-ad-id 789 --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json targets list --campaign-id 123
cli-anything-amazon-ads-ops-workbench --json targets add-asin --campaign-id 123 --ad-group-id 456 --asin B000000001 --bid 0.88 --dry-run
cli-anything-amazon-ads-ops-workbench --json targets add-category --campaign-id 123 --ad-group-id 456 --category-id 123456 --bid 0.67 --dry-run
cli-anything-amazon-ads-ops-workbench --json targets add-expression --campaign-id 123 --ad-group-id 456 --category-id 123456 --predicate BRAND_SAME_AS=Brand --expression-type AUTO --dry-run
cli-anything-amazon-ads-ops-workbench --json targets edit-bid --target-id 789 --bid 0.79 --dry-run
cli-anything-amazon-ads-ops-workbench --json targets set-state --target-id 789 --state ARCHIVED --dry-run
cli-anything-amazon-ads-ops-workbench --json negatives list --campaign-id 123 --scope both
cli-anything-amazon-ads-ops-workbench --json negatives add-ad-group --campaign-id 123 --ad-group-id 456 --keyword-text "carplay wireless adapter" --match-type NEGATIVE_EXACT --dry-run
cli-anything-amazon-ads-ops-workbench --json negatives add-campaign --campaign-id 123 --keyword-text "usb c camera" --match-type NEGATIVE_EXACT --dry-run
cli-anything-amazon-ads-ops-workbench --json negatives set-state --negative-keyword-id 789 --scope adGroup --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json negative-targets list --campaign-id 123 --scope both
cli-anything-amazon-ads-ops-workbench --json negative-targets add-ad-group --campaign-id 123 --ad-group-id 456 --asin B000000001 --expression-type AUTO --dry-run
cli-anything-amazon-ads-ops-workbench --json negative-targets add-campaign --campaign-id 123 --category-id 123456 --dry-run
cli-anything-amazon-ads-ops-workbench --json negative-targets set-state --negative-target-id 789 --scope campaign --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json sp-raw request --method POST --path /sp/targets/list --payload-json '{"maxResults":10}' --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-campaigns list --marketplace US
cli-anything-amazon-ads-ops-workbench --json sb-campaigns create --name "SB Brand Core" --budget 15 --start-date 2026-07-29 --smart-default MANUAL --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-campaigns set-state --campaign-id 123 --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-campaigns edit-budget --campaign-id 123 --budget 20 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-campaigns edit-name --campaign-id 123 --name "SB Brand Core 2" --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-campaigns edit-bidding --campaign-id 123 --no-bid-optimization --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-campaigns archive --campaign-id 123 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-ad-groups list --campaign-id 123
cli-anything-amazon-ads-ops-workbench --json sb-ad-groups create --campaign-id 123 --name "SB Exact" --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-ad-groups set-state --ad-group-id 456 --state PAUSED --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-ad-groups edit-name --ad-group-id 456 --name "SB Phrase" --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-ad-groups archive --ad-group-id 456 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-keywords list --campaign-id 123 --ad-group-id 456
cli-anything-amazon-ads-ops-workbench --json sb-keywords add --campaign-id 123 --ad-group-id 456 --keyword-text "ai recorder" --match-type exact --bid 0.91 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-keywords edit-bid --keyword-id 789 --bid 0.92 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-keywords set-state --keyword-id 789 --state paused --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-keywords archive --keyword-id 789 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-negatives add-ad-group --campaign-id 123 --ad-group-id 456 --keyword-text "usb c camera" --match-type negativeExact --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-negatives add-campaign --campaign-id 123 --keyword-text "free" --match-type negativePhrase --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-targets add-asin --campaign-id 123 --ad-group-id 456 --asin B000000001 --bid 0.88 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-targets add-expression --campaign-id 123 --ad-group-id 456 --asin B000000001 --predicate asinPriceBetween=10-20 --bid 0.88 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-negative-targets add-campaign --campaign-id 123 --asin B000000001 --dry-run
cli-anything-amazon-ads-ops-workbench --json sb-raw request --method POST --path /sb/v4/campaigns/list --payload-json '{"maxResults":10}' --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-campaigns list --marketplace US
cli-anything-amazon-ads-ops-workbench --json sd-campaigns create --name "SD Retargeting" --budget 18.5 --start-date 2026-07-29 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-campaigns edit-budget --campaign-id 123 --budget 20 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-ad-groups create --campaign-id 123 --name "SD Core" --default-bid 0.72 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-product-ads add --campaign-id 123 --ad-group-id 456 --sku SKU-1 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-targets add-audience --ad-group-id 456 --audience-id aud-1 --bid 0.88 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-targets edit-bid --target-id 789 --bid 0.79 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-locations add --ad-group-id 456 --location-id loc-1 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-budget-rules create --name "Prime Day" --rule-type SCHEDULE --increase-type PERCENT --increase-value 20 --start-date 2026-07-29 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-budget-rules associate --campaign-id 123 --rule-id rule-1 --dry-run
cli-anything-amazon-ads-ops-workbench --json sd-snapshots request --record-type campaigns
cli-anything-amazon-ads-ops-workbench --json sd-raw request --method POST --path /sd/campaigns --payload-json '[{"name":"x"}]' --dry-run
cli-anything-amazon-ads-ops-workbench --json reports create-sp-keywords --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sp-campaign-placement --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY
cli-anything-amazon-ads-ops-workbench --json reports create-search-terms --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sb-campaigns --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sb-ad-groups --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sb-targeting --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sb-search-terms --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sb-campaign-placement --start-date 2026-07-01 --end-date 2026-07-07 --time-unit DAILY
cli-anything-amazon-ads-ops-workbench --json reports create-sd-campaigns --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sd-ad-groups --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sd-product-ads --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-sd-targeting --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-full-funnel-campaigns --start-date 2026-07-01 --end-date 2026-07-07
cli-anything-amazon-ads-ops-workbench --json reports create-full-funnel-campaigns --start-date 2026-07-01 --end-date 2026-07-07 --fields metric.roas --fields metric.userReach
cli-anything-amazon-ads-ops-workbench --json reports status --report-id <REPORT_ID>
cli-anything-amazon-ads-ops-workbench --json reports download --report-id <REPORT_ID>
cli-anything-amazon-ads-ops-workbench --json reports parse-search-terms --input-file ~/Downloads/spSearchTerm.json
cli-anything-amazon-ads-ops-workbench --json reports parse-sp-keywords --input-file ~/Downloads/spKeywords.json
cli-anything-amazon-ads-ops-workbench --json reports parse-sp-campaign-placement --input-file ~/Downloads/spCampaignPlacement.json
cli-anything-amazon-ads-ops-workbench --json reports parse-sb-report --input-file ~/Downloads/sbCampaigns.json
cli-anything-amazon-ads-ops-workbench --json reports parse-sd-report --input-file ~/Downloads/sdCampaigns.json
cli-anything-amazon-ads-ops-workbench --json snapshot --marketplace US
```

## Capability contract for agents

Agents should call `capabilities` before claiming an Amazon Ads operation cannot be executed.

```bash
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SP --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SP --operation campaigns.edit-budget --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SB --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SB --operation sb-keywords.edit-bid --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SBV --writes-only
cli-anything-amazon-ads-ops-workbench --json capabilities --ad-product SD --operation sd-targets.edit-bid --writes-only
```

For listed SP, SB, SBV, or SD write operations, `canExecute: true` means the CLI has execution capability after the approval gate. It does not mean the initial write command submits directly. The correct path is:

```text
typed command without --dry-run -> approval plan -> ask exact confirmation prompt -> approvals execute
```

If a row says `approvalRequired: true`, the agent must ask the confirmation prompt before execution. Do not answer that SP/SB/SBV/SD has no execution capability when the target operation appears in this contract with `canExecute: true`.

For SB and SBV, the capability contract separates executable non-creative operations from blocked creative/media work. SB campaign, ad group, keyword, negative keyword, target, negative target, and approved raw non-media requests can execute through the approval gate. SB/SBV ad, creative, image, video, logo, media, asset, and landing-page upload operations remain intentionally unsupported.

For SD, campaign, ad group, product ad, targeting, location, budget rule, snapshot, report, and approved raw non-media requests are covered. SD creative, image, video, logo, media, and asset APIs remain intentionally unsupported.

## Approval gate for live mutations

Read commands and report commands run normally. SP, SB, and SD write commands do not submit directly by default. When a write command is run without `--dry-run`, the CLI writes an approval plan and returns `meta.mode = "approval-plan"` with a `planId`, payload hash, risk level, and this required prompt:

```text
是否执行？执行请回复“确认”，不执行则无需回复！
```

After the user replies exactly `确认`, execute the saved plan:

```bash
cli-anything-amazon-ads-ops-workbench --json approvals show --plan-id <PLAN_ID>
cli-anything-amazon-ads-ops-workbench --json approvals execute --plan-id <PLAN_ID> --confirm-text 确认
```

If the user does not reply exactly `确认`, do not call `approvals execute`.

## Agent recommendation flow

The CLI is an execution and data-access layer; it does not embed an LLM. Agents should use read commands and reports to generate optimization recommendations in the conversation layer, then translate user-approved recommendations into typed `--dry-run` commands or approval plans.

For SB, this means recommendations can cover campaigns, ad groups, keywords, negative keywords, product targets, negative targets, budgets, bids, and states. Recommendations must not produce SB ad, creative, image, video, logo, media, asset, or landing-page upload operations.

For SD, recommendations can cover campaigns, ad groups, product ads, product/audience/location targeting, budget rules, bids, budgets, and states. Recommendations must not produce SD creative, image, video, logo, media, or asset operations.

## Placement bid adjustment

`campaigns edit-placement-bids` is an interface only. Pass only placement percentages explicitly supplied by the user; the CLI does not recommend or auto-calculate bid adjustments.

Supported flags are `--top-of-search`, `--product-pages`, and `--rest-of-search`, each in the 0-900 range. Use `--dry-run` to inspect the request payload without creating an approval plan.

## SP mutation coverage

| SP object | Create/Add | Bid/Budget edit | Pause | Archive |
|---|---|---|---|---|
| Portfolio | `portfolios create` | portfolio budget on create | `portfolios set-state --state PAUSED` | `portfolios set-state --state ARCHIVED` |
| Campaign | `campaigns create` | `campaigns edit-budget`, `campaigns edit-bidding-strategy`, `campaigns edit-placement-bids` | `campaigns set-state --state PAUSED` | `campaigns set-state --state ARCHIVED` |
| Ad group | `ad-groups create` | `ad-groups edit-bid` | `ad-groups set-state --state PAUSED` | `ad-groups set-state --state ARCHIVED` |
| Keyword | `keywords add` | `keywords edit-bid` | `keywords set-state --state PAUSED` | `keywords set-state --state ARCHIVED` |
| Product ad | `product-ads add` | not applicable | `product-ads set-state --state PAUSED` | `product-ads set-state --state ARCHIVED` |
| Product/category target | `targets add-asin`, `targets add-category`, `targets add-expression` | `targets edit-bid` | `targets set-state --state PAUSED` | `targets set-state --state ARCHIVED` |
| Negative keyword | `negatives add-ad-group`, `negatives add-campaign` | not applicable | `negatives set-state --state PAUSED` | state support follows Amazon Ads negative keyword API |
| Negative product/category target | `negative-targets add-ad-group`, `negative-targets add-campaign` | not applicable | `negative-targets set-state --state PAUSED` | `negative-targets set-state --state ARCHIVED` |

All commands in this table support `--dry-run`. Without `--dry-run`, they create approval plans instead of directly submitting to Amazon Ads.

## SB mutation coverage

The SB surface intentionally excludes ad/creative creation and all paths or payloads that touch images, videos, logos, media, assets, or landing-page creative objects.

| SB object | Create/Add | Bid/Budget edit | Pause | Archive |
|---|---|---|---|---|
| Campaign | `sb-campaigns create` | `sb-campaigns edit-budget`, `sb-campaigns edit-bidding` | `sb-campaigns set-state --state PAUSED` | `sb-campaigns archive` |
| Ad group | `sb-ad-groups create` | not supported by SB v4 ad group resources | `sb-ad-groups set-state --state PAUSED` | `sb-ad-groups archive` |
| Keyword | `sb-keywords add` | `sb-keywords edit-bid` | `sb-keywords set-state --state paused` | `sb-keywords archive` |
| Negative keyword | `sb-negatives add-ad-group`, `sb-negatives add-campaign` | not applicable | `sb-negatives set-state --state paused` | `sb-negatives archive` |
| Product/category target | `sb-targets add-asin`, `sb-targets add-category`, `sb-targets add-expression` | `sb-targets edit-bid` | `sb-targets set-state --state paused` | `sb-targets archive` |
| Negative product/category target | `sb-negative-targets add-ad-group`, `sb-negative-targets add-campaign` | not applicable | `sb-negative-targets set-state --state paused` | `sb-negative-targets archive` |

All SB write commands support `--dry-run`. Without `--dry-run`, they create approval plans and require the same `确认` execution gate as SP.

## SD mutation coverage

The SD surface intentionally excludes all creative/media APIs and all paths or payloads that touch images, videos, logos, media, assets, or creative objects.

| SD object | Create/Add | Bid/Budget edit | Pause | Archive |
|---|---|---|---|---|
| Campaign | `sd-campaigns create` | `sd-campaigns edit-budget` | `sd-campaigns set-state --state paused` | `sd-campaigns archive` |
| Ad group | `sd-ad-groups create` | `sd-ad-groups edit-bid` | `sd-ad-groups set-state --state paused` | `sd-ad-groups archive` |
| Product ad | `sd-product-ads add` | not applicable | `sd-product-ads set-state --state paused` | `sd-product-ads archive` |
| Product/audience target | `sd-targets add-asin`, `sd-targets add-category`, `sd-targets add-audience`, `sd-targets add-expression` | `sd-targets edit-bid` | `sd-targets set-state --state paused` | `sd-targets archive` |
| Location target | `sd-locations add` | not applicable | `sd-locations set-state --state paused` | `sd-locations archive` |
| Budget rule | `sd-budget-rules create`, `sd-budget-rules associate` | `sd-budget-rules update` | rule state update via `sd-budget-rules update --state PAUSED` | `sd-budget-rules disassociate` |

All SD write commands support `--dry-run`. Without `--dry-run`, they create approval plans and require the same `确认` execution gate as SP/SB.

## Raw SP escape hatch

`sp-raw request` is intentionally restricted to paths beginning with `/sp/`. Use it only when an official SP endpoint is not yet wrapped by a typed command. Raw SP requests are also approval-gated; run `--dry-run` to inspect the exact method, path, payload, and optional media types, or run without `--dry-run` to create an approval plan for `approvals execute`.

## Raw SB escape hatch

`sb-raw request` is intentionally restricted to paths beginning with `/sb/`, and rejects media/creative paths or payloads before an approval plan can be created. Blocked path or payload tokens include ads, creative, asset, image, video, logo, media, custom image, brand logo, and landing-page creative fields.

Use typed `sb-*` commands first. Use `sb-raw request` only for official non-media SB endpoints that are not yet wrapped.

## Raw SD escape hatch

`sd-raw request` is intentionally restricted to paths beginning with `/sd/`, and rejects media/creative paths or payloads before an approval plan can be created. Blocked path or payload tokens include creative, asset, image, video, logo, media, custom image, and brand logo.

Use typed `sd-*` commands first. Use `sd-raw request` only for official non-media SD endpoints that are not yet wrapped.
