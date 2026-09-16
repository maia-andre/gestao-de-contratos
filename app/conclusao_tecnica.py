CONCLUSAO_REGULAR = "regular"
CONCLUSAO_REGULAR_COM_RESSALVAS = "regular_com_ressalvas"
CONCLUSAO_IRREGULAR = "irregular"

GRAVIDADES_IRREGULAR = {"grave"}
GRAVIDADES_RESSALVA = {"leve", "media"}


def sugerir_conclusao_tecnica(
    ocorrencias_do_mes: list,
    decisao_recebimento_provisorio: str | None,
    pendencias_pre_os_ok: bool,
) -> str:
    gravidades = {o.gravidade for o in ocorrencias_do_mes}
    if gravidades & GRAVIDADES_IRREGULAR or decisao_recebimento_provisorio == "recusado":
        return CONCLUSAO_IRREGULAR
    if (
        gravidades & GRAVIDADES_RESSALVA
        or not pendencias_pre_os_ok
        or decisao_recebimento_provisorio == "aceito_com_ressalva"
    ):
        return CONCLUSAO_REGULAR_COM_RESSALVAS
    return CONCLUSAO_REGULAR
