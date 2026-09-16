import calendar
from datetime import date

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_gestor import EntregaListagemSemestral
from app.prazos import STATUS_ATENCAO, STATUS_DENTRO_DO_PRAZO, STATUS_VENCIDO
from app.routers.contratos import buscar_contrato_ou_404
from app.routers.prorrogacao import obter_ou_criar_configuracao
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["listagem-semestral"])

STATUS_CUMPRIDO = "Cumprido"


def somar_meses(data_base: date, meses: int) -> date:
    # Dia fixado ao último dia do mês de destino quando necessário (ex.: 31/08 + 6m → 28/02).
    total = data_base.month - 1 + meses
    ano = data_base.year + total // 12
    mes = total % 12 + 1
    dia = min(data_base.day, calendar.monthrange(ano, mes)[1])
    return date(ano, mes, dia)


def datas_dos_marcos(vigencia_inicio: date, vigencia_fim: date) -> list[date]:
    # RN-05: marcos a cada 6 meses do início, enquanto caírem dentro da vigência (CE-05).
    marcos = []
    k = 1
    while True:
        marco = somar_meses(vigencia_inicio, 6 * k)
        if marco > vigencia_fim:
            break
        marcos.append(marco)
        k += 1
    return marcos


def marcos_com_status(
    vigencia_inicio: date,
    vigencia_fim: date,
    entregas: list[EntregaListagemSemestral],
    antecedencia_dias: int,
    hoje: date,
) -> list[dict]:
    linhas = []
    anterior = vigencia_inicio
    for marco in datas_dos_marcos(vigencia_inicio, vigencia_fim):
        entrega = next(
            (e for e in entregas if anterior < e.data <= marco),
            None,
        )
        if entrega is not None:
            status = STATUS_CUMPRIDO
        elif hoje > marco:
            status = STATUS_VENCIDO
        elif (marco - hoje).days <= antecedencia_dias:
            status = STATUS_ATENCAO
        else:
            status = STATUS_DENTRO_DO_PRAZO
        linhas.append({"marco": marco, "status": status, "entrega": entrega})
        anterior = marco
    return linhas


def _entregas(contrato_id: int, db: Session) -> list[EntregaListagemSemestral]:
    return (
        db.query(EntregaListagemSemestral)
        .filter_by(contrato_id=contrato_id)
        .order_by(EntregaListagemSemestral.data)
        .all()
    )


def _render(request: Request, contrato, db: Session, erros=None, status_code=200):
    configuracao = obter_ou_criar_configuracao(contrato.id, db)
    entregas = _entregas(contrato.id, db)
    marcos = marcos_com_status(
        contrato.vigencia_inicio,
        contrato.vigencia_fim,
        entregas,
        configuracao.antecedencia_semestral_dias,
        date.today(),
    )
    return templates.TemplateResponse(
        request,
        "listagem_semestral/pagina.html",
        {
            "contrato": contrato,
            "marcos": marcos,
            "entregas": entregas,
            "erros": erros or [],
        },
        status_code=status_code,
    )


@router.get("/{contrato_id}/listagem-semestral")
def listagem_semestral(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return _render(request, contrato, db)


@router.post("/{contrato_id}/listagem-semestral")
def registrar_entrega(
    contrato_id: int,
    request: Request,
    data: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    erros: list[str] = []
    data_entrega = None
    valor = (data or "").strip()
    if not valor:
        erros.append("Data da entrega é obrigatória.")
    else:
        try:
            data_entrega = date.fromisoformat(valor)
        except ValueError:
            erros.append("Data da entrega inválida.")

    if erros:
        return _render(request, contrato, db, erros, 422)

    db.add(
        EntregaListagemSemestral(
            contrato_id=contrato_id,
            data=data_entrega,
            observacao=observacao.strip() or None,
        )
    )
    db.commit()
    return RedirectResponse(
        url=f"/contratos/{contrato_id}/listagem-semestral", status_code=303
    )
