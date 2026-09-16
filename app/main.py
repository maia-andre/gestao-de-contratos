import os
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from app.database import init_db
from app.routers import (
    checklist_documental,
    competencias,
    contratos,
    cpfs_conhecidos,
    documentos,
    equipe,
    exportacao,
    folha,
    listagem_semestral,
    ocorrencias,
    painel,
    parametros,
    pendencias_pre_os,
    prorrogacao,
    recebimento_provisorio,
    relatorio_administrativo,
    relatorio_final,
    relatorio_tecnico,
    reunioes,
    terceirizados,
)
from app.templating import templates

STATIC_DIR = Path(__file__).resolve().parent / "static"


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


# Identidade e autenticação ficam FORA deste repositório, de propósito. Esta
# versão é local: sobe em 127.0.0.1, sem login, uma instância por máquina — o
# dado não sai do computador de quem fiscaliza. No município de origem a mesma
# aplicação roda em rede atrás do portal de acesso único do órgão (JWT RS256 em
# cookie, validado offline com a chave pública do portal), por uma dependência
# global de rota; para pôr em rede, faça o mesmo com o SSO ou o proxy
# autenticador da sua casa. Nunca acrescentar bind LDAP, tabela de senha ou
# tela de login a este repositório.

# Cabeçalho dos documentos gerados (atas, termos, notificações, relatório final):
# o nome do órgão e o município da data são configuração, não código.
templates.env.globals["orgao"] = os.environ.get("GESTAO_ORGAO", "Prefeitura Municipal")
templates.env.globals["municipio"] = os.environ.get("GESTAO_MUNICIPIO", "Município")

app = FastAPI(
    title="Central de Apoio à Equipe de Fiscalização de Contratos",
    lifespan=lifespan,
    # /docs, /redoc e /openapi.json serviam o mapa completo das 54 rotas. Este
    # sistema é Jinja2 server-side, sem consumidor de API — a documentação não
    # tem público, então some.
    docs_url=None,
    redoc_url=None,
    openapi_url=None,
)
app.include_router(contratos.router)
app.include_router(equipe.router)
app.include_router(competencias.router)
app.include_router(terceirizados.router)
app.include_router(reunioes.router)
app.include_router(documentos.router)
app.include_router(pendencias_pre_os.router)
app.include_router(prorrogacao.router)
app.include_router(listagem_semestral.router)
app.include_router(ocorrencias.router)
app.include_router(recebimento_provisorio.router)
app.include_router(folha.router)
app.include_router(cpfs_conhecidos.router)
app.include_router(checklist_documental.router)
app.include_router(relatorio_administrativo.router)
app.include_router(relatorio_final.router)
app.include_router(relatorio_tecnico.router)
app.include_router(parametros.router)
app.include_router(painel.router)
app.include_router(exportacao.router)
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")


@app.get("/")
def home(request: Request):
    return templates.TemplateResponse(request, "home.html", {})
