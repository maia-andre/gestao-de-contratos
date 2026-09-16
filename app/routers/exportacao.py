import json
from datetime import date, time
from decimal import Decimal, InvalidOperation

from fastapi import APIRouter, Depends, File, Request, UploadFile
from fastapi.responses import RedirectResponse, Response
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Contrato, MembroEquipe, PapelMembro
from app.models_fiscalizacao import (
    Competencia,
    ConclusaoAdministrativa,
    CpfConhecido,
    ItemChecklistDocumental,
    ItemFolha,
    Ocorrencia,
    PendenciaPreOS,
    RecebimentoProvisorio,
    RelatorioTecnico,
    Reuniao,
    Terceirizado,
)
from app.models_gestor import (
    ROTULOS_ESTADO_CICLO,
    CicloProrrogacao,
    ConfiguracaoPrazos,
    EntregaListagemSemestral,
    RelatorioFinal,
)
from app.routers.contratos import buscar_contrato_ou_404
from app.routers.relatorio_final import CONCEITOS
from app.templating import templates

router = APIRouter(tags=["exportacao"])

CAMPOS_CONTRATO = [
    "numero",
    "objeto",
    "contratada_razao_social",
    "contratada_cnpj",
    "vigencia_inicio",
    "vigencia_fim",
    "mao_de_obra_exclusiva",
    "valor_global",
    "modalidade",
]
CAMPOS_MEMBRO = ["nome", "matricula_cargo", "lotacao", "data_designacao"]
CAMPOS_TERCEIRIZADO = ["cpf", "nome", "cargo", "salario_base", "data_admissao"]
CAMPOS_REUNIAO = ["data", "participantes", "resumo"]
CAMPOS_PENDENCIA = ["item", "status"]
CAMPOS_OCORRENCIA = ["data", "descricao", "gravidade"]
CAMPOS_CPF_CONHECIDO = [
    "cpf",
    "nome",
    "motivo",
    "competencia_referencia_ano",
    "competencia_referencia_mes",
]
CAMPOS_ITEM_FOLHA_STR = ["cpf", "nome", "cargo"]
CAMPOS_ITEM_FOLHA_DECIMAIS = [
    "salario_base",
    "total_vencimentos",
    "base_inss",
    "base_fgts",
    "inss_descontado",
    "fgts_depositado",
    "liquido",
]
CAMPOS_ITEM_CHECKLIST = ["chave", "rotulo", "status"]
CAMPOS_RECEBIMENTO = ["data", "decisao"]
CAMPOS_RELATORIO_TECNICO = ["avaliacao", "conclusao", "fiscal_responsavel_nome", "data_ateste"]
CAMPOS_CONFIGURACAO_PRAZOS = [
    "antecedencia_notificacao_dias",
    "prazo_resposta_dias_uteis",
    "antecedencia_certidoes_dias",
    "antecedencia_semestral_dias",
    "dia_limite_gfd_darf",
]
CAMPOS_CICLO_DATAS = [
    "data_envio_notificacao",
    "data_resposta",
    "data_registro_aditivo",
    "vigencia_fim_anterior",
    "nova_vigencia_fim",
    "data_area_acionada",
    "data_encerramento",
]

MENSAGEM_ARQUIVO_INVALIDO = "Arquivo inválido ou corrompido. Verifique se é um .json exportado por este sistema."


def terceirizado_para_exportacao(t: Terceirizado) -> dict:
    return {
        "cpf": t.cpf,
        "nome": t.nome,
        "cargo": t.cargo,
        "salario_base": str(t.salario_base),
        "data_admissao": t.data_admissao.isoformat(),
        "data_desligamento": t.data_desligamento.isoformat() if t.data_desligamento else None,
    }


def reuniao_para_exportacao(r: Reuniao) -> dict:
    return {
        "data": r.data.isoformat(),
        "hora": r.hora,
        "local": r.local,
        "participantes": r.participantes,
        "resumo": r.resumo,
    }


def pendencia_para_exportacao(p: PendenciaPreOS) -> dict:
    return {"item": p.item, "status": p.status}


def ocorrencia_para_exportacao(o: Ocorrencia) -> dict:
    return {"data": o.data.isoformat(), "descricao": o.descricao, "gravidade": o.gravidade}


def cpf_conhecido_para_exportacao(c: CpfConhecido) -> dict:
    return {
        "cpf": c.cpf,
        "nome": c.nome,
        "motivo": c.motivo,
        "competencia_referencia_ano": c.competencia_referencia_ano,
        "competencia_referencia_mes": c.competencia_referencia_mes,
    }


def item_folha_para_exportacao(i: ItemFolha) -> dict:
    return {
        "cpf": i.cpf,
        "nome": i.nome,
        "cargo": i.cargo,
        "salario_base": str(i.salario_base),
        "total_vencimentos": str(i.total_vencimentos),
        "base_inss": str(i.base_inss),
        "base_fgts": str(i.base_fgts),
        "inss_descontado": str(i.inss_descontado),
        "fgts_depositado": str(i.fgts_depositado),
        "liquido": str(i.liquido),
    }


