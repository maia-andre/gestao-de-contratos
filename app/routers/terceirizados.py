from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models_fiscalizacao import Terceirizado
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates
from app.terceirizados import parsear_csv_lista_mestra, validar_terceirizado

router = APIRouter(prefix="/contratos", tags=["terceirizados"])


def buscar_terceirizado_ou_404(contrato_id: int, terceirizado_id: int, db: Session) -> Terceirizado:
    terceirizado = db.get(Terceirizado, terceirizado_id)
    if terceirizado is None or terceirizado.contrato_id != contrato_id:
        raise HTTPException(status_code=404, detail="Terceirizado não encontrado.")
    return terceirizado


@router.get("/{contrato_id}/terceirizados")
def listar_terceirizados(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    terceirizados = (
        db.query(Terceirizado).filter_by(contrato_id=contrato_id).order_by(Terceirizado.nome).all()
    )
    return templates.TemplateResponse(
        request,
        "terceirizados/lista.html",
        {"contrato": contrato, "terceirizados": terceirizados},
    )


@router.get("/{contrato_id}/terceirizados/novo")
def novo_terceirizado_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request,
        "terceirizados/form.html",
        {"contrato": contrato, "erros": [], "valores": {}, "titulo": "Cadastrar terceirizado"},
    )


@router.get("/{contrato_id}/terceirizados/importar")
def importar_terceirizados_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request, "terceirizados/importar.html", {"contrato": contrato, "erros": []}
    )


@router.post("/{contrato_id}/terceirizados")
def criar_terceirizado(
    contrato_id: int,
    request: Request,
    cpf: str = Form(""),
    nome: str = Form(""),
    cargo: str = Form(""),
    salario_base: str = Form(""),
    data_admissao: str = Form(""),
    data_desligamento: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    dados = {
        "cpf": cpf,
        "nome": nome,
        "cargo": cargo,
        "salario_base": salario_base,
        "data_admissao": data_admissao,
        "data_desligamento": data_desligamento,
    }
    erros, dados_validos = validar_terceirizado(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "terceirizados/form.html",
            {"contrato": contrato, "erros": erros, "valores": dados, "titulo": "Cadastrar terceirizado"},
            status_code=422,
        )

    terceirizado = Terceirizado(contrato_id=contrato_id, **dados_validos)
    db.add(terceirizado)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/terceirizados", status_code=303)


@router.post("/{contrato_id}/terceirizados/importar")
async def importar_terceirizados(
    contrato_id: int,
    request: Request,
    arquivo: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    conteudo_bytes = await arquivo.read()
    try:
        conteudo = conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return templates.TemplateResponse(
            request,
            "terceirizados/importar.html",
            {"contrato": contrato, "erros": ["Arquivo inválido ou corrompido."]},
            status_code=422,
        )

    validos, erros_linha = parsear_csv_lista_mestra(conteudo)

    for dados in validos:
        db.add(Terceirizado(contrato_id=contrato_id, **dados))
    if validos:
        db.commit()

    if erros_linha:
        return templates.TemplateResponse(
            request,
            "terceirizados/importar.html",
            {"contrato": contrato, "erros": erros_linha, "importados": len(validos)},
            status_code=207,
        )

    return RedirectResponse(url=f"/contratos/{contrato_id}/terceirizados", status_code=303)


@router.get("/{contrato_id}/terceirizados/{terceirizado_id}/editar")
def editar_terceirizado_form(
    contrato_id: int, terceirizado_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    terceirizado = buscar_terceirizado_ou_404(contrato_id, terceirizado_id, db)
    valores = {
        "cpf": terceirizado.cpf,
        "nome": terceirizado.nome,
        "cargo": terceirizado.cargo,
        "salario_base": str(terceirizado.salario_base),
        "data_admissao": terceirizado.data_admissao.isoformat(),
        "data_desligamento": terceirizado.data_desligamento.isoformat()
        if terceirizado.data_desligamento
        else "",
    }
    return templates.TemplateResponse(
        request,
        "terceirizados/form.html",
        {
            "contrato": contrato,
            "erros": [],
            "valores": valores,
            "titulo": "Editar terceirizado",
            "action": f"/contratos/{contrato_id}/terceirizados/{terceirizado_id}/editar",
        },
    )


@router.post("/{contrato_id}/terceirizados/{terceirizado_id}/editar")
def editar_terceirizado(
    contrato_id: int,
    terceirizado_id: int,
    request: Request,
    cpf: str = Form(""),
    nome: str = Form(""),
    cargo: str = Form(""),
    salario_base: str = Form(""),
    data_admissao: str = Form(""),
    data_desligamento: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    terceirizado = buscar_terceirizado_ou_404(contrato_id, terceirizado_id, db)

    dados = {
        "cpf": cpf,
        "nome": nome,
        "cargo": cargo,
        "salario_base": salario_base,
        "data_admissao": data_admissao,
        "data_desligamento": data_desligamento,
    }
    erros, dados_validos = validar_terceirizado(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "terceirizados/form.html",
            {
                "contrato": contrato,
                "erros": erros,
                "valores": dados,
                "titulo": "Editar terceirizado",
                "action": f"/contratos/{contrato_id}/terceirizados/{terceirizado_id}/editar",
            },
            status_code=422,
        )

    for campo, valor in dados_validos.items():
        setattr(terceirizado, campo, valor)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/terceirizados", status_code=303)


@router.post("/{contrato_id}/terceirizados/{terceirizado_id}/remover")
def remover_terceirizado(
    contrato_id: int, terceirizado_id: int, db: Session = Depends(get_db)
):
    buscar_contrato_ou_404(contrato_id, db)
    terceirizado = buscar_terceirizado_ou_404(contrato_id, terceirizado_id, db)
    db.delete(terceirizado)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/terceirizados", status_code=303)
