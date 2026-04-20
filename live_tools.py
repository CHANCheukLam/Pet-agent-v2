from __future__ import annotations

"""Live Gaode/Amap + QWeather tool-calling helpers.


Design goals:
- use environment variables for secrets
- time out quickly and fail gracefully
- keep output shapes aligned with the provided dynamic_tools schemas
- support fallback-friendly orchestration
"""

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Optional, Sequence, Tuple
from uuid import uuid4

import requests

from .repositories import get_experience_context, get_lodging_context, get_transport_context


try:  # Best-effort .env loading for local runs.
    from dotenv import load_dotenv  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    load_dotenv = None  # type: ignore


HttpRequester = Callable[..., Any]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _request_id() -> str:
    return f"live-{uuid4().hex[:12]}"


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        return int(float(value))
    except Exception:
        return default

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        return float(value)
    except Exception:
        return default


def _compact_text(*parts: Any) -> str:
    return " | ".join(str(part) for part in parts if part not in (None, ""))


def _failure_envelope(service: str, message: str, *, retryable: bool = True, code: str = "UPSTREAM_ERROR") -> Dict[str, Any]:
    return {
        "ok": False,
        "request_id": _request_id(),
        "data": None,
        "error": {
            "code": code,
            "message": message,
            "retryable": retryable,
        },
    }


def _safe_live_call(service: str, caller: Callable[[], Dict[str, Any]]) -> Dict[str, Any]:
    try:
        result = caller()
    except requests.Timeout:
        return _failure_envelope(service, f"{service} request timed out", retryable=True, code="TIMEOUT")
    except Exception as exc:  # pragma: no cover - defensive guard around custom clients
        return _failure_envelope(service, f"{service} request failed: {exc}", retryable=True)

    if isinstance(result, dict):
        return result
    return _failure_envelope(service, f"{service} returned a non-object response", retryable=True)


@dataclass
class LiveToolClientConfig:
    gaode_api_key: str = ""
    qweather_api_key: str = ""
    gaode_base_url: str = "https://restapi.amap.com"
    qweather_base_url: str = "https://devapi.qweather.com"
    timeout_seconds: float = 3.0