def item_checklist_para_exportacao(i: ItemChecklistDocumental) -> dict:
    return {
        "chave": i.chave,
        "rotulo": i.rotulo,
        "status": i.status,
        "data_referencia": i.data_referencia.isoformat() if i.data_referencia else None,
    }


def competencia_para_exportacao(comp: Competencia, db: Session) -> dict:
    itens_folha = db.query(ItemFolha).filter_by(competencia_id=comp.id).order_by(ItemFolha.nome).all()
    checklist = (
        db.query(ItemChecklistDocumental)
        .filter_by(competencia_id=comp.id)
        .order_by(ItemChecklistDocumental.id)
        .all()
    )
    recebimento = db.query(RecebimentoProvisorio).filter_by(competencia_id=comp.id).first()
    conclusao_administrativa = db.query(ConclusaoAdministrativa).filter_by(competencia_id=comp.id).first()
    relatorio_tecnico = db.query(RelatorioTecnico).filter_by(competencia_id=comp.id).first()

    return {
        "ano": comp.ano,
        "mes": comp.mes,
        "relatorio_tecnico": (
            {
                "avaliacao": relatorio_tecnico.avaliacao,
                "conclusao": relatorio_tecnico.conclusao,
                "fiscal_responsavel_nome": relatorio_tecnico.fiscal_responsavel.nome,
                "data_ateste": relatorio_tecnico.data_ateste.isoformat(),
            }
            if relatorio_tecnico is not None
            else None
        ),
        "recebimento_provisorio": (
            {
                "data": recebimento.data.isoformat(),
                "decisao": recebimento.decisao,
                "observacao": recebimento.observacao,
            }
            if recebimento is not None
            else None
        ),
        "folha": [item_folha_para_exportacao(i) for i in itens_folha],
        "checklist_documental": [item_checklist_para_exportacao(i) for i in checklist],
        "conclusao_administrativa": (
            conclusao_administrativa.conclusao if conclusao_administrativa is not None else None
        ),
    }


def ciclo_para_exportacao(ciclo: CicloProrrogacao) -> dict:
    dados = {"estado": ciclo.estado, "teor_resposta": ciclo.teor_resposta}
    for campo in CAMPOS_CICLO_DATAS:
        valor = getattr(ciclo, campo)
        dados[campo] = valor.isoformat() if valor is not None else None
    dados["observacao_area"] = ciclo.observacao_area
    dados["observacao_encerramento"] = ciclo.observacao_encerramento
    return dados


def contrato_para_exportacao(contrato: Contrato, db: Session) -> dict:
    terceirizados = db.query(Terceirizado).filter_by(contrato_id=contrato.id).order_by(Terceirizado.nome).all()
    reunioes = db.query(Reuniao).filter_by(contrato_id=contrato.id).order_by(Reuniao.data).all()
    pendencias = db.query(PendenciaPreOS).filter_by(contrato_id=contrato.id).order_by(PendenciaPreOS.id).all()
    ocorrencias = db.query(Ocorrencia).filter_by(contrato_id=contrato.id).order_by(Ocorrencia.data).all()
    cpfs_conhecidos = db.query(CpfConhecido).filter_by(contrato_id=contrato.id).order_by(CpfConhecido.nome).all()
    competencias = (
        db.query(Competencia)
        .filter_by(contrato_id=contrato.id)
        .order_by(Competencia.ano, Competencia.mes)
        .all()
    )

    return {
        "numero": contrato.numero,
        "objeto": contrato.objeto,
        "contratada_razao_social": contrato.contratada_razao_social,
        "contratada_cnpj": contrato.contratada_cnpj,
        "vigencia_inicio": contrato.vigencia_inicio.isoformat(),
        "vigencia_fim": contrato.vigencia_fim.isoformat(),
        "mao_de_obra_exclusiva": contrato.mao_de_obra_exclusiva,
        "valor_global": str(contrato.valor_global),
        "modalidade": contrato.modalidade,
        "equipe": [
            {
                "nome": membro.nome,
                "matricula_cargo": membro.matricula_cargo,
                "lotacao": membro.lotacao,
                "data_designacao": membro.data_designacao.isoformat(),
                "substituto": membro.substituto,
                "papeis": [p.papel for p in membro.papeis],
            }
            for membro in contrato.membros
        ],
        "terceirizados": [terceirizado_para_exportacao(t) for t in terceirizados],
        "reunioes": [reuniao_para_exportacao(r) for r in reunioes],
        "pendencias_pre_os": [pendencia_para_exportacao(p) for p in pendencias],
        "ocorrencias": [ocorrencia_para_exportacao(o) for o in ocorrencias],
        "cpfs_conhecidos": [cpf_conhecido_para_exportacao(c) for c in cpfs_conhecidos],
        "competencias": [competencia_para_exportacao(comp, db) for comp in competencias],
        "configuracoes_prazos": (
            {campo: getattr(configuracao, campo) for campo in CAMPOS_CONFIGURACAO_PRAZOS}
            if (
                configuracao := db.query(ConfiguracaoPrazos)
                .filter_by(contrato_id=contrato.id)
                .first()
            )
            is not None
            else None
        ),
        "ciclos_prorrogacao": [
            ciclo_para_exportacao(c)
            for c in db.query(CicloProrrogacao)
            .filter_by(contrato_id=contrato.id)
            .order_by(CicloProrrogacao.id)
            .all()
        ],
        "relatorio_final": (
            {
                "conceito": relatorio.conceito,
                "justificativa": relatorio.justificativa,
                "licoes": relatorio.licoes,
            }
            if (
                relatorio := db.query(RelatorioFinal)
                .filter_by(contrato_id=contrato.id)
                .first()
            )
            is not None
            else None
        ),
        "entregas_listagem_semestral": [
            {"data": e.data.isoformat(), "observacao": e.observacao}
            for e in db.query(EntregaListagemSemestral)
            .filter_by(contrato_id=contrato.id)
            .order_by(EntregaListagemSemestral.data)
            .all()
        ],
    }


