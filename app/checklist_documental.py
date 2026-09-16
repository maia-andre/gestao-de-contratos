from datetime import date

from sqlalchemy.orm import Session

from app.models_fiscalizacao import ItemChecklistDocumental

VALIDADE_DIAS = {
    "cndt": 180,
    "crf_fgts": 30,
}

ITENS_PADRAO = [
    ("cndt", "CNDT"),
    ("crf_fgts", "CRF/FGTS"),
    ("certidao_rfb_pgfn", "Certidão RFB/PGFN"),
    ("gfd_paga", "GFD paga"),
    ("darf_pago", "DARF pago"),
    ("holerites_mes", "Holerites do mês"),
    ("comprovantes_salario", "Comprovantes de salário"),
]


def calcular_validade_certidao(chave: str, data_referencia: date | None, hoje: date) -> str | None:
    dias_validade = VALIDADE_DIAS.get(chave)
    if dias_validade is None or data_referencia is None:
        return None
    dias_passados = (hoje - data_referencia).days
    return "vencido" if dias_passados > dias_validade else "válido"


def garantir_itens_padrao(competencia_id: int, db: Session) -> None:
    existentes = db.query(ItemChecklistDocumental).filter_by(competencia_id=competencia_id).count()
    if existentes > 0:
        return
    for chave, rotulo in ITENS_PADRAO:
        db.add(
            ItemChecklistDocumental(
                competencia_id=competencia_id, chave=chave, rotulo=rotulo, status="pendente"
            )
        )
    db.commit()


def checklist_completo_e_valido(itens: list, hoje: date) -> bool:
    for item in itens:
        if item.status != "ok":
            return False
        if calcular_validade_certidao(item.chave, item.data_referencia, hoje) == "vencido":
            return False
    return True
