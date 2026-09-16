from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import ParametroFaixaINSS, ParametroGeral
from app.parametros import carregar_parametros_atuais
from app.templating import templates

router = APIRouter(tags=["parametros"])


def _parse_decimal(valor: str, rotulo: str, erros: list[str]) -> Decimal | None:
    try:
        return Decimal((valor or "").strip())
    except InvalidOperation:
        erros.append(f"{rotulo} inválido.")
        return None


@router.get("/parametros")
def ver_parametros(request: Request, db: Session = Depends(get_db)):
    parametros = carregar_parametros_atuais(db)
    return templates.TemplateResponse(
        request, "parametros/form.html", {"parametros": parametros, "erros": []}
    )


@router.post("/parametros")
def salvar_parametros(
    request: Request,
    limite_1: str = Form(""),
    aliquota_1: str = Form(""),
    limite_2: str = Form(""),
    aliquota_2: str = Form(""),
    limite_3: str = Form(""),
    aliquota_3: str = Form(""),
    limite_4: str = Form(""),
    aliquota_4: str = Form(""),
    percentual_fgts: str = Form(""),
    db: Session = Depends(get_db),
):
    parametros_atuais = carregar_parametros_atuais(db)

    erros: list[str] = []
    limites = [
        _parse_decimal(limite_1, "Limite da faixa 1", erros),
        _parse_decimal(limite_2, "Limite da faixa 2", erros),
        _parse_decimal(limite_3, "Limite da faixa 3", erros),
        _parse_decimal(limite_4, "Limite da faixa 4", erros),
    ]
    aliquotas = [
        _parse_decimal(aliquota_1, "Alíquota da faixa 1", erros),
        _parse_decimal(aliquota_2, "Alíquota da faixa 2", erros),
        _parse_decimal(aliquota_3, "Alíquota da faixa 3", erros),
        _parse_decimal(aliquota_4, "Alíquota da faixa 4", erros),
    ]
    novo_percentual_fgts = _parse_decimal(percentual_fgts, "Percentual de FGTS", erros)

    for indice, aliquota in enumerate(aliquotas, start=1):
        if aliquota is not None and not (Decimal("0") <= aliquota <= Decimal("1")):
            erros.append(f"Alíquota da faixa {indice} deve estar entre 0 e 1.")

    if novo_percentual_fgts is not None and not (
        Decimal("0") <= novo_percentual_fgts <= Decimal("1")
    ):
        erros.append("Percentual de FGTS deve estar entre 0 e 1.")

    if all(limite is not None for limite in limites):
        if not (limites[0] < limites[1] < limites[2] < limites[3]):
            erros.append("Os limites das faixas devem estar em ordem crescente.")

    if erros:
        return templates.TemplateResponse(
            request,
            "parametros/form.html",
            {"parametros": parametros_atuais, "erros": erros},
            status_code=422,
        )

    faixas = db.query(ParametroFaixaINSS).order_by(ParametroFaixaINSS.ordem).all()
    for faixa, limite, aliquota in zip(faixas, limites, aliquotas):
        faixa.limite_superior = limite
        faixa.aliquota = aliquota

    geral = db.query(ParametroGeral).first()
    geral.percentual_fgts = novo_percentual_fgts

    db.commit()
    return RedirectResponse(url="/parametros", status_code=303)