class LiveToolClient:
    """HTTP adapter for the live map/weather tool contracts."""

    def __init__(
        self,
        config: Optional[LiveToolClientConfig] = None,
        requester: Optional[HttpRequester] = None,
    ) -> None:
        self.config = config or LiveToolClientConfig()
        self.requester = requester or requests.get

    @classmethod
    def from_env(cls) -> "LiveToolClient":
        if load_dotenv is not None:
            try:
                project_root = Path(__file__).resolve().parents[2]
                load_dotenv(project_root / ".env", override=False)
            except Exception:
                pass

        timeout = 3.0
        try:
            timeout = float(
                __import__("os").getenv("LIVE_TOOL_TIMEOUT_SECONDS", "3.0")
            )
        except Exception:
            timeout = 3.0

        return cls(
            config=LiveToolClientConfig(
                gaode_api_key=__import__("os").getenv("GAODE_API_KEY", ""),
                qweather_api_key=__import__("os").getenv("QWEATHER_API_KEY", ""),
                gaode_base_url=__import__("os").getenv("GAODE_BASE_URL", "https://restapi.amap.com"),
                qweather_base_url=__import__("os").getenv("QWEATHER_BASE_URL", "https://devapi.qweather.com"),
                timeout_seconds=timeout,
            )
        )

    # ------------------------------------------------------------------
    # Low-level HTTP helpers
    # ------------------------------------------------------------------
    def _build_url(self, base_url: str, path: str) -> str:
        return f"{base_url.rstrip('/')}/{path.lstrip('/')}"

    def _request_json(
        self,
        *,
        base_url: str,
        path: str,
        params: Dict[str, Any],
        service: str,
        api_key: str,
    ) -> Tuple[Dict[str, Any], bool]:
        if not api_key:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "AUTH_FAILED",
                    "message": f"Missing API key for {service}",
                    "retryable": False,
                },
            }, False

        url = self._build_url(base_url, path)
        request_params = dict(params)
        request_params["key"] = api_key

        try:
            response = self.requester(url, params=request_params, timeout=self.config.timeout_seconds)
        except requests.Timeout:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "TIMEOUT",
                    "message": f"{service} request timed out",
                    "retryable": True,
                },
            }, False
        except Exception as exc:  # pragma: no cover - network/runtime failure
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": f"{service} request failed: {exc}",
                    "retryable": True,
                },
            }, False

        status_code = getattr(response, "status_code", 0)
        if status_code in (401, 403):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "AUTH_FAILED",
                    "message": f"{service} authorization failed",
                    "retryable": False,
                    "upstream_status": str(status_code),
                },
            }, False
        if status_code == 429:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "RATE_LIMITED",
                    "message": f"{service} rate limited",
                    "retryable": True,
                    "upstream_status": str(status_code),
                },
            }, False
        if status_code >= 400:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": f"{service} upstream returned HTTP {status_code}",
                    "retryable": True,
                    "upstream_status": str(status_code),
                },
            }, False

        try:
            payload = response.json()
        except Exception as exc:  # pragma: no cover - malformed upstream response
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": f"{service} returned non-JSON payload: {exc}",
                    "retryable": True,
                },
            }, False

        if not isinstance(payload, dict):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_ERROR",
                    "message": f"{service} returned a non-object JSON payload",
                    "retryable": True,
                },
            }, False

        return payload, True

    def _gaode_success(self, data: Dict[str, Any]) -> bool:
        return str(data.get("status", "1")) == "1"

    def _qweather_success(self, data: Dict[str, Any]) -> bool:
        return str(data.get("code", "200")) == "200"

    def _wrap_error(self, service: str, payload: Dict[str, Any], upstream_code: Optional[str] = None) -> Dict[str, Any]:
        error = payload.get("error") or {}
        return {
            "ok": False,
            "request_id": payload.get("request_id") or _request_id(),
            "data": None,
            "error": {
                "code": error.get("code", "UPSTREAM_ERROR"),
                "message": error.get("message", f"{service} request failed"),
                "retryable": bool(error.get("retryable", True)),
                "upstream_status": error.get("upstream_status"),
                "upstream_code": upstream_code or error.get("upstream_code"),
            },
        }

    # ------------------------------------------------------------------
    # Gaode / Amap tools
    # ------------------------------------------------------------------
    def geocode(self, address: str, city: Optional[str] = None) -> Dict[str, Any]:
        payload, success = self._request_json(
            base_url=self.config.gaode_base_url,
            path="/v3/geocode/geo",
            params={"address": address, **({"city": city} if city else {})},
            service="gaode.geocode",
            api_key=self.config.gaode_api_key,
        )
        if not success:
            return payload
        if not self._gaode_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("info") or "gaode geocode returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        geocodes = payload.get("geocodes") or []
        items: List[Dict[str, Any]] = []
        for item in geocodes:
            items.append(
                {
                    "formatted_address": str(item.get("formatted_address") or address),
                    "province": str(item.get("province") or ""),
                    "city": str(item.get("city") or city or ""),
                    "district": str(item.get("district") or ""),
                    "adcode": str(item.get("adcode") or ""),
                    "location": str(item.get("location") or ""),
                    "level": str(item.get("level") or ""),
                }
            )

        if not items:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": "gaode geocode returned empty results",
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "gaode",
                "items": items,
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("status", "1")),
                "upstream_code": str(payload.get("infocode") or "OK"),
                "upstream_message": str(payload.get("info") or "success"),
            },
            "error": None,
        }

    def poi_around(
        self,
        location: str,
        keywords: Optional[str] = None,
        types: Optional[str] = None,
        radius: int = 3000,
        sortrule: str = "distance",
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "location": location,
            "radius": radius,
            "sortrule": sortrule,
            "page_num": page,
            "page_size": page_size,
        }
        if keywords:
            params["keywords"] = keywords
        if types:
            params["types"] = types

        payload, success = self._request_json(
            base_url=self.config.gaode_base_url,
            path="/v5/place/around",
            params=params,
            service="gaode.poi_around",
            api_key=self.config.gaode_api_key,
        )
        if not success:
            return payload
        if not self._gaode_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("info") or "gaode poi around returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        pois = payload.get("pois") or []
        items = [_normalize_poi(item) for item in pois]
        if not items:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": "gaode poi around returned empty results",
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "gaode",
                "items": items,
                "total_count": _safe_int(payload.get("count"), len(items)),
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("status", "1")),
                "upstream_code": str(payload.get("infocode") or "OK"),
                "upstream_message": str(payload.get("info") or "success"),
            },
            "error": None,
        }

    def poi_keyword(
        self,
        keywords: str,
        city: str,
        types: Optional[str] = None,
        city_limit: bool = True,
        page: int = 1,
        page_size: int = 20,
    ) -> Dict[str, Any]:
        params: Dict[str, Any] = {
            "keywords": keywords,
            "city": city,
            "city_limit": str(city_limit).lower(),
            "page_num": page,
            "page_size": page_size,
        }
        if types:
            params["types"] = types

        payload, success = self._request_json(
            base_url=self.config.gaode_base_url,
            path="/v5/place/text",
            params=params,
            service="gaode.poi_keyword",
            api_key=self.config.gaode_api_key,
        )
        if not success:
            return payload
        if not self._gaode_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("info") or "gaode poi keyword returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        pois = payload.get("pois") or []
        items = [_normalize_poi(item) for item in pois]
        if not items:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": "gaode poi keyword returned empty results",
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "gaode",
                "items": items,
                "total_count": _safe_int(payload.get("count"), len(items)),
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("status", "1")),
                "upstream_code": str(payload.get("infocode") or "OK"),
                "upstream_message": str(payload.get("info") or "success"),
            },
            "error": None,
        }

    def route_matrix(
        self,
        origins: Sequence[str],
        destinations: Sequence[str],
        travel_mode: str,
        city: Optional[str] = None,
        cityd: Optional[str] = None,
        depart_at: Optional[str] = None,
        need_live_traffic: bool = True,
        alternatives: int = 1,
        pet_constraints: Optional[Dict[str, Any]] = None,
        route_preference: str = "fastest",
    ) -> Dict[str, Any]:
        if not origins or not destinations:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": "origins and destinations are required",
                    "retryable": False,
                },
            }

        pairs: List[Dict[str, Any]] = []
        for origin in origins:
            for destination in destinations:
                pair_payload = self._route_pair(
                    origin=origin,
                    destination=destination,
                    travel_mode=travel_mode,
                    city=city,
                    cityd=cityd,
                    depart_at=depart_at,
                    need_live_traffic=need_live_traffic,
                    alternatives=alternatives,
                    route_preference=route_preference,
                    pet_constraints=pet_constraints or {},
                )
                if pair_payload.get("ok") and pair_payload.get("data"):
                    pairs.extend(pair_payload["data"].get("pairs", []))

        if not pairs:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": f"route matrix returned no results for {travel_mode}",
                    "retryable": True,
                },
            }

        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "gaode",
                "travel_mode": travel_mode,
                "pairs": pairs,
                "updated_at": _utc_now(),
                "upstream_status": "200",
                "upstream_code": "OK",
                "upstream_message": "success",
            },
            "error": None,
        }

    def _route_pair(
        self,
        *,
        origin: str,
        destination: str,
        travel_mode: str,
        city: Optional[str],
        cityd: Optional[str],
        depart_at: Optional[str],
        need_live_traffic: bool,
        alternatives: int,
        route_preference: str,
        pet_constraints: Dict[str, Any],
    ) -> Dict[str, Any]:
        if travel_mode == "driving":
            path = "/v3/direction/driving"
            params: Dict[str, Any] = {
                "origin": origin,
                "destination": destination,
                "extensions": "base",
                "strategy": _strategy_from_preference(route_preference),
                "show_fields": "cost,traffic",
            }
            if depart_at:
                params["depart_at"] = depart_at
        elif travel_mode == "walking":
            path = "/v3/direction/walking"
            params = {"origin": origin, "destination": destination, "extensions": "base"}
        elif travel_mode == "bicycling":
            path = "/v4/direction/bicycling"
            params = {"origin": origin, "destination": destination, "extensions": "base"}
        elif travel_mode == "transit":
            path = "/v3/direction/transit/integrated"
            params = {
                "origin": origin,
                "destination": destination,
                "city": city or cityd or "",
                "cityd": cityd or city or "",
                "strategy": 0,
                "extensions": "base",
            }
        else:
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "VALIDATION_ERROR",
                    "message": f"unsupported travel_mode: {travel_mode}",
                    "retryable": False,
                },
            }

        payload, success = self._request_json(
            base_url=self.config.gaode_base_url,
            path=path,
            params=params,
            service=f"gaode.route_{travel_mode}",
            api_key=self.config.gaode_api_key,
        )
        if not success:
            return payload

        if not self._gaode_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("info") or f"gaode route {travel_mode} returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("status", "0")),
                    "upstream_code": str(payload.get("infocode") or ""),
                },
            }

        pair = _normalize_route_pair(
            origin=origin,
            destination=destination,
            travel_mode=travel_mode,
            raw=payload,
            need_live_traffic=need_live_traffic,
            alternatives=alternatives,
            pet_constraints=pet_constraints,
        )
        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "gaode",
                "travel_mode": travel_mode,
                "pairs": [pair],
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("status", "1")),
                "upstream_code": str(payload.get("infocode") or "OK"),
                "upstream_message": str(payload.get("info") or "success"),
            },
            "error": None,
        }

    # ------------------------------------------------------------------
    # QWeather tools
    # ------------------------------------------------------------------
    def qweather_now(self, location: str, lang: str = "zh", unit: str = "m") -> Dict[str, Any]:
        payload, success = self._request_json(
            base_url=self.config.qweather_base_url,
            path="/v7/weather/now",
            params={"location": location, "lang": lang, "unit": unit},
            service="qweather.now",
            api_key=self.config.qweather_api_key,
        )
        if not success:
            return payload
        if not self._qweather_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("fxLink") or payload.get("message") or "qweather now returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("code", "0")),
                    "upstream_code": str(payload.get("code") or ""),
                },
            }

        now = (payload.get("now") or {})
        obs_time = str(payload.get("fxLink") or now.get("obsTime") or _utc_now())
        if "Z" not in obs_time and "+" not in obs_time:
            obs_time = _utc_now()

        temp_c = _safe_float(now.get("temp"))
        precip_mm = _safe_float(now.get("precip"))
        pet_comfort = _pet_comfort_from_now(temp_c=temp_c, precip_mm=precip_mm, text=str(now.get("text") or ""))

        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "qweather",
                "now": {
                    "obs_time": str(now.get("obsTime") or obs_time),
                    "temp_c": temp_c,
                    "feels_like_c": _safe_float(now.get("feelsLike"), temp_c),
                    "text": str(now.get("text") or ""),
                    "humidity_pct": _safe_int(now.get("humidity"), 0),
                    "wind_dir": str(now.get("windDir") or ""),
                    "wind_scale": str(now.get("windScale") or ""),
                    "precip_mm": precip_mm,
                },
                "pet_comfort": pet_comfort,
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("code", "200")),
                "upstream_code": str(payload.get("code") or "200"),
                "upstream_message": str(payload.get("updateTime") or payload.get("fxLink") or "success"),
            },
            "error": None,
        }

    def qweather_forecast(self, location: str, days: int = 3, lang: str = "zh", unit: str = "m") -> Dict[str, Any]:
        days = 7 if days not in (3, 7) else days
        payload, success = self._request_json(
            base_url=self.config.qweather_base_url,
            path=f"/v7/weather/{days}d",
            params={"location": location, "lang": lang, "unit": unit},
            service="qweather.forecast",
            api_key=self.config.qweather_api_key,
        )
        if not success:
            return payload
        if not self._qweather_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("message") or "qweather forecast returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("code", "0")),
                    "upstream_code": str(payload.get("code") or ""),
                },
            }

        daily = payload.get("daily") or []
        items = [_normalize_weather_day(item) for item in daily]
        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "qweather",
                "days": items,
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("code", "200")),
                "upstream_code": str(payload.get("code") or "200"),
                "upstream_message": str(payload.get("updateTime") or "success"),
            },
            "error": None,
        }

    def qweather_minutely(self, location: str, lang: str = "zh") -> Dict[str, Any]:
        payload, success = self._request_json(
            base_url=self.config.qweather_base_url,
            path="/v7/minutely/5m",
            params={"location": location, "lang": lang},
            service="qweather.minutely",
            api_key=self.config.qweather_api_key,
        )
        if not success:
            return payload
        if not self._qweather_success(payload):
            return {
                "ok": False,
                "request_id": _request_id(),
                "data": None,
                "error": {
                    "code": "UPSTREAM_EMPTY",
                    "message": str(payload.get("message") or "qweather minutely returned no results"),
                    "retryable": True,
                    "upstream_status": str(payload.get("code", "0")),
                    "upstream_code": str(payload.get("code") or ""),
                },
            }

        summary = str(payload.get("summary") or payload.get("fxLink") or "")
        precipitation = payload.get("precipitation") or payload.get("minuteData") or []
        minutes = []
        for item in precipitation:
            minutes.append(
                {
                    "fx_time": str(item.get("fxTime") or item.get("fx_time") or _utc_now()),
                    "precip_mm": _safe_float(item.get("precip"), 0.0),
                }
            )
        return {
            "ok": True,
            "request_id": _request_id(),
            "data": {
                "source": "qweather",
                "will_rain_2h": any(m.get("precip_mm", 0) > 0 for m in minutes),
                "summary": summary,
                "minutes": minutes,
                "updated_at": _utc_now(),
                "upstream_status": str(payload.get("code", "200")),
                "upstream_code": str(payload.get("code") or "200"),
                "upstream_message": str(payload.get("updateTime") or "success"),
            },
            "error": None,
        }


