from sqlalchemy import Column, Date, ForeignKey, Integer, String

from app.database import Base

ESTADO_AGUARDANDO_NOTIFICACAO = "aguardando_notificacao"
ESTADO_NOTIFICACAO_ENVIADA = "notificacao_enviada"
ESTADO_RESPOSTA_COM_INTERESSE = "resposta_com_interesse"
ESTADO_RESPOSTA_SEM_INTERESSE = "resposta_sem_interesse"
ESTADO_ADITIVO_ASSINADO = "aditivo_assinado"
ESTADO_AREA_ACIONADA = "area_acionada"
ESTADO_ENCERRADO_SEM_PRORROGACAO = "encerrado_sem_prorrogacao"

ESTADOS_FINAIS = {
    ESTADO_ADITIVO_ASSINADO,
    ESTADO_AREA_ACIONADA,
    ESTADO_ENCERRADO_SEM_PRORROGACAO,
}

ROTULOS_ESTADO_CICLO = {
    ESTADO_AGUARDANDO_NOTIFICACAO: "Aguardando notificação",
    ESTADO_NOTIFICACAO_ENVIADA: "Notificação enviada",
    ESTADO_RESPOSTA_COM_INTERESSE: "Resposta registrada — com interesse",
    ESTADO_RESPOSTA_SEM_INTERESSE: "Resposta registrada — sem interesse",
    ESTADO_ADITIVO_ASSINADO: "Aditivo assinado",
    ESTADO_AREA_ACIONADA: "Área demandante acionada",
    ESTADO_ENCERRADO_SEM_PRORROGACAO: "Encerrado — não haverá prorrogação (decisão da administração)",
}


class CicloProrrogacao(Base):
    __tablename__ = "ciclos_prorrogacao"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    estado = Column(String, nullable=False, default=ESTADO_AGUARDANDO_NOTIFICACAO)
    data_envio_notificacao = Column(Date, nullable=True)
    data_resposta = Column(Date, nullable=True)
    teor_resposta = Column(String, nullable=True)
    data_registro_aditivo = Column(Date, nullable=True)
    vigencia_fim_anterior = Column(Date, nullable=True)
    nova_vigencia_fim = Column(Date, nullable=True)
    data_area_acionada = Column(Date, nullable=True)
    observacao_area = Column(String, nullable=True)
    data_encerramento = Column(Date, nullable=True)
    observacao_encerramento = Column(String, nullable=True)

    @property
    def rotulo_estado(self) -> str:
        return ROTULOS_ESTADO_CICLO.get(self.estado, self.estado)


class RelatorioFinal(Base):
    __tablename__ = "relatorios_finais"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False, unique=True)
    conceito = Column(String, nullable=False)
    justificativa = Column(String, nullable=False)
    licoes = Column(String, nullable=True)


class EntregaListagemSemestral(Base):
    __tablename__ = "entregas_listagem_semestral"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False)
    data = Column(Date, nullable=False)
    observacao = Column(String, nullable=True)


class ConfiguracaoPrazos(Base):
    __tablename__ = "configuracoes_prazos"

    id = Column(Integer, primary_key=True, index=True)
    contrato_id = Column(Integer, ForeignKey("contratos.id"), nullable=False, unique=True)
    antecedencia_notificacao_dias = Column(Integer, nullable=False, default=90)
    prazo_resposta_dias_uteis = Column(Integer, nullable=False, default=3)
    antecedencia_certidoes_dias = Column(Integer, nullable=False, default=15)
    antecedencia_semestral_dias = Column(Integer, nullable=False, default=30)
    dia_limite_gfd_darf = Column(Integer, nullable=False, default=20)
