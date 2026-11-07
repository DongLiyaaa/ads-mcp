/** Display metadata for Amazon Ads report columns (see core/reports.py). */
type Format = "int" | "money" | "share";
type Column = { label: string; format?: Format };

/** Amazon suffixes attributed metrics with their window, e.g. sales7d. */
function attribution(key: string, label: string, format: Format): [string, Column][] {
  return [1, 7, 14, 30].map((d) => [`${key}${d}d`, { label: `${label}（${d} 天）`, format }]);
}

const COLUMNS: [string, Column][] = [
  ["date", { label: "日期" }],
  ["dateRange", { label: "日期范围" }],
  ["campaignName", { label: "广告活动" }],
  ["campaignId", { label: "活动 ID" }],
  ["campaignStatus", { label: "活动状态" }],
  ["campaignBiddingStrategy", { label: "竞价策略" }],
  ["campaignBudgetType", { label: "预算类型" }],
  ["campaignBudgetAmount", { label: "预算", format: "money" }],
  ["adGroupName", { label: "广告组" }],
  ["adGroupId", { label: "广告组 ID" }],
  ["adStatus", { label: "广告组状态" }],
  ["adId", { label: "广告 ID" }],
  ["asin", { label: "ASIN" }],
  ["sku", { label: "SKU" }],
  ["advertisedAsin", { label: "推广 ASIN" }],
  ["advertisedSku", { label: "推广 SKU" }],
  ["purchasedAsin", { label: "购买的 ASIN" }],
  ["placementClassification", { label: "广告位" }],
  ["keyword", { label: "关键词" }],
  ["keywordText", { label: "关键词" }],
  ["keywordId", { label: "关键词 ID" }],
  ["keywordType", { label: "关键词类型" }],
  ["matchType", { label: "匹配类型" }],
  ["targeting", { label: "投放表达式" }],
  ["adKeywordStatus", { label: "投放状态" }],
  ["keywordBid", { label: "竞价", format: "money" }],
  ["targetingText", { label: "投放目标" }],
  ["targetingType", { label: "投放类型" }],
  ["targetingId", { label: "投放 ID" }],
  ["targetId", { label: "投放 ID" }],
  ["searchTerm", { label: "搜索词" }],
  ["campaignBudgetCurrencyCode", { label: "币种" }],
  ["event_date", { label: "日期" }],
  ["ad_product_type", { label: "广告类型" }],
  ["ad_product_combo", { label: "广告类型组合" }],
  ["campaign", { label: "广告活动" }],
  ["campaign_id", { label: "活动 ID" }],
  ["ad_group", { label: "广告组" }],
  ["target_expression", { label: "投放表达式" }],
  ["match_type", { label: "匹配类型" }],
  ["customer_search_term", { label: "搜索词" }],
  ["tracked_asin", { label: "购买的 ASIN" }],
  ["frequency_bucket", { label: "曝光频次" }],
  ["time_to_purchase", { label: "购买时长" }],
  ["hour_of_day", { label: "小时" }],
  ["reached_users", { label: "触达人数", format: "int" }],
  ["purchasing_users", { label: "购买人数", format: "int" }],
  ["impressions", { label: "曝光", format: "int" }],
  ["viewable_impressions", { label: "可见曝光", format: "int" }],
  ["clicks", { label: "点击", format: "int" }],
  ["clickThroughRate", { label: "点击率", format: "share" }],
  ["costPerClick", { label: "单次点击花费", format: "money" }],
  ["cost", { label: "花费", format: "money" }],
  ["purchases", { label: "订单", format: "int" }],
  ["sales", { label: "销售额", format: "money" }],
  ["unitsSold", { label: "销量", format: "int" }],
  ["addToCart", { label: "加购", format: "int" }],
  ["detailPageViews", { label: "详情页浏览", format: "int" }],
  ["newToBrandPurchases", { label: "新客订单", format: "int" }],
  ["newToBrandSales", { label: "新客销售额", format: "money" }],
  // Full-funnel (Reporting API v1) defaults; see core/unified_reports.py.
  ["viewableImpressions", { label: "可见曝光", format: "int" }],
  ["viewableRate", { label: "可见率", format: "share" }],
  ["ctr", { label: "点击率", format: "share" }],
  ["cpc", { label: "单次点击花费", format: "money" }],
  ["cpm", { label: "千次曝光花费", format: "money" }],
  ["vcpm", { label: "千次可见曝光花费", format: "money" }],
  ["roas", { label: "ROAS", format: "share" }],
  ["costPerPurchase", { label: "单次订单花费", format: "money" }],
  ["purchaseRate", { label: "购买率", format: "share" }],
  ["salesFromClicks", { label: "点击归因销售额", format: "money" }],
  ["salesFromViews", { label: "浏览归因销售额", format: "money" }],
  ["purchasesFromClicks", { label: "点击归因订单", format: "int" }],
  ["purchasesFromViews", { label: "浏览归因订单", format: "int" }],
  ["salesPromoted", { label: "推广商品销售额", format: "money" }],
  ["salesHalo", { label: "光环销售额", format: "money" }],
  ["addToList", { label: "加入心愿单", format: "int" }],
  ["brandedSearches", { label: "品牌搜索", format: "int" }],
  ["brandStorePageViews", { label: "品牌旗舰店浏览", format: "int" }],
  ["newToBrandDetailPageViews", { label: "新客详情页浏览", format: "int" }],
  ["userReach", { label: "触达用户", format: "int" }],
  ["averageUserImpressionFrequency", { label: "人均曝光频次", format: "share" }],
  ["spend", { label: "花费", format: "money" }],
  ["product_sales", { label: "销售额", format: "money" }],
  ["units_sold", { label: "销量", format: "int" }],
  ["ntb_purchases", { label: "新客订单", format: "int" }],
  ["ntb_product_sales", { label: "新客销售额", format: "money" }],
  ["add_to_cart", { label: "加购", format: "int" }],
  ["detail_page_views", { label: "详情页浏览", format: "int" }],
  ["five_sec_views", { label: "5 秒观看", format: "int" }],
  ["video_first_quartile_views", { label: "视频 25% 观看", format: "int" }],
  ["video_midpoint_views", { label: "视频 50% 观看", format: "int" }],
  ["video_third_quartile_views", { label: "视频 75% 观看", format: "int" }],
  ["video_complete_views", { label: "视频完整观看", format: "int" }],
  ["video_unmutes", { label: "视频取消静音", format: "int" }],
  ...attribution("purchases", "订单", "int"),
  ...attribution("sales", "销售额", "money"),
  ...attribution("unitsSoldClicks", "销量", "int"),
  ...attribution("purchasesSameSku", "同 SKU 订单", "int"),
  ...attribution("attributedSalesSameSku", "同 SKU 销售额", "money"),
  ...attribution("unitsSoldSameSku", "同 SKU 销量", "int"),
  ...attribution("purchasesOtherSku", "其他 SKU 订单", "int"),
  ...attribution("salesOtherSku", "其他 SKU 销售额", "money"),
  ...attribution("unitsSoldOtherSku", "其他 SKU 销量", "int"),
  ["topOfSearchImpressionShare", { label: "搜索顶部曝光份额", format: "share" }],
  ["grossImpressions", { label: "总曝光", format: "int" }],
  ["grossClickThroughs", { label: "总点击", format: "int" }],
  ["invalidImpressions", { label: "无效曝光", format: "int" }],
  ["invalidClickThroughs", { label: "无效点击", format: "int" }],
  ["invalidImpressionRate", { label: "无效曝光率", format: "share" }],
  ["invalidClickThroughRate", { label: "无效点击率", format: "share" }],
];
const known = new Map(COLUMNS.map(([key, c], i) => [key, { ...c, order: i }]));

