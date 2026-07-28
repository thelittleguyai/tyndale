"""OneUpWrapper* — CoverageSource / ClaimsSource / AccumulatorSource adapters
that read 1upHealth data over HTTP from the standalone wrapper Container App.

The wrapper (api-wrapper/, deployed as tyndale-dev-wrapper) is a TypeScript
service that normalizes 1upHealth FHIR into vendor-neutral envelopes and exposes
them behind a thin HTTP API. This module is the Python counterpart: it registers
behind the SAME four DL-68 Protocols as the upload adapters, so agents/tools call
it with zero change. The whole seam is gated OFF (enable_coverage_connection) and
only registered when the flag is on and the URL/token are set — see
app.sources.__init__.

Transport + provenance are faithful here. What is DELIBERATELY not resolved yet
is the domain PAYLOAD SHAPE (see the TODO on _wrap_data): the runtime's
SourceResult.data is contractually "the exact tool dict shape" (e.g.
upload_extract_coverage's {coverage{...}, coverage_terms_confidence, raw_ocr}),
whereas the wrapper emits its own normalized envelopes (value/provenance/
freshness/confidence). Reconciling those two — deciding how BenefitsContext
consumes a vendor reading under DL-72 — is a real design step that must happen
before the gate flips on. Until then we carry the wrapper's envelopes through
verbatim under a namespaced key so nothing is silently mis-shaped.

Wrapper HTTP contract (see api-wrapper/src/server.ts):
  GET /v1/coverages?app_user_id=..            -> SourceResult<CoveragePlan>[]
  GET /v1/claims?app_user_id=..[&since=ISO]   -> SourceResult<ClaimRecord>[]
  GET /v1/accumulators?app_user_id=..         -> SourceResult<AccumulatorSnapshot>[] (len 1)
Auth: Authorization: Bearer <wrapper_auth_token>. Errors: 401 (bad token),
503 (gated off / unconfigured), 424 (no connected payer), 502 (upstream 1up).
"""

from __future__ import annotations

from datetime import date, datetime, timezone
from typing import TYPE_CHECKING, Any

import httpx
import structlog

from app.config import get_settings
from app.schemas.provenance import Provenance
from app.sources.base import AccumulatorResult, ClaimsResult, CoverageResult

log = structlog.get_logger(__name__)

# Wrapper confidence.level -> a numeric Provenance.confidence. The wrapper's
# levels are coarse (high/medium/low); these midpoints preserve ordering without
# implying false precision.
_CONFIDENCE_BY_LEVEL: dict[str, float] = {"high": 0.9, "medium": 0.6, "low": 0.3}
_DEFAULT_CONFIDENCE = 0.5


class WrapperError(RuntimeError):
    """A wrapper call failed (transport, non-2xx, or a documented 4xx/5xx). The
    status (when HTTP) is carried so callers can distinguish 424 no-payer from a
    502 upstream fault."""

    def __init__(self, message: str, *, status: int | None = None) -> None:
        super().__init__(message)
        self.status = status


def _resolve_app_user_id(case_file_id: str, args: dict[str, Any] | None) -> str:
    """Map the runtime handle to the wrapper's app_user_id.

    TODO(coverage-connection): the runtime's canonical handle is case_file_id; the
    wrapper keys on the 1upHealth app_user_id. The real mapping (case_file ->
    connected 1up user) doesn't exist yet. For now we accept an explicit
    args["app_user_id"] and otherwise pass case_file_id through unchanged. This is
    safe while gated off; it MUST be replaced with a real lookup before enabling.
    """
    if args and args.get("app_user_id"):
        return str(args["app_user_id"])
    return case_file_id


def _confidence_from_envelope(env: dict[str, Any]) -> float:
    level = ((env.get("confidence") or {}).get("level") or "").lower()
    return _CONFIDENCE_BY_LEVEL.get(level, _DEFAULT_CONFIDENCE)


def _as_of_from_envelope(env: dict[str, Any]) -> datetime | None:
    """Parse freshness.asOf (ISO 8601) into an aware datetime, or None."""
    raw = (env.get("freshness") or {}).get("asOf")
    if not raw:
        return None
    try:
        # Wrapper emits Date.toISOString() -> trailing 'Z'; fromisoformat wants +00:00.
        return datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except ValueError:
        log.warning("wrapper.bad_as_of", value=raw)
        return None


def _best_confidence(envelopes: list[dict[str, Any]]) -> float:
    if not envelopes:
        return _DEFAULT_CONFIDENCE
    return max(_confidence_from_envelope(e) for e in envelopes)


def _reasons(envelopes: list[dict[str, Any]]) -> list[str]:
    out: list[str] = []
    for e in envelopes:
        for r in (e.get("confidence") or {}).get("reasons", []) or []:
            if r not in out:
                out.append(str(r))
    return out


