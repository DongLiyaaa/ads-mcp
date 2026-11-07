from __future__ import annotations

import json
import gzip
import os
from typing import Any
from urllib import error, parse, request

from .env import AdsEnvironment, get_region_base_url
from .relay import opener_for
from .sponsored_brands import assert_sb_raw_allowed
from .sponsored_display import assert_sd_raw_allowed


class AmazonAdsClient:
    def __init__(self, env: AdsEnvironment):
        self.env = env
        self.opener = opener_for(getattr(env, "relay", None))

    def exchange_refresh_token(self) -> str:
        from .runtime import current_runtime
        runtime = current_runtime.get()
        if runtime is not None and runtime.env == self.env and runtime.token:
            return runtime.token
        payload = parse.urlencode(
            {
                "grant_type": "refresh_token",
                "refresh_token": self.env.refresh_token,
                "client_id": self.env.client_id,
                "client_secret": self.env.client_secret,
            }
        ).encode("utf-8")
        req = request.Request(
            "https://api.amazon.com/auth/o2/token",
            method="POST",
            data=payload,
            headers={"Content-Type": "application/x-www-form-urlencoded;charset=UTF-8"},
        )
        data = self._send_json(req, "OAuth token exchange")
        token = data.get("access_token", "")
        if not isinstance(token, str) or not token:
            raise RuntimeError("OAuth token exchange failed: access_token missing")
        return token

    def list_profiles(self, access_token: str) -> list[dict[str, Any]]:
        from .runtime import current_runtime
        runtime = current_runtime.get()
        if runtime is not None and runtime.env == self.env and runtime.profiles:
            return runtime.profiles
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/v2/profiles",
            headers=self._build_headers(access_token),
            method="GET",
        )
        data = self._send_json(req, "Profiles list")
        if not isinstance(data, list):
            raise RuntimeError("Profiles list failed: payload is not an array")
        return [item for item in data if isinstance(item, dict)]

    def list_campaigns(self, access_token: str, profile_id: str) -> list[dict[str, Any]]:
        return self._paginate_campaigns("/sp/campaigns/list", access_token, profile_id)

    def list_sb_campaigns(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sb/v4/campaigns/list", access_token, profile_id, payload)

    def create_sb_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sb/v4/campaigns",
            "POST",
            access_token,
            profile_id,
            self._wrap_campaign_payload(payload),
            "Create SB campaign",
        )

    def edit_sb_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sb/v4/campaigns",
            "PUT",
            access_token,
            profile_id,
            self._wrap_campaign_payload(payload),
            "Edit SB campaign",
        )

    def archive_sb_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sb/v4/campaigns/delete",
            "POST",
            access_token,
            profile_id,
            payload,
            "Archive SB campaign",
        )

    def create_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_campaign_payload(payload)
        return self._send_mutation(
            "/sp/campaigns",
            "POST",
            access_token,
            profile_id,
            body,
            "Create campaign",
        )

    def edit_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_campaign_payload(payload)
        return self._send_mutation(
            "/sp/campaigns",
            "PUT",
            access_token,
            profile_id,
            body,
            "Edit campaign",
        )

    def list_sd_campaigns(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list("/sd/campaigns", access_token, profile_id, query, "SD campaigns list")

    def create_sd_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/campaigns",
            "POST",
            access_token,
            profile_id,
            payload.get("campaigns") if "campaigns" in payload else [payload],
            "Create SD campaign",
            accept="application/json",
            content_type="application/json",
        )

    def edit_sd_campaign(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/campaigns",
            "PUT",
            access_token,
            profile_id,
            payload.get("campaigns") if "campaigns" in payload else [payload],
            "Edit SD campaign",
            accept="application/json",
            content_type="application/json",
        )

    def list_portfolios(self, access_token: str, profile_id: str) -> list[dict[str, Any]]:
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/portfolios/list",
            headers={
                **self._build_headers(access_token),
                "Content-Type": "application/json",
                "Amazon-Advertising-API-Scope": profile_id,
            },
            data=json.dumps({}).encode("utf-8"),
            method="POST",
        )
        data = self._send_json(req, "Portfolios list")
        if isinstance(data, dict):
            rows = data.get("portfolios")
            if isinstance(rows, list):
                return [item for item in rows if isinstance(item, dict)]
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        raise RuntimeError("Portfolios list failed: payload is not an array")

    def create_portfolio(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/portfolios",
            "POST",
            access_token,
            profile_id,
            self._wrap_portfolio_payload(payload),
            "Create portfolio",
        )

    def edit_portfolio(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/portfolios",
            "PUT",
            access_token,
            profile_id,
            self._wrap_portfolio_payload(payload),
            "Edit portfolio",
        )

    def list_ad_groups(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sp/adGroups/list", access_token, profile_id, payload)

    def list_sb_ad_groups(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sb/v4/adGroups/list", access_token, profile_id, payload)

    def create_sb_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sb/v4/adGroups",
            "POST",
            access_token,
            profile_id,
            self._wrap_ad_group_payload(payload),
            "Create SB ad group",
        )

    def edit_sb_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sb/v4/adGroups",
            "PUT",
            access_token,
            profile_id,
            self._wrap_ad_group_payload(payload),
            "Edit SB ad group",
        )

    def archive_sb_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sb/v4/adGroups/delete",
            "POST",
            access_token,
            profile_id,
            payload,
            "Archive SB ad group",
        )

    def create_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/adGroups",
            "POST",
            access_token,
            profile_id,
            self._wrap_ad_group_payload(payload),
            "Create ad group",
        )

    def edit_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/adGroups",
            "PUT",
            access_token,
            profile_id,
            self._wrap_ad_group_payload(payload),
            "Edit ad group",
        )

    def list_sd_ad_groups(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list("/sd/adGroups", access_token, profile_id, query, "SD ad groups list")

    def create_sd_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/adGroups",
            "POST",
            access_token,
            profile_id,
            payload.get("adGroups") if "adGroups" in payload else [payload],
            "Create SD ad group",
            accept="application/json",
            content_type="application/json",
        )

    def edit_sd_ad_group(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/adGroups",
            "PUT",
            access_token,
            profile_id,
            payload.get("adGroups") if "adGroups" in payload else [payload],
            "Edit SD ad group",
            accept="application/json",
            content_type="application/json",
        )

    def list_keywords(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sp/keywords/list", access_token, profile_id, payload)

    def list_sb_keywords(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list(
            "/sb/keywords",
            access_token,
            profile_id,
            query,
            "SB keywords list",
            accept="application/vnd.sbkeyword.v3+json",
        )

    def create_sb_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/keywords",
            "POST",
            access_token,
            profile_id,
            payload.get("keywords") if "keywords" in payload else [payload],
            "Create SB keyword",
            content_type="application/json",
            accept="application/vnd.sbkeywordresponse.v3+json",
        )

    def edit_sb_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/keywords",
            "PUT",
            access_token,
            profile_id,
            payload.get("keywords") if "keywords" in payload else [payload],
            "Edit SB keyword",
            content_type="application/json",
            accept="application/vnd.sbkeywordresponse.v3+json",
        )

    def archive_sb_keyword(
        self,
        access_token: str,
        profile_id: str,
        keyword_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sb/keywords/{keyword_id}",
            "DELETE",
            access_token,
            profile_id,
            None,
            "Archive SB keyword",
            accept="application/json",
        )

    def create_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_keyword_edit_payload(payload)
        return self._send_mutation(
            "/sp/keywords",
            "POST",
            access_token,
            profile_id,
            body,
            "Create keyword",
        )

    def edit_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_keyword_edit_payload(payload)
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/sp/keywords",
            method="PUT",
            data=json.dumps(body).encode("utf-8"),
            headers={
                **self._build_headers(access_token, accept_path="/sp/keywords"),
                "Content-Type": self._content_media_type("/sp/keywords"),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        return self._send_json(req, "Edit keyword")

    def list_negative_keywords(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sp/negativeKeywords/list", access_token, profile_id, payload)

    def list_sb_negative_keywords(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list(
            "/sb/negativeKeywords",
            access_token,
            profile_id,
            query,
            "SB negative keywords list",
            accept="application/vnd.sbnegativekeyword.v3+json",
        )

    def create_sb_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/negativeKeywords",
            "POST",
            access_token,
            profile_id,
            payload.get("negativeKeywords") if "negativeKeywords" in payload else [payload],
            "Create SB negative keyword",
            content_type="application/json",
            accept="application/vnd.sbnegativekeywordresponse.v3+json",
        )

    def edit_sb_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/negativeKeywords",
            "PUT",
            access_token,
            profile_id,
            payload.get("negativeKeywords") if "negativeKeywords" in payload else [payload],
            "Edit SB negative keyword",
            content_type="application/json",
            accept="application/vnd.sbnegativekeywordresponse.v3+json",
        )

    def archive_sb_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        keyword_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sb/negativeKeywords/{keyword_id}",
            "DELETE",
            access_token,
            profile_id,
            None,
            "Archive SB negative keyword",
            accept="application/json",
        )

    def list_product_ads(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sp/productAds/list", access_token, profile_id, payload)

    def create_product_ad(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/productAds",
            "POST",
            access_token,
            profile_id,
            self._wrap_product_ad_payload(payload),
            "Create product ad",
        )

    def edit_product_ad(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/productAds",
            "PUT",
            access_token,
            profile_id,
            self._wrap_product_ad_payload(payload),
            "Edit product ad",
        )

    def list_sd_product_ads(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list("/sd/productAds", access_token, profile_id, query, "SD product ads list")

    def create_sd_product_ad(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/productAds",
            "POST",
            access_token,
            profile_id,
            payload.get("productAds") if "productAds" in payload else [payload],
            "Create SD product ad",
            accept="application/json",
            content_type="application/json",
        )

    def edit_sd_product_ad(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/productAds",
            "PUT",
            access_token,
            profile_id,
            payload.get("productAds") if "productAds" in payload else [payload],
            "Edit SD product ad",
            accept="application/json",
            content_type="application/json",
        )

    def list_targets(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sp/targets/list", access_token, profile_id, payload)

    def list_sb_targets(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list(
            "/sb/targets",
            access_token,
            profile_id,
            query,
            "SB targets list",
            accept="application/vnd.sbtargeting.v3+json",
        )

    def create_sb_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/targets",
            "POST",
            access_token,
            profile_id,
            payload.get("targets") if "targets" in payload else [payload],
            "Create SB target",
            content_type="application/json",
            accept="application/vnd.sbtargetingresponse.v3+json",
        )

    def edit_sb_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/targets",
            "PUT",
            access_token,
            profile_id,
            payload.get("targets") if "targets" in payload else [payload],
            "Edit SB target",
            content_type="application/json",
            accept="application/vnd.sbtargetingresponse.v3+json",
        )

    def archive_sb_target(
        self,
        access_token: str,
        profile_id: str,
        target_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sb/targets/{target_id}",
            "DELETE",
            access_token,
            profile_id,
            None,
            "Archive SB target",
            accept="application/json",
        )

    def create_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/targets",
            "POST",
            access_token,
            profile_id,
            self._wrap_target_payload(payload),
            "Create target",
        )

    def edit_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/targets",
            "PUT",
            access_token,
            profile_id,
            self._wrap_target_payload(payload),
            "Edit target",
        )

    def list_sd_targets(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list("/sd/targets", access_token, profile_id, query, "SD targets list")

    def create_sd_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/targets",
            "POST",
            access_token,
            profile_id,
            payload.get("targets") if "targets" in payload else [payload],
            "Create SD target",
            accept="application/json",
            content_type="application/json",
        )

    def edit_sd_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/targets",
            "PUT",
            access_token,
            profile_id,
            payload.get("targets") if "targets" in payload else [payload],
            "Edit SD target",
            accept="application/json",
            content_type="application/json",
        )

    def list_sd_locations(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list("/sd/locations", access_token, profile_id, query, "SD locations list")

    def create_sd_location(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/locations",
            "POST",
            access_token,
            profile_id,
            payload.get("locations") if "locations" in payload else [payload],
            "Create SD location target",
            accept="application/json",
            content_type="application/json",
        )

    def edit_sd_location(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/locations",
            "PUT",
            access_token,
            profile_id,
            payload.get("locations") if "locations" in payload else [payload],
            "Edit SD location target",
            accept="application/json",
            content_type="application/json",
        )

    def sd_audience_taxonomy(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/audiences/taxonomy/list",
            "POST",
            access_token,
            profile_id,
            payload,
            "SD audience taxonomy",
            accept="application/json",
            content_type="application/json",
        )

    def sd_audience_discovery(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/audiences/list",
            "POST",
            access_token,
            profile_id,
            payload,
            "SD audience discovery",
            accept="application/json",
            content_type="application/json",
        )

    def list_negative_targets(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list("/sp/negativeTargets/list", access_token, profile_id, payload)

    def list_sb_negative_targets(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list(
            "/sb/negativeTargets",
            access_token,
            profile_id,
            query,
            "SB negative targets list",
            accept="application/vnd.sbtargeting.v3+json",
        )

    def create_sb_negative_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/negativeTargets",
            "POST",
            access_token,
            profile_id,
            payload.get("negativeTargets") if "negativeTargets" in payload else [payload],
            "Create SB negative target",
            content_type="application/json",
            accept="application/vnd.sbtargetingresponse.v3+json",
        )

    def edit_sb_negative_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sb/negativeTargets",
            "PUT",
            access_token,
            profile_id,
            payload.get("negativeTargets") if "negativeTargets" in payload else [payload],
            "Edit SB negative target",
            content_type="application/json",
            accept="application/vnd.sbtargetingresponse.v3+json",
        )

    def archive_sb_negative_target(
        self,
        access_token: str,
        profile_id: str,
        target_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sb/negativeTargets/{target_id}",
            "DELETE",
            access_token,
            profile_id,
            None,
            "Archive SB negative target",
            accept="application/json",
        )

    def create_negative_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/negativeTargets",
            "POST",
            access_token,
            profile_id,
            self._wrap_negative_target_payload(payload),
            "Create negative target",
        )

    def edit_negative_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/negativeTargets",
            "PUT",
            access_token,
            profile_id,
            self._wrap_negative_target_payload(payload),
            "Edit negative target",
        )

    def list_campaign_negative_keywords(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list(
            "/sp/campaignNegativeKeywords/list",
            access_token,
            profile_id,
            payload,
        )

    def create_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_negative_keyword_payload(payload)
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/sp/negativeKeywords",
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                **self._build_headers(access_token, accept_path="/sp/negativeKeywords"),
                "Content-Type": self._content_media_type("/sp/negativeKeywords"),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        return self._send_json(req, "Create negative keyword")

    def create_campaign_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_campaign_negative_keyword_payload(payload)
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/sp/campaignNegativeKeywords",
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers={
                **self._build_headers(
                    access_token, accept_path="/sp/campaignNegativeKeywords"
                ),
                "Content-Type": self._content_media_type("/sp/campaignNegativeKeywords"),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        return self._send_json(req, "Create campaign negative keyword")

    def edit_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_negative_keyword_payload(payload)
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/sp/negativeKeywords",
            method="PUT",
            data=json.dumps(body).encode("utf-8"),
            headers={
                **self._build_headers(access_token, accept_path="/sp/negativeKeywords"),
                "Content-Type": self._content_media_type("/sp/negativeKeywords"),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        return self._send_json(req, "Edit negative keyword")

    def edit_campaign_negative_keyword(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        body = self._wrap_campaign_negative_keyword_payload(payload)
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/sp/campaignNegativeKeywords",
            method="PUT",
            data=json.dumps(body).encode("utf-8"),
            headers={
                **self._build_headers(
                    access_token, accept_path="/sp/campaignNegativeKeywords"
                ),
                "Content-Type": self._content_media_type("/sp/campaignNegativeKeywords"),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        return self._send_json(req, "Edit campaign negative keyword")

    def list_campaign_negative_targets(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        return self._post_list(
            "/sp/campaignNegativeTargets/list",
            access_token,
            profile_id,
            payload,
        )

    def create_campaign_negative_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/campaignNegativeTargets",
            "POST",
            access_token,
            profile_id,
            self._wrap_campaign_negative_target_payload(payload),
            "Create campaign negative target",
        )

    def edit_campaign_negative_target(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_mutation(
            "/sp/campaignNegativeTargets",
            "PUT",
            access_token,
            profile_id,
            self._wrap_campaign_negative_target_payload(payload),
            "Edit campaign negative target",
        )

    def list_sd_budget_rules(
        self,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
    ) -> list[dict[str, Any]]:
        return self._get_list("/sd/budgetRules", access_token, profile_id, query, "SD budget rules list")

    def get_sd_budget_rule(
        self,
        access_token: str,
        profile_id: str,
        rule_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sd/budgetRules/{rule_id}",
            "GET",
            access_token,
            profile_id,
            None,
            "Get SD budget rule",
            accept="application/json",
        )

    def create_sd_budget_rule(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/budgetRules",
            "POST",
            access_token,
            profile_id,
            payload,
            "Create SD budget rule",
            accept="application/json",
            content_type="application/json",
        )

    def update_sd_budget_rule(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/budgetRules",
            "PUT",
            access_token,
            profile_id,
            payload,
            "Update SD budget rule",
            accept="application/json",
            content_type="application/json",
        )

    def associate_sd_budget_rule(
        self,
        access_token: str,
        profile_id: str,
        campaign_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            f"/sd/campaigns/{campaign_id}/budgetRules",
            "POST",
            access_token,
            profile_id,
            payload,
            "Associate SD budget rule",
            accept="application/json",
            content_type="application/json",
        )

    def disassociate_sd_budget_rule(
        self,
        access_token: str,
        profile_id: str,
        campaign_id: str,
        rule_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sd/campaigns/{campaign_id}/budgetRules/{rule_id}",
            "DELETE",
            access_token,
            profile_id,
            None,
            "Disassociate SD budget rule",
            accept="application/json",
        )

    def list_sd_budget_rule_campaigns(
        self,
        access_token: str,
        profile_id: str,
        rule_id: str,
        query: dict[str, str],
    ) -> Any:
        query_string = parse.urlencode({key: value for key, value in query.items() if value})
        path = f"/sd/budgetRules/{rule_id}/campaigns"
        if query_string:
            path = f"{path}?{query_string}"
        return self._send_request_json(
            path,
            "GET",
            access_token,
            profile_id,
            None,
            "List SD budget rule campaigns",
            accept="application/json",
        )

    def list_sd_campaign_budget_rules(
        self,
        access_token: str,
        profile_id: str,
        campaign_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sd/campaigns/{campaign_id}/budgetRules",
            "GET",
            access_token,
            profile_id,
            None,
            "List SD campaign budget rules",
            accept="application/json",
        )

    def sd_budget_usage(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            "/sd/campaigns/budget/usage",
            "POST",
            access_token,
            profile_id,
            payload,
            "SD budget usage",
            accept="application/json",
            content_type="application/json",
        )

    def request_sd_snapshot(
        self,
        access_token: str,
        profile_id: str,
        record_type: str,
        payload: dict[str, Any],
    ) -> Any:
        return self._send_request_json(
            f"/sd/{record_type}/snapshot",
            "POST",
            access_token,
            profile_id,
            payload,
            "Request SD snapshot",
            accept="application/json",
            content_type="application/json",
        )

    def get_sd_snapshot(
        self,
        access_token: str,
        profile_id: str,
        snapshot_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sd/snapshots/{snapshot_id}",
            "GET",
            access_token,
            profile_id,
            None,
            "Get SD snapshot",
            accept="application/json",
        )

    def download_sd_snapshot(
        self,
        access_token: str,
        profile_id: str,
        snapshot_id: str,
    ) -> Any:
        return self._send_request_json(
            f"/sd/snapshots/{snapshot_id}/download",
            "GET",
            access_token,
            profile_id,
            None,
            "Download SD snapshot",
            accept="application/json",
        )

    def send_sp_raw(
        self,
        access_token: str,
        profile_id: str,
        method: str,
        path: str,
        payload: dict[str, Any] | list[Any] | None = None,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> Any:
        if not path.startswith("/sp/"):
            raise ValueError("Raw SP requests must use a path that starts with /sp/.")
        normalized_method = method.upper()
        data = None
        headers = {
            **self._build_headers(access_token, accept_path=path),
            "Amazon-Advertising-API-Scope": profile_id,
        }
        if accept:
            headers["Accept"] = accept
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = content_type or self._content_media_type(path)
        elif content_type:
            headers["Content-Type"] = content_type
        req = request.Request(
            f"{get_region_base_url(self.env.region)}{path}",
            method=normalized_method,
            data=data,
            headers=headers,
        )
        return self._send_json(req, f"Raw SP request {normalized_method} {path}")

    def send_sd_raw(
        self,
        access_token: str,
        profile_id: str,
        method: str,
        path: str,
        payload: dict[str, Any] | list[Any] | None = None,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> Any:
        assert_sd_raw_allowed(path, payload)
        normalized_method = method.upper()
        return self._send_request_json(
            path,
            normalized_method,
            access_token,
            profile_id,
            payload,
            f"Raw SD request {normalized_method} {path}",
            accept=accept,
            content_type=content_type,
        )

    def send_sb_raw(
        self,
        access_token: str,
        profile_id: str,
        method: str,
        path: str,
        payload: dict[str, Any] | list[Any] | None = None,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> Any:
        assert_sb_raw_allowed(path, payload)
        normalized_method = method.upper()
        return self._send_request_json(
            path,
            normalized_method,
            access_token,
            profile_id,
            payload,
            f"Raw SB request {normalized_method} {path}",
            accept=accept,
            content_type=content_type,
        )

    def create_report(
        self,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        from .runtime import current_runtime
        runtime = current_runtime.get()
        if runtime is not None and runtime.mode == 'report_plan':
            runtime.report = payload
            return {'reportId': 'local-plan', 'status': 'LOCAL_ONLY'}
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/reporting/reports",
            method="POST",
            data=json.dumps(payload).encode("utf-8"),
            headers={
                **self._build_headers(access_token),
                "Content-Type": "application/json",
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        data = self._send_json(req, "Create report")
        if not isinstance(data, dict):
            raise RuntimeError("Create report failed: payload is not an object")
        return data

    def get_report(self, access_token: str, profile_id: str, report_id: str) -> dict[str, Any]:
        req = request.Request(
            f"{get_region_base_url(self.env.region)}/reporting/reports/{report_id}",
            method="GET",
            headers={
                **self._build_headers(access_token),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        data = self._send_json(req, "Get report status")
        if not isinstance(data, dict):
            raise RuntimeError("Get report status failed: payload is not an object")
        return data

    def _ads_api_send(
        self, access_token: str, path: str, label: str, body: dict[str, Any], profile_id: str | None = None
    ) -> dict[str, Any]:
        """Unified Ads API (/adsApi/v1); a profile scope narrows queries to one marketplace."""
        headers = {
            **self._build_headers(access_token),
            "Amazon-Ads-ClientId": self.env.client_id,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if profile_id:
            headers["Amazon-Advertising-API-Scope"] = profile_id
        req = request.Request(
            f"{get_region_base_url(self.env.region)}{path}",
            method="POST",
            data=json.dumps(body).encode("utf-8"),
            headers=headers,
        )
        data = self._send_json(req, label)
        if not isinstance(data, dict):
            raise RuntimeError(f"{label} failed: payload is not an object")
        return data

    def query_campaigns(
        self,
        access_token: str,
        profile_id: str,
        ad_product: str,
        states: list[str] | None = None,
        campaign_ids: list[str] | None = None,
        name: str | None = None,
        limit: int | None = None,
    ) -> list[dict[str, Any]]:
        """Campaigns of one ad product through the unified API v1, following nextToken."""
        campaigns: list[dict[str, Any]] = []
        next_token, seen = None, set()
        while True:
            body: dict[str, Any] = {"adProductFilter": {"include": [ad_product]}, "maxResults": 100}
            if states:
                body["stateFilter"] = {"include": list(states)}
            if campaign_ids:
                body["campaignIdFilter"] = {"include": [str(c) for c in campaign_ids]}
            if name:
                body["nameFilter"] = {"include": [name], "queryTermMatchType": "BROAD_MATCH"}
            if next_token:
                body["nextToken"] = next_token
            data = self._ads_api_send(access_token, "/adsApi/v1/query/campaigns", "Query campaigns", body, profile_id)
            campaigns.extend(c for c in data.get("campaigns") or [] if isinstance(c, dict))
            next_token = data.get("nextToken")
            if (limit and len(campaigns) >= limit) or not next_token or next_token in seen:
                return campaigns[:limit] if limit else campaigns
            seen.add(next_token)

    def query_campaign_ids(self, access_token: str, profile_id: str, ad_product: str) -> list[str]:
        return [
            str(c["campaignId"])
            for c in self.query_campaigns(access_token, profile_id, ad_product)
            if c.get("campaignId")
        ]

    def advertiser_account_id(self, access_token: str, profile_id: str) -> str:
        from .unified_reports import pick_advertiser_account

        data = self._ads_api_send(access_token, "/adsApi/v1/query/advertiserAccounts", "Advertiser accounts", {})
        try:
            return pick_advertiser_account(data.get("advertiserAccounts") or [], profile_id)
        except ValueError as exc:
            raise RuntimeError(f"Advertiser accounts failed: {exc}") from None

    def _unified_report(self, data: dict[str, Any], label: str) -> dict[str, Any]:
        # Multi-status (207): per-report results arrive in success / error arrays.
        success = data.get("success") or []
        if success and isinstance(success[0].get("report"), dict):
            return success[0]["report"]
        raise RuntimeError(f"{label} failed: 400 {json.dumps(data.get('error') or data, ensure_ascii=False)[:1000]}")

    def unified_create_report(self, access_token: str, body: dict[str, Any]) -> dict[str, Any]:
        data = self._ads_api_send(access_token, "/adsApi/v1/create/reports", "Create unified report", body)
        report = self._unified_report(data, "Create unified report")
        if not report.get("reportId"):
            raise RuntimeError("Create unified report failed: reportId missing")
        return report

    def unified_get_report(self, access_token: str, report_id: str) -> dict[str, Any]:
        data = self._ads_api_send(
            access_token, "/adsApi/v1/retrieve/reports", "Get unified report", {"reportIds": [report_id]}
        )
        return self._unified_report(data, "Get unified report")

    def list_ads_accounts(self, access_token: str) -> list[dict[str, Any]]:
        """Account Management API; alternateIds carry the sponsored ads entity IDs."""
        media = "application/vnd.listaccountsresource.v1+json"
        accounts: list[dict[str, Any]] = []
        next_token, seen = None, set()
        while True:
            body: dict[str, Any] = {"maxResults": 100}
            if next_token:
                body["nextToken"] = next_token
            req = request.Request(
                f"{get_region_base_url(self.env.region)}/adsAccounts/list",
                method="POST",
                data=json.dumps(body).encode("utf-8"),
                headers={**self._build_headers(access_token), "Content-Type": media, "Accept": media},
            )
            data = self._send_json(req, "Ads accounts list")
            accounts.extend(a for a in data.get("adsAccounts") or [] if isinstance(a, dict))
            next_token = data.get("nextToken")
            if not next_token or next_token in seen:
                return accounts
            seen.add(next_token)

    def _amc_send(
        self,
        access_token: str,
        entity_id: str,
        method: str,
        path: str,
        label: str,
        body: dict[str, Any] | None = None,
    ) -> Any:
        from .amc import MARKETPLACE_IDS

        marketplace = MARKETPLACE_IDS.get((self.env.marketplace or "").upper())
        if not marketplace:
            raise RuntimeError(f"{label} failed: AMC 不支持站点 {self.env.marketplace}")
        req = request.Request(
            f"{get_region_base_url(self.env.region)}{path}",
            method=method,
            data=json.dumps(body).encode("utf-8") if body is not None else None,
            headers={
                **self._build_headers(access_token),
                "Content-Type": "application/json",
                "Amazon-Advertising-API-AdvertiserId": entity_id,
                "Amazon-Advertising-API-MarketplaceId": marketplace,
            },
        )
        return self._send_json(req, label)

    def amc_context(
        self, access_token: str, instance_id: str | None = None
    ) -> tuple[str, dict[str, Any]]:
        """Resolve (sponsored ads entity ID, AMC instance) for this profile."""
        from .amc import pick_entity, pick_instance

        entity = pick_entity(
            self.list_ads_accounts(access_token), self.env.marketplace, self.env.profile_id
        )
        data = self._amc_send(access_token, entity, "GET", "/amc/instances", "AMC instances")
        return entity, pick_instance(data.get("instances") or [], instance_id)

    def amc_data_sources(
        self, access_token: str, entity_id: str, instance_id: str
    ) -> list[dict[str, Any]]:
        sources: list[dict[str, Any]] = []
        next_token, seen = None, set()
        while True:
            query = "?" + parse.urlencode({"nextToken": next_token}) if next_token else ""
            data = self._amc_send(
                access_token,
                entity_id,
                "GET",
                f"/amc/reporting/{parse.quote(instance_id)}/dataSources{query}",
                "AMC data sources",
            )
            sources.extend(data.get("dataSources") or [])
            next_token = data.get("nextToken")
            if not next_token or next_token in seen:
                return sources
            seen.add(next_token)

    def amc_list_executions(
        self, access_token: str, entity_id: str, instance_id: str, min_creation_time: str
    ) -> list[dict[str, Any]]:
        query = parse.urlencode({"minCreationTime": min_creation_time})
        data = self._amc_send(
            access_token,
            entity_id,
            "GET",
            f"/amc/reporting/{parse.quote(instance_id)}/workflowExecutions?{query}",
            "AMC executions",
        )
        return data.get("executions") or data.get("workflowExecutions") or []

    def amc_create_execution(
        self,
        access_token: str,
        entity_id: str,
        instance_id: str | None,
        body: dict[str, Any],
    ) -> dict[str, Any]:
        from .runtime import current_runtime

        runtime = current_runtime.get()
        if runtime is not None and runtime.mode == "report_plan":
            # The worker resolves the entity and instance when it submits.
            runtime.report = {"amc": True, "instanceId": instance_id, "execution": body}
            return {"workflowExecutionId": "local-plan", "status": "LOCAL_ONLY"}
        data = self._amc_send(
            access_token,
            entity_id,
            "POST",
            f"/amc/reporting/{parse.quote(instance_id or '')}/workflowExecutions",
            "Create AMC execution",
            body,
        )
        if not isinstance(data, dict) or not data.get("workflowExecutionId"):
            raise RuntimeError("Create AMC execution failed: workflowExecutionId missing")
        return data

    def amc_get_execution(
        self, access_token: str, entity_id: str, instance_id: str, execution_id: str
    ) -> dict[str, Any]:
        return self._amc_send(
            access_token,
            entity_id,
            "GET",
            f"/amc/reporting/{parse.quote(instance_id)}/workflowExecutions/{parse.quote(execution_id)}",
            "Get AMC execution",
        )

    def amc_download_urls(
        self, access_token: str, entity_id: str, instance_id: str, execution_id: str
    ) -> list[str]:
        data = self._amc_send(
            access_token,
            entity_id,
            "GET",
            f"/amc/reporting/{parse.quote(instance_id)}/workflowExecutions/{parse.quote(execution_id)}/downloadUrls",
            "AMC download URLs",
        )
        return [u for u in data.get("downloadUrls") or [] if isinstance(u, str)]

    def download_report_file(self, url: str, output_path: str) -> dict[str, Any]:
        try:
            with self.opener.open(url, timeout=60) as resp:
                raw = resp.read()
                content_type = resp.headers.get("Content-Type", "")
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"Download report failed: {exc.code} {payload}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"Download report failed: {exc.reason}") from exc

        data = raw
        if raw[:2] == b"\x1f\x8b" or "gzip" in content_type.lower():
            data = gzip.decompress(raw)

        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "wb") as fh:
            fh.write(data)
        return {
            "localPath": output_path,
            "bytesWritten": len(data),
        }

    def _paginate_campaigns(self, path, access_token, profile_id):
        return self._post_list(path, access_token, profile_id, {"pageSize": 30})

    def _post_list(self, path, access_token, profile_id, payload):
        records = []
        body = dict(payload)
        seen = set()
        keys = ("campaigns", "adGroups", "keywords", "negativeKeywords",
                "campaignNegativeKeywords", "productAds", "targetingClauses",
                "negativeTargetingClauses", "campaignNegativeTargetingClauses",
                "portfolios", "budgetRulesDetails", "budgetRules", "locations",
                "audiences", "snapshots", "results", "items")
        for _ in range(100):
            req = request.Request(
                f"{get_region_base_url(self.env.region)}{path}",
                method="POST", data=json.dumps(body).encode("utf-8"),
                headers={**self._build_headers(access_token, accept_path=path),
                         "Content-Type": self._content_media_type(path),
                         "Amazon-Advertising-API-Scope": profile_id},
            )
            data = self._send_json(req, f"List request {path}")
            if isinstance(data, list):
                records.extend(item for item in data if isinstance(item, dict))
                return records
            if not isinstance(data, dict):
                raise RuntimeError("List response is neither an object nor an array")
            page = next((data[key] for key in keys if isinstance(data.get(key), list)), [])
            records.extend(item for item in page if isinstance(item, dict))
            token = data.get("nextToken")
            if not token:
                return records
            if token in seen:
                raise RuntimeError("Repeated pagination token; refusing incomplete results")
            seen.add(token)
            body["nextToken"] = token
        raise RuntimeError("Pagination exceeded 100 pages; narrow the query filters")

    def _get_list(
        self,
        path: str,
        access_token: str,
        profile_id: str,
        query: dict[str, str],
        label: str,
        accept: str | None = None,
    ) -> list[dict[str, Any]]:
        query_string = parse.urlencode(
            {key: value for key, value in query.items() if value}
        )
        url = f"{get_region_base_url(self.env.region)}{path}"
        if query_string:
            url = f"{url}?{query_string}"
        headers = {
            **self._build_headers(access_token, accept_path=path),
            "Amazon-Advertising-API-Scope": profile_id,
        }
        if accept:
            headers["Accept"] = accept
        req = request.Request(url, method="GET", headers=headers)
        data = self._send_json(req, label)
        if isinstance(data, list):
            return [item for item in data if isinstance(item, dict)]
        if isinstance(data, dict):
            for key in (
                "campaigns",
                "adGroups",
                "keywords",
                "negativeKeywords",
                "targets",
                "negativeTargets",
                "targetingClauses",
                "negativeTargetingClauses",
                "productAds",
                "budgetRulesDetails",
                "budgetRules",
                "locations",
                "audiences",
                "taxonomies",
                "results",
                "items",
            ):
                candidate = data.get(key)
                if isinstance(candidate, list):
                    return [item for item in candidate if isinstance(item, dict)]
        return []

    def _send_mutation(
        self,
        path: str,
        method: str,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any],
        label: str,
    ) -> Any:
        req = request.Request(
            f"{get_region_base_url(self.env.region)}{path}",
            method=method,
            data=json.dumps(payload).encode("utf-8"),
            headers={
                **self._build_headers(access_token, accept_path=path),
                "Content-Type": self._content_media_type(path),
                "Amazon-Advertising-API-Scope": profile_id,
            },
        )
        return self._send_json(req, label)

    def _send_request_json(
        self,
        path: str,
        method: str,
        access_token: str,
        profile_id: str,
        payload: dict[str, Any] | list[Any] | None,
        label: str,
        accept: str | None = None,
        content_type: str | None = None,
    ) -> Any:
        data = None
        headers = {
            **self._build_headers(access_token, accept_path=path),
            "Amazon-Advertising-API-Scope": profile_id,
        }
        if accept:
            headers["Accept"] = accept
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = content_type or self._content_media_type(path)
        elif content_type:
            headers["Content-Type"] = content_type
        req = request.Request(
            f"{get_region_base_url(self.env.region)}{path}",
            method=method,
            data=data,
            headers=headers,
        )
        return self._send_json(req, label)

    def _build_headers(
        self,
        access_token: str,
        accept_path: str | None = None,
    ) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Amazon-Advertising-API-ClientId": self.env.client_id,
        }
        accept = self._accept_media_type(accept_path)
        if accept:
            headers["Accept"] = accept
        return headers

    def _accept_media_type(self, path: str | None) -> str:
        media_types = {
            "/sp/campaigns/list": "application/vnd.spcampaign.v3+json",
            "/sp/campaigns": "application/vnd.spcampaign.v3+json",
            "/sp/adGroups/list": "application/vnd.spadgroup.v3+json",
            "/sp/adGroups": "application/vnd.spadgroup.v3+json",
            "/sp/keywords/list": "application/vnd.spkeyword.v3+json",
            "/sp/keywords": "application/vnd.spkeyword.v3+json",
            "/sp/productAds/list": "application/vnd.spproductad.v3+json",
            "/sp/productAds": "application/vnd.spproductad.v3+json",
            "/sp/targets/list": "application/vnd.sptargetingclause.v3+json",
            "/sp/targets": "application/vnd.sptargetingclause.v3+json",
            "/sp/negativeTargets/list": "application/vnd.spnegativetargetingclause.v3+json",
            "/sp/negativeTargets": "application/vnd.spnegativetargetingclause.v3+json",
            "/sp/negativeKeywords/list": "application/vnd.spnegativekeyword.v3+json",
            "/sp/negativeKeywords": "application/vnd.spnegativekeyword.v3+json",
            "/sp/campaignNegativeKeywords/list": "application/vnd.spcampaignnegativekeyword.v3+json",
            "/sp/campaignNegativeKeywords": "application/vnd.spcampaignnegativekeyword.v3+json",
            "/sp/campaignNegativeTargets/list": "application/vnd.spcampaignnegativetargetingclause.v3+json",
            "/sp/campaignNegativeTargets": "application/vnd.spcampaignnegativetargetingclause.v3+json",
            "/sb/v4/campaigns/list": "application/vnd.sbcampaignresource.v4+json",
            "/sb/v4/campaigns": "application/vnd.sbcampaignresource.v4+json",
            "/sb/v4/campaigns/delete": "application/vnd.sbcampaignresource.v4+json",
            "/sb/v4/adGroups/list": "application/vnd.sbadgroupresource.v4+json",
            "/sb/v4/adGroups": "application/vnd.sbadgroupresource.v4+json",
            "/sb/v4/adGroups/delete": "application/vnd.sbadgroupresource.v4+json",
            "/sb/targets/products/count": "application/vnd.sbtargeting.v4+json",
        }
        return media_types.get(path or "", "")

    def _content_media_type(self, path: str | None) -> str:
        return self._accept_media_type(path) or "application/json"

    def _wrap_keyword_edit_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "keywords" in payload else {"keywords": [payload]}

    def _wrap_campaign_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "campaigns" in payload else {"campaigns": [payload]}

    def _wrap_portfolio_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "portfolios" in payload else {"portfolios": [payload]}

    def _wrap_ad_group_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "adGroups" in payload else {"adGroups": [payload]}

    def _wrap_product_ad_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "productAds" in payload else {"productAds": [payload]}

    def _wrap_target_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "targetingClauses" in payload else {"targetingClauses": [payload]}

    def _wrap_negative_target_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "negativeTargetingClauses" in payload:
            return payload
        return {"negativeTargetingClauses": [payload]}

    def _wrap_negative_keyword_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        return payload if "negativeKeywords" in payload else {"negativeKeywords": [payload]}

    def _wrap_campaign_negative_keyword_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "campaignNegativeKeywords" in payload:
            return payload
        return {"campaignNegativeKeywords": [payload]}

    def _wrap_campaign_negative_target_payload(self, payload: dict[str, Any]) -> dict[str, Any]:
        if "campaignNegativeTargetingClauses" in payload:
            return payload
        return {"campaignNegativeTargetingClauses": [payload]}

    def _send_json(self, req: request.Request, label: str) -> Any:
        try:
            with self.opener.open(req, timeout=30) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except error.HTTPError as exc:
            payload = exc.read().decode("utf-8", errors="replace")
            raise RuntimeError(f"{label} failed: {exc.code} {payload}") from exc
        except error.URLError as exc:
            raise RuntimeError(f"{label} failed: {exc.reason}") from exc
