import json
import logging
from dataclasses import dataclass
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from django.conf import settings

logger = logging.getLogger(__name__)


class NominatimLookupError(Exception):
    """Erro de consulta para a API Nominatim."""


class NominatimTemporaryUnavailableError(NominatimLookupError):
    """Erro temporario de indisponibilidade da API Nominatim."""


@dataclass(frozen=True)
class LocalizacaoMapa:
    latitude: float
    longitude: float
    display_name: str

    def as_dict(self) -> dict[str, str | float]:
        return {
            "latitude": self.latitude,
            "longitude": self.longitude,
            "display_name": self.display_name,
        }


class NominatimService:
    def __init__(
        self,
        base_url: str | None = None,
        timeout: float | None = None,
        user_agent: str | None = None,
    ) -> None:
        self.base_url = (base_url if base_url is not None else settings.NOMINATIM_BASE_URL).rstrip("/")
        self.timeout = timeout if timeout is not None else settings.NOMINATIM_TIMEOUT
        self.user_agent = (
            user_agent if user_agent is not None else settings.NOMINATIM_USER_AGENT
        ).strip()

    def geocodificar(
        self,
        *,
        endereco: str = "",
        cep: str = "",
        logradouro: str = "",
        numero: str = "",
        bairro: str = "",
        cidade: str = "",
        uf: str = "",
    ) -> LocalizacaoMapa:
        queries = self._montar_consultas(
            endereco=endereco,
            cep=cep,
            logradouro=logradouro,
            numero=numero,
            bairro=bairro,
            cidade=cidade,
            uf=uf,
        )
        if not queries:
            raise NominatimLookupError("Preencha um endereço mais completo para localizar no mapa.")

        payload = self._buscar_estruturado(
            cep=cep,
            logradouro=logradouro,
            numero=numero,
            cidade=cidade,
            uf=uf,
        )
        if isinstance(payload, list) and payload:
            item = payload[0]
            return LocalizacaoMapa(
                latitude=float(item["lat"]),
                longitude=float(item["lon"]),
                display_name=item.get("display_name", queries[0]),
            )

        for query in queries:
            payload = self._get_json(
                "/search",
                {
                    "q": query,
                    "format": "jsonv2",
                    "limit": "1",
                    "countrycodes": "br",
                    "addressdetails": "1",
                },
            )
            if isinstance(payload, list) and payload:
                item = payload[0]
                return LocalizacaoMapa(
                    latitude=float(item["lat"]),
                    longitude=float(item["lon"]),
                    display_name=item.get("display_name", query),
                )

        raise NominatimLookupError("Não foi possível localizar esse endereço no mapa.")

    def _buscar_estruturado(
        self,
        *,
        cep: str,
        logradouro: str,
        numero: str,
        cidade: str,
        uf: str,
    ) -> list[dict]:
        if not logradouro or not cidade:
            return []

        street = " ".join(parte for parte in [numero.strip(), logradouro.strip()] if parte)
        return self._get_json(
            "/search",
            {
                "street": street,
                "city": cidade.strip(),
                "state": uf.strip().upper(),
                "postalcode": cep.strip(),
                "country": "Brasil",
                "format": "jsonv2",
                "limit": "1",
                "countrycodes": "br",
                "addressdetails": "1",
            },
        )

    def _montar_consultas(
        self,
        *,
        endereco: str,
        cep: str,
        logradouro: str,
        numero: str,
        bairro: str,
        cidade: str,
        uf: str,
    ) -> list[str]:
        endereco = endereco.strip()
        cep = cep.strip()
        logradouro = logradouro.strip()
        numero = numero.strip()
        bairro = bairro.strip()
        cidade = cidade.strip()
        uf = uf.strip().upper()

        variacoes = [
            [endereco, cep, "Brasil"],
            [logradouro, numero, bairro, cidade, uf, cep, "Brasil"],
            [logradouro, numero, cidade, uf, "Brasil"],
            [logradouro, numero, cep, "Brasil"],
            [logradouro, bairro, cidade, uf, "Brasil"],
            [logradouro, cidade, uf, "Brasil"],
            [cep, cidade, uf, "Brasil"],
            [cep, "Brasil"],
        ]

        consultas = []
        for partes in variacoes:
            query = ", ".join(parte for parte in partes if parte)
            if len(query) >= 8 and query not in consultas:
                consultas.append(query)
        return consultas

    def _get_json(self, path: str, params: dict[str, str]) -> list[dict]:
        url = f"{self.base_url}{path}?{urlencode(params)}"
        try:
            request = Request(url, headers={"Accept": "application/json", "User-Agent": self.user_agent})
            with urlopen(request, timeout=self.timeout) as response:
                data = response.read().decode("utf-8")
            return json.loads(data)
        except HTTPError as exc:
            logger.warning("Falha ao consultar Nominatim. status=%s url=%s", exc.code, url)
            if exc.code in {400, 422}:
                raise NominatimLookupError("Os dados informados para localizar no mapa são inválidos.") from exc
            if exc.code in {429, 500, 502, 503, 504}:
                raise NominatimTemporaryUnavailableError(
                    "A localização no mapa está indisponível no momento. Tente novamente em instantes."
                ) from exc
            raise NominatimLookupError("Falha ao consultar a localização do mapa.") from exc
        except (TimeoutError, URLError) as exc:
            logger.warning("Falha de conexao ao consultar Nominatim. url=%s erro=%s", url, exc)
            raise NominatimTemporaryUnavailableError(
                "Não foi possível consultar a localização do mapa no momento."
            ) from exc