class _OneUpWrapperBase:
    """Shared HTTP plumbing. One httpx call per read; the wrapper does the 1up
    fan-out. Settings are read lazily per call so an env change (or the gate
    flipping) takes effect without a process restart in tests."""

    def _endpoint(self, path: str) -> tuple[str, str]:
        settings = get_settings()
        base = (settings.coverage_wrapper_url or "").rstrip("/")
        token = settings.wrapper_auth_token or ""
        if not base or not token:
            # Should be unreachable: __init__ only registers us when ready. Guard
            # anyway so a misconfig surfaces as a clear error, not an httpx crash.
            raise WrapperError("coverage wrapper URL/token not configured")
        return f"{base}{path}", token

    async def _get(self, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        url, token = self._endpoint(path)
        settings = get_settings()
        try:
            async with httpx.AsyncClient(
                timeout=settings.coverage_wrapper_timeout_seconds
            ) as client:
                resp = await client.get(
                    url, params=params, headers={"authorization": f"Bearer {token}"}
                )
        except httpx.HTTPError as exc:
            raise WrapperError(f"wrapper transport error: {exc}") from exc

        if resp.status_code != 200:
            # Surface the documented status codes verbatim; the body is JSON with
            # an "error" tag we log for diagnostics.
            body = _safe_json(resp)
            log.warning(
                "wrapper.non_200",
                path=path,
                status=resp.status_code,
                error=body.get("error") if isinstance(body, dict) else None,
            )
            raise WrapperError(
                f"wrapper {path} returned {resp.status_code}", status=resp.status_code
            )

        data = _safe_json(resp)
        if not isinstance(data, list):
            raise WrapperError(f"wrapper {path} did not return a JSON array")
        return data


def _safe_json(resp: httpx.Response) -> Any:
    try:
        return resp.json()
    except ValueError:
        return {}


def _wrap_data(envelopes: list[dict[str, Any]]) -> dict[str, Any]:
    """Carry the wrapper's normalized envelopes through under a namespaced key.

    TODO(coverage-connection): this is NOT the final SourceResult.data shape. The
    runtime contract is that data mirrors the corresponding tool's dict (so
    BenefitsContext / the agents read known keys). The wrapper's envelope shape is
    different by design. Mapping wrapper envelopes -> the tool-dict contract is a
    deliberate design decision (DL-72) left for when the gate is turned on; until
    then we namespace the raw payload so it is never mistaken for the tool shape.
    """
    return {"wrapper_envelopes": envelopes}


class OneUpWrapperCoverage(_OneUpWrapperBase):
    """Implements CoverageSource over the wrapper's /v1/coverages."""

    adapter_name = "OneUpWrapperCoverage"

    async def get_coverage(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> CoverageResult:
        app_user_id = _resolve_app_user_id(case_file_id, args)
        envelopes = await self._get("/v1/coverages", {"app_user_id": app_user_id})
        return CoverageResult(
            data=_wrap_data(envelopes),
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="vendor",
                as_of=next((a for e in envelopes if (a := _as_of_from_envelope(e))), None),
                confidence=_best_confidence(envelopes),
                assumptions=_reasons(envelopes)
                + ["payload shape carried verbatim from wrapper (see TODO)"],
            ),
        )


class OneUpWrapperClaims(_OneUpWrapperBase):
    """Implements ClaimsSource over the wrapper's /v1/claims."""

    adapter_name = "OneUpWrapperClaims"

    async def get_claims(
        self, case_file_id: str, args: dict[str, Any] | None = None
    ) -> ClaimsResult:
        app_user_id = _resolve_app_user_id(case_file_id, args)
        params = {"app_user_id": app_user_id}
        # ClaimsQuery.since (ISO date) is optional; pass it through when supplied.
        if args and args.get("since"):
            params["since"] = str(args["since"])
        envelopes = await self._get("/v1/claims", params)
        return ClaimsResult(
            data=_wrap_data(envelopes),
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="vendor",
                as_of=next((a for e in envelopes if (a := _as_of_from_envelope(e))), None),
                confidence=_best_confidence(envelopes),
                assumptions=_reasons(envelopes)
                + ["payload shape carried verbatim from wrapper (see TODO)"],
            ),
        )


class OneUpWrapperAccumulator(_OneUpWrapperBase):
    """Implements AccumulatorSource over the wrapper's /v1/accumulators.

    DL-69: AccumulatorResult.provenance.as_of is MANDATORY. The wrapper always
    stamps freshness.asOf (retrievedAt when nothing better), so a well-formed
    response yields a non-null as_of; if it somehow doesn't, we fall back to the
    caller's as_of argument so the required-field invariant always holds.
    """

    adapter_name = "OneUpWrapperAccumulator"

    async def get_accumulator(
        self, case_file_id: str, as_of: date, args: dict[str, Any] | None = None
    ) -> AccumulatorResult:
        app_user_id = _resolve_app_user_id(case_file_id, args)
        envelopes = await self._get("/v1/accumulators", {"app_user_id": app_user_id})
        resolved_as_of = next(
            (a for e in envelopes if (a := _as_of_from_envelope(e))), None
        ) or datetime(as_of.year, as_of.month, as_of.day, tzinfo=timezone.utc)
        return AccumulatorResult(
            data=_wrap_data(envelopes),
            provenance=Provenance(
                adapter=self.adapter_name,
                source_kind="vendor",
                as_of=resolved_as_of,
                confidence=_best_confidence(envelopes),
                assumptions=_reasons(envelopes)
                + ["payload shape carried verbatim from wrapper (see TODO)"],
            ),
        )


if TYPE_CHECKING:
    from app.sources.base import AccumulatorSource, ClaimsSource, CoverageSource

    # structural-conformance checks (mypy)
    _c: CoverageSource = OneUpWrapperCoverage()
    _l: ClaimsSource = OneUpWrapperClaims()
    _a: AccumulatorSource = OneUpWrapperAccumulator()
