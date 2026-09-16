from sqlalchemy import Column, Date, ForeignKey, Integer, Numeric, String, UniqueConstraint
from sqlalchemy.orm import relationship

from app.database import Base


class Competencia(Base):
    __tablename__ = "competencias"
    __table_args__ = (
        UniqueConstraint("contrato_id", "ano", "mes", name="uq_competencia_contrato_ano_mes"),
    )

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    ano = Column(Integer, nullable=False)
    mes = Column(Integer, nullable=False)

    contrato = relationship("Contrato")


class Reuniao(Base):
    __tablename__ = "reunioes"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    data = Column(Date, nullable=False)
    hora = Column(String, nullable=True)
    local = Column(String, nullable=True)
    participantes = Column(String, nullable=False)
    resumo = Column(String, nullable=False)

    contrato = relationship("Contrato")


class RecebimentoProvisorio(Base):
    __tablename__ = "recebimentos_provisorios"

    id = Column(Integer, primary_key=True, index=True)
    competencia_id = Column(Integer, ForeignKey("competencias.id"), nullable=False, unique=True)
    data = Column(Date, nullable=False)
    decisao = Column(String, nullable=False)
    observacao = Column(String, nullable=True)

    competencia = relationship("Competencia")


class Ocorrencia(Base):
    __tablename__ = "ocorrencias"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    data = Column(Date, nullable=False)
    descricao = Column(String, nullable=False)
    gravidade = Column(String, nullable=False)

    contrato = relationship("Contrato")


class PendenciaPreOS(Base):
    __tablename__ = "pendencias_pre_os"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    item = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pendente")

    contrato = relationship("Contrato")


class Terceirizado(Base):
    __tablename__ = "terceirizados"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    cpf = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    cargo = Column(String, nullable=False)
    salario_base = Column(Numeric(14, 2), nullable=False)
    data_admissao = Column(Date, nullable=False)
    data_desligamento = Column(Date, nullable=True)

    contrato = relationship("Contrato")


class ParametroFaixaINSS(Base):
    __tablename__ = "parametros_faixas_inss"

    id = Column(Integer, primary_key=True, index=True)
    ordem = Column(Integer, nullable=False, unique=True)
    limite_superior = Column(Numeric(14, 2), nullable=False)
    aliquota = Column(Numeric(6, 4), nullable=False)


class ParametroGeral(Base):
    __tablename__ = "parametros_gerais"

    id = Column(Integer, primary_key=True, index=True)
    percentual_fgts = Column(Numeric(6, 4), nullable=False)


class CpfConhecido(Base):
    __tablename__ = "cpfs_conhecidos"
    __table_args__ = (UniqueConstraint("contrato_id", "cpf", name="uq_cpf_conhecido_contrato_cpf"),)

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    cpf = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    motivo = Column(String, nullable=False)
    competencia_referencia_ano = Column(Integer, nullable=False)
    competencia_referencia_mes = Column(Integer, nullable=False)

    contrato = relationship("Contrato")


class ItemChecklistDocumental(Base):
    __tablename__ = "itens_checklist_documental"

    id = Column(Integer, primary_key=True, index=True)
    competencia_id = Column(Integer, ForeignKey("competencias.id"), nullable=False)
    chave = Column(String, nullable=False)
    rotulo = Column(String, nullable=False)
    status = Column(String, nullable=False, default="pendente")
    data_referencia = Column(Date, nullable=True)

    competencia = relationship("Competencia")


class ConclusaoAdministrativa(Base):
    __tablename__ = "conclusoes_administrativas"

    id = Column(Integer, primary_key=True, index=True)
    competencia_id = Column(Integer, ForeignKey("competencias.id"), nullable=False, unique=True)
    conclusao = Column(String, nullable=False)

    competencia = relationship("Competencia")


class RelatorioTecnico(Base):
    __tablename__ = "relatorios_tecnicos"

    id = Column(Integer, primary_key=True, index=True)
    competencia_id = Column(Integer, ForeignKey("competencias.id"), nullable=False, unique=True)
    avaliacao = Column(String, nullable=False)
    conclusao = Column(String, nullable=False)
    fiscal_responsavel_id = Column(Integer, ForeignKey("membros_equipe.id"), nullable=False)
    data_ateste = Column(Date, nullable=False)

    competencia = relationship("Competencia")
    fiscal_responsavel = relationship("MembroEquipe")


class ItemFolha(Base):
    __tablename__ = "itens_folha"

    id = Column(Integer, primary_key=True, index=True)
    competencia_id = Column(Integer, ForeignKey("competencias.id"), nullable=False)
    cpf = Column(String, nullable=False)
    nome = Column(String, nullable=False)
    cargo = Column(String, nullable=False)
    salario_base = Column(Numeric(14, 2), nullable=False)
    total_vencimentos = Column(Numeric(14, 2), nullable=False)
    base_inss = Column(Numeric(14, 2), nullable=False)
    base_fgts = Column(Numeric(14, 2), nullable=False)
    inss_descontado = Column(Numeric(14, 2), nullable=False)
    fgts_depositado = Column(Numeric(14, 2), nullable=False)
    liquido = Column(Numeric(14, 2), nullable=False)

    competencia = relationship("Competencia")
