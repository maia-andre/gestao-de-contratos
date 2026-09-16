from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from app.divergencias import calcular_divergencias

FAIXAS = [
    (Decimal("1621.00"), Decimal("0.0750")),
    (Decimal("2902.84"), Decimal("0.0900")),
    (Decimal("4354.27"), Decimal("0.1200")),
    (Decimal("8475.55"), Decimal("0.1400")),
]
PERCENTUAL_FGTS = Decimal("0.08")


@dataclass
class TerceirizadoFake:
    cpf: str
    nome: str
    data_desligamento: date | None = None


@dataclass
class ItemFolhaFake:
    cpf: str
    nome: str
    base_inss: Decimal
    base_fgts: Decimal
    inss_descontado: Decimal
    fgts_depositado: Decimal


def test_sem_divergencia_quando_tudo_bate():
    terceirizados = [TerceirizadoFake(cpf="11111111111", nome="Maria Silva")]
    itens = [
        ItemFolhaFake(
            cpf="11111111111",
            nome="Maria Silva",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("75.00"),
            fgts_depositado=Decimal("80.00"),
        )
    ]
    divergencias = calcular_divergencias(itens, terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert divergencias == []


def test_ce06_diferenca_dentro_da_tolerancia_nao_gera_divergencia():
    terceirizados = [TerceirizadoFake(cpf="11111111111", nome="Maria Silva")]
    itens = [
        ItemFolhaFake(
            cpf="11111111111",
            nome="Maria Silva",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("75.00"),
            fgts_depositado=Decimal("80.01"),  # 0,01 acima do esperado (80.00)
        )
    ]
    divergencias = calcular_divergencias(itens, terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert divergencias == []


def test_req16_diferenca_acima_da_tolerancia_gera_divergencia_de_valor():
    terceirizados = [TerceirizadoFake(cpf="11111111111", nome="Maria Silva")]
    itens = [
        ItemFolhaFake(
            cpf="11111111111",
            nome="Maria Silva",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("75.00"),
            fgts_depositado=Decimal("70.00"),  # esperado 80.00
        )
    ]
    divergencias = calcular_divergencias(itens, terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "valor_fgts"
    assert divergencias[0].cpf == "11111111111"


def test_req17_cpf_ativo_ausente_da_folha_gera_divergencia_de_ausencia():
    terceirizados = [TerceirizadoFake(cpf="11111111111", nome="Maria Silva")]
    divergencias = calcular_divergencias([], terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "ausencia"


def test_ce03_desligado_antes_da_competencia_nao_gera_divergencia_de_ausencia():
    terceirizados = [
        TerceirizadoFake(cpf="11111111111", nome="Maria Silva", data_desligamento=date(2026, 4, 15))
    ]
    divergencias = calcular_divergencias([], terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert divergencias == []


def test_ce04_desligado_dentro_do_mes_deve_constar_e_e_batido_normalmente():
    terceirizados = [
        TerceirizadoFake(cpf="11111111111", nome="Maria Silva", data_desligamento=date(2026, 5, 20))
    ]
    # ausente da folha -> ainda ativo no mês do desligamento, deve gerar divergência de ausência
    divergencias = calcular_divergencias([], terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "ausencia"


def test_req18_ce05_cpf_na_folha_ausente_da_lista_mestra_gera_divergencia():
    itens = [
        ItemFolhaFake(
            cpf="22222222222",
            nome="Fora Da Lista",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("75.00"),
            fgts_depositado=Decimal("80.00"),
        )
    ]
    divergencias = calcular_divergencias(itens, [], 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "fora_da_lista_mestra"


def test_req19_fgts_zerado_com_base_positiva_gera_divergencia_especifica():
    terceirizados = [TerceirizadoFake(cpf="11111111111", nome="Maria Silva")]
    itens = [
        ItemFolhaFake(
            cpf="11111111111",
            nome="Maria Silva",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("75.00"),
            fgts_depositado=Decimal("0.00"),
        )
    ]
    divergencias = calcular_divergencias(itens, terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "fgts_zerado"


def test_req19_inss_zerado_com_base_positiva_gera_divergencia_especifica():
    terceirizados = [TerceirizadoFake(cpf="11111111111", nome="Maria Silva")]
    itens = [
        ItemFolhaFake(
            cpf="11111111111",
            nome="Maria Silva",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("0.00"),
            fgts_depositado=Decimal("80.00"),
        )
    ]
    divergencias = calcular_divergencias(itens, terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "inss_zerado"


def test_multiplas_divergencias_no_mesmo_batimento():
    terceirizados = [
        TerceirizadoFake(cpf="11111111111", nome="Maria Silva"),  # ausente da folha
    ]
    itens = [
        ItemFolhaFake(
            cpf="22222222222",
            nome="Fora Da Lista",
            base_inss=Decimal("1000.00"),
            base_fgts=Decimal("1000.00"),
            inss_descontado=Decimal("75.00"),
            fgts_depositado=Decimal("80.00"),
        )
    ]
    divergencias = calcular_divergencias(itens, terceirizados, 2026, 5, FAIXAS, PERCENTUAL_FGTS)
    tipos = {d.tipo for d in divergencias}
    assert tipos == {"ausencia", "fora_da_lista_mestra"}


def _item_fora_da_lista(cpf="22222222222", nome="Fora Da Lista"):
    return ItemFolhaFake(
        cpf=cpf,
        nome=nome,
        base_inss=Decimal("1000.00"),
        base_fgts=Decimal("1000.00"),
        inss_descontado=Decimal("75.00"),
        fgts_depositado=Decimal("80.00"),
    )


def test_rn09_cpf_conhecido_suprime_divergencia_na_competencia_de_referencia():
    itens = [_item_fora_da_lista()]
    cpfs_conhecidos = {"22222222222": (2026, 5)}
    divergencias = calcular_divergencias(
        itens, [], 2026, 5, FAIXAS, PERCENTUAL_FGTS, cpfs_conhecidos=cpfs_conhecidos
    )
    assert divergencias == []


def test_rn09_cpf_conhecido_suprime_divergencia_em_competencia_posterior():
    itens = [_item_fora_da_lista()]
    cpfs_conhecidos = {"22222222222": (2026, 5)}
    divergencias = calcular_divergencias(
        itens, [], 2026, 6, FAIXAS, PERCENTUAL_FGTS, cpfs_conhecidos=cpfs_conhecidos
    )
    assert divergencias == []


def test_rn09_cpf_conhecido_nao_suprime_divergencia_em_competencia_anterior_a_referencia():
    itens = [_item_fora_da_lista()]
    cpfs_conhecidos = {"22222222222": (2026, 5)}
    divergencias = calcular_divergencias(
        itens, [], 2026, 4, FAIXAS, PERCENTUAL_FGTS, cpfs_conhecidos=cpfs_conhecidos
    )
    assert len(divergencias) == 1
    assert divergencias[0].tipo == "fora_da_lista_mestra"