export function columnLabel(key: string) {
  return known.get(key)?.label ?? key;
}

export function isNumericColumn(key: string) {
  return !!known.get(key)?.format;
}

/**
 * Labelled numeric columns, plus unlabelled ones (custom full-funnel fields)
 * whose values on this page are all numbers; IDs never count.
 */
export function numericColumns(keys: string[], rows: Record<string, unknown>[]) {
  return new Set(
    keys.filter((k) => {
      if (isNumericColumn(k)) return true;
      if (known.has(k) || /id$/i.test(k)) return false;
      const values = rows.map((r) => r?.[k]).filter((v) => v !== null && v !== undefined);
      return values.length > 0 && values.every((v) => typeof v === "number");
    }),
  );
}

/** Known columns in a fixed business order, unknown ones after in first-seen order. */
export function orderColumns(rows: Record<string, unknown>[]) {
  const keys = Array.from(new Set(rows.flatMap((r) => Object.keys(r ?? {}))));
  const rank = (k: string) => known.get(k)?.order ?? COLUMNS.length;
  return keys
    .map((k, i) => ({ k, i }))
    .sort((a, b) => rank(a.k) - rank(b.k) || a.i - b.i)
    .map(({ k }) => k);
}

const money = new Intl.NumberFormat("zh-CN", {
  minimumFractionDigits: 2,
  maximumFractionDigits: 2,
});
const integer = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 0 });
const share = new Intl.NumberFormat("zh-CN", { maximumFractionDigits: 2 });

