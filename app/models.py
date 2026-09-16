from sqlalchemy import Boolean, Column, Date, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import relationship

from app.database import Base


class Contrato(Base):
    __tablename__ = "contratos"

    id = Column(Integer, primary_key=True, index=True)
    numero = Column(String, nullable=False)
    objeto = Column(String, nullable=False)
    contratada_razao_social = Column(String, nullable=False)
    contratada_cnpj = Column(String, nullable=False)
    vigencia_inicio = Column(Date, nullable=False)
    vigencia_fim = Column(Date, nullable=False)
    mao_de_obra_exclusiva = Column(Boolean, nullable=False)
    valor_global = Column(Numeric(14, 2), nullable=False)
    modalidade = Column(String, nullable=False)

    membros = relationship(
        "MembroEquipe", back_populates="contrato", cascade="all, delete-orphan"
    )


class MembroEquipe(Base):
    __tablename__ = "membros_equipe"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    nome = Column(String, nullable=False)
    matricula_cargo = Column(String, nullable=False)
    lotacao = Column(String, nullable=False)
    data_designacao = Column(Date, nullable=False)
    substituto = Column(String, nullable=True)

    contrato = relationship("Contrato", back_populates="membros")
    papeis = relationship(
        "PapelMembro", back_populates="membro", cascade="all, delete-orphan"
    )


class PapelMembro(Base):
    __tablename__ = "papeis_membro"

    id = Column(Integer, primary_key=True, index=True)
    membro_id = Column(Integer, ForeignKey("membros_equipe.id"), nullable=False)
    papel = Column(String, nullable=False)

    membro = relationship("MembroEquipe", back_populates="papeis")