def _resposta_json_para_download(payload: dict, nome_arquivo: str) -> Response:
    return Response(
        content=json.dumps(payload, ensure_ascii=False, indent=2),
        media_type="application/json",
        headers={"Content-Disposition": f"attachment; filename={nome_arquivo}"},
    )


@router.get("/exportar")
def exportar_todos(db: Session = Depends(get_db)):
    contratos = db.query(Contrato).order_by(Contrato.id).all()
    payload = {"contratos": [contrato_para_exportacao(c, db) for c in contratos]}
    return _resposta_json_para_download(payload, "contratos.json")


@router.get("/contratos/{contrato_id}/exportar")
def exportar_um(contrato_id: int, db: Session = Depends(get_db)):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    payload = {"contratos": [contrato_para_exportacao(contrato, db)]}
    return _resposta_json_para_download(payload, f"contrato_{contrato_id}.json")


def _validar_membro_importado(item_indice: int, m_indice: int, membro: dict, erros: list[str]) -> dict | None:
    if not isinstance(membro, dict):
        erros.append(f"Contrato #{item_indice}, membro #{m_indice}: formato inválido.")
        return None

    faltando = [c for c in CAMPOS_MEMBRO if c not in membro]
    if faltando:
        erros.append(f"Contrato #{item_indice}, membro #{m_indice}: campos ausentes: {', '.join(faltando)}.")
        return None

    try:
        data_designacao = date.fromisoformat(str(membro["data_designacao"]))
    except ValueError:
        erros.append(f"Contrato #{item_indice}, membro #{m_indice}: data de designação inválida.")
        return None

    papeis = membro.get("papeis", [])
    if not isinstance(papeis, list):
        erros.append(f"Contrato #{item_indice}, membro #{m_indice}: 'papeis' deve ser uma lista.")
        return None

    return {
        "nome": str(membro["nome"]),
        "matricula_cargo": str(membro["matricula_cargo"]),
        "lotacao": str(membro["lotacao"]),
        "data_designacao": data_designacao,
        "substituto": membro.get("substituto") or None,
        "papeis": [str(p) for p in papeis],
    }


