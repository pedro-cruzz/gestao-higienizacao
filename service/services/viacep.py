import json
import logging
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class ViaCepLookupError(Exception):
    """Erro de consulta para a API ViaCEP."""


class ViaCepTemporaryUnavailableError(ViaCepLookupError):
    """Erro temporario de indisponibilidade da API ViaCEP."""


@dataclass(frozen=True)
class EnderecoViaCep:
    cep: str
    logradouro: str
    bairro: str
    cidade: str
    uf: str
    complemento: str = ""

    def as_dict(self) -> dict[str, str]:
        return {
            "cep": self.cep,
            "logradouro": self.logradouro,
            "bairro": self.bairro,
            "cidade": self.cidade,
            "uf": self.uf,
            "complemento": self.complemento,
        }


class ViaCepService:
    def __init__(self, base_url: str | None = None, timeout: float | None = None) -> None:
        self.base_url = (base_url if base_url is not None else settings.VIACEP_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.VIACEP_TIMEOUT

    def buscar_por_cep(self, cep: str) -> EnderecoViaCep:
        cep_limpo = self._normalizar_cep(cep)
        payload = self._get_json(f"/ws/{cep_limpo}/json/")
        if payload.get("erro"):
            raise ViaCepLookupError("Nenhum endereço foi encontrado para o CEP informado.")
        return self._normalizar_endereco(payload)

    def buscar_por_endereco(
        self,
        *,
        logradouro: str,
        cidade: str,
        uf: str,
        bairro: str = "",
    ) -> list[EnderecoViaCep]:
        logradouro_limpo = logradouro.strip()
        cidade_limpa = cidade.strip()
        uf_limpa = uf.strip().upper()

        if len(logradouro_limpo) < 3:
            raise ViaCepLookupError("Informe um logradouro com pelo menos 3 caracteres para pesquisar o CEP.")
        if len(cidade_limpa) < 3:
            raise ViaCepLookupError("Informe uma cidade com pelo menos 3 caracteres para pesquisar o CEP.")
        if len(uf_limpa) != 2:
            raise ViaCepLookupError("Informe uma UF valida com 2 letras para pesquisar o CEP.")

        path = f"/ws/{quote(uf_limpa)}/{quote(cidade_limpa)}/{quote(logradouro_limpo)}/json/"
        payload = self._get_json(path)
        if not isinstance(payload, list):
            raise ViaCepLookupError("A API ViaCEP retornou um formato de endereço inesperado.")

        resultados = [self._normalizar_endereco(item) for item in payload if self._aceita_bairro(item, bairro)]
        return resultados

    def _aceita_bairro(self, payload: dict[str, Any], bairro: str) -> bool:
        if not bairro.strip():
            return True
        return bairro.strip().lower() in (payload.get("bairro") or "").strip().lower()

    def _normalizar_cep(self, cep: str) -> str:
        digits = "".join(char for char in cep if char.isdigit())
        if len(digits) != 8:
            raise ViaCepLookupError("Informe um CEP com 8 digitos.")
        return digits

    def _normalizar_endereco(self, payload: dict[str, Any]) -> EnderecoViaCep:
        if not isinstance(payload, dict):
            raise ViaCepLookupError("A API ViaCEP retornou um formato de endereço inesperado.")

        return EnderecoViaCep(
            cep=(payload.get("cep") or "").strip(),
            logradouro=(payload.get("logradouro") or "").strip(),
            bairro=(payload.get("bairro") or "").strip(),
            cidade=(payload.get("localidade") or "").strip(),
            uf=(payload.get("uf") or "").strip(),
            complemento=(payload.get("complemento") or "").strip(),
        )

    def _get_json(self, path: str) -> Any:
        url = f"{self.base_url}{path}"
        try:
            request = Request(url, headers={"Accept": "application/json"})
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read().decode("utf-8")
            return json.loads(data)
        except HTTPError as exc:
            logger.warning("Falha ao consultar ViaCEP. status=%s url=%s", exc.code, url)
            if exc.code == 400:
                raise ViaCepLookupError("Os dados informados para consulta de CEP são inválidos.") from exc
            if exc.code in {500, 502, 503, 504}:
                raise ViaCepTemporaryUnavailableError(
                    "A consulta de CEP está indisponível no momento. "
                    "Você pode preencher o endereço manualmente e tentar novamente depois."
                ) from exc
            raise ViaCepLookupError("Falha ao consultar a API ViaCEP.") from exc
        except (TimeoutError, URLError) as exc:
            logger.warning("Falha de conexao ao consultar ViaCEP. url=%s erro=%s", url, exc)
            raise ViaCepTemporaryUnavailableError(
                "Não foi possível consultar o ViaCEP no momento. "
                "Você pode preencher o endereço manualmente e tentar novamente depois."
            ) from exc
