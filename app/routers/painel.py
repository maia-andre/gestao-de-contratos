from datetime import date

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.alertas import (
    alerta_certidao,
    alerta_notificacao,
    alerta_resposta,
    alertas_gfd_darf,
    relatorio_final_pendente,
)
from app.checklist_documental import VALIDADE_DIAS
from app.database import get_db
from app.models import Contrato
from app.models_fiscalizacao import Competencia, ItemChecklistDocumental
from app.models_gestor import (
    ESTADO_AGUARDANDO_NOTIFICACAO,
    ESTADO_NOTIFICACAO_ENVIADA,
    ESTADOS_FINAIS,
    RelatorioFinal,
)
from app.prazos import (
    STATUS_ATENCAO,
    STATUS_DENTRO_DO_PRAZO,
    STATUS_VENCIDO,
    dias_restantes,
    status_prorrogacao,
)
from app.routers.listagem_semestral import STATUS_CUMPRIDO, marcos_com_status
from app.routers.listagem_semestral import _entregas as entregas_semestrais
from app.routers.prorrogacao import (
    obter_ou_criar_ciclo,
    obter_ou_criar_configuracao,
    somar_dias_uteis,
)
from app.templating import templates

router = APIRouter(prefix="/painel", tags=["painel"])

CLASSE_STATUS = {
    STATUS_DENTRO_DO_PRAZO: "dentro-do-prazo",
    STATUS_ATENCAO: "atencao",
    STATUS_VENCIDO: "vencido",
}

ROTULOS_CERTIDAO = {"cndt": "CNDT", "crf_fgts": "CRF/FGTS"}


def _alertas_certidoes(contrato: Contrato, configuracao, hoje: date, db: Session) -> list[dict]:
    alertas = []
    for chave, rotulo in ROTULOS_CERTIDAO.items():
        item = (
            db.query(ItemChecklistDocumental)
            .join(Competencia, ItemChecklistDocumental.competencia_id == Competencia.id)
            .filter(
                Competencia.contrato_id == contrato.id,
                ItemChecklistDocumental.chave == chave,
                ItemChecklistDocumental.data_referencia.isnot(None),
            )
            .order_by(ItemChecklistDocumental.data_referencia.desc())
            .first()
        )
        data_referencia = item.data_referencia if item else None
        status, descricao = alerta_certidao(
            data_referencia,
            VALIDADE_DIAS[chave],
            configuracao.antecedencia_certidoes_dias,
            hoje,
        )
        if item is not None:
            url = f"/contratos/{contrato.id}/competencias/{item.competencia_id}/checklist"
        else:
            url = f"/contratos/{contrato.id}/competencias"
        alertas.append(
            {"rotulo": f"{rotulo} {descricao}", "status": status, "url": url}
        )
    return alertas


def _alertas_prorrogacao(contrato: Contrato, ciclo, configuracao, hoje: date) -> list[dict]:
    if ciclo.estado in ESTADOS_FINAIS:
        return []
    url = f"/contratos/{contrato.id}/prorrogacao"
    if ciclo.estado == ESTADO_AGUARDANDO_NOTIFICACAO:
        status, rotulo = alerta_notificacao(
            contrato.vigencia_fim, configuracao.antecedencia_notificacao_dias, hoje
        )
        return [{"rotulo": rotulo, "status": status, "url": url}]
    if ciclo.estado == ESTADO_NOTIFICACAO_ENVIADA:
        data_limite = somar_dias_uteis(
            ciclo.data_envio_notificacao, configuracao.prazo_resposta_dias_uteis
        )
        status, rotulo = alerta_resposta(data_limite, hoje)
        return [{"rotulo": rotulo, "status": status, "url": url}]
    return []