def _validar_terceirizado_importado(c_indice: int, t_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, terceirizado #{t_indice}: formato inválido.")
        return None
    faltando = [c for c in CAMPOS_TERCEIRIZADO if c not in item]
    if faltando:
        erros.append(f"Contrato #{c_indice}, terceirizado #{t_indice}: campos ausentes: {', '.join(faltando)}.")
        return None
    try:
        data_admissao = date.fromisoformat(str(item["data_admissao"]))
        data_desligamento = (
            date.fromisoformat(str(item["data_desligamento"])) if item.get("data_desligamento") else None
        )
        salario_base = Decimal(str(item["salario_base"]))
    except (ValueError, InvalidOperation, TypeError):
        erros.append(f"Contrato #{c_indice}, terceirizado #{t_indice}: data ou salário em formato inválido.")
        return None
    return {
        "cpf": str(item["cpf"]),
        "nome": str(item["nome"]),
        "cargo": str(item["cargo"]),
        "salario_base": salario_base,
        "data_admissao": data_admissao,
        "data_desligamento": data_desligamento,
    }


def _validar_reuniao_importada(c_indice: int, r_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, reunião #{r_indice}: formato inválido.")
        return None
    faltando = [c for c in CAMPOS_REUNIAO if c not in item]
    if faltando:
        erros.append(f"Contrato #{c_indice}, reunião #{r_indice}: campos ausentes: {', '.join(faltando)}.")
        return None
    try:
        data = date.fromisoformat(str(item["data"]))
    except ValueError:
        erros.append(f"Contrato #{c_indice}, reunião #{r_indice}: data inválida.")
        return None
    # hora e local passaram a existir na Fase 2; arquivos anteriores não têm as chaves.
    hora = item.get("hora") or None
    if hora is not None:
        try:
            time.fromisoformat(str(hora))
        except ValueError:
            erros.append(f"Contrato #{c_indice}, reunião #{r_indice}: hora inválida.")
            return None
        hora = str(hora)
    local = item.get("local") or None
    if local is not None:
        local = str(local)
    return {
        "data": data,
        "hora": hora,
        "local": local,
        "participantes": str(item["participantes"]),
        "resumo": str(item["resumo"]),
    }


def _validar_pendencia_importada(c_indice: int, p_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, pendência pré-OS #{p_indice}: formato inválido.")
        return None
    faltando = [c for c in CAMPOS_PENDENCIA if c not in item]
    if faltando:
        erros.append(f"Contrato #{c_indice}, pendência pré-OS #{p_indice}: campos ausentes: {', '.join(faltando)}.")
        return None
    return {"item": str(item["item"]), "status": str(item["status"])}


def _validar_ocorrencia_importada(c_indice: int, o_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, ocorrência #{o_indice}: formato inválido.")
        return None
    faltando = [c for c in CAMPOS_OCORRENCIA if c not in item]
    if faltando:
        erros.append(f"Contrato #{c_indice}, ocorrência #{o_indice}: campos ausentes: {', '.join(faltando)}.")
        return None
    try:
        data = date.fromisoformat(str(item["data"]))
    except ValueError:
        erros.append(f"Contrato #{c_indice}, ocorrência #{o_indice}: data inválida.")
        return None
    return {"data": data, "descricao": str(item["descricao"]), "gravidade": str(item["gravidade"])}


def _validar_cpf_conhecido_importado(c_indice: int, k_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, CPF conhecido #{k_indice}: formato inválido.")
        return None
    faltando = [c for c in CAMPOS_CPF_CONHECIDO if c not in item]
    if faltando:
        erros.append(f"Contrato #{c_indice}, CPF conhecido #{k_indice}: campos ausentes: {', '.join(faltando)}.")
        return None
    try:
        ano = int(item["competencia_referencia_ano"])
        mes = int(item["competencia_referencia_mes"])
    except (ValueError, TypeError):
        erros.append(f"Contrato #{c_indice}, CPF conhecido #{k_indice}: competência de referência inválida.")
        return None
    return {
        "cpf": str(item["cpf"]),
        "nome": str(item["nome"]),
        "motivo": str(item["motivo"]),
        "competencia_referencia_ano": ano,
        "competencia_referencia_mes": mes,
    }


def _validar_item_folha_importado(
    c_indice: int, comp_indice: int, f_indice: int, item, erros: list[str]
) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}, folha #{f_indice}: formato inválido.")
        return None
    campos = CAMPOS_ITEM_FOLHA_STR + CAMPOS_ITEM_FOLHA_DECIMAIS
    faltando = [c for c in campos if c not in item]
    if faltando:
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}, folha #{f_indice}: "
            f"campos ausentes: {', '.join(faltando)}."
        )
        return None
    try:
        valores_decimais = {c: Decimal(str(item[c])) for c in CAMPOS_ITEM_FOLHA_DECIMAIS}
    except InvalidOperation:
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}, folha #{f_indice}: valor numérico inválido."
        )
        return None
    return {**{c: str(item[c]) for c in CAMPOS_ITEM_FOLHA_STR}, **valores_decimais}


def _validar_item_checklist_importado(
    c_indice: int, comp_indice: int, i_indice: int, item, erros: list[str]
) -> dict | None:
    if not isinstance(item, dict):
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}, checklist #{i_indice}: formato inválido."
        )
        return None
    faltando = [c for c in CAMPOS_ITEM_CHECKLIST if c not in item]
    if faltando:
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}, checklist #{i_indice}: "
            f"campos ausentes: {', '.join(faltando)}."
        )
        return None
    data_referencia = None
    if item.get("data_referencia"):
        try:
            data_referencia = date.fromisoformat(str(item["data_referencia"]))
        except ValueError:
            erros.append(
                f"Contrato #{c_indice}, competência #{comp_indice}, checklist #{i_indice}: "
                "data de referência inválida."
            )
            return None
    return {
        "chave": str(item["chave"]),
        "rotulo": str(item["rotulo"]),
        "status": str(item["status"]),
        "data_referencia": data_referencia,
    }