def _static_transport_bundle(
    departure: str,
    destination: str,
    travel_preference: Optional[str],
    failure_reason: str,
) -> Dict[str, Any]:
    transport_context, data_source = get_transport_context(departure, destination)
    return {
        "source": "cosmos",
        "status": "fallback",
        "fallback_reason": failure_reason,
        "departure_geocode": _failure_envelope("gaode.geocode", "live geocode unavailable", retryable=True, code="LIVE_FALLBACK"),
        "destination_geocode": _failure_envelope("gaode.geocode", "live geocode unavailable", retryable=True, code="LIVE_FALLBACK"),
        "route_matrix": {},
        "weather_now": _failure_envelope("qweather.now", "live weather unavailable", retryable=True, code="LIVE_FALLBACK"),
        "weather_forecast": _failure_envelope("qweather.forecast", "live forecast unavailable", retryable=True, code="LIVE_FALLBACK"),
        "weather_minutely": _failure_envelope("qweather.minutely", "live minutely unavailable", retryable=True, code="LIVE_FALLBACK"),
        "traffic_live": {
            "source": "cosmos",
            "congestion_level": "unknown",
            "affected": False,
            "recommend_replan": False,
            "replan_reason": failure_reason,
            "avg_speed_kmh": 0.0,
            "affected_roads": [],
        },
        "route_data": transport_context,
        "route_data_source": data_source,
        "travel_preference": travel_preference,
        "updated_at": _utc_now(),
        "notes": [
            "Live transport API calls timed out or failed; using Cosmos-backed transport context.",
            "Weather fields remain unavailable because only route and rule data are stored in Cosmos.",
        ],
    }