def _alertas_semestral(contrato: Contrato, configuracao, hoje: date, db: Session) -> list[dict]:
    marcos = marcos_com_status(
        contrato.vigencia_inicio,
        contrato.vigencia_fim,
        entregas_semestrais(contrato.id, db),
        configuracao.antecedencia_semestral_dias,
        hoje,
    )
    return [
        {
            "rotulo": f"Listagem semestral — marco {linha['marco'].strftime('%d/%m/%Y')}",
            "status": linha["status"],
            "url": f"/contratos/{contrato.id}/listagem-semestral",
        }
        for linha in marcos
        if linha["status"] in (STATUS_ATENCAO, STATUS_VENCIDO)
    ]


def _alertas_gfd(contrato: Contrato, configuracao, hoje: date, db: Session) -> list[dict]:
    competencias = db.query(Competencia).filter_by(contrato_id=contrato.id).all()
    situacao: dict[tuple[int, int], bool] = {}
    ids_por_mes: dict[tuple[int, int], int] = {}
    for comp in competencias:
        itens_ok = {
            item.chave: item.status == "ok"
            for item in db.query(ItemChecklistDocumental)
            .filter(
                ItemChecklistDocumental.competencia_id == comp.id,
                ItemChecklistDocumental.chave.in_(["gfd_paga", "darf_pago"]),
            )
            .all()
        }
        situacao[(comp.ano, comp.mes)] = bool(
            itens_ok.get("gfd_paga") and itens_ok.get("darf_pago")
        )
        ids_por_mes[(comp.ano, comp.mes)] = comp.id
    alertas = []
    for alerta in alertas_gfd_darf(
        contrato.vigencia_inicio,
        contrato.vigencia_fim,
        configuracao.dia_limite_gfd_darf,
        hoje,
        situacao,
    ):
        chave_mes = (alerta["ano"], alerta["mes"])
        if alerta["registrada"]:
            detalhe = "pendente"
            url = f"/contratos/{contrato.id}/competencias/{ids_por_mes[chave_mes]}/checklist"
        else:
            detalhe = "competência não registrada"
            url = f"/contratos/{contrato.id}/competencias"
        alertas.append(
            {
                "rotulo": f"GFD/DARF {alerta['mes']:02d}/{alerta['ano']} — {detalhe}",
                "status": alerta["status"],
                "url": url,
            }
        )
    return alertas


def _alerta_relatorio_final(contrato: Contrato, hoje: date, db: Session) -> list[dict]:
    tem_parecer = (
        db.query(RelatorioFinal).filter_by(contrato_id=contrato.id).first() is not None
    )
    if relatorio_final_pendente(contrato.vigencia_fim, tem_parecer, hoje):
        return [
            {
                "rotulo": "Relatório Final pendente",
                "status": STATUS_VENCIDO,
                "url": f"/contratos/{contrato.id}/relatorio-final",
            }
        ]
    return []


@router.get("")
def painel_prazos(request: Request, db: Session = Depends(get_db)):
    hoje = date.today()
    contratos = db.query(Contrato).order_by(Contrato.vigencia_fim).all()
    linhas = []
    for contrato in contratos:
        ciclo = obter_ou_criar_ciclo(contrato.id, db)
        configuracao = obter_ou_criar_configuracao(contrato.id, db)
        dias = dias_restantes(contrato.vigencia_fim, hoje)
        status = status_prorrogacao(dias)
        alertas = (
            _alertas_prorrogacao(contrato, ciclo, configuracao, hoje)
            + _alertas_certidoes(contrato, configuracao, hoje, db)
            + _alertas_semestral(contrato, configuracao, hoje, db)
            + _alertas_gfd(contrato, configuracao, hoje, db)
            + _alerta_relatorio_final(contrato, hoje, db)
        )
        for alerta in alertas:
            alerta["status_classe"] = CLASSE_STATUS[alerta["status"]]
        linhas.append(
            {
                "contrato": contrato,
                "dias_restantes": dias,
                "status": status,
                "status_classe": CLASSE_STATUS[status],
                "alertas": alertas,
            }
        )
    return templates.TemplateResponse(request, "painel/painel.html", {"linhas": linhas})