export function formatCell(key: string, value: unknown) {
  if (value === null || value === undefined || value === "") return "—";
  const format = known.get(key)?.format;
  // IDs stay verbatim: grouping separators would corrupt them.
  if (format && typeof value === "number") {
    if (format === "money") return money.format(value);
    if (format === "int") return integer.format(value);
    return share.format(value);
  }
  return typeof value === "object" ? JSON.stringify(value) : String(value);
}

/** Money/count fields that are rates or settings, so summing them is meaningless. */
const NON_ADDITIVE = new Set([
  "campaignBudgetAmount",
  "keywordBid",
  "costPerClick",
  "searchTermImpressionRank",
  "cpc",
  "cpm",
  "vcpm",
  "costPerPurchase",
  // Unique users: summing across days or campaigns double-counts.
  "userReach",
]);

export function isAdditiveColumn(key: string) {
  const format = known.get(key)?.format;
  return (format === "int" || format === "money") && !NON_ADDITIVE.has(key);
}

export type Derived = {
  key: string;
  label: string;
  format: "percent" | "money" | "ratio";
  calc: (sums: Record<string, number | null>) => number | null;
};

function ratio(a: number | null | undefined, b: number | null | undefined) {
  return a == null || !b ? null : a / b;
}

function windowLabel(key: string) {
  const days = key.match(/(\d+)d$/)?.[1];
  return days ? `（${days} 天）` : "";
}

/** Ratios recomputed from summed totals (averaging row-level ratios would be wrong). */
export function derivedMetrics(metrics: string[]): Derived[] {
  const has = (k: string) => metrics.includes(k);
  const cost = ["cost", "spend"].find(has);
  const sales = ["sales7d", "sales", "sales14d", "sales30d", "product_sales", "sales1d"].find(has);
  const orders = ["purchases7d", "purchases", "purchases14d", "purchases30d", "purchases1d"].find(has);
  const out: Derived[] = [];
  if (has("clicks") && has("impressions"))
    out.push({ key: "ctr", label: "点击率", format: "percent", calc: (s) => ratio(s.clicks, s.impressions) });
  if (cost && has("clicks"))
    out.push({ key: "cpc", label: "单次点击花费", format: "money", calc: (s) => ratio(s[cost], s.clicks) });
  if (orders && has("clicks"))
    out.push({ key: "cvr", label: `转化率${windowLabel(orders)}`, format: "percent", calc: (s) => ratio(s[orders], s.clicks) });
  if (cost && sales) {
    out.push({ key: "acos", label: `ACOS${windowLabel(sales)}`, format: "percent", calc: (s) => ratio(s[cost], s[sales]) });
    out.push({ key: "roas", label: `ROAS${windowLabel(sales)}`, format: "ratio", calc: (s) => ratio(s[sales], s[cost]) });
  }
  if (has("purchasing_users") && has("reached_users"))
    out.push({ key: "buy_rate", label: "购买率", format: "percent", calc: (s) => ratio(s.purchasing_users, s.reached_users) });
  return out;
}

export function formatDerived(format: Derived["format"], value: number | null) {
  if (value == null || !Number.isFinite(value)) return "—";
  if (format === "percent") return `${(value * 100).toFixed(2)}%`;
  if (format === "money") return money.format(value);
  return value.toFixed(2);
}

/** Dimensions with a natural order sort by value instead of by size. */
export function sortsByKey(key: string) {
  return /(^date$|date$|hour|bucket|time_to_purchase)/.test(key);
}
