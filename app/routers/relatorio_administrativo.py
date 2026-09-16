from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.checklist_documental import calcular_validade_certidao, checklist_completo_e_valido, garantir_itens_padrao
from app.conclusoes import (
    CONCLUSAO_IRREGULAR,
    CONCLUSAO_REGULAR,
    CONCLUSAO_REGULAR_COM_RESSALVAS,
    sugerir_conclusao_administrativa,
)
from app.database import get_db
from app.divergencias import calcular_divergencias
from app.models_fiscalizacao import (
    ConclusaoAdministrativa,
    CpfConhecido,
    ItemChecklistDocumental,
    ItemFolha,
    Terceirizado,
)
from app.parametros import carregar_parametros_atuais
from app.routers.competencias import buscar_competencia_ou_404
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["relatorio-administrativo"])

CONCLUSOES_VALIDAS = {
    CONCLUSAO_REGULAR: "Regular",
    CONCLUSAO_REGULAR_COM_RESSALVAS: "Regular com ressalvas",
    CONCLUSAO_IRREGULAR: "Irregular",
}


def _montar_contexto(contrato, competencia, db: Session) -> dict:
    itens_folha = db.query(ItemFolha).filter_by(competencia_id=competencia.id).order_by(ItemFolha.nome).all()
    terceirizados = db.query(Terceirizado).filter_by(contrato_id=contrato.id).all()
    conhecidos = db.query(CpfConhecido).filter_by(contrato_id=contrato.id).all()
    cpfs_conhecidos = {
        c.cpf: (c.competencia_referencia_ano, c.competencia_referencia_mes) for c in conhecidos
    }
    parametros = carregar_parametros_atuais(db)
    divergencias = calcular_divergencias(
        itens_folha,
        terceirizados,
        competencia.ano,
        competencia.mes,
        parametros.faixas_inss,
        parametros.percentual_fgts,
        cpfs_conhecidos=cpfs_conhecidos,
    )

    garantir_itens_padrao(competencia.id, db)
    itens_checklist = (
        db.query(ItemChecklistDocumental)
        .filter_by(competencia_id=competencia.id)
        .order_by(ItemChecklistDocumental.id)
        .all()
    )
    hoje = date.today()
    linhas_checklist = [
        {"item": item, "validade": calcular_validade_certidao(item.chave, item.data_referencia, hoje)}
        for item in itens_checklist
    ]
    checklist_ok = checklist_completo_e_valido(itens_checklist, hoje)

    sugestao = sugerir_conclusao_administrativa(divergencias, checklist_ok)
    salva = db.query(ConclusaoAdministrativa).filter_by(competencia_id=competencia.id).first()
    conclusao_atual = salva.conclusao if salva is not None else sugestao

    return {
        "contrato": contrato,
        "competencia": competencia,
        "divergencias": divergencias,
        "linhas_checklist": linhas_checklist,
        "sugestao": sugestao,
        "conclusao_atual": conclusao_atual,
        "conclusoes": CONCLUSOES_VALIDAS,
    }


@router.get("/{contrato_id}/competencias/{competencia_id}/relatorio-administrativo")
def ver_relatorio_administrativo(
    contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)

    tem_folha = db.query(ItemFolha).filter_by(competencia_id=competencia_id).first() is not None
    if not tem_folha:
        return templates.TemplateResponse(
            request,
            "relatorio_administrativo/bloqueado.html",
            {"contrato": contrato, "competencia": competencia},
            status_code=422,
        )

    contexto = _montar_contexto(contrato, competencia, db)
    return templates.TemplateResponse(request, "relatorio_administrativo/pagina.html", contexto)


@router.post("/{contrato_id}/competencias/{competencia_id}/relatorio-administrativo/conclusao")
def salvar_conclusao_administrativa(
    contrato_id: int,
    competencia_id: int,
    request: Request,
    conclusao: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)

    if conclusao not in CONCLUSOES_VALIDAS:
        tem_folha = db.query(ItemFolha).filter_by(competencia_id=competencia_id).first() is not None
        if not tem_folha:
            return templates.TemplateResponse(
                request,
                "relatorio_administrativo/bloqueado.html",
                {"contrato": contrato, "competencia": competencia},
                status_code=422,
            )
        contexto = _montar_contexto(contrato, competencia, db)
        contexto["erro"] = "Conclusão inválida: use regular, regular com ressalvas ou irregular."
        return templates.TemplateResponse(
            request, "relatorio_administrativo/pagina.html", contexto, status_code=422
        )

    salva = db.query(ConclusaoAdministrativa).filter_by(competencia_id=competencia_id).first()
    if salva is None:
        salva = ConclusaoAdministrativa(competencia_id=competencia_id, conclusao=conclusao)
        db.add(salva)
    else:
        salva.conclusao = conclusao
    db.commit()

    return RedirectResponse(
        url=f"/contratos/{contrato_id}/competencias/{competencia_id}/relatorio-administrativo",
        status_code=303,
    )
