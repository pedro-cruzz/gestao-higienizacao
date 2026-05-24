from datetime import datetime, time
import tempfile
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from service.models import CategoriaCatalogo, Cliente, Lead, Orcamento, OrdemServico, Service_catalog, Tecnico
from service.services.nominatim import LocalizacaoMapa, NominatimService
from service.services.viacep import EnderecoViaCep


class ServiceViewsTests(TestCase):
    def setUp(self):
        self.item_a = Service_catalog.objects.create(
            name="Banner 1x1",
            tipo="Impressao",
            valor=120.0,
            descricao="Banner em lona",
        )
        self.item_b = Service_catalog.objects.create(
            name="Adesivo vitrine",
            tipo="Recorte",
            valor=80.0,
            descricao="Adesivo para vitrine",
        )

    def test_catalogo_retorna_ok(self):
        response = self.client.get(reverse("catalogo"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Catalogo")
        self.assertContains(response, self.item_a.name)
        self.assertContains(response, "Orcar item")

    def test_lista_clientes_retorna_ok(self):
        Cliente.objects.create(
            name="Maria Cliente",
            email="maria@teste.com",
            telefone="11911112222",
            endereco="Rua das Flores, 12",
        )

        response = self.client.get(reverse("clientes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Clientes")
        self.assertContains(response, "Maria Cliente")

    def test_inicio_exibe_metricas_reais(self):
        Lead.objects.create(
            name="Lead Dashboard",
            email="lead@teste.com",
            telefone="11922223333",
        )
        cliente = Cliente.objects.create(
            name="Cliente Dashboard",
            email="cliente-dashboard@teste.com",
            telefone="11922223333",
        )
        orcamento = Orcamento.objects.create(
            name="Cliente Dashboard",
            email="dashboard@teste.com",
            quantidade=1,
            valor=120.0,
            aprovado=True,
            cliente=cliente,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.get(reverse("inicio"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead Dashboard")
        self.assertContains(response, "Cliente Dashboard")
        self.assertContains(response, "100%")
        self.assertContains(response, "bi-house-door")
        self.assertNotContains(response, "bi-columns-gap")

    def test_agenda_retorna_ok(self):
        OrdemServico.objects.create(
            titulo="Servico agenda teste",
            data_agendada=timezone.localdate(),
            hora_inicio="09:00",
            administrador_executa=True,
            valor=120.0,
        )

        response = self.client.get(reverse("agenda"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "agenda-month-card")
        self.assertContains(response, "agenda-week-cards")
        self.assertNotContains(response, "agenda-calendar-card")
        self.assertContains(response, "Servico agenda teste")
        self.assertContains(response, "Administrador / dono")

    def test_configuracoes_retorna_ok(self):
        response = self.client.get(reverse("configuracoes"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Configura")
        self.assertContains(response, "Esta pagina sera implementada futuramente")
        self.assertNotContains(response, ">Equipe<")

    def test_login_placeholder_e_link_de_saida(self):
        login_response = self.client.get(reverse("login"))
        inicio_response = self.client.get(reverse("inicio"))

        self.assertEqual(login_response.status_code, 200)
        self.assertContains(login_response, "login-shell")
        self.assertContains(login_response, "Bem-vindo ao HigiFlow")
        self.assertContains(login_response, "seu@email.com")
        self.assertContains(login_response, "Gerencie seu neg")
        self.assertNotContains(login_response, "hf-sidebar")
        self.assertContains(inicio_response, f'href="{reverse("login")}"')
        self.assertContains(inicio_response, ">Sair<")

    def test_cria_lead(self):
        response = self.client.post(
            reverse("novo_lead"),
            {
                "name": "Lead Novo",
                "email": " NOVO@TESTE.COM ",
                "telefone": "+55 (11) 93333-4444",
                "endereco": "Rua Lead, 10",
                "status": Lead.Status.CONTATADO,
                "origem": Lead.Origem.WHATSAPP,
            },
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get(email="novo@teste.com")
        self.assertEqual(lead.telefone, "(11) 93333-4444")

    def test_nao_cria_lead_com_telefone_invalido(self):
        response = self.client.post(
            reverse("novo_lead"),
            {
                "name": "Lead Telefone Invalido",
                "email": "telefone-invalido@teste.com",
                "telefone": "12345",
                "status": Lead.Status.NOVO,
                "origem": Lead.Origem.MANUAL,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Informe um telefone com DDD")
        self.assertFalse(Lead.objects.filter(email="telefone-invalido@teste.com").exists())

    def test_lista_leads_exibe_status_e_origem_visuais(self):
        Lead.objects.create(
            name="Lead Visual",
            email="visual@teste.com",
            telefone="11933334444",
            status=Lead.Status.CONTATADO,
            origem=Lead.Origem.INSTAGRAM,
        )

        response = self.client.get(reverse("leads"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lead-status-contacted")
        self.assertContains(response, "lead-origin-instagram")
        self.assertContains(response, "bi-instagram")

    def test_filtra_leads_por_status_origem_e_periodo(self):
        dentro = Lead.objects.create(
            name="Lead Dentro",
            email="dentro@teste.com",
            status=Lead.Status.AGUARDANDO,
            origem=Lead.Origem.WHATSAPP,
        )
        fora_status = Lead.objects.create(
            name="Lead Fora Status",
            email="fora-status@teste.com",
            status=Lead.Status.NOVO,
            origem=Lead.Origem.WHATSAPP,
        )
        fora_data = Lead.objects.create(
            name="Lead Fora Data",
            email="fora-data@teste.com",
            status=Lead.Status.AGUARDANDO,
            origem=Lead.Origem.WHATSAPP,
        )
        tz = timezone.get_current_timezone()
        Lead.objects.filter(pk=dentro.pk).update(
            created_at=timezone.make_aware(datetime.combine(datetime(2026, 5, 15).date(), time.min), tz)
        )
        Lead.objects.filter(pk=fora_status.pk).update(
            created_at=timezone.make_aware(datetime.combine(datetime(2026, 5, 15).date(), time.min), tz)
        )
        Lead.objects.filter(pk=fora_data.pk).update(
            created_at=timezone.make_aware(datetime.combine(datetime(2026, 4, 30).date(), time.min), tz)
        )

        response = self.client.get(
            reverse("leads"),
            {
                "status": Lead.Status.AGUARDANDO,
                "origem": Lead.Origem.WHATSAPP,
                "data_inicio": "2026-05-01",
                "data_fim": "2026-05-31",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Lead Dentro")
        self.assertNotContains(response, "Lead Fora Status")
        self.assertNotContains(response, "Lead Fora Data")

    def test_cria_lead_com_endereco_via_cep(self):
        response = self.client.post(
            reverse("novo_lead"),
            {
                "name": "Lead CEP",
                "email": "lead-cep@teste.com",
                "telefone": "11933334444",
                "cep": "01001-000",
                "logradouro": "Praca da Se",
                "numero": "200",
                "complemento": "Casa",
                "bairro": "Se",
                "cidade": "Sao Paulo",
                "uf": "sp",
                "status": Lead.Status.NOVO,
                "origem": Lead.Origem.MANUAL,
            },
        )

        self.assertEqual(response.status_code, 302)
        lead = Lead.objects.get(email="lead-cep@teste.com")
        self.assertEqual(lead.cep, "01001-000")
        self.assertEqual(lead.logradouro, "Praca da Se")
        self.assertEqual(lead.numero, "200")
        self.assertEqual(lead.bairro, "Se")
        self.assertEqual(lead.cidade, "Sao Paulo")
        self.assertEqual(lead.uf, "SP")
        self.assertIn("Praca da Se, 200", lead.endereco)

    def test_lead_vira_cliente(self):
        lead = Lead.objects.create(
            name="Lead para Cliente",
            email="vira-cliente@teste.com",
            telefone="11933334444",
            origem=Lead.Origem.INSTAGRAM,
        )

        response = self.client.post(
            f"{reverse('novo_cliente')}?lead={lead.pk}",
            {
                "name": lead.name,
                "email": lead.email,
                "telefone": lead.telefone,
                "endereco": "Rua Conversao, 10",
                "status": Cliente.Status.CONVERTIDO,
            },
        )

        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.CONVERTIDO)
        self.assertIsNotNone(lead.cliente)
        self.assertTrue(Cliente.objects.filter(email="vira-cliente@teste.com").exists())

    def test_lead_convertido_mostra_acao_de_abrir_cliente(self):
        cliente = Cliente.objects.create(
            name="Cliente Convertido",
            email="cliente-convertido@teste.com",
        )
        Lead.objects.create(
            name="Lead Convertido",
            email="lead-convertido@teste.com",
            status=Lead.Status.CONVERTIDO,
            cliente=cliente,
        )

        response = self.client.get(reverse("leads"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Convertido")
        self.assertContains(response, "Abrir cliente")
        self.assertNotContains(response, "Virar cliente")

    def test_lead_vira_orcamento(self):
        lead = Lead.objects.create(
            name="Lead para Orcamento",
            email="vira-orcamento@teste.com",
            telefone="11955556666",
            origem=Lead.Origem.WHATSAPP,
        )

        response = self.client.post(
            f"{reverse('novo_orcamento')}?lead={lead.pk}",
            {
                "name": lead.name,
                "email": lead.email,
                "telefone": lead.telefone,
                "quantidade": 2,
                "itens": [str(self.item_a.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        orcamento = Orcamento.objects.get(email="vira-orcamento@teste.com")
        self.assertEqual(orcamento.lead, lead)
        self.assertEqual(orcamento.valor, self.item_a.valor * 2)
        self.assertEqual(lead.status, Lead.Status.CONTATADO)

    def test_orcamento_puxa_dados_do_lead_selecionado(self):
        lead = Lead.objects.create(
            name="Lead Selecionado",
            email="LEAD-SELECIONADO@TESTE.COM",
            telefone="11922223333",
            cep="01001-000",
            logradouro="Praca da Se",
            numero="100",
            bairro="Se",
            cidade="Sao Paulo",
            uf="SP",
        )

        response = self.client.post(
            reverse("novo_orcamento"),
            {
                "lead": lead.pk,
                "quantidade": 1,
                "itens": [str(self.item_a.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        orcamento = Orcamento.objects.get(email="lead-selecionado@teste.com")
        self.assertEqual(orcamento.lead, lead)
        self.assertEqual(orcamento.name, "Lead Selecionado")
        self.assertEqual(orcamento.telefone, "(11) 92222-3333")
        self.assertEqual(orcamento.logradouro, "Praca da Se")
        self.assertEqual(lead.status, Lead.Status.CONTATADO)

    def test_busca_dados_do_lead_para_preencher_orcamento(self):
        lead = Lead.objects.create(
            name="Lead Ajax",
            email="ajax@teste.com",
            telefone="(11) 93333-4444",
            logradouro="Rua Ajax",
            numero="10",
            bairro="Centro",
            cidade="Sao Paulo",
            uf="SP",
        )

        response = self.client.get(reverse("buscar_lead_dados", args=[lead.pk]))

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["lead"]["name"], "Lead Ajax")
        self.assertEqual(data["lead"]["telefone"], "(11) 93333-4444")
        self.assertEqual(data["lead"]["logradouro"], "Rua Ajax")

    def test_form_orcamento_tem_url_para_buscar_lead(self):
        response = self.client.get(reverse("novo_orcamento"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "data-lead-url-template")

    def test_lead_aguardando_mantem_status_ao_virar_orcamento(self):
        lead = Lead.objects.create(
            name="Lead Aguardando Orcamento",
            email="lead-aguardando@teste.com",
            status=Lead.Status.AGUARDANDO,
        )

        response = self.client.post(
            f"{reverse('novo_orcamento')}?lead={lead.pk}",
            {
                "name": lead.name,
                "email": lead.email,
                "quantidade": 1,
                "itens": [str(self.item_a.pk)],
            },
        )

        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.AGUARDANDO)

    def test_orcamento_do_lead_ao_virar_cliente_atualiza_lead(self):
        lead = Lead.objects.create(
            name="Lead Orcamento Cliente",
            email="lead-orcamento-cliente@teste.com",
        )
        orcamento = Orcamento.objects.create(
            name=lead.name,
            email=lead.email,
            quantidade=1,
            valor=120.0,
            lead=lead,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("cadastrar_cliente_orcamento", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 302)
        lead.refresh_from_db()
        self.assertEqual(lead.status, Lead.Status.CONVERTIDO)
        self.assertIsNotNone(lead.cliente)
        self.assertEqual(lead.cliente.email, lead.email)

    def test_cria_cliente(self):
        response = self.client.post(
            reverse("novo_cliente"),
            {
                "name": "Cliente Novo",
                "email": "cliente-novo@teste.com",
                "telefone": "11944445555",
                "cep": "01001-000",
                "logradouro": "Praca da Se",
                "numero": "300",
                "bairro": "Se",
                "cidade": "Sao Paulo",
                "uf": "sp",
                "status": Cliente.Status.CONTATADO,
            },
        )

        self.assertEqual(response.status_code, 302)
        cliente = Cliente.objects.get(email="cliente-novo@teste.com")
        self.assertEqual(cliente.name, "Cliente Novo")
        self.assertEqual(cliente.uf, "SP")
        self.assertIn("Praca da Se, 300", cliente.endereco)

    def test_cria_cliente_puxando_dados_do_orcamento(self):
        orcamento = Orcamento.objects.create(
            name="Cliente do Orcamento",
            email="origem@teste.com",
            telefone="11988889999",
            cep="37502-118",
            logradouro="Rua Orlando Mohallen",
            numero="298",
            bairro="Medicina",
            cidade="Itajuba",
            uf="mg",
            endereco="Rua Orlando Mohallen, 298 | Medicina | Itajuba - MG",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("novo_cliente"),
            {
                "orcamento_origem": orcamento.pk,
            },
        )

        self.assertEqual(response.status_code, 302)
        cliente = Cliente.objects.get(email="origem@teste.com")
        self.assertEqual(cliente.name, "Cliente do Orcamento")
        self.assertEqual(cliente.telefone, "(11) 98888-9999")
        self.assertEqual(cliente.status, Cliente.Status.CONVERTIDO)
        self.assertEqual(cliente.uf, "MG")

        orcamento.refresh_from_db()
        self.assertEqual(orcamento.cliente, cliente)

    def test_form_cliente_exibe_opcao_de_orcamento(self):
        Orcamento.objects.create(
            name="Cliente Origem Form",
            email="form@teste.com",
            quantidade=1,
            valor=120.0,
        ).itens.set([self.item_a])

        response = self.client.get(reverse("novo_cliente"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Puxar dados de um orcamento")
        self.assertContains(response, "Cliente Origem Form")

    def test_edita_cliente(self):
        cliente = Cliente.objects.create(
            name="Cliente Antigo",
            email="antigo@teste.com",
            telefone="11955556666",
            status=Cliente.Status.NOVO,
        )

        response = self.client.post(
            reverse("editar_cliente", args=[cliente.pk]),
            {
                "name": "Cliente Atualizado",
                "email": "atualizado@teste.com",
                "telefone": "11977778888",
                "cep": "37502-118",
                "logradouro": "Rua Orlando Mohallen",
                "numero": "298",
                "bairro": "Medicina",
                "cidade": "Itajuba",
                "uf": "mg",
                "status": Cliente.Status.CONVERTIDO,
            },
        )

        self.assertEqual(response.status_code, 302)
        cliente.refresh_from_db()
        self.assertEqual(cliente.name, "Cliente Atualizado")
        self.assertEqual(cliente.email, "atualizado@teste.com")
        self.assertEqual(cliente.status, Cliente.Status.CONVERTIDO)
        self.assertEqual(cliente.uf, "MG")

    def test_lista_orcamentos_retorna_ok(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Lista",
            email="lista@teste.com",
            quantidade=1,
            valor=120.0,
            descricao="Busca por lista",
        )
        orcamento.itens.set([self.item_a])

        response = self.client.get(reverse("orcamentos"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Cliente Lista")
        self.assertContains(response, "120.00")

    def test_lista_ordens_servico_retorna_ok(self):
        OrdemServico.objects.create(
            titulo="OS Cliente Ordem",
            data_agendada=timezone.localdate(),
            hora_inicio="09:00",
            administrador_executa=True,
            valor=120.0,
        )

        response = self.client.get(reverse("ordens_servico"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "service-orders-board")
        self.assertContains(response, "OS Cliente Ordem")
        self.assertContains(response, "R$ 120,00")

    def test_atualiza_status_os_pelo_kanban(self):
        ordem = OrdemServico.objects.create(
            titulo="OS Kanban",
            data_agendada=timezone.localdate(),
            hora_inicio="09:00",
            administrador_executa=True,
            valor=120.0,
        )

        response = self.client.post(
            reverse("atualizar_status_os", args=[ordem.pk]),
            {"status": OrdemServico.Status.EM_ANDAMENTO},
        )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["status"], OrdemServico.Status.EM_ANDAMENTO)
        self.assertEqual(payload["totais"][OrdemServico.Status.EM_ANDAMENTO], 1)

        ordem.refresh_from_db()
        self.assertEqual(ordem.status, OrdemServico.Status.EM_ANDAMENTO)

    def test_deleta_cliente_sem_apagar_orcamento(self):
        cliente = Cliente.objects.create(
            name="Cliente Remover",
            email="remover@teste.com",
        )
        orcamento = Orcamento.objects.create(
            name="Cliente Remover",
            email="remover@teste.com",
            quantidade=1,
            valor=120.0,
            cliente=cliente,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("deletar_cliente", args=[cliente.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Cliente.objects.filter(pk=cliente.pk).exists())
        orcamento.refresh_from_db()
        self.assertIsNone(orcamento.cliente)

    def test_deleta_orcamento(self):
        orcamento = Orcamento.objects.create(
            name="Orcamento Remover",
            email="orcamento-remover@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("deletar_orcamento", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Orcamento.objects.filter(pk=orcamento.pk).exists())

    def test_cria_produto_no_catalogo(self):
        categoria = CategoriaCatalogo.objects.create(name="Sofas")
        response = self.client.post(
            reverse("novo_produto"),
            {
                "name": "Sofa retratil 3 lugares",
                "categoria": categoria.pk,
                "valor": 59.9,
                "descricao": "Higienizacao completa de sofa.",
                "tempo": "2 horas",
                "formato": "Retratil",
                "tamanho": "Grande",
                "largura": "70 cm",
                "comprimento": "300 cm",
                "tecido": "Suede",
            },
        )

        self.assertEqual(response.status_code, 302)
        produto = Service_catalog.objects.get(name="Sofa retratil 3 lugares")
        self.assertEqual(produto.categoria, categoria)
        self.assertEqual(produto.tipo, "Sofas")

    def test_cria_produto_com_imagem_no_catalogo(self):
        categoria = CategoriaCatalogo.objects.create(name="Tapetes")
        image = SimpleUploadedFile(
            "tapete.gif",
            b"GIF87a\x01\x00\x01\x00\x80\x01\x00\x00\x00\x00\xff\xff\xff,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;",
            content_type="image/gif",
        )

        with tempfile.TemporaryDirectory() as media_root, self.settings(MEDIA_ROOT=media_root):
            response = self.client.post(
                reverse("novo_produto"),
                {
                    "name": "Tapete com imagem",
                    "categoria": categoria.pk,
                    "valor": 90,
                    "descricao": "Higienizacao de tapete.",
                    "imagem": image,
                },
            )

            self.assertEqual(response.status_code, 302)
            produto = Service_catalog.objects.get(name="Tapete com imagem")
            self.assertTrue(produto.imagem.name.startswith("catalogo/"))

    def test_form_produto_tem_upload_de_imagem(self):
        response = self.client.get(reverse("novo_produto"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, 'enctype="multipart/form-data"')
        self.assertContains(response, 'type="file"')

    def test_cria_categoria_do_catalogo(self):
        response = self.client.post(
            reverse("nova_categoria"),
            {
                "name": "Tapetes",
                "descricao": "Itens de higienizacao para tapetes.",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertTrue(CategoriaCatalogo.objects.filter(name="Tapetes").exists())

    def test_edita_item_do_catalogo(self):
        categoria = CategoriaCatalogo.objects.create(name="Colchoes")

        response = self.client.post(
            reverse("editar_produto", args=[self.item_a.pk]),
            {
                "name": "Colchao queen",
                "categoria": categoria.pk,
                "valor": 180.0,
                "descricao": "Higienizacao de colchao queen.",
                "tempo": "2 horas",
                "formato": "Queen",
                "tamanho": "Queen",
                "largura": "158 cm",
                "comprimento": "198 cm",
                "tecido": "Malha",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.item_a.refresh_from_db()
        self.assertEqual(self.item_a.name, "Colchao queen")
        self.assertEqual(self.item_a.categoria, categoria)
        self.assertEqual(self.item_a.tipo, "Colchoes")

    def test_deleta_item_do_catalogo(self):
        response = self.client.post(reverse("deletar_produto", args=[self.item_b.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertFalse(Service_catalog.objects.filter(pk=self.item_b.pk).exists())

    def test_cria_orcamento_com_total(self):
        response = self.client.post(
            reverse("novo_orcamento"),
            {
                "name": "Cliente Teste",
                "email": "cliente@teste.com",
                "telefone": "11999999999",
                "endereco": "Rua Teste, 123",
                "descricao": "Pedido inicial",
                "quantidade": 2,
                "itens": [self.item_a.pk, self.item_b.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Orcamento.objects.count(), 1)

        orcamento = Orcamento.objects.get()
        self.assertEqual(orcamento.valor, 400.0)
        self.assertEqual(orcamento.quantidade, 2)
        self.assertEqual(orcamento.email, "cliente@teste.com")

    def test_cria_orcamento_com_endereco_via_cep(self):
        response = self.client.post(
            reverse("novo_orcamento"),
            {
                "name": "Cliente CEP",
                "email": "cep@teste.com",
                "telefone": "11999999999",
                "cep": "01001-000",
                "logradouro": "Praca da Se",
                "numero": "100",
                "complemento": "Sala 2",
                "bairro": "Se",
                "cidade": "Sao Paulo",
                "uf": "sp",
                "descricao": "Pedido com endereco estruturado",
                "quantidade": 1,
                "itens": [self.item_a.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        orcamento = Orcamento.objects.get(name="Cliente CEP")
        self.assertEqual(orcamento.cep, "01001-000")
        self.assertEqual(orcamento.logradouro, "Praca da Se")
        self.assertEqual(orcamento.numero, "100")
        self.assertEqual(orcamento.bairro, "Se")
        self.assertEqual(orcamento.cidade, "Sao Paulo")
        self.assertEqual(orcamento.uf, "SP")
        self.assertIn("Praca da Se, 100", orcamento.endereco)

    @patch("service.views.orcamentos.ViaCepService")
    def test_busca_endereco_por_cep(self, service_mock):
        service_mock.return_value.buscar_por_cep.return_value = EnderecoViaCep(
            cep="01001-000",
            logradouro="Praca da Se",
            bairro="Se",
            cidade="Sao Paulo",
            uf="SP",
            complemento="lado impar",
        )

        response = self.client.get(reverse("buscar_endereco_cep", args=["01001000"]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["endereco"]["logradouro"], "Praca da Se")
        self.assertEqual(payload["endereco"]["cidade"], "Sao Paulo")

    @patch("service.views.orcamentos.NominatimService")
    def test_busca_mapa_do_orcamento(self, service_mock):
        orcamento = Orcamento.objects.create(
            name="Cliente Mapa",
            email="mapa@teste.com",
            cep="01001-000",
            logradouro="Praca da Se",
            numero="100",
            bairro="Se",
            cidade="Sao Paulo",
            uf="SP",
            endereco="Praca da Se, 100 - Se, Sao Paulo - SP",
            quantidade=1,
            valor=120.0,
        )
        service_mock.return_value.geocodificar.return_value = LocalizacaoMapa(
            latitude=-23.55052,
            longitude=-46.633308,
            display_name="Praca da Se, Sao Paulo",
        )

        response = self.client.get(reverse("buscar_mapa_orcamento", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertTrue(payload["ok"])
        self.assertEqual(payload["localizacao"]["latitude"], -23.55052)
        self.assertEqual(payload["localizacao"]["longitude"], -46.633308)
        service_mock.return_value.geocodificar.assert_called_once()
        self.assertEqual(
            service_mock.return_value.geocodificar.call_args.kwargs["endereco"],
            "Praca da Se, 100, Se, Sao Paulo, SP, 01001-000",
        )

    def test_nominatim_tenta_variacoes_de_endereco(self):
        service = NominatimService()

        with patch.object(
            service,
            "_get_json",
            side_effect=[
                [],
                [],
                [
                    {
                        "lat": "-23.55052",
                        "lon": "-46.633308",
                        "display_name": "Rua localizada",
                    }
                ],
            ],
        ) as get_json_mock:
            localizacao = service.geocodificar(
                endereco="Rua Orlando Mohallen, 298 | Medicina | Itajubá - MG",
                cep="37502-118",
                logradouro="Rua Orlando Mohallen",
                numero="298",
                bairro="Medicina",
                cidade="Itajubá",
                uf="MG",
            )

        self.assertEqual(localizacao.latitude, -23.55052)
        self.assertEqual(get_json_mock.call_count, 3)

    def test_novo_orcamento_preseleciona_item_do_catalogo(self):
        response = self.client.get(f"{reverse('novo_orcamento')}?item={self.item_a.pk}")

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, self.item_a.name)
        self.assertContains(response, f'value="{self.item_a.pk}" selected')

    def test_edita_orcamento_e_recalcula_total(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Editar",
            email="editar@teste.com",
            telefone="11988887777",
            endereco="Rua Antiga, 10",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("editar_orcamento", args=[orcamento.pk]),
            {
                "name": "Cliente Editado",
                "email": "editado@teste.com",
                "telefone": "11911112222",
                "cep": "37502-118",
                "logradouro": "Rua Orlando Mohallen",
                "numero": "298",
                "complemento": "",
                "bairro": "Medicina",
                "cidade": "Itajuba",
                "uf": "mg",
                "descricao": "Orcamento atualizado",
                "quantidade": 2,
                "itens": [self.item_a.pk, self.item_b.pk],
            },
        )

        self.assertEqual(response.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.name, "Cliente Editado")
        self.assertEqual(orcamento.uf, "MG")
        self.assertEqual(orcamento.valor, 400.0)
        self.assertEqual(orcamento.itens.count(), 2)

    def test_vincula_cliente_existente_ao_orcamento(self):
        cliente = Cliente.objects.create(
            name="Cliente Existente",
            email="existente@teste.com",
        )
        orcamento = Orcamento.objects.create(
            name="Cliente Orcamento",
            email="orcamento@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("vincular_cliente_orcamento", args=[orcamento.pk]),
            {"cliente": cliente.pk},
        )

        self.assertEqual(response.status_code, 302)
        orcamento.refresh_from_db()
        self.assertEqual(orcamento.cliente, cliente)

    def test_vincula_cliente_existente_e_aprova_orcamento(self):
        cliente = Cliente.objects.create(
            name="Cliente Existente",
            email="existente@teste.com",
        )
        orcamento = Orcamento.objects.create(
            name="Cliente Orcamento",
            email="orcamento@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("vincular_cliente_orcamento", args=[orcamento.pk]),
            {"cliente": cliente.pk, "aprovar_orcamento": "1"},
        )

        self.assertEqual(response.status_code, 302)
        orcamento.refresh_from_db()
        self.assertTrue(orcamento.aprovado)
        self.assertEqual(orcamento.cliente, cliente)

    def test_vincula_cliente_existente_e_volta_para_aprovacao(self):
        cliente = Cliente.objects.create(
            name="Cliente Existente",
            email="existente@teste.com",
        )
        orcamento = Orcamento.objects.create(
            name="Cliente Orcamento",
            email="orcamento@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("vincular_cliente_orcamento", args=[orcamento.pk]),
            {"cliente": cliente.pk, "voltar_para_aprovacao": "1"},
        )

        self.assertRedirects(
            response,
            f"{reverse('orcamento_detalhe', args=[orcamento.pk])}?aprovar=1",
            fetch_redirect_response=False,
        )
        orcamento.refresh_from_db()
        self.assertFalse(orcamento.aprovado)
        self.assertEqual(orcamento.cliente, cliente)

    def test_nao_aprova_orcamento_sem_cliente_vinculado(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Concluir",
            email="concluir@teste.com",
            telefone="11988887777",
            endereco="Rua Concluir, 10",
            quantidade=1,
            valor=120.0,
            descricao="Teste de conclusao",
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("concluir_orcamento", args=[orcamento.pk]))

        self.assertRedirects(
            response,
            f"{reverse('orcamento_detalhe', args=[orcamento.pk])}?aprovar=1",
            fetch_redirect_response=False,
        )
        self.assertEqual(Cliente.objects.count(), 0)

        orcamento.refresh_from_db()
        self.assertFalse(orcamento.aprovado)
        self.assertIsNone(orcamento.cliente)

    def test_detalhe_mostra_cliente_ainda_nao_vinculado(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Sem Vinculo",
            email="sem-vinculo@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.get(reverse("orcamento_detalhe", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Ainda nao vinculado")

    def test_aprova_orcamento_com_cliente_vinculado(self):
        cliente = Cliente.objects.create(
            name="Cliente Vinculado",
            email="vinculado@teste.com",
        )
        orcamento = Orcamento.objects.create(
            name="Cliente Concluir",
            email="concluir@teste.com",
            telefone="11988887777",
            endereco="Rua Concluir, 10",
            quantidade=1,
            valor=120.0,
            descricao="Teste de conclusao",
            cliente=cliente,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("concluir_orcamento", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 302)
        orcamento.refresh_from_db()
        self.assertTrue(orcamento.aprovado)
        self.assertEqual(orcamento.cliente, cliente)

    def test_cadastra_cliente_do_orcamento_sem_concluir(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Cadastrado",
            email="cadastrado@teste.com",
            telefone="11988887777",
            endereco="Rua Cadastro, 10",
            quantidade=1,
            valor=120.0,
            descricao="Teste de cadastro",
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("cadastrar_cliente_orcamento", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cliente.objects.count(), 1)

        orcamento.refresh_from_db()
        cliente = Cliente.objects.get()
        self.assertFalse(orcamento.aprovado)
        self.assertEqual(orcamento.cliente, cliente)
        self.assertEqual(cliente.email, "cadastrado@teste.com")

    def test_cadastra_cliente_do_orcamento_e_volta_para_aprovacao(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Pre Aprovacao",
            email="pre-aprovacao@teste.com",
            telefone="11988887777",
            endereco="Rua Pre Aprovacao, 10",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("cadastrar_cliente_orcamento", args=[orcamento.pk]),
            {"voltar_para_aprovacao": "1"},
        )

        self.assertRedirects(
            response,
            f"{reverse('orcamento_detalhe', args=[orcamento.pk])}?aprovar=1",
            fetch_redirect_response=False,
        )
        orcamento.refresh_from_db()
        self.assertFalse(orcamento.aprovado)
        self.assertIsNotNone(orcamento.cliente)

    def test_cadastra_cliente_do_orcamento_e_aprova(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Aprovado Modal",
            email="modal@teste.com",
            telefone="11988887777",
            endereco="Rua Modal, 10",
            quantidade=1,
            valor=120.0,
            descricao="Teste de aprovacao pelo modal",
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("cadastrar_cliente_orcamento", args=[orcamento.pk]),
            {"aprovar_orcamento": "1"},
        )

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cliente.objects.count(), 1)

        orcamento.refresh_from_db()
        cliente = Cliente.objects.get()
        self.assertTrue(orcamento.aprovado)
        self.assertEqual(orcamento.cliente, cliente)
        self.assertEqual(cliente.email, "modal@teste.com")

    def test_aprova_orcamento_e_cria_cliente_por_rota_legada(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Aprovado",
            email="aprovado@teste.com",
            telefone="11988887777",
            endereco="Rua Aprovada, 10",
            quantidade=1,
            valor=120.0,
            descricao="Teste de aprovacao",
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(reverse("aprovar_orcamento", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 302)
        self.assertEqual(Cliente.objects.count(), 1)

        orcamento.refresh_from_db()
        cliente = Cliente.objects.get()
        self.assertTrue(orcamento.aprovado)
        self.assertEqual(orcamento.cliente, cliente)
        self.assertEqual(cliente.email, "aprovado@teste.com")

    def test_gera_pdf_do_orcamento(self):
        orcamento = Orcamento.objects.create(
            name="Cliente PDF",
            email="pdf@teste.com",
            telefone="11977776666",
            endereco="Rua PDF, 100",
            quantidade=1,
            valor=120.0,
            descricao="Teste de PDF",
        )
        orcamento.itens.set([self.item_a, self.item_b])

        response = self.client.get(reverse("gerar_orcamento_pdf", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertIn(f'orcamento-{orcamento.pk}.pdf', response["Content-Disposition"])
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_detalhe_exibe_modal_de_personalizacao_do_pdf(self):
        orcamento = Orcamento.objects.create(
            name="Cliente Modal PDF",
            email="modal-pdf@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.get(reverse("orcamento_detalhe", args=[orcamento.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Personalizar PDF")
        self.assertContains(response, 'name="pdf_phrase"')
        self.assertNotContains(response, 'name="pdf_logo"')

    def test_gera_pdf_personalizado_com_logo_e_frase(self):
        orcamento = Orcamento.objects.create(
            name="Cliente PDF Personalizado",
            email="pdf-personalizado@teste.com",
            quantidade=1,
            valor=120.0,
        )
        orcamento.itens.set([self.item_a])
        logo = SimpleUploadedFile(
            "logo.png",
            (
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01"
                b"\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
                b"\x00\x00\x00\rIDATx\x9cc\xf8\xff\xff?\x00\x05\xfe"
                b"\x02\xfeA\xe2%\xb3\x00\x00\x00\x00IEND\xaeB`\x82"
            ),
            content_type="image/png",
        )

        response = self.client.post(
            reverse("gerar_orcamento_pdf", args=[orcamento.pk]),
            {
                "pdf_brand": "Minha Empresa",
                "pdf_phrase": "Frase personalizada para o cliente.",
                "pdf_accent_color": "#14532D",
                "pdf_logo": logo,
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    def test_gera_pdf_com_muitos_itens_e_textos_longos(self):
        itens = []
        for index in range(14):
            itens.append(
                Service_catalog.objects.create(
                    name=f"Servico profissional com nome longo para validar quebra de linha {index}",
                    tipo="Higienizacao residencial especializada",
                    valor=75 + index,
                    descricao=(
                        "Descricao detalhada do procedimento, materiais, acabamento tecnico "
                        "e cuidados de execucao para nao estourar o layout do PDF."
                    ),
                    tecido="Suede premium com tratamento impermeabilizante",
                    tamanho="Grande",
                )
            )
        orcamento = Orcamento.objects.create(
            name="Cliente com nome muito longo para proposta comercial profissional",
            email="cliente-com-email-longo-para-pdf@teste.com",
            telefone="11999998888",
            endereco=(
                "Rua com endereco bastante extenso, 1234, complemento amplo, "
                "bairro central, cidade de teste - SP"
            ),
            quantidade=3,
            valor=sum(item.valor for item in itens) * 3,
            descricao="Mensagem final personalizada com texto maior para testar o bloco de observacoes.",
        )
        orcamento.itens.set(itens)

        response = self.client.post(
            reverse("gerar_orcamento_pdf", args=[orcamento.pk]),
            {
                "pdf_brand": "Empresa Profissional de Higienizacao e Conservacao",
                "pdf_phrase": (
                    "Obrigado pela oportunidade. Esta proposta foi preparada com cuidado "
                    "para atender os pontos tecnicos do servico solicitado."
                ),
                "pdf_accent_color": "#14532D",
            },
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))
        self.assertGreater(len(response.content), 3000)

    def test_cria_tecnico(self):
        response = self.client.post(
            reverse("novo_tecnico"),
            {
                "name": "Equipe A",
                "email": "equipe@teste.com",
                "telefone": "11912345678",
                "especialidade": "Sofas e tapetes",
                "ativo": "on",
                "observacoes": "Atende zona sul.",
            },
        )

        self.assertEqual(response.status_code, 302)
        tecnico = Tecnico.objects.get(name="Equipe A")
        self.assertTrue(tecnico.ativo)
        self.assertEqual(tecnico.especialidade, "Sofas e tapetes")

    def test_cria_os_a_partir_de_orcamento_com_tecnico(self):
        cliente = Cliente.objects.create(name="Cliente OS", email="os@teste.com")
        tecnico = Tecnico.objects.create(name="Equipe OS", ativo=True)
        orcamento = Orcamento.objects.create(
            name="Cliente OS",
            email="os@teste.com",
            endereco="Rua OS, 10",
            quantidade=1,
            valor=120.0,
            aprovado=True,
            cliente=cliente,
        )
        orcamento.itens.set([self.item_a])

        response = self.client.post(
            reverse("nova_os"),
            {
                "orcamento": orcamento.pk,
                "cliente": cliente.pk,
                "data_agendada": timezone.localdate().isoformat(),
                "hora_inicio": "09:00",
                "hora_fim": "11:00",
                "tecnico": tecnico.pk,
                "status": OrdemServico.Status.AGENDADA,
                "instrucoes": "Levar extratora.",
                "checklist": "Fotos antes e depois.",
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem = OrdemServico.objects.get(orcamento=orcamento)
        self.assertEqual(ordem.cliente, cliente)
        self.assertEqual(ordem.tecnico, tecnico)
        self.assertEqual(ordem.titulo, "Servico para Cliente OS")
        self.assertEqual(ordem.valor, 120.0)
        self.assertEqual(ordem.endereco, "Rua OS, 10")

    def test_cria_os_executada_pelo_administrador_sem_tecnico(self):
        response = self.client.post(
            reverse("nova_os"),
            {
                "titulo": "Servico feito pelo dono",
                "descricao": "Atendimento manual.",
                "endereco": "Rua Admin, 20",
                "data_agendada": timezone.localdate().isoformat(),
                "hora_inicio": "14:00",
                "administrador_executa": "on",
                "status": OrdemServico.Status.AGENDADA,
                "valor": "90.00",
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem = OrdemServico.objects.get(titulo="Servico feito pelo dono")
        self.assertTrue(ordem.administrador_executa)
        self.assertIsNone(ordem.tecnico)
        self.assertEqual(ordem.responsavel_nome, "Administrador / dono")

    def test_agenda_exibe_os_da_semana(self):
        ordem = OrdemServico.objects.create(
            titulo="OS na agenda",
            data_agendada=timezone.localdate(),
            hora_inicio="08:30",
            administrador_executa=True,
            valor=150.0,
        )

        response = self.client.get(reverse("agenda"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "OS na agenda")
        self.assertContains(response, ordem.get_status_display())

    def test_conclui_os_pelo_administrador(self):
        ordem = OrdemServico.objects.create(
            titulo="OS para concluir",
            data_agendada=timezone.localdate(),
            hora_inicio="10:00",
            administrador_executa=True,
            valor=150.0,
        )

        response = self.client.post(
            reverse("concluir_os", args=[ordem.pk]),
            {
                "status": OrdemServico.Status.CONCLUIDA,
                "checklist": "Servico executado.",
                "observacoes_execucao": "Cliente aprovou o resultado.",
            },
        )

        self.assertEqual(response.status_code, 302)
        ordem.refresh_from_db()
        self.assertEqual(ordem.status, OrdemServico.Status.CONCLUIDA)
        self.assertIsNotNone(ordem.data_conclusao)
        self.assertEqual(ordem.observacoes_execucao, "Cliente aprovou o resultado.")
