CONCLUSAO_REGULAR = "regular"
CONCLUSAO_REGULAR_COM_RESSALVAS = "regular_com_ressalvas"
CONCLUSAO_IRREGULAR = "irregular"

TIPOS_DIVERGENCIA_IRREGULAR = {"ausencia", "valor_fgts", "valor_inss"}


def sugerir_conclusao_administrativa(divergencias: list, checklist_ok: bool) -> str:
    tipos = {d.tipo for d in divergencias}
    if tipos & TIPOS_DIVERGENCIA_IRREGULAR:
        return CONCLUSAO_IRREGULAR
    if not divergencias and checklist_ok:
        return CONCLUSAO_REGULAR
    return CONCLUSAO_REGULAR_COM_RESSALVAS
