from sqlalchemy.orm import Session

from app.models_fiscalizacao import PendenciaPreOS

ITENS_PADRAO = [
    "Contratada designou preposto",
    "Documentação inicial entregue",
]


def garantir_itens_padrao(contrato_id: int, db: Session) -> None:
    existentes = db.query(PendenciaPreOS).filter_by(contrato_id=contrato_id).count()
    if existentes > 0:
        return
    for item in ITENS_PADRAO:
        db.add(PendenciaPreOS(contrato_id=contrato_id, item=item, status="pendente"))
    db.commit()


def todas_ok(itens: list) -> bool:
    return all(item.status == "ok" for item in itens)
