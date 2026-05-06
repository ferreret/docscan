"""Cliente HTTP que el agente local usa para hablar con el SaaS.

Wrappea httpx con dos métodos: ``pair_claim`` (canjea el código por un
``agent_token``) y ``whoami`` (devuelve info del dispositivo + user +
tenant). El cliente es síncrono — el agente FastAPI usa endpoints sync,
no necesitamos asyncio aquí.

Errores:
- ``SaasUnavailable``: la red falló (connect/timeout/etc.).
- ``PairClaimError``: el SaaS respondió con 4xx/5xx en pair-claim.
- ``WhoamiError``: ídem en whoami.

Las dos últimas exponen ``status_code`` y ``detail`` para que el router
``/pair`` del agente los relayée al frontend con el mensaje original.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import httpx

from docscan_local_agent.saas_schemas import AgentInfo

log = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class PairClaimResult:
    """Lo que devuelve el SaaS en POST /api/agent/pair-claim."""

    agent_token: str
    device_id: int


class SaasUnavailable(RuntimeError):
    """El SaaS no respondió (red caída, timeout, DNS, etc.)."""


class _SaasHttpError(RuntimeError):
    """Base para errores 4xx/5xx del SaaS. No instanciar directamente."""

    def __init__(self, status_code: int, detail: str) -> None:
        super().__init__(f"{status_code}: {detail}")
        self.status_code = status_code
        self.detail = detail


class PairClaimError(_SaasHttpError):
    """El SaaS rechazó el pair-claim (404 código no válido, 410 expirado, ...)."""


class WhoamiError(_SaasHttpError):
    """El SaaS rechazó el whoami (401 token inválido, ...)."""


class UploadError(_SaasHttpError):
    """El SaaS rechazó la subida (404 lote ajeno, 401 token revocado, ...)."""


def _extract_detail(resp: httpx.Response) -> str:
    """Saca ``detail`` del body JSON; si no es JSON, devuelve el reason phrase."""
    try:
        body = resp.json()
        if isinstance(body, dict) and "detail" in body:
            return str(body["detail"])
    except (ValueError, TypeError):
        pass
    return resp.reason_phrase or f"HTTP {resp.status_code}"


class SaasClient:
    """Cliente HTTP fino contra los endpoints ``/api/agent/*`` del SaaS.

    El ``http_client`` es inyectable para que los tests pasen un
    ``httpx.MockTransport`` sin tocar la red.
    """

    DEFAULT_TIMEOUT = 10.0

    def __init__(
        self,
        base_url: str,
        *,
        http_client: httpx.Client | None = None,
        timeout: float | None = None,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._owns_client = http_client is None
        self._http = http_client or httpx.Client(
            timeout=timeout or self.DEFAULT_TIMEOUT
        )

    def close(self) -> None:
        if self._owns_client:
            self._http.close()

    def __enter__(self) -> SaasClient:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()

    # ------------------------------------------------------------------
    # pair-claim (público — sin auth)
    # ------------------------------------------------------------------

    def pair_claim(self, code: str) -> PairClaimResult:
        """Canjea el código de pairing por un ``agent_token`` long-lived."""
        normalised = code.strip().upper()
        url = f"{self._base_url}/api/agent/pair-claim"

        try:
            resp = self._http.post(url, json={"code": normalised})
        except httpx.HTTPError as exc:
            log.warning("pair-claim: SaaS inalcanzable (%s): %s", url, exc)
            raise SaasUnavailable(str(exc)) from exc

        if resp.status_code != 200:
            raise PairClaimError(resp.status_code, _extract_detail(resp))

        body = resp.json()
        return PairClaimResult(
            agent_token=body["agent_token"],
            device_id=int(body["device_id"]),
        )

    # ------------------------------------------------------------------
    # whoami (Bearer agent_token)
    # ------------------------------------------------------------------

    def whoami(self, agent_token: str) -> AgentInfo:
        """Devuelve la info del dispositivo + user + tenant propietarios."""
        url = f"{self._base_url}/api/agent/whoami"
        headers = {"Authorization": f"Bearer {agent_token}"}

        try:
            resp = self._http.get(url, headers=headers)
        except httpx.HTTPError as exc:
            log.warning("whoami: SaaS inalcanzable (%s): %s", url, exc)
            raise SaasUnavailable(str(exc)) from exc

        if resp.status_code != 200:
            raise WhoamiError(resp.status_code, _extract_detail(resp))

        return AgentInfo.model_validate(resp.json())

    # ------------------------------------------------------------------
    # upload_page (Bearer agent_token, multipart)
    # ------------------------------------------------------------------

    def upload_page(
        self,
        batch_id: int,
        agent_token: str,
        png_bytes: bytes,
        filename: str = "scan.png",
    ) -> dict:
        """Sube un PNG como nueva página del ``batch_id``.

        El SaaS valida con la dependency híbrida del hito 7: el
        ``agent_token`` lleva implícito el tenant del dueño del
        device, y ``get_batch_for_tenant`` hace 404 si el lote no es
        suyo.

        Returns:
            El dict crudo devuelto por el SaaS (``PageUploadResponse``):
            ``{"created": [...], "batch_page_count": int}``.

        Raises:
            UploadError: Si el SaaS responde 4xx/5xx.
            SaasUnavailable: Si la red al SaaS falla.
        """
        url = f"{self._base_url}/api/batches/{batch_id}/pages"
        headers = {"Authorization": f"Bearer {agent_token}"}
        files = {"files": (filename, png_bytes, "image/png")}

        try:
            resp = self._http.post(url, headers=headers, files=files)
        except httpx.HTTPError as exc:
            log.warning("upload_page: SaaS inalcanzable (%s): %s", url, exc)
            raise SaasUnavailable(str(exc)) from exc

        if resp.status_code != 201:
            raise UploadError(resp.status_code, _extract_detail(resp))

        return resp.json()
