from fastapi import APIRouter, Depends, File, Form, Request, UploadFile
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.batimento import calcular_fgts_esperado, calcular_inss_esperado
from app.database import get_db
from app.divergencias import calcular_divergencias
from app.folha import parsear_csv_folha
from app.models_fiscalizacao import CpfConhecido, ItemFolha, Terceirizado
from app.parametros import carregar_parametros_atuais
from app.routers.competencias import buscar_competencia_ou_404
from app.routers.contratos import buscar_contrato_ou_404
from app.templating import templates

router = APIRouter(prefix="/contratos", tags=["folha"])


@router.get("/{contrato_id}/competencias/{competencia_id}/folha")
def ver_folha(contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    itens = db.query(ItemFolha).filter_by(competencia_id=competencia_id).order_by(ItemFolha.nome).all()

    parametros = carregar_parametros_atuais(db)
    linhas = []
    for item in itens:
        linhas.append(
            {
                "item": item,
                "fgts_esperado": calcular_fgts_esperado(item.base_fgts, parametros.percentual_fgts),
                "inss_esperado": calcular_inss_esperado(item.base_inss, parametros.faixas_inss),
            }
        )

    terceirizados = db.query(Terceirizado).filter_by(contrato_id=contrato_id).all()
    conhecidos = db.query(CpfConhecido).filter_by(contrato_id=contrato_id).all()
    cpfs_conhecidos = {
        c.cpf: (c.competencia_referencia_ano, c.competencia_referencia_mes) for c in conhecidos
    }
    divergencias = calcular_divergencias(
        itens,
        terceirizados,
        competencia.ano,
        competencia.mes,
        parametros.faixas_inss,
        parametros.percentual_fgts,
        cpfs_conhecidos=cpfs_conhecidos,
    )

    divergencias_fora_da_lista = [d for d in divergencias if d.tipo == "fora_da_lista_mestra"]
    outras_divergencias = [d for d in divergencias if d.tipo != "fora_da_lista_mestra"]

    return templates.TemplateResponse(
        request,
        "folha/lista.html",
        {
            "contrato": contrato,
            "competencia": competencia,
            "linhas": linhas,
            "divergencias": outras_divergencias,
            "divergencias_fora_da_lista": divergencias_fora_da_lista,
            "erros": [],
        },
    )


@router.get("/{contrato_id}/competencias/{competencia_id}/folha/importar")
def importar_folha_form(
    contrato_id: int, competencia_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)
    ja_existe = (
        db.query(ItemFolha).filter_by(competencia_id=competencia_id).first() is not None
    )
    return templates.TemplateResponse(
        request,
        "folha/importar.html",
        {"contrato": contrato, "competencia": competencia, "erros": [], "ja_existe": ja_existe},
    )


@router.post("/{contrato_id}/competencias/{competencia_id}/folha/importar")
async def importar_folha(
    contrato_id: int,
    competencia_id: int,
    request: Request,
    arquivo: UploadFile = File(...),
    confirmar_substituicao: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    competencia = buscar_competencia_ou_404(contrato_id, competencia_id, db)

    ja_existe = db.query(ItemFolha).filter_by(competencia_id=competencia_id).first() is not None
    if ja_existe and confirmar_substituicao != "sim":
        return templates.TemplateResponse(
            request,
            "folha/importar.html",
            {
                "contrato": contrato,
                "competencia": competencia,
                "erros": [
                    "Já existe uma folha importada para esta competência. "
                    "Confirme a substituição para importar um novo arquivo."
                ],
                "ja_existe": ja_existe,
            },
            status_code=422,
        )

    conteudo_bytes = await arquivo.read()
    try:
        conteudo = conteudo_bytes.decode("utf-8")
    except UnicodeDecodeError:
        return templates.TemplateResponse(
            request,
            "folha/importar.html",
            {
                "contrato": contrato,
                "competencia": competencia,
                "erros": ["Arquivo inválido ou corrompido."],
                "ja_existe": ja_existe,
            },
            status_code=422,
        )

    validos, erros_linha = parsear_csv_folha(conteudo)

    if ja_existe:
        db.query(ItemFolha).filter_by(competencia_id=competencia_id).delete()

    for dados in validos:
        db.add(ItemFolha(competencia_id=competencia_id, **dados))
    if validos or ja_existe:
        db.commit()

    if erros_linha:
        return templates.TemplateResponse(
            request,
            "folha/importar.html",
            {
                "contrato": contrato,
                "competencia": competencia,
                "erros": erros_linha,
                "importados": len(validos),
                "ja_existe": ja_existe,
            },
            status_code=207,
        )

    return RedirectResponse(
        url=f"/contratos/{contrato_id}/competencias/{competencia_id}/folha", status_code=303
    )