def _hotel_candidates_from_lodging_context(lodging_context: Dict[str, Any]) -> List[Dict[str, Any]]:
    hotel_candidates: List[Dict[str, Any]] = []
    for record in (lodging_context.get("hotel_records") or [])[:10]:
        name = str(record.get("name") or "")
        if not name:
            continue
        hotel_candidates.append(
            {
                "poi_id": str(record.get("id") or uuid4().hex),
                "name": name,
                "type": "lodging",
                "address": str(lodging_context.get("city") or ""),
                "location": "",
                "distance_m": 0,
                "indoor_outdoor": "indoor",
                "open_now": None,
                "is_24h": None,
                "tel": "",
                "business_hours": "",
                "ticket_price_cny": 0.0,
                "user_rating": 0.0,
                "hospital_type": "unknown",
                "hotel_grade": _infer_hotel_grade("lodging", name),
                "pet_policy": str(record.get("pet_policy") or "unknown"),
                "pet_friendly_hint": str(record.get("pet_policy") or ""),
            }
        )
    return hotel_candidates


def _static_experience_bundle(
    destination: str,
    pet_type: str,
    failure_reason: str,
) -> Dict[str, Any]:
    exp_context, exp_source = get_experience_context(destination, pet_type)
    lodging_context, lodging_source = get_lodging_context(destination, pet_type)
    recommended_hotels = lodging_context.get("recommended_hotels") or exp_context.get("recommended_hotels") or []

    return {
        "source": "cosmos",
        "status": "fallback",
        "fallback_reason": failure_reason,
        "destination_geocode": _failure_envelope("gaode.geocode", "live geocode unavailable", retryable=True, code="LIVE_FALLBACK"),
        "hotel_candidates": _hotel_candidates_from_lodging_context(lodging_context),
        "hospital_candidates": [],
        "attraction_candidates": [],
        "food_candidates": [],
        "weather_now": _failure_envelope("qweather.now", "live weather unavailable", retryable=True, code="LIVE_FALLBACK"),
        "weather_forecast": _failure_envelope("qweather.forecast", "live forecast unavailable", retryable=True, code="LIVE_FALLBACK"),
        "weather_minutely": _failure_envelope("qweather.minutely", "live minutely unavailable", retryable=True, code="LIVE_FALLBACK"),
        "recommended_hotels": recommended_hotels[:5],
        "experience_data": exp_context,
        "experience_data_source": exp_source,
        "lodging_data": lodging_context,
        "lodging_data_source": lodging_source,
        "updated_at": _utc_now(),
        "notes": [
            "Live experience API calls timed out or failed; using Cosmos-backed experience and lodging context.",
            "Hotel recommendations are sourced from Cosmos-backed lodging documents.",
        ],
    }


