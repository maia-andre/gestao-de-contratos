from dataclasses import dataclass
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models_fiscalizacao import ParametroFaixaINSS, ParametroGeral

FAIXAS_PADRAO = [
    (Decimal("1621.00"), Decimal("0.0750")),
    (Decimal("2902.84"), Decimal("0.0900")),
    (Decimal("4354.27"), Decimal("0.1200")),
    (Decimal("8475.55"), Decimal("0.1400")),
]
PERCENTUAL_FGTS_PADRAO = Decimal("0.0800")


@dataclass
class ParametrosAtuais:
    faixas_inss: list[tuple[Decimal, Decimal]]
    percentual_fgts: Decimal

    @property
    def teto_inss(self) -> Decimal:
        return self.faixas_inss[-1][0]


def garantir_parametros_padrao(db: Session) -> None:
    if db.query(ParametroFaixaINSS).count() == 0:
        for ordem, (limite, aliquota) in enumerate(FAIXAS_PADRAO, start=1):
            db.add(ParametroFaixaINSS(ordem=ordem, limite_superior=limite, aliquota=aliquota))
    if db.query(ParametroGeral).count() == 0:
        db.add(ParametroGeral(percentual_fgts=PERCENTUAL_FGTS_PADRAO))
    db.commit()


def carregar_parametros_atuais(db: Session) -> ParametrosAtuais:
    garantir_parametros_padrao(db)
    faixas = db.query(ParametroFaixaINSS).order_by(ParametroFaixaINSS.ordem).all()
    geral = db.query(ParametroGeral).first()
    return ParametrosAtuais(
        faixas_inss=[(faixa.limite_superior, faixa.aliquota) for faixa in faixas],
        percentual_fgts=geral.percentual_fgts,
    )