def _validar_recebimento_importado(c_indice: int, comp_indice: int, item, erros: list[str]) -> dict | None:
    if item is None:
        return None
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: recebimento provisório inválido.")
        return None
    faltando = [c for c in CAMPOS_RECEBIMENTO if c not in item]
    if faltando:
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}: recebimento provisório com campos "
            f"ausentes: {', '.join(faltando)}."
        )
        return None
    try:
        data = date.fromisoformat(str(item["data"]))
    except ValueError:
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: data do recebimento provisório inválida.")
        return None
    return {"data": data, "decisao": str(item["decisao"]), "observacao": item.get("observacao")}


def _validar_relatorio_tecnico_importado(
    c_indice: int, comp_indice: int, item, erros: list[str], nomes_fiscais_validos: set[str]
) -> dict | None:
    if item is None:
        return None
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: relatório técnico inválido.")
        return None
    faltando = [c for c in CAMPOS_RELATORIO_TECNICO if c not in item]
    if faltando:
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}: relatório técnico com campos "
            f"ausentes: {', '.join(faltando)}."
        )
        return None
    try:
        data_ateste = date.fromisoformat(str(item["data_ateste"]))
    except ValueError:
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: data do ateste inválida.")
        return None
    nome_fiscal = str(item["fiscal_responsavel_nome"])
    if nome_fiscal not in nomes_fiscais_validos:
        erros.append(
            f"Contrato #{c_indice}, competência #{comp_indice}: relatório técnico aponta para um fiscal "
            f"responsável ('{nome_fiscal}') que não está na equipe do contrato."
        )
        return None
    return {
        "avaliacao": str(item["avaliacao"]),
        "conclusao": str(item["conclusao"]),
        "fiscal_responsavel_nome": nome_fiscal,
        "data_ateste": data_ateste,
    }


def _validar_competencia_importada(
    c_indice: int,
    comp_indice: int,
    item,
    erros: list[str],
    nomes_fiscais_validos: set[str],
    anos_meses_vistos: set[tuple[int, int]],
) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: formato inválido.")
        return None
    if "ano" not in item or "mes" not in item:
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: campos ausentes: ano, mes.")
        return None
    try:
        ano = int(item["ano"])
        mes = int(item["mes"])
    except (ValueError, TypeError):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: ano/mês inválidos.")
        return None
    if (ano, mes) in anos_meses_vistos:
        erros.append(f"Contrato #{c_indice}: competência {mes:02d}/{ano} duplicada no arquivo.")
        return None
    anos_meses_vistos.add((ano, mes))

    houve_erro = False

    relatorio_tecnico = _validar_relatorio_tecnico_importado(
        c_indice, comp_indice, item.get("relatorio_tecnico"), erros, nomes_fiscais_validos
    )
    if item.get("relatorio_tecnico") is not None and relatorio_tecnico is None:
        houve_erro = True

    recebimento_provisorio = _validar_recebimento_importado(
        c_indice, comp_indice, item.get("recebimento_provisorio"), erros
    )
    if item.get("recebimento_provisorio") is not None and recebimento_provisorio is None:
        houve_erro = True

    folha_bruta = item.get("folha", [])
    folha = []
    if not isinstance(folha_bruta, list):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: 'folha' deve ser uma lista.")
        houve_erro = True
    else:
        for f_indice, f_item in enumerate(folha_bruta, start=1):
            preparado = _validar_item_folha_importado(c_indice, comp_indice, f_indice, f_item, erros)
            if preparado is None:
                houve_erro = True
            else:
                folha.append(preparado)

    checklist_bruto = item.get("checklist_documental", [])
    checklist = []
    if not isinstance(checklist_bruto, list):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: 'checklist_documental' deve ser uma lista.")
        houve_erro = True
    else:
        for i_indice, i_item in enumerate(checklist_bruto, start=1):
            preparado = _validar_item_checklist_importado(c_indice, comp_indice, i_indice, i_item, erros)
            if preparado is None:
                houve_erro = True
            else:
                checklist.append(preparado)

    conclusao_administrativa = item.get("conclusao_administrativa")
    if conclusao_administrativa is not None and not isinstance(conclusao_administrativa, str):
        erros.append(f"Contrato #{c_indice}, competência #{comp_indice}: 'conclusao_administrativa' deve ser texto.")
        houve_erro = True

    if houve_erro:
        return None

    return {
        "ano": ano,
        "mes": mes,
        "relatorio_tecnico": relatorio_tecnico,
        "recebimento_provisorio": recebimento_provisorio,
        "folha": folha,
        "checklist_documental": checklist,
        "conclusao_administrativa": conclusao_administrativa,
    }


