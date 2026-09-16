from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import RecebimentoProvisorio
from app.routers.competencias import buscar_competencia_ou_404
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["recebimento-provisorio"])

DECISOES_VALIDAS = {
    "aceito": "Aceito",
    "aceito_com_ressalva": "Aceito com ressalva",
    "recusado": "Recusado",
}


def validar_recebimento(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    data_str = (dados.get("data") or "").strip()
    decisao = (dados.get("decisao") or "").strip()
    observacao = (dados.get("observacao") or "").strip()

    if not data_str:
        erros.append("Data é obrigatório.")
    if not decisao:
        erros.append("Decisão é obrigatório.")
    elif decisao not in DECISOES_VALIDAS:
        erros.append("Decisão inválida: use aceito, aceito com ressalva ou recusado.")

    data_recebimento = None
    if data_str:
        try:
            data_recebimento = date.fromisoformat(data_str)
        except ValueError:
            erros.append("Data inválida.")

    if decisao == "recusado" and not observacao:
        erros.append("Observação é obrigatória quando o recebimento é recusado.")

    if erros:
        return erros, None

    return [], {"data": data_recebimento, "decisao": decisao, "observacao": observacao or None}


@router.get("/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio")
def ver_recebimento_provisorio(
    contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    recebimento = (
        db.query(RecebimentoProvisorio).filter_by(competencia_id=competencia_id).first()
    )
    valores = {}
    if recebimento is not None:
        valores = {
            "data": recebimento.data.isoformat(),
            "decisao": recebimento.decisao,
            "observacao": recebimento.observacao or "",
        }
    return templates.TemplateResponse(
        request,
        "recebimento_provisorio/form.html",
        {
            "contrato": contrato,
            "competencia": competencia,
            "erros": [],
            "valores": valores,
            "decisoes": DECISOES_VALIDAS,
        },
    )


@router.post("/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio")
def salvar_recebimento_provisorio(
    contrato_id: int,
    competencia_id: int,
    request: Request,
    data: str = Form(""),
    decisao: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)

    dados = {"data": data, "decisao": decisao, "observacao": observacao}
    erros, dados_validos = validar_recebimento(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "recebimento_provisorio/form.html",
            {
                "contrato": contrato,
                "competencia": competencia,
                "erros": erros,
                "valores": dados,
                "decisoes": DECISOES_VALIDAS,
            },
            status_code=422,
        )

    recebimento = (
        db.query(RecebimentoProvisorio).filter_by(competencia_id=competencia_id).first()
    )
    if recebimento is None:
        recebimento = RecebimentoProvisorio(competencia_id=competencia_id, **dados_validos)
        db.add(recebimento)
    else:
        for campo, valor in dados_validos.items():
            setattr(recebimento, campo, valor)
    db.commit()
    return RedirectResponse(
        url=f"/contratos/{contrato_id}/competencias/{competencia_id}/recebimento-provisorio",
        status_code=303,
    )
