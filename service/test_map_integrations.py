import ssl
from unittest.mock import patch

from django.test import SimpleTestCase

from service.services.http import get_ssl_context
from service.services.nominatim import NominatimService
from service.services.viacep import ViaCepService


class MapHttpsTests(SimpleTestCase):
    def tearDown(self):
        get_ssl_context.cache_clear()
        super().tearDown()

    def assert_verified_tls(self, context):
        self.assertTrue(context.check_hostname)
        self.assertEqual(context.verify_mode, ssl.CERT_REQUIRED)
        self.assertGreater(context.cert_store_stats()["x509_ca"], 0)

    def test_carrega_certificados_quando_python_nao_tem_cas_configuradas(self):
        empty_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        self.assertEqual(empty_context.cert_store_stats()["x509_ca"], 0)
        get_ssl_context.cache_clear()

        with patch("service.services.http.ssl.create_default_context", return_value=empty_context):
            context = get_ssl_context()

        self.assert_verified_tls(context)

    @patch("service.services.nominatim.urlopen")
    def test_nominatim_consulta_com_certificados_e_validacao_https(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.read.return_value = b"[]"

        result = NominatimService()._get_json("/search", {"q": "Brasil"})

        self.assertEqual(result, [])
        self.assert_verified_tls(urlopen_mock.call_args.kwargs["context"])

    @patch("service.services.viacep.urlopen")
    def test_viacep_consulta_com_certificados_e_validacao_https(self, urlopen_mock):
        urlopen_mock.return_value.__enter__.return_value.read.return_value = b'{"cep": "01001-000"}'

        result = ViaCepService().buscar_por_cep("01001000")

        self.assertEqual(result.cep, "01001-000")
        self.assert_verified_tls(urlopen_mock.call_args.kwargs["context"])