def _validar_configuracao_importada(c_indice: int, item, erros: list[str]) -> dict | None:
    if item is None:
        return None
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}: 'configuracoes_prazos' deve ser um objeto.")
        return None
    faltando = [c for c in CAMPOS_CONFIGURACAO_PRAZOS if c not in item]
    if faltando:
        erros.append(
            f"Contrato #{c_indice}: configurações de prazos com campos ausentes: {', '.join(faltando)}."
        )
        return None
    valores = {}
    for campo in CAMPOS_CONFIGURACAO_PRAZOS:
        try:
            valores[campo] = int(item[campo])
        except (ValueError, TypeError):
            erros.append(f"Contrato #{c_indice}: configuração '{campo}' deve ser um número inteiro.")
            return None
        if valores[campo] < 1:
            erros.append(f"Contrato #{c_indice}: configuração '{campo}' deve ser maior que zero.")
            return None
    if not 1 <= valores["dia_limite_gfd_darf"] <= 28:
        erros.append(
            f"Contrato #{c_indice}: 'dia_limite_gfd_darf' deve estar entre 1 e 28."
        )
        return None
    return valores


def _validar_ciclo_prorrogacao_importado(c_indice: int, i_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, ciclo de prorrogação #{i_indice}: formato inválido.")
        return None
    estado = item.get("estado")
    if estado not in ROTULOS_ESTADO_CICLO:
        erros.append(
            f"Contrato #{c_indice}, ciclo de prorrogação #{i_indice}: estado de ciclo inválido."
        )
        return None
    teor = item.get("teor_resposta")
    if teor is not None and teor not in ("com_interesse", "sem_interesse"):
        erros.append(
            f"Contrato #{c_indice}, ciclo de prorrogação #{i_indice}: teor de resposta inválido."
        )
        return None
    dados = {"estado": estado, "teor_resposta": teor}
    for campo in CAMPOS_CICLO_DATAS:
        valor = item.get(campo)
        if valor is None:
            dados[campo] = None
            continue
        try:
            dados[campo] = date.fromisoformat(str(valor))
        except ValueError:
            erros.append(
                f"Contrato #{c_indice}, ciclo de prorrogação #{i_indice}: '{campo}' inválido."
            )
            return None
    dados["observacao_area"] = item.get("observacao_area") or None
    dados["observacao_encerramento"] = item.get("observacao_encerramento") or None
    return dados


def _validar_relatorio_final_importado(c_indice: int, item, erros: list[str]) -> dict | None:
    if item is None:
        return None
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}: 'relatorio_final' deve ser um objeto.")
        return None
    if item.get("conceito") not in CONCEITOS:
        erros.append(f"Contrato #{c_indice}: conceito do relatório final inválido.")
        return None
    justificativa = item.get("justificativa")
    if not isinstance(justificativa, str) or not justificativa.strip():
        erros.append(f"Contrato #{c_indice}: justificativa do relatório final é obrigatória.")
        return None
    licoes = item.get("licoes")
    if licoes is not None and not isinstance(licoes, str):
        erros.append(f"Contrato #{c_indice}: 'licoes' do relatório final deve ser texto.")
        return None
    return {
        "conceito": item["conceito"],
        "justificativa": justificativa.strip(),
        "licoes": (licoes.strip() or None) if licoes else None,
    }