# ----------------------------------------------------------------------
# High-level bundle builders used by member_7 agents and planner inputs.
# ----------------------------------------------------------------------

def build_transport_live_context(
    departure: str,
    destination: str,
    travel_preference: Optional[str] = None,
    client: Optional[LiveToolClient] = None,
) -> Dict[str, Any]:
    if client is None:
        client = LiveToolClient.from_env()
    assert client is not None
    departure_geo = _safe_live_call("gaode.geocode", lambda: client.geocode(departure))
    destination_geo = _safe_live_call("gaode.geocode", lambda: client.geocode(destination))

    if not departure_geo.get("ok") or not destination_geo.get("ok"):
        failure_reason = _compact_text(
            departure_geo.get("error", {}).get("message") if isinstance(departure_geo.get("error"), dict) else departure_geo,
            destination_geo.get("error", {}).get("message") if isinstance(destination_geo.get("error"), dict) else destination_geo,
        ) or "live geocode unavailable"
        return _static_transport_bundle(departure, destination, travel_preference, failure_reason)

    departure_loc = _first_location(departure_geo)
    destination_loc = _first_location(destination_geo)
    transport_modes = _transport_modes_from_preference(travel_preference)
    assert departure_loc is not None and destination_loc is not None
    departure_loc_str = str(departure_loc)
    destination_loc_str = str(destination_loc)

    route_matrix: Dict[str, Any] = {}
    route_failure: Optional[Dict[str, Any]] = None
    for mode in transport_modes:
        if departure_loc_str and destination_loc_str:
            route_matrix[mode] = _safe_live_call(
                f"gaode.route_{mode}",
                lambda mode=mode: client.route_matrix(
                    origins=[departure_loc_str],
                    destinations=[destination_loc_str],
                    travel_mode=mode,
                    city=destination,
                    cityd=destination,
                    need_live_traffic=True,
                    alternatives=1,
                    route_preference="pet_friendly",
                ),
            )
            if route_failure is None and not route_matrix[mode].get("ok"):
                route_failure = route_matrix[mode]
        else:
            route_matrix[mode] = _failure_envelope(
                f"gaode.route_{mode}",
                "missing geocode coordinates for live route lookup",
                retryable=True,
                code="UPSTREAM_EMPTY",
            )
            if route_failure is None:
                route_failure = route_matrix[mode]

    weather_now = _safe_live_call("qweather.now", lambda: client.qweather_now(destination_loc or destination))
    weather_forecast = _safe_live_call("qweather.forecast", lambda: client.qweather_forecast(destination_loc or destination, days=3))
    weather_minutely = _safe_live_call("qweather.minutely", lambda: client.qweather_minutely(destination_loc or destination))

    if any(not envelope.get("ok") for envelope in [departure_geo, destination_geo, *route_matrix.values(), weather_now, weather_forecast, weather_minutely]):
        failure_envelope = route_failure or weather_now or weather_forecast or weather_minutely or departure_geo or destination_geo
        failure_reason = str((failure_envelope.get("error") or {}).get("message") if isinstance(failure_envelope, dict) else "live API unavailable")
        return _static_transport_bundle(departure, destination, travel_preference, failure_reason or "live API unavailable")

    traffic_live = _derive_traffic_snapshot(route_matrix.get("driving"), weather_now)
    status = _bundle_status([departure_geo, destination_geo, *route_matrix.values(), weather_now, weather_forecast])

    return {
        "source": "live",
        "status": status,
        "departure_geocode": departure_geo,
        "destination_geocode": destination_geo,
        "route_matrix": route_matrix,
        "weather_now": weather_now,
        "weather_forecast": weather_forecast,
        "weather_minutely": weather_minutely,
        "traffic_live": traffic_live,
        "notes": [
            "Live transport context built from Gaode geocode + route matrix and QWeather.",
            "All API calls are wrapped with timeout and graceful degradation.",
        ],
    }


