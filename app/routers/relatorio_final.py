from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import (
    Competencia,
    ConclusaoAdministrativa,
    Ocorrencia,
    RecebimentoProvisorio,
    RelatorioTecnico,
    Reuniao,
)
from app.models_gestor import ESTADO_ADITIVO_ASSINADO, CicloProrrogacao, RelatorioFinal
from app.routers.contratos import buscar_contrato_ou_404
from app.routers.prorrogacao import gestor_unico, membros_da_equipe
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["relatorio-final"])

CONCEITOS = {
    "alcancados": "Objetivos alcançados",
    "parcialmente": "Objetivos parcialmente alcançados",
    "nao_alcancados": "Objetivos não alcançados",
}

GRAVIDADES = ["leve", "média", "grave"]


def _relatorio_do_contrato(contrato_id: int, db: Session) -> RelatorioFinal | None:
    return db.query(RelatorioFinal).filter_by(contrato_id=contrato_id).first()


def _resumo_execucao(contrato_id: int, db: Session) -> dict:
    competencias = (
        db.query(Competencia)
        .filter_by(contrato_id=contrato_id)
        .order_by(Competencia.ano, Competencia.mes)
        .all()
    )
    linhas_competencias = []
    recebimentos = []
    for comp in competencias:
        tecnico = db.query(RelatorioTecnico).filter_by(competencia_id=comp.id).first()
        administrativa = (
            db.query(ConclusaoAdministrativa).filter_by(competencia_id=comp.id).first()
        )
        linhas_competencias.append(
            {
                "rotulo": f"{comp.mes:02d}/{comp.ano}",
                "conclusao_tecnica": tecnico.conclusao if tecnico else None,
                "conclusao_administrativa": administrativa.conclusao if administrativa else None,
            }
        )
        recebimento = (
            db.query(RecebimentoProvisorio).filter_by(competencia_id=comp.id).first()
        )
        if recebimento:
            recebimentos.append(
                {
                    "competencia": f"{comp.mes:02d}/{comp.ano}",
                    "data": recebimento.data,
                    "decisao": recebimento.decisao,
                }
            )

    ocorrencias = db.query(Ocorrencia).filter_by(contrato_id=contrato_id).all()
    ocorrencias_por_gravidade = {
        gravidade: sum(1 for o in ocorrencias if o.gravidade == gravidade)
        for gravidade in GRAVIDADES
    }

    return {
        "total_reunioes": db.query(Reuniao).filter_by(contrato_id=contrato_id).count(),
        "competencias": linhas_competencias,
        "ocorrencias_por_gravidade": ocorrencias_por_gravidade,
        "total_ocorrencias": len(ocorrencias),
        "recebimentos": recebimentos,
    }


def _historico_prorrogacoes(contrato_id: int, db: Session) -> list[CicloProrrogacao]:
    return (
        db.query(CicloProrrogacao)
        .filter_by(contrato_id=contrato_id, estado=ESTADO_ADITIVO_ASSINADO)
        .order_by(CicloProrrogacao.id)
        .all()
    )


@router.get("/{contrato_id}/relatorio-final")
def relatorio_final_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    relatorio = _relatorio_do_contrato(contrato_id, db)
    valores = {
        "conceito": relatorio.conceito if relatorio else "",
        "justificativa": relatorio.justificativa if relatorio else "",
        "licoes": (relatorio.licoes if relatorio else "") or "",
    }
    return templates.TemplateResponse(
        request,
        "relatorio_final/form.html",
        {"contrato": contrato, "erros": [], "valores": valores, "conceitos": CONCEITOS},
    )


@router.post("/{contrato_id}/relatorio-final")
def salvar_relatorio_final(
    contrato_id: int,
    request: Request,
    conceito: str = Form(""),
    justificativa: str = Form(""),
    licoes: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    erros: list[str] = []
    justificativa = justificativa.strip()
    licoes = licoes.strip()
    if conceito not in CONCEITOS:
        erros.append("Conceito do parecer inválido.")
    if not justificativa:
        erros.append("Justificativa do parecer é obrigatória.")

    if erros:
        return templates.TemplateResponse(
            request,
            "relatorio_final/form.html",
            {
                "contrato": contrato,
                "erros": erros,
                "valores": {"conceito": conceito, "justificativa": justificativa, "licoes": licoes},
                "conceitos": CONCEITOS,
            },
            status_code=422,
        )

    relatorio = _relatorio_do_contrato(contrato_id, db)
    if relatorio is None:
        relatorio = RelatorioFinal(contrato_id=contrato_id)
        db.add(relatorio)
    relatorio.conceito = conceito
    relatorio.justificativa = justificativa
    # RN-11: dados persistidos e editáveis; o documento renderiza sempre o conteúdo atual.
    relatorio.licoes = licoes or None
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/relatorio-final", status_code=303)


@router.get("/{contrato_id}/relatorio-final/documento")
def gerar_relatorio_final(
    contrato_id: int,
    request: Request,
    emissor_id: int | None = None,
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    relatorio = _relatorio_do_contrato(contrato_id, db)
    membros = membros_da_equipe(contrato_id, db)

    if relatorio is None:
        # CE-09: sem parecer registrado não há relatório a emitir.
        return templates.TemplateResponse(
            request,
            "relatorio_final/bloqueado.html",
            {
                "contrato": contrato,
                "motivo": "registre o parecer sobre a consecução dos objetivos primeiro",
                "acao_url": f"/contratos/{contrato.id}/relatorio-final",
                "acao_rotulo": "Registrar parecer",
            },
            status_code=422,
        )

    if not membros:
        # CE-03: sem equipe não há emissor possível.
        return templates.TemplateResponse(
            request,
            "relatorio_final/bloqueado.html",
            {
                "contrato": contrato,
                "motivo": "este contrato ainda não tem equipe cadastrada",
                "acao_url": f"/contratos/{contrato.id}/equipe/novo",
                "acao_rotulo": "Adicionar membro de equipe",
            },
            status_code=422,
        )

    if emissor_id is None:
        return templates.TemplateResponse(
            request,
            "relatorio_final/selecionar.html",
            {
                "contrato": contrato,
                "membros": membros,
                "preselecionado": gestor_unico(membros),
            },
        )

    emissor = next((m for m in membros if m.id == emissor_id), None)
    if emissor is None:
        raise HTTPException(
            status_code=404, detail="Emissor não encontrado na equipe deste contrato"
        )

    historico = _historico_prorrogacoes(contrato_id, db)
    vigencia_fim_original = (
        historico[0].vigencia_fim_anterior if historico else contrato.vigencia_fim
    )
    return templates.TemplateResponse(
        request,
        "relatorio_final/documento.html",
        {
            "contrato": contrato,
            "relatorio": relatorio,
            "conceito_rotulo": CONCEITOS[relatorio.conceito],
            "membros": membros,
            "emissor": emissor,
            "historico": historico,
            "vigencia_fim_original": vigencia_fim_original,
            "resumo": _resumo_execucao(contrato_id, db),
            "hoje": date.today(),
        },
    )