def _validar_entrega_semestral_importada(c_indice: int, e_indice: int, item, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{c_indice}, entrega de listagem #{e_indice}: formato inválido.")
        return None
    if "data" not in item:
        erros.append(f"Contrato #{c_indice}, entrega de listagem #{e_indice}: campos ausentes: data.")
        return None
    try:
        data = date.fromisoformat(str(item["data"]))
    except ValueError:
        erros.append(f"Contrato #{c_indice}, entrega de listagem #{e_indice}: data inválida.")
        return None
    return {"data": data, "observacao": item.get("observacao") or None}


def _validar_lista(c_indice: int, item: dict, chave: str, rotulo: str, validador, erros: list[str]) -> list | None:
    bruta = item.get(chave, [])
    if not isinstance(bruta, list):
        erros.append(f"Contrato #{c_indice}: '{chave}' deve ser uma lista.")
        return None
    preparados = []
    houve_erro = False
    for indice, sub_item in enumerate(bruta, start=1):
        preparado = validador(c_indice, indice, sub_item, erros)
        if preparado is None:
            houve_erro = True
        else:
            preparados.append(preparado)
    return None if houve_erro else preparados


def _validar_contrato_importado(indice: int, item: dict, erros: list[str]) -> dict | None:
    if not isinstance(item, dict):
        erros.append(f"Contrato #{indice}: formato inválido.")
        return None

    faltando = [c for c in CAMPOS_CONTRATO if c not in item]
    if faltando:
        erros.append(f"Contrato #{indice}: campos ausentes: {', '.join(faltando)}.")
        return None

    if not isinstance(item["mao_de_obra_exclusiva"], bool):
        erros.append(f"Contrato #{indice}: 'mao_de_obra_exclusiva' deve ser verdadeiro/falso.")
        return None

    try:
        vigencia_inicio = date.fromisoformat(str(item["vigencia_inicio"]))
        vigencia_fim = date.fromisoformat(str(item["vigencia_fim"]))
        valor_global = Decimal(str(item["valor_global"]))
    except (ValueError, InvalidOperation, TypeError):
        erros.append(f"Contrato #{indice}: data ou valor global em formato inválido.")
        return None

    equipe = item.get("equipe", [])
    if not isinstance(equipe, list):
        erros.append(f"Contrato #{indice}: 'equipe' deve ser uma lista.")
        return None

    membros_preparados = []
    houve_erro_membro = False
    for m_indice, membro in enumerate(equipe, start=1):
        membro_preparado = _validar_membro_importado(indice, m_indice, membro, erros)
        if membro_preparado is None:
            houve_erro_membro = True
        else:
            membros_preparados.append(membro_preparado)

    if houve_erro_membro:
        return None

    nomes_fiscais_validos = {m["nome"] for m in membros_preparados}

    terceirizados = _validar_lista(indice, item, "terceirizados", "terceirizado", _validar_terceirizado_importado, erros)
    reunioes = _validar_lista(indice, item, "reunioes", "reunião", _validar_reuniao_importada, erros)
    pendencias_pre_os = _validar_lista(indice, item, "pendencias_pre_os", "pendência", _validar_pendencia_importada, erros)
    ocorrencias = _validar_lista(indice, item, "ocorrencias", "ocorrência", _validar_ocorrencia_importada, erros)
    cpfs_conhecidos = _validar_lista(indice, item, "cpfs_conhecidos", "CPF conhecido", _validar_cpf_conhecido_importado, erros)
    if cpfs_conhecidos is not None:
        cpfs_vistos: set[str] = set()
        cpfs_duplicados: set[str] = set()
        for conhecido in cpfs_conhecidos:
            if conhecido["cpf"] in cpfs_vistos:
                cpfs_duplicados.add(conhecido["cpf"])
            cpfs_vistos.add(conhecido["cpf"])
        if cpfs_duplicados:
            for cpf in sorted(cpfs_duplicados):
                erros.append(f"Contrato #{indice}: CPF conhecido {cpf} duplicado no arquivo.")
            cpfs_conhecidos = None

    competencias_bruta = item.get("competencias", [])
    competencias = []
    houve_erro_competencia = False
    if not isinstance(competencias_bruta, list):
        erros.append(f"Contrato #{indice}: 'competencias' deve ser uma lista.")
        houve_erro_competencia = True
    else:
        anos_meses_vistos: set[tuple[int, int]] = set()
        for comp_indice, comp_item in enumerate(competencias_bruta, start=1):
            preparada = _validar_competencia_importada(
                indice, comp_indice, comp_item, erros, nomes_fiscais_validos, anos_meses_vistos
            )
            if preparada is None:
                houve_erro_competencia = True
            else:
                competencias.append(preparada)

    # Blocos da Fase 3 — ausentes em arquivos de fases anteriores (CE-08).
    erros_antes_fase3 = len(erros)
    configuracoes_prazos = _validar_configuracao_importada(indice, item.get("configuracoes_prazos"), erros)
    relatorio_final = _validar_relatorio_final_importado(indice, item.get("relatorio_final"), erros)
    ciclos_prorrogacao = _validar_lista(
        indice, item, "ciclos_prorrogacao", "ciclo de prorrogação", _validar_ciclo_prorrogacao_importado, erros
    )
    entregas_listagem = _validar_lista(
        indice, item, "entregas_listagem_semestral", "entrega de listagem", _validar_entrega_semestral_importada, erros
    )
    houve_erro_fase3 = (
        len(erros) > erros_antes_fase3 or ciclos_prorrogacao is None or entregas_listagem is None
    )

    if (
        terceirizados is None
        or reunioes is None
        or pendencias_pre_os is None
        or ocorrencias is None
        or cpfs_conhecidos is None
        or houve_erro_competencia
        or houve_erro_fase3
    ):
        return None

    return {
        "numero": str(item["numero"]),
        "objeto": str(item["objeto"]),
        "contratada_razao_social": str(item["contratada_razao_social"]),
        "contratada_cnpj": str(item["contratada_cnpj"]),
        "vigencia_inicio": vigencia_inicio,
        "vigencia_fim": vigencia_fim,
        "mao_de_obra_exclusiva": item["mao_de_obra_exclusiva"],
        "valor_global": valor_global,
        "modalidade": str(item["modalidade"]),
        "equipe": membros_preparados,
        "terceirizados": terceirizados,
        "reunioes": reunioes,
        "pendencias_pre_os": pendencias_pre_os,
        "ocorrencias": ocorrencias,
        "cpfs_conhecidos": cpfs_conhecidos,
        "competencias": competencias,
        "configuracoes_prazos": configuracoes_prazos,
        "ciclos_prorrogacao": ciclos_prorrogacao,
        "relatorio_final": relatorio_final,
        "entregas_listagem_semestral": entregas_listagem,
    }


def validar_arquivo_importacao(dados) -> tuple[list[str], list[dict] | None]:
    if not isinstance(dados, dict) or not isinstance(dados.get("contratos"), list):
        return ["Esperado um objeto com a chave 'contratos' contendo uma lista."], None

    erros: list[str] = []
    contratos_preparados = []
    for indice, item in enumerate(dados["contratos"], start=1):
        contrato_preparado = _validar_contrato_importado(indice, item, erros)
        if contrato_preparado is not None:
            contratos_preparados.append(contrato_preparado)

    if erros:
        return erros, None

    return [], contratos_preparados


@router.get("/importar")
def importar_form(request: Request):
    return templates.TemplateResponse(request, "exportacao/importar.html", {"erro": None})


@router.post("/importar")
async def importar(request: Request, arquivo: UploadFile = File(...), db: Session = Depends(get_db)):
    conteudo = await arquivo.read()
    try:
        dados = json.loads(conteudo)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return templates.TemplateResponse(
            request,
            "exportacao/importar.html",
            {"erro": MENSAGEM_ARQUIVO_INVALIDO},
            status_code=422,
        )

    erros, contratos_preparados = validar_arquivo_importacao(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "exportacao/importar.html",
            {"erro": MENSAGEM_ARQUIVO_INVALIDO + " Detalhes: " + " ".join(erros)},
            status_code=422,
        )

    for item in contratos_preparados:
        equipe = item.pop("equipe")
        terceirizados = item.pop("terceirizados")
        reunioes = item.pop("reunioes")
        pendencias_pre_os = item.pop("pendencias_pre_os")
        ocorrencias = item.pop("ocorrencias")
        cpfs_conhecidos = item.pop("cpfs_conhecidos")
        competencias = item.pop("competencias")
        configuracoes_prazos = item.pop("configuracoes_prazos")
        ciclos_prorrogacao = item.pop("ciclos_prorrogacao")
        relatorio_final = item.pop("relatorio_final")
        entregas_listagem = item.pop("entregas_listagem_semestral")

        contrato = Contrato(**item)

        for membro_dados in equipe:
            papeis = membro_dados.pop("papeis")
            membro = MembroEquipe(**membro_dados)
            membro.papeis = [PapelMembro(papel=p) for p in papeis]
            contrato.membros.append(membro)
        membros_por_nome = {m.nome: m for m in contrato.membros}

        db.add(contrato)

        for dados_terceirizado in terceirizados:
            db.add(Terceirizado(contrato=contrato, **dados_terceirizado))
        for dados_reuniao in reunioes:
            db.add(Reuniao(contrato=contrato, **dados_reuniao))
        for dados_pendencia in pendencias_pre_os:
            db.add(PendenciaPreOS(contrato=contrato, **dados_pendencia))
        for dados_ocorrencia in ocorrencias:
            db.add(Ocorrencia(contrato=contrato, **dados_ocorrencia))
        for dados_cpf_conhecido in cpfs_conhecidos:
            db.add(CpfConhecido(contrato=contrato, **dados_cpf_conhecido))

        for dados_competencia in competencias:
            dados_relatorio_tecnico = dados_competencia.pop("relatorio_tecnico")
            dados_recebimento = dados_competencia.pop("recebimento_provisorio")
            dados_folha = dados_competencia.pop("folha")
            dados_checklist = dados_competencia.pop("checklist_documental")
            conclusao_administrativa = dados_competencia.pop("conclusao_administrativa")

            competencia = Competencia(contrato=contrato, **dados_competencia)
            db.add(competencia)

            if dados_relatorio_tecnico is not None:
                fiscal = membros_por_nome[dados_relatorio_tecnico.pop("fiscal_responsavel_nome")]
                db.add(
                    RelatorioTecnico(competencia=competencia, fiscal_responsavel=fiscal, **dados_relatorio_tecnico)
                )
            if dados_recebimento is not None:
                db.add(RecebimentoProvisorio(competencia=competencia, **dados_recebimento))
            for dados_item_folha in dados_folha:
                db.add(ItemFolha(competencia=competencia, **dados_item_folha))
            for dados_item_checklist in dados_checklist:
                db.add(ItemChecklistDocumental(competencia=competencia, **dados_item_checklist))
            if conclusao_administrativa is not None:
                db.add(ConclusaoAdministrativa(competencia=competencia, conclusao=conclusao_administrativa))

        # Blocos da Fase 3 (modelos sem relationship — precisam do id do contrato).
        db.flush()
        if configuracoes_prazos is not None:
            db.add(ConfiguracaoPrazos(contrato_id=contrato.id, **configuracoes_prazos))
        for dados_ciclo in ciclos_prorrogacao:
            db.add(CicloProrrogacao(contrato_id=contrato.id, **dados_ciclo))
        if relatorio_final is not None:
            db.add(RelatorioFinal(contrato_id=contrato.id, **relatorio_final))
        for dados_entrega in entregas_listagem:
            db.add(EntregaListagemSemestral(contrato_id=contrato.id, **dados_entrega))

    db.commit()
    return RedirectResponse(url="/contratos", status_code=303)
