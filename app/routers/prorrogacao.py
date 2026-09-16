from datetime import date, timedelta

from fastapi import APIRouter, Depends, Form, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import MembroEquipe
from app.models_gestor import (
    ESTADO_ADITIVO_ASSINADO,
    ESTADO_AGUARDANDO_NOTIFICACAO,
    ESTADO_AREA_ACIONADA,
    ESTADO_ENCERRADO_SEM_PRORROGACAO,
    ESTADO_NOTIFICACAO_ENVIADA,
    ESTADO_RESPOSTA_COM_INTERESSE,
    ESTADO_RESPOSTA_SEM_INTERESSE,
    ESTADOS_FINAIS,
    CicloProrrogacao,
    ConfiguracaoPrazos,
)
from app.routers.contratos import buscar_contrato_ou_404
from app.routers.equipe import GESTOR
from app.templating import templates

TEORES_RESPOSTA = {
    "com_interesse": ESTADO_RESPOSTA_COM_INTERESSE,
    "sem_interesse": ESTADO_RESPOSTA_SEM_INTERESSE,
}


def somar_anos(data: date, anos: int) -> date:
    try:
        return data.replace(year=data.year + anos)
    except ValueError:  # 29/02 em ano não bissexto
        return data.replace(year=data.year + anos, day=28)


def duracao_acumulada(inicio: date, fim: date) -> str:
    # REQ-09: do início da vigência original ao fim vigente, em anos completos + dias.
    anos = 0
    while somar_anos(inicio, anos + 1) <= fim:
        anos += 1
    dias = (fim - somar_anos(inicio, anos)).days
    partes = []
    if anos:
        partes.append(f"{anos} ano" + ("s" if anos > 1 else ""))
    if dias or not anos:
        partes.append(f"{dias} dia" + ("s" if dias != 1 else ""))
    return " e ".join(partes)


def somar_dias_uteis(inicio: date, dias: int) -> date:
    # RN-02: dias úteis = segunda a sexta, sem tabela de feriados.
    atual = inicio
    restantes = dias
    while restantes > 0:
        atual += timedelta(days=1)
        if atual.weekday() < 5:
            restantes -= 1
    return atual

router = APIRouter(prefix="/contratos", tags=["prorrogacao"])

CAMPOS_CONFIGURACAO = {
    "antecedencia_notificacao_dias": "Antecedência da notificação (dias)",
    "prazo_resposta_dias_uteis": "Prazo de resposta da contratada (dias úteis)",
    "antecedencia_certidoes_dias": "Antecedência do alerta de certidões (dias)",
    "antecedencia_semestral_dias": "Antecedência do alerta da listagem semestral (dias)",
    "dia_limite_gfd_darf": "Dia-limite da documentação GFD/DARF (mês subsequente)",
}


def obter_ou_criar_ciclo(contrato_id: int, db: Session) -> CicloProrrogacao:
    # Contratos de fases anteriores não têm ciclo; criar no primeiro acesso é a migração.
    ciclo = (
        db.query(CicloProrrogacao)
        .filter_by(contrato_id=contrato_id)
        .order_by(CicloProrrogacao.id.desc())
        .first()
    )
    if ciclo is None:
        ciclo = CicloProrrogacao(contrato_id=contrato_id)
        db.add(ciclo)
        db.commit()
        db.refresh(ciclo)
    return ciclo


def obter_ou_criar_configuracao(contrato_id: int, db: Session) -> ConfiguracaoPrazos:
    configuracao = db.query(ConfiguracaoPrazos).filter_by(contrato_id=contrato_id).first()
    if configuracao is None:
        configuracao = ConfiguracaoPrazos(contrato_id=contrato_id)
        db.add(configuracao)
        db.commit()
        db.refresh(configuracao)
    return configuracao