def build_experience_live_context(
    destination: str,
    pet_type: str,
    client: Optional[LiveToolClient] = None,
) -> Dict[str, Any]:
    if client is None:
        client = LiveToolClient.from_env()
    assert client is not None
    destination_geo = _safe_live_call("gaode.geocode", lambda: client.geocode(destination))

    if not destination_geo.get("ok"):
        failure_reason = str((destination_geo.get("error") or {}).get("message") or "live geocode unavailable")
        return _static_experience_bundle(destination, pet_type, failure_reason)

    destination_loc = _first_location(destination_geo)
    assert destination_loc is not None
    destination_loc_str = str(destination_loc)

    hotel_search = _poi_search_bundle(client, destination, destination_loc_str, "宠物友好酒店")
    hospital_search = _poi_search_bundle(client, destination, destination_loc_str, "宠物医院")
    attraction_search = _poi_search_bundle(client, destination, destination_loc_str, "景点")
    food_search = _poi_search_bundle(client, destination, destination_loc_str, "餐厅")

    weather_now = _safe_live_call("qweather.now", lambda: client.qweather_now(destination_loc or destination))
    weather_forecast = _safe_live_call("qweather.forecast", lambda: client.qweather_forecast(destination_loc or destination, days=3))
    weather_minutely = _safe_live_call("qweather.minutely", lambda: client.qweather_minutely(destination_loc or destination))

    if any(not envelope.get("ok") for envelope in [hotel_search, hospital_search, attraction_search, food_search, weather_now, weather_forecast, weather_minutely]):
        failure_envelope = next(
            (envelope for envelope in [hotel_search, hospital_search, attraction_search, food_search, weather_now, weather_forecast, weather_minutely] if isinstance(envelope, dict) and not envelope.get("ok")),
            None,
        )
        failure_reason = str((failure_envelope.get("error") or {}).get("message") if failure_envelope else "live experience lookup unavailable")
        return _static_experience_bundle(destination, pet_type, failure_reason or "live experience lookup unavailable")

    recommended_hotels = _top_names(hotel_search)
    status = _bundle_status([
        destination_geo,
        hotel_search,
        hospital_search,
        attraction_search,
        food_search,
        weather_now,
        weather_forecast,
    ])

    return {
        "source": "live",
        "status": status,
        "destination_geocode": destination_geo,
        "hotel_candidates": hotel_search,
        "hospital_candidates": hospital_search,
        "attraction_candidates": attraction_search,
        "food_candidates": food_search,
        "weather_now": weather_now,
        "weather_forecast": weather_forecast,
        "weather_minutely": weather_minutely,
        "recommended_hotels": recommended_hotels,
        "notes": [
            "Live experience context built from Gaode POI search and QWeather.",
            f"Pet type hint: {pet_type}",
        ],
    }


def collect_live_context(
    departure: str,
    destination: str,
    pet_type: str,
    travel_preference: Optional[str] = None,
    client: Optional[LiveToolClient] = None,
) -> Dict[str, Any]:
    if client is None:
        client = LiveToolClient.from_env()
    transport = build_transport_live_context(
        departure=departure,
        destination=destination,
        travel_preference=travel_preference,
        client=client,
    )
    experience = build_experience_live_context(
        destination=destination,
        pet_type=pet_type,
        client=client,
    )

    overall_status = _bundle_status([transport, experience])
    transport_source = str(transport.get("source") or "")
    experience_source = str(experience.get("source") or "")
    overall_source = "live"
    if transport_source == "cosmos" and experience_source == "cosmos":
        overall_source = "cosmos"
    elif overall_status == "partial":
        overall_source = "mixed"
    elif overall_status == "fallback":
        overall_source = "cosmos"

    return {
        "status": overall_status,
        "transport": transport,
        "experience": experience,
        "source": overall_source,
        "notes": [
            "Combined live map/weather context for member_7 orchestration.",
            "If any upstream call fails, the downstream agents can still fall back to Cosmos-backed context.",
        ],
    }


# ----------------------------------------------------------------------
# Normalization helpers
# ----------------------------------------------------------------------

def _normalize_poi(raw: Dict[str, Any]) -> Dict[str, Any]:
    type_name = str(raw.get("type") or raw.get("typecode") or raw.get("type_name") or "unknown")
    name = str(raw.get("name") or raw.get("title") or "")
    location = str(raw.get("location") or raw.get("lnglat") or raw.get("point") or "")
    if not location and raw.get("longitude") and raw.get("latitude"):
        location = f"{raw.get('longitude')},{raw.get('latitude')}"

    return {
        "poi_id": str(raw.get("id") or raw.get("poi_id") or raw.get("uid") or uuid4().hex),
        "name": name,
        "type": type_name,
        "address": str(raw.get("address") or ""),
        "location": location,
        "distance_m": _safe_int(raw.get("distance"), 0),
        "indoor_outdoor": _infer_indoor_outdoor(type_name, name),
        "open_now": _infer_bool(raw.get("business") or raw.get("open")),
        "is_24h": _infer_bool(raw.get("is24h") or raw.get("is_24_hour") or raw.get("24h")),
        "tel": str(raw.get("tel") or raw.get("telephone") or ""),
        "business_hours": str(raw.get("business_hours") or raw.get("biz_ext", {}).get("open_time") if isinstance(raw.get("biz_ext"), dict) else ""),
        "ticket_price_cny": _safe_float(raw.get("price"), 0.0),
        "user_rating": _safe_float(raw.get("rating"), 0.0),
        "hospital_type": _infer_hospital_type(type_name, name),
        "hotel_grade": _infer_hotel_grade(type_name, name),
        "pet_policy": _infer_pet_policy(raw),
        "pet_friendly_hint": str(raw.get("snippet") or raw.get("business_area") or ""),
    }


