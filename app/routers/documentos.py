from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MembroEquipe
from app.routers.contratos import buscar_contrato_ou_404
from app.routers.reunioes import buscar_reuniao_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["documentos"])


def _membros_da_equipe(contrato_id: int, db: Session) -> list[MembroEquipe]:
    return (
        db.query(MembroEquipe)
        .filter_by(contrato_id=contrato_id)
        .order_by(MembroEquipe.nome)
        .all()
    )


@router.get("/{contrato_id}/reunioes/{reuniao_id}/convocacao")
def gerar_convocacao(
    contrato_id: int,
    reuniao_id: int,
    request: Request,
    emissor_id: int | None = None,
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    reuniao = buscar_reuniao_ou_404(contrato_id, reuniao_id, db)

    faltantes = []
    if not reuniao.hora:
        faltantes.append("hora")
    if not reuniao.local:
        faltantes.append("local")
    if faltantes:
        return templates.TemplateResponse(
            request,
            "documentos/convocacao_bloqueada.html",
            {"contrato": contrato, "reuniao": reuniao, "faltantes": faltantes},
            status_code=422,
        )

    membros = _membros_da_equipe(contrato_id, db)
    if emissor_id is None:
        return templates.TemplateResponse(
            request,
            "documentos/convocacao_selecionar.html",
            {"contrato": contrato, "reuniao": reuniao, "membros": membros},
        )

    emissor = next((m for m in membros if m.id == emissor_id), None)
    if emissor is None:
        raise HTTPException(
            status_code=404, detail="Emissor não encontrado na equipe deste contrato"
        )

    return templates.TemplateResponse(
        request,
        "documentos/convocacao.html",
        {"contrato": contrato, "reuniao": reuniao, "emissor": emissor, "hoje": date.today()},
    )


@router.get("/{contrato_id}/reunioes/{reuniao_id}/ata")
def gerar_ata(
    contrato_id: int, reuniao_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    reuniao = buscar_reuniao_ou_404(contrato_id, reuniao_id, db)

    # RN-01: uma entrada por linha do campo participantes vira um participante individual.
    participantes = [
        linha.strip() for linha in reuniao.participantes.splitlines() if linha.strip()
    ]

    return templates.TemplateResponse(
        request,
        "documentos/ata.html",
        {"contrato": contrato, "reuniao": reuniao, "participantes": participantes},
    )


@router.get("/{contrato_id}/termo-designacao")
def gerar_termo_designacao(
    contrato_id: int,
    request: Request,
    autoridade_nome: str = "",
    autoridade_cargo: str = "",
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    membros = _membros_da_equipe(contrato_id, db)

    if not membros:
        return templates.TemplateResponse(
            request,
            "documentos/termo_designacao_bloqueado.html",
            {"contrato": contrato},
            status_code=422,
        )

    autoridade_nome = autoridade_nome.strip()
    autoridade_cargo = autoridade_cargo.strip()
    formulario_enviado = "autoridade_nome" in request.query_params

    if not autoridade_nome or not autoridade_cargo:
        erros = []
        if formulario_enviado:
            if not autoridade_nome:
                erros.append("Nome da autoridade signatária é obrigatório.")
            if not autoridade_cargo:
                erros.append("Cargo da autoridade signatária é obrigatório.")
        return templates.TemplateResponse(
            request,
            "documentos/termo_designacao_selecionar.html",
            {
                "contrato": contrato,
                "erros": erros,
                "valores": {"autoridade_nome": autoridade_nome, "autoridade_cargo": autoridade_cargo},
            },
            status_code=422 if erros else 200,
        )

    return templates.TemplateResponse(
        request,
        "documentos/termo_designacao.html",
        {
            "contrato": contrato,
            "membros": membros,
            "autoridade_nome": autoridade_nome,
            "autoridade_cargo": autoridade_cargo,
            "hoje": date.today(),
        },
    )