def validar_configuracao(dados: dict) -> tuple[list[str], dict | None]:
    erros: list[str] = []
    valores: dict[str, int] = {}

    for campo, rotulo in CAMPOS_CONFIGURACAO.items():
        bruto = (dados.get(campo) or "").strip()
        if not bruto:
            erros.append(f"{rotulo} é obrigatório.")
            continue
        try:
            valor = int(bruto)
        except ValueError:
            erros.append(f"{rotulo} deve ser um número inteiro.")
            continue
        if campo == "dia_limite_gfd_darf":
            if not 1 <= valor <= 28:
                erros.append(
                    f"{rotulo} deve estar entre 1 e 28 (dias existentes em todos os meses)."
                )
                continue
        elif valor < 1:
            erros.append(f"{rotulo} deve ser maior que zero.")
            continue
        valores[campo] = valor

    if erros:
        return erros, None
    return [], valores


def membros_da_equipe(contrato_id: int, db: Session) -> list[MembroEquipe]:
    return (
        db.query(MembroEquipe)
        .filter_by(contrato_id=contrato_id)
        .order_by(MembroEquipe.nome)
        .all()
    )


def gestor_unico(membros: list[MembroEquipe]) -> MembroEquipe | None:
    # Pré-seleção do emissor: só quando há exatamente um membro com papel Gestor.
    gestores = [
        m for m in membros if any(p.papel == GESTOR for p in m.papeis)
    ]
    return gestores[0] if len(gestores) == 1 else None


