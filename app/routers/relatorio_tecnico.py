from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.conclusao_tecnica import (
    CONCLUSAO_IRREGULAR,
    CONCLUSAO_REGULAR,
    CONCLUSAO_REGULAR_COM_RESSALVAS,
    sugerir_conclusao_tecnica,
)
from app.database import get_db
from app.models import MembroEquipe, PapelMembro
from app.models_fiscalizacao import Ocorrencia, PendenciaPreOS, RecebimentoProvisorio, RelatorioTecnico
from app.pendencias_pre_os import garantir_itens_padrao, todas_ok
from app.routers.competencias import buscar_competencia_ou_404
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["relatorio-tecnico"])

CONCLUSOES_VALIDAS = {
    CONCLUSAO_REGULAR: "Regular",
    CONCLUSAO_REGULAR_COM_RESSALVAS: "Regular com ressalvas",
    CONCLUSAO_IRREGULAR: "Irregular",
}


def _fiscais_tecnicos(contrato_id: int, db: Session) -> list[MembroEquipe]:
    return (
        db.query(MembroEquipe)
        .join(PapelMembro)
        .filter(MembroEquipe.contrato_id == contrato_id, PapelMembro.papel == "Fiscal Técnico")
        .order_by(MembroEquipe.nome)
        .all()
    )


def _sugestao_atual(contrato_id: int, competencia, db: Session) -> str:
    ocorrencias_do_mes = (
        db.query(Ocorrencia)
        .filter_by(contrato_id=contrato_id)
        .all()
    )
    ocorrencias_do_mes = [
        o for o in ocorrencias_do_mes if o.data.year == competencia.ano and o.data.month == competencia.mes
    ]
    recebimento = db.query(RecebimentoProvisorio).filter_by(competencia_id=competencia.id).first()
    decisao = recebimento.decisao if recebimento is not None else None

    garantir_itens_padrao(contrato_id, db)
    pendencias = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).all()

    return sugerir_conclusao_tecnica(ocorrencias_do_mes, decisao, todas_ok(pendencias))


def _montar_contexto(contrato, competencia, db: Session) -> dict:
    sugestao = _sugestao_atual(contrato.id, competencia, db)
    salvo = db.query(RelatorioTecnico).filter_by(competencia_id=competencia.id).first()

    if salvo is not None:
        valores = {
            "avaliacao": salvo.avaliacao,
            "conclusao": salvo.conclusao,
            "fiscal_responsavel_id": salvo.fiscal_responsavel_id,
            "data_ateste": salvo.data_ateste.isoformat(),
        }
    else:
        valores = {
            "avaliacao": "",
            "conclusao": sugestao,
            "fiscal_responsavel_id": None,
            "data_ateste": "",
        }

    return {
        "contrato": contrato,
        "competencia": competencia,
        "sugestao": sugestao,
        "conclusoes": CONCLUSOES_VALIDAS,
        "fiscais": _fiscais_tecnicos(contrato.id, db),
        "valores": valores,
        "salvo": salvo,
    }


@router.get("/{contrato_id}/competencias/{competencia_id}/relatorio-tecnico")
def ver_relatorio_tecnico(
    contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    contexto = _montar_contexto(contrato, competencia, db)
    return templates.TemplateResponse(request, "relatorio_tecnico/pagina.html", contexto)


@router.post("/{contrato_id}/competencias/{competencia_id}/relatorio-tecnico")
def salvar_relatorio_tecnico(
    contrato_id: int,
    competencia_id: int,
    request: Request,
    avaliacao: str = Form(""),
    conclusao: str = Form(""),
    fiscal_responsavel_id: str = Form(""),
    data_ateste: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)

    erros: list[str] = []
    avaliacao = avaliacao.strip()
    if not avaliacao:
        erros.append("Avaliação é obrigatória.")
    if conclusao not in CONCLUSOES_VALIDAS:
        erros.append("Conclusão inválida.")

    fiscal = None
    if not fiscal_responsavel_id:
        erros.append("Selecione o fiscal responsável pelo ateste.")
    else:
        try:
            fiscal_id_int = int(fiscal_responsavel_id)
        except ValueError:
            erros.append("Fiscal responsável inválido.")
        else:
            fiscal = next(
                (f for f in _fiscais_tecnicos(contrato_id, db) if f.id == fiscal_id_int), None
            )
            if fiscal is None:
                erros.append(
                    "O fiscal responsável pelo ateste deve ser um membro da equipe com papel "
                    "Fiscal Técnico neste contrato."
                )

    data_ateste_str = data_ateste.strip()
    data_ateste_valor = None
    if not data_ateste_str:
        erros.append("Data do ateste é obrigatória.")
    else:
        try:
            data_ateste_valor = date.fromisoformat(data_ateste_str)
        except ValueError:
            erros.append("Data do ateste inválida.")

    if erros:
        contexto = _montar_contexto(contrato, competencia, db)
        contexto["valores"] = {
            "avaliacao": avaliacao,
            "conclusao": conclusao,
            "fiscal_responsavel_id": fiscal_responsavel_id,
            "data_ateste": data_ateste_str,
        }
        contexto["erros"] = erros
        return templates.TemplateResponse(
            request, "relatorio_tecnico/pagina.html", contexto, status_code=422
        )

    salvo = db.query(RelatorioTecnico).filter_by(competencia_id=competencia_id).first()
    if salvo is None:
        salvo = RelatorioTecnico(competencia_id=competencia_id)
        db.add(salvo)
    salvo.avaliacao = avaliacao
    salvo.conclusao = conclusao
    salvo.fiscal_responsavel_id = fiscal.id
    salvo.data_ateste = data_ateste_valor
    db.commit()

    return RedirectResponse(
        url=f"/contratos/{contrato_id}/competencias/{competencia_id}/relatorio-tecnico",
        status_code=303,
    )