def _normalize_route_pair(
    *,
    origin: str,
    destination: str,
    travel_mode: str,
    raw: Dict[str, Any],
    need_live_traffic: bool,
    alternatives: int,
    pet_constraints: Dict[str, Any],
) -> Dict[str, Any]:
    distance_m = 0
    duration_s = 0
    cost_cny = 0.0
    tolls_cny = 0.0
    transfers = 0
    walking_distance_m = 0

    if travel_mode == "driving":
        paths = (((raw.get("route") or {}).get("paths")) or [])
        first = paths[0] if paths else {}
        distance_m = _safe_int(first.get("distance"), 0)
        duration_s = _safe_int(first.get("duration"), 0)
        cost_cny = _safe_float(((first.get("cost") or {}).get("tolls")), 0.0) if isinstance(first.get("cost"), dict) else 0.0
        tolls_cny = cost_cny
    elif travel_mode == "walking":
        paths = (((raw.get("route") or {}).get("paths")) or [])
        first = paths[0] if paths else {}
        distance_m = _safe_int(first.get("distance"), 0)
        duration_s = _safe_int(first.get("duration"), 0)
        walking_distance_m = distance_m
    elif travel_mode == "bicycling":
        data = raw.get("data") or raw
        paths = (((data.get("route") or data).get("paths")) or []) if isinstance(data, dict) else []
        first = paths[0] if paths else {}
        distance_m = _safe_int(first.get("distance"), 0)
        duration_s = _safe_int(first.get("duration"), 0)
    elif travel_mode == "transit":
        transits = (((raw.get("route") or {}).get("transits")) or [])
        first = transits[0] if transits else {}
        distance_m = _safe_int(first.get("distance"), 0)
        duration_s = _safe_int(first.get("duration"), 0)
        transfers = _safe_int(first.get("transfers"), 0)
        walking_distance_m = _safe_int(first.get("walking_distance"), 0)
    else:
        distance_m = _safe_int(raw.get("distance"), 0)
        duration_s = _safe_int(raw.get("duration"), 0)

    traffic_status = _traffic_status_from_speed(distance_m, duration_s)
    if need_live_traffic and travel_mode == "driving":
        traffic_status = traffic_status if traffic_status != "unknown" else "smooth"

    return {
        "origin": origin,
        "destination": destination,
        "distance_m": distance_m,
        "duration_s": duration_s,
        "walking_distance_m": walking_distance_m,
        "transfers": transfers,
        "cost_cny": cost_cny,
        "tolls_cny": tolls_cny,
        "traffic_status": traffic_status,
    }


def _strategy_from_preference(route_preference: str) -> int:
    preference = (route_preference or "").lower()
    if preference == "least_transfer":
        return 1
    if preference == "least_walk":
        return 2
    if preference == "avoid_toll":
        return 3
    if preference == "pet_friendly":
        return 4
    return 0


def _transport_modes_from_preference(preference: Optional[str]) -> List[str]:
    text = (preference or "").lower()
    if "walk" in text:
        return ["walking", "driving"]
    if "bike" in text:
        return ["bicycling", "driving"]
    if any(token in text for token in ["transit", "metro", "subway", "bus", "train"]):
        return ["transit", "driving"]
    return ["driving", "transit"]


def _first_location(geocode_payload: Dict[str, Any]) -> Optional[str]:
    data = geocode_payload.get("data") or {}
    items = data.get("items") or []
    if not items:
        return None
    return str(items[0].get("location") or "") or None


def _infer_indoor_outdoor(type_name: str, name: str) -> str:
    text = f"{type_name} {name}".lower()
    if any(token in text for token in ["hotel", "hospital", "mall", "museum", "restaurant", "cafe"]):
        return "indoor"
    if any(token in text for token in ["park", "garden", "square", "view", "beach"]):
        return "outdoor"
    return "unknown"


def _infer_bool(value: Any) -> Optional[bool]:
    if value is None or value == "":
        return None
    if isinstance(value, bool):
        return value
    text = str(value).strip().lower()
    if text in {"1", "true", "yes", "open", "allowed", "y"}:
        return True
    if text in {"0", "false", "no", "closed", "not_allowed", "n"}:
        return False
    return None


def _infer_hospital_type(type_name: str, name: str) -> str:
    text = f"{type_name} {name}".lower()
    if "pet" in text or "animal" in text:
        return "pet_hospital"
    if "pharmacy" in text:
        return "pharmacy"
    if any(token in text for token in ["emergency", "accident"]):
        return "emergency"
    if any(token in text for token in ["clinic", "hospital", "medical"]):
        return "general"
    return "unknown"


def _infer_hotel_grade(type_name: str, name: str) -> str:
    text = f"{type_name} {name}".lower()
    if any(token in text for token in ["luxury", "ritz", "st regis", "intercontinental"]):
        return "luxury"
    if any(token in text for token in ["high-end", "hilton", "hyatt", "marriott"]):
        return "high_end"
    if any(token in text for token in ["comfort", "holiday inn", "novotel"]):
        return "comfort"
    if any(token in text for token in ["inn", "express", "economy", "ibis", "homeinn"]):
        return "economy"
    return "unknown"


def _infer_pet_policy(raw: Dict[str, Any]) -> str:
    text = _compact_text(
        raw.get("pet_policy"),
        raw.get("biz_ext"),
        raw.get("snippet"),
        raw.get("name"),
    ).lower()
    if any(token in text for token in ["allowed", "pet friendly", "宠物", "可携带"]):
        return "allowed"
    if any(token in text for token in ["not allowed", "禁止", "no pets"]):
        return "not_allowed"
    if any(token in text for token in ["restricted", "limited", "需咨询"]):
        return "restricted"
    return "unknown"


def _normalize_weather_day(raw: Dict[str, Any]) -> Dict[str, Any]:
    temp_min = _safe_float(raw.get("tempMin"), 0.0)
    temp_max = _safe_float(raw.get("tempMax"), temp_min)
    precip = _safe_float(raw.get("precip"), 0.0)
    precip_prob = _safe_float(raw.get("precipProbability"), 0.0)
    risk_tag = _risk_tag(temp_min=temp_min, temp_max=temp_max, precip_mm=precip, precip_prob=precip_prob, text=str(raw.get("textDay") or ""))
    return {
        "date": str(raw.get("fxDate") or ""),
        "text_day": str(raw.get("textDay") or ""),
        "text_night": str(raw.get("textNight") or ""),
        "temp_min_c": temp_min,
        "temp_max_c": temp_max,
        "precip_mm": precip,
        "precip_prob": precip_prob,
        "wind_scale_day": str(raw.get("windScaleDay") or ""),
        "risk_tag": risk_tag,
    }