@router.get("/{contrato_id}/notificacao-prorrogacao")
def gerar_notificacao_prorrogacao(
    contrato_id: int,
    request: Request,
    emissor_id: int | None = None,
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    membros = membros_da_equipe(contrato_id, db)

    if not membros:
        return templates.TemplateResponse(
            request,
            "prorrogacao/notificacao_bloqueada.html",
            {"contrato": contrato},
            status_code=422,
        )

    if emissor_id is None:
        return templates.TemplateResponse(
            request,
            "prorrogacao/notificacao_selecionar.html",
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

    configuracao = obter_ou_criar_configuracao(contrato_id, db)
    return templates.TemplateResponse(
        request,
        "prorrogacao/notificacao.html",
        {
            "contrato": contrato,
            "emissor": emissor,
            "prazo_resposta": configuracao.prazo_resposta_dias_uteis,
            "hoje": date.today(),
        },
    )


AVISO_LIMITE_10_ANOS = (
    "A duração acumulada do contrato ultrapassa 10 anos (Lei 14.133/2021, art. 107). "
    "O registro foi efetivado; confirme o enquadramento jurídico da prorrogação."
)


def _render_ciclo(
    request: Request,
    db: Session,
    contrato,
    ciclo: CicloProrrogacao,
    configuracao: ConfiguracaoPrazos,
    erros: list[str] | None = None,
    status_code: int = 200,
    avisos: list[str] | None = None,
):
    data_limite_resposta = None
    if ciclo.data_envio_notificacao is not None:
        data_limite_resposta = somar_dias_uteis(
            ciclo.data_envio_notificacao, configuracao.prazo_resposta_dias_uteis
        )
    historico = (
        db.query(CicloProrrogacao)
        .filter_by(contrato_id=contrato.id, estado=ESTADO_ADITIVO_ASSINADO)
        .order_by(CicloProrrogacao.id)
        .all()
    )
    return templates.TemplateResponse(
        request,
        "prorrogacao/ciclo.html",
        {
            "contrato": contrato,
            "ciclo": ciclo,
            "configuracao": configuracao,
            "data_limite_resposta": data_limite_resposta,
            "duracao": duracao_acumulada(contrato.vigencia_inicio, contrato.vigencia_fim),
            "historico": historico,
            "ciclo_encerravel": ciclo.estado not in ESTADOS_FINAIS,
            "erros": erros or [],
            "avisos": avisos or [],
        },
        status_code=status_code,
    )


@router.get("/{contrato_id}/prorrogacao")
def ciclo_prorrogacao(
    contrato_id: int,
    request: Request,
    aviso: str | None = None,
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)
    avisos = [AVISO_LIMITE_10_ANOS] if aviso == "limite-10-anos" else []
    return _render_ciclo(request, db, contrato, ciclo, configuracao, avisos=avisos)


@router.post("/{contrato_id}/prorrogacao/envio")
def registrar_envio(
    contrato_id: int,
    request: Request,
    data_envio: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)

    erros: list[str] = []
    if ciclo.estado != ESTADO_AGUARDANDO_NOTIFICACAO:
        # RN-01/CE-01: envio só a partir de "aguardando notificação".
        if ciclo.estado == ESTADO_NOTIFICACAO_ENVIADA:
            erros.append("O envio da notificação já foi registrado neste ciclo.")
        else:
            erros.append(
                "Não é possível registrar o envio: o ciclo já avançou deste estado."
            )

    data = None
    valor = (data_envio or "").strip()
    if not valor:
        erros.append("Data do envio é obrigatória.")
    else:
        try:
            data = date.fromisoformat(valor)
        except ValueError:
            erros.append("Data do envio inválida.")

    if erros:
        return _render_ciclo(request, db, contrato, ciclo, configuracao, erros, 422)

    ciclo.data_envio_notificacao = data
    ciclo.estado = ESTADO_NOTIFICACAO_ENVIADA
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/prorrogacao", status_code=303)


@router.post("/{contrato_id}/prorrogacao/resposta")
def registrar_resposta(
    contrato_id: int,
    request: Request,
    data_resposta: str = Form(""),
    teor: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)

    erros: list[str] = []
    if ciclo.estado == ESTADO_AGUARDANDO_NOTIFICACAO:
        # RN-01/CE-01: resposta exige notificação enviada.
        erros.append(
            "Não é possível registrar a resposta antes de registrar o envio da notificação."
        )
    elif ciclo.estado != ESTADO_NOTIFICACAO_ENVIADA:
        erros.append("A resposta já foi registrada neste ciclo.")

    data = None
    valor = (data_resposta or "").strip()
    if not valor:
        erros.append("Data da resposta é obrigatória.")
    else:
        try:
            data = date.fromisoformat(valor)
        except ValueError:
            erros.append("Data da resposta inválida.")

    if teor not in TEORES_RESPOSTA:
        erros.append("Teor da resposta inválido.")

    if erros:
        return _render_ciclo(request, db, contrato, ciclo, configuracao, erros, 422)

    ciclo.data_resposta = data
    ciclo.teor_resposta = teor
    ciclo.estado = TEORES_RESPOSTA[teor]
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/prorrogacao", status_code=303)


@router.post("/{contrato_id}/prorrogacao/aditivo")
def registrar_aditivo(
    contrato_id: int,
    request: Request,
    nova_vigencia_fim: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)

    erros: list[str] = []
    if ciclo.estado != ESTADO_RESPOSTA_COM_INTERESSE:
        # RN-01: aditivo só após resposta com interesse.
        erros.append(
            "Não é possível registrar o aditivo: é preciso ter uma resposta com interesse registrada."
        )

    nova_data = None
    valor = (nova_vigencia_fim or "").strip()
    if not valor:
        erros.append("Nova data de fim de vigência é obrigatória.")
    else:
        try:
            nova_data = date.fromisoformat(valor)
        except ValueError:
            erros.append("Nova data de fim de vigência inválida.")

    # RN-07/CE-02: a prorrogação precisa estender a vigência.
    if nova_data is not None and nova_data <= contrato.vigencia_fim:
        erros.append(
            f"Nova data de fim de vigência deve ser posterior à data de fim vigente "
            f"({contrato.vigencia_fim.strftime('%d/%m/%Y')})."
        )

    if erros:
        return _render_ciclo(request, db, contrato, ciclo, configuracao, erros, 422)

    # RN-10/CE-10: ultrapassar 10 anos gera aviso, não bloqueio.
    ultrapassa_10_anos = nova_data > somar_anos(contrato.vigencia_inicio, 10)

    ciclo.vigencia_fim_anterior = contrato.vigencia_fim
    ciclo.nova_vigencia_fim = nova_data
    ciclo.data_registro_aditivo = date.today()
    ciclo.estado = ESTADO_ADITIVO_ASSINADO
    contrato.vigencia_fim = nova_data
    # RN-08: novo ciclo para a nova vigência (as configurações são do contrato, valem para ele).
    db.add(CicloProrrogacao(contrato_id=contrato_id))
    db.commit()

    url = f"/contratos/{contrato_id}/prorrogacao"
    if ultrapassa_10_anos:
        url += "?aviso=limite-10-anos"
    return RedirectResponse(url=url, status_code=303)


@router.post("/{contrato_id}/prorrogacao/area-demandante")
def registrar_area_demandante(
    contrato_id: int,
    request: Request,
    data_acionamento: str = Form(""),
    observacao: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)

    erros: list[str] = []
    if ciclo.estado != ESTADO_RESPOSTA_SEM_INTERESSE:
        # RN-01: acionamento só após resposta sem interesse.
        erros.append(
            "Não é possível registrar o acionamento: é preciso ter uma resposta sem interesse registrada."
        )

    data = None
    valor = (data_acionamento or "").strip()
    if not valor:
        erros.append("Data do acionamento é obrigatória.")
    else:
        try:
            data = date.fromisoformat(valor)
        except ValueError:
            erros.append("Data do acionamento inválida.")

    if erros:
        return _render_ciclo(request, db, contrato, ciclo, configuracao, erros, 422)

    ciclo.data_area_acionada = data
    ciclo.observacao_area = observacao.strip() or None
    ciclo.estado = ESTADO_AREA_ACIONADA
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/prorrogacao", status_code=303)


@router.post("/{contrato_id}/prorrogacao/encerrar")
def encerrar_ciclo(
    contrato_id: int,
    request: Request,
    observacao: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    ciclo = obter_ou_criar_ciclo(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)

    # REQ-08: encerramento manual permitido em qualquer estado não-final.
    if ciclo.estado in ESTADOS_FINAIS:
        return _render_ciclo(
            request,
            db,
            contrato,
            ciclo,
            configuracao,
            ["O ciclo já está encerrado."],
            422,
        )

    ciclo.data_encerramento = date.today()
    ciclo.observacao_encerramento = observacao.strip() or None
    ciclo.estado = ESTADO_ENCERRADO_SEM_PRORROGACAO
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/prorrogacao", status_code=303)


@router.get("/{contrato_id}/configuracoes-prazos")
def configuracoes_prazos_form(
    contrato_id: int, request: Request, db: Session = Depends(get_db)
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)
    valores = {campo: getattr(configuracao, campo) for campo in CAMPOS_CONFIGURACAO}
    return templates.TemplateResponse(
        request,
        "prorrogacao/configuracoes.html",
        {"contrato": contrato, "erros": [], "valores": valores},
    )


@router.post("/{contrato_id}/configuracoes-prazos")
def salvar_configuracoes_prazos(
    contrato_id: int,
    request: Request,
    antecedencia_notificacao_dias: str = Form(""),
    prazo_resposta_dias_uteis: str = Form(""),
    antecedencia_certidoes_dias: str = Form(""),
    antecedencia_semestral_dias: str = Form(""),
    dia_limite_gfd_darf: str = Form(""),
    db: Session = Depends(get_db),
):
    contrato = buscar_contrato_ou_404(contrato_id, db)
    configuracao = obter_ou_criar_configuracao(contrato_id, db)

    dados = {
        "antecedencia_notificacao_dias": antecedencia_notificacao_dias,
        "prazo_resposta_dias_uteis": prazo_resposta_dias_uteis,
        "antecedencia_certidoes_dias": antecedencia_certidoes_dias,
        "antecedencia_semestral_dias": antecedencia_semestral_dias,
        "dia_limite_gfd_darf": dia_limite_gfd_darf,
    }
    erros, valores = validar_configuracao(dados)
    if erros:
        return templates.TemplateResponse(
            request,
            "prorrogacao/configuracoes.html",
            {"contrato": contrato, "erros": erros, "valores": dados},
            status_code=422,
        )

    for campo, valor in valores.items():
        setattr(configuracao, campo, valor)
    db.commit()
    return RedirectResponse(url=f"/contratos/{contrato_id}/prorrogacao", status_code=303)
