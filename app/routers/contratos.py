from datetime import date
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contrato
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["contratos"])

CAMPOS_OBRIGATORIOS = {
    "numero": "Número",
    "objeto": "Objeto",
    "contratada_razao_social": "Razão social da contratada",
    "contratada_cnpj": "CNPJ da contratada",
    "vigencia_inicio": "Data de início da vigência",
    "vigencia_fim": "Data de fim da vigência",
    "mao_de_obra_exclusiva": "Indicador de mão de obra exclusiva",
    "valor_global": "Valor global",
    "modalidade": "Modalidade de contratação",
}


def validar_contrato(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    valores = {campo: (dados.get(campo) or "").strip() for campo in CAMPOS_OBRIGATORIOS}

    for campo, rotulo in CAMPOS_OBRIGATORIOS.items():
        if not valores[campo]:
            erros.append(f"{rotulo} é obrigatório.")

    vigencia_inicio = None
    if valores["vigencia_inicio"]:
        try:
            vigencia_inicio = date.fromisoformat(valores["vigencia_inicio"])
        except ValueError:
            erros.append("Data de início da vigência inválida.")

    vigencia_fim = None
    if valores["vigencia_fim"]:
        try:
            vigencia_fim = date.fromisoformat(valores["vigencia_fim"])
        except ValueError:
            erros.append("Data de fim da vigência inválida.")

    if vigencia_inicio and vigencia_fim and vigencia_fim < vigencia_inicio:
        erros.append("A data de fim da vigência não pode ser anterior à data de início.")

    valor_global = None
    if valores["valor_global"]:
        try:
            valor_global = Decimal(valores["valor_global"])
        except InvalidOperation:
            erros.append("Valor global inválido.")
        else:
            if valor_global < 0:
                erros.append("O valor global não pode ser negativo.")

    mao_de_obra_exclusiva = None
    if valores["mao_de_obra_exclusiva"] and valores["mao_de_obra_exclusiva"] not in ("sim", "nao"):
        erros.append("Indicador de mão de obra exclusiva inválido.")
    elif valores["mao_de_obra_exclusiva"]:
        mao_de_obra_exclusiva = valores["mao_de_obra_exclusiva"] == "sim"

    if erros:
        return erros, None

    return [], {
        "numero": valores["numero"],
        "objeto": valores["objeto"],
        "contratada_razao_social": valores["contratada_razao_social"],
        "contratada_cnpj": valores["contratada_cnpj"],
        "vigencia_inicio": vigencia_inicio,
        "vigencia_fim": vigencia_fim,
        "mao_de_obra_exclusiva": mao_de_obra_exclusiva,
        "valor_global": valor_global,
        "modalidade": valores["modalidade"],
    }


def contrato_para_valores(contrato: Contrato) -> dict:
    return {
        "numero": contrato.numero,
        "objeto": contrato.objeto,
        "contratada_razao_social": contrato.contratada_razao_social,
        "contratada_cnpj": contrato.contratada_cnpj,
        "vigencia_inicio": contrato.vigencia_inicio.isoformat(),
        "vigencia_fim": contrato.vigencia_fim.isoformat(),
        "mao_de_obra_exclusiva": "sim" if contrato.mao_de_obra_exclusiva else "nao",
        "valor_global": str(contrato.valor_global),
        "modalidade": contrato.modalidade,
    }


def buscar_contrato_ou_404(contrato_id: int, db: Session) -> Contrato:
    contrato = db.get(Contrato, contrato_id)
    if contrato is None:
        raise HTTPException(status_code=404, detail="Contrato não encontrado.")
    return contrato


async def dados_do_formulario(
    numero: str = Form(""),
    objeto: str = Form(""),
    contratada_razao_social: str = Form(""),
    contratada_cnpj: str = Form(""),
    vigencia_inicio: str = Form(""),
    vigencia_fim: str = Form(""),
    mao_de_obra_exclusiva: str = Form(""),
    valor_global: str = Form(""),
    modalidade: str = Form(""),
) -> dict:
    return {
        "numero": numero,
        "objeto": objeto,
        "contratada_razao_social": contratada_razao_social,
        "contratada_cnpj": contratada_cnpj,
        "vigencia_inicio": vigencia_inicio,
        "vigencia_fim": vigencia_fim,
        "mao_de_obra_exclusiva": mao_de_obra_exclusiva,
        "valor_global": valor_global,
        "modalidade": modalidade,
    }


@router.get("")
def listar_contratos(request: Request, db: Session = Depends(get_db)):
    contratos = db.query(Contrato).order_by(Contrato.id).all()
    return templates.TemplateResponse(request, "contratos/lista.html", {"contratos": contratos})


@router.get("/novo")
def novo_contrato_form(request: Request):
    return templates.TemplateResponse(
        request,
        "contratos/form.html",
        {"erros": [], "valores": {}, "titulo": "Cadastrar contrato", "action": "/contratos"},
    )


@router.post("")
def criar_contrato(
    request: Request,
    dados: dict = Depends(dados_do_formulario),
    db: Session = Depends(get_db),
):
    erros, dados_validos = validar_contrato(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "contratos/form.html",
            {"erros": erros, "valores": dados, "titulo": "Cadastrar contrato", "action": "/contratos"},
            status_code=422,
        )

    contrato = Contrato(**dados_validos)
    db.add(contrato)
    db.commit()
    return RedirectResponse(url="/contratos", status_code=303)


@router.get("/{contrato_id}")
def detalhe_contrato(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    # Import local: prorrogacao importa buscar_contrato_ou_404 deste módulo.
    from app.routers.prorrogacao import obter_ou_criar_ciclo

    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    return templates.TemplateResponse(
        request, "contratos/detalhe.html", {"contrato": contrato, "ciclo": ciclo}
    )


@router.get("/{contrato_id}/editar")
def editar_contrato_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request,
        "contratos/form.html",
        {
            "erros": [],
            "valores": contrato_para_valores(contrato),
            "titulo": "Editar contrato",
            "action": f"/contratos/{contrato_id}/editar",
        },
    )


@router.post("/{contrato_id}/editar")
def editar_contrato(
    contrato_id: int,
    request: Request,
    dados: dict = Depends(dados_do_formulario),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    erros, dados_validos = validar_contrato(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "contratos/form.html",
            {
                "erros": erros,
                "valores": dados,
                "titulo": "Editar contrato",
                "action": f"/contratos/{contrato_id}/editar",
            },
            status_code=422,
        )

    for campo, valor in dados_validos.items():
        setattr(contrato, campo, valor)
    db.commit()
    return RedirectResponse(url="/contratos", status_code=303)