def _pet_comfort_from_now(temp_c: float, precip_mm: float, text: str) -> Dict[str, str]:
    if temp_c <= -12 or temp_c >= 30 or precip_mm > 0 or any(token in text.lower() for token in ["rain", "storm", "snow", "heat"]):
        if temp_c <= -12 or temp_c >= 35:
            level = "risky"
            reason = f"temperature {temp_c:.1f}°C may be unsafe for pets"
        else:
            level = "caution"
            reason = "weather conditions suggest extra pet care and shorter outdoor windows"
        return {"level": level, "reason": reason}
    return {"level": "comfortable", "reason": "current weather is within a comfortable range for most pet outings"}


def _risk_tag(temp_min: float, temp_max: float, precip_mm: float, precip_prob: float, text: str) -> str:
    text = text.lower()
    if precip_mm > 0 or precip_prob >= 0.5 or any(token in text for token in ["rain", "storm", "shower"]):
        return "rain"
    if temp_max >= 30 or any(token in text for token in ["hot", "heat"]):
        return "heat"
    if temp_min <= -5 or any(token in text for token in ["cold", "snow", "ice"]):
        return "cold"
    return "normal"


def _traffic_status_from_speed(distance_m: int, duration_s: int) -> str:
    if distance_m <= 0 or duration_s <= 0:
        return "unknown"
    speed_kmh = (distance_m / 1000.0) / (duration_s / 3600.0)
    if speed_kmh >= 40:
        return "smooth"
    if speed_kmh >= 25:
        return "low"
    if speed_kmh >= 15:
        return "medium"
    if speed_kmh >= 8:
        return "high"
    return "severe"


def _derive_traffic_snapshot(route_matrix_envelope: Optional[Dict[str, Any]], weather_now_envelope: Dict[str, Any]) -> Dict[str, Any]:
    if not route_matrix_envelope or not route_matrix_envelope.get("ok"):
        return {
            "source": "derived",
            "congestion_level": "unknown",
            "affected": False,
            "recommend_replan": False,
            "replan_reason": "route matrix not available",
            "avg_speed_kmh": 0.0,
            "affected_roads": [],
        }

    data = route_matrix_envelope.get("data") or {}
    pairs = data.get("pairs") or []
    first = pairs[0] if pairs else {}
    distance_m = _safe_int(first.get("distance_m"), 0)
    duration_s = _safe_int(first.get("duration_s"), 0)
    speed_kmh = 0.0
    if distance_m > 0 and duration_s > 0:
        speed_kmh = (distance_m / 1000.0) / (duration_s / 3600.0)
    congestion = _traffic_status_from_speed(distance_m, duration_s)
    pet_comfort = (((weather_now_envelope.get("data") or {}).get("pet_comfort")) or {})
    recommend_replan = congestion in {"high", "severe"} or pet_comfort.get("level") == "risky"
    reason = "traffic conditions and pet comfort remain acceptable"
    if pet_comfort.get("level") == "risky":
        reason = str(pet_comfort.get("reason") or reason)
    elif congestion in {"high", "severe"}:
        reason = f"live route speed is low ({speed_kmh:.1f} km/h)"

    return {
        "source": "derived",
        "congestion_level": congestion if congestion != "unknown" else "medium",
        "affected": congestion in {"high", "severe"},
        "recommend_replan": recommend_replan,
        "replan_reason": reason,
        "avg_speed_kmh": round(speed_kmh, 1),
        "affected_roads": [
            {
                "name": f"{first.get('origin')} -> {first.get('destination')}",
                "congestion_level": congestion if congestion != "unknown" else "medium",
                "speed_kmh": round(speed_kmh, 1),
                "delay_s": max(0, duration_s - int((distance_m / 1000.0) / 40.0 * 3600)) if distance_m > 0 and duration_s > 0 else 0,
            }
        ],
    }


def _bundle_status(envelopes: Iterable[Dict[str, Any]]) -> str:
    has_live = False
    has_partial = False
    has_fallback = False
    for envelope in envelopes:
        if not isinstance(envelope, dict):
            continue
        if envelope.get("status") == "fallback" or envelope.get("source") == "cosmos":
            has_fallback = True
        elif envelope.get("ok"):
            has_live = True
        else:
            has_partial = True
    if has_live and has_partial:
        return "partial"
    if has_live and has_fallback:
        return "partial"
    if has_live:
        return "live"
    if has_fallback:
        return "fallback"
    return "unavailable"


def _poi_search_bundle(
    client: LiveToolClient,
    city: str,
    location: Optional[str],
    keywords: str,
) -> Dict[str, Any]:
    around = None
    if location:
        search_location = str(location)
        around = _safe_live_call(
            f"gaode.poi_around[{keywords}]",
            lambda: client.poi_around(location=search_location, keywords=keywords, radius=5000, page=1, page_size=10),
        )
    if around and around.get("ok"):
        return around

    keyword = _safe_live_call(
        f"gaode.poi_keyword[{keywords}]",
        lambda: client.poi_keyword(keywords=keywords, city=city, city_limit=True, page=1, page_size=10),
    )
    return keyword


def _top_names(poi_envelope: Dict[str, Any]) -> List[str]:
    if not poi_envelope.get("ok"):
        return []
    data = poi_envelope.get("data") or {}
    items = data.get("items") or []
    names = []
    for item in items[:5]:
        name = str(item.get("name") or "").strip()
        if name and name not in names:
            names.append(name)
    return names


