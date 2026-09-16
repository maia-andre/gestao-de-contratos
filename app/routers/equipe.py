from datetime import date

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MembroEquipe, PapelMembro
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["equipe"])

PAPEIS_VALIDOS = [
    "Gestor de Contratos",
    "Fiscal Técnico",
    "Fiscal Administrativo",
    "Chefe de Contratos",
]
GESTOR = "Gestor de Contratos"
PAPEIS_FISCAL = {"Fiscal Técnico", "Fiscal Administrativo"}

CAMPOS_OBRIGATORIOS = {
    "nome": "Nome",
    "matricula_cargo": "Matrícula/cargo",
    "lotacao": "Lotação",
    "data_designacao": "Data de designação",
}


def validar_membro(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    valores = {campo: (dados.get(campo) or "").strip() for campo in CAMPOS_OBRIGATORIOS}
    substituto = (dados.get("substituto") or "").strip()
    papeis = [p.strip() for p in (dados.get("papeis") or []) if p and p.strip()]

    for campo, rotulo in CAMPOS_OBRIGATORIOS.items():
        if not valores[campo]:
            erros.append(f"{rotulo} é obrigatório.")

    data_designacao = None
    if valores["data_designacao"]:
        try:
            data_designacao = date.fromisoformat(valores["data_designacao"])
        except ValueError:
            erros.append("Data de designação inválida.")

    if not papeis:
        erros.append("Selecione ao menos um papel.")
    else:
        invalidos = [p for p in papeis if p not in PAPEIS_VALIDOS]
        if invalidos:
            erros.append(f"Papel inválido: {', '.join(invalidos)}.")

    papeis_selecionados = set(papeis) & set(PAPEIS_VALIDOS)
    if GESTOR in papeis_selecionados and papeis_selecionados & PAPEIS_FISCAL:
        erros.append(
            "Um mesmo membro não pode acumular o papel de Gestor de Contratos "
            "com um papel de Fiscal (Técnico ou Administrativo) no mesmo contrato."
        )

    if erros:
        return erros, None

    return [], {
        "nome": valores["nome"],
        "matricula_cargo": valores["matricula_cargo"],
        "lotacao": valores["lotacao"],
        "data_designacao": data_designacao,
        "substituto": substituto or None,
        "papeis": papeis,
    }


def membro_para_valores(membro: MembroEquipe) -> dict:
    return {
        "nome": membro.nome,
        "matricula_cargo": membro.matricula_cargo,
        "lotacao": membro.lotacao,
        "data_designacao": membro.data_designacao.isoformat(),
        "substituto": membro.substituto or "",
        "papeis": [p.papel for p in membro.papeis],
    }


def buscar_membro_ou_404(contrato_id: int, membro_id: int, db: Session) -> MembroEquipe:
    membro = db.get(MembroEquipe, membro_id)
    if membro is None or membro.contrato_id != contrato_id:
        raise HTTPException(status_code=404, detail="Membro de equipe não encontrado.")
    return membro


async def dados_do_formulario_membro(
    nome: str = Form(""),
    matricula_cargo: str = Form(""),
    lotacao: str = Form(""),
    papeis: list[str] = Form([]),
    data_designacao: str = Form(""),
    substituto: str = Form(""),
) -> dict:
    return {
        "nome": nome,
        "matricula_cargo": matricula_cargo,
        "lotacao": lotacao,
        "papeis": papeis,
        "data_designacao": data_designacao,
        "substituto": substituto,
    }


@router.get("/{contrato_id}/equipe/novo")
def novo_membro_form(contrato_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    return templates.TemplateResponse(
        request,
        "equipe/form.html",
        {"erros": [], "valores": {}, "contrato": contrato, "papeis_validos": PAPEIS_VALIDOS},
    )


@router.post("/{contrato_id}/equipe")
def criar_membro(
    contrato_id: int,
    request: Request,
    dados: dict = Depends(dados_do_formulario_membro),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)

    erros, dados_validos = validar_membro(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "equipe/form.html",
            {"erros": erros, "valores": dados, "contrato": contrato, "papeis_validos": PAPEIS_VALIDOS},
            status_code=422,
        )

    papeis_selecionados = dados_validos.pop("papeis")
    membro = MembroEquipe(contrato_id=contrato_id, **dados_validos)
    membro.papeis = [PapelMembro(papel=p) for p in papeis_selecionados]
    db.add(membro)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}", status_code=303)


@router.get("/{contrato_id}/equipe/{membro_id}/editar")
def editar_membro_form(
    contrato_id: int, membro_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    membro = buscar_membro_ou_404(contrato_id, membro_id, db)
    return templates.TemplateResponse(
        request,
        "equipe/form.html",
        {
            "erros": [],
            "valores": membro_para_valores(membro),
            "contrato": contrato,
            "papeis_validos": PAPEIS_VALIDOS,
            "titulo": "Editar membro de equipe",
            "action": f"/contratos/{contrato_id}/equipe/{membro_id}/editar",
        },
    )


@router.post("/{contrato_id}/equipe/{membro_id}/editar")
def editar_membro(
    contrato_id: int,
    membro_id: int,
    request: Request,
    dados: dict = Depends(dados_do_formulario_membro),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    membro = buscar_membro_ou_404(contrato_id, membro_id, db)

    erros, dados_validos = validar_membro(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "equipe/form.html",
            {
                "erros": erros,
                "valores": dados,
                "contrato": contrato,
                "papeis_validos": PAPEIS_VALIDOS,
                "titulo": "Editar membro de equipe",
                "action": f"/contratos/{contrato_id}/equipe/{membro_id}/editar",
            },
            status_code=422,
        )

    papeis_selecionados = dados_validos.pop("papeis")
    for campo, valor in dados_validos.items():
        setattr(membro, campo, valor)
    membro.papeis = [PapelMembro(papel=p) for p in papeis_selecionados]
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}", status_code=303)


@router.post("/{contrato_id}/equipe/{membro_id}/remover")
def remover_membro(contrato_id: int, membro_id: int, db: Session = Depends(get_db)):
    buscar_contrato_ou_404(contrato_id, db)
    membro = buscar_membro_ou_404(contrato_id, membro_id, db)
    db.delete(membro)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}", status_code=303)
