# Sobe a Central de Apoio à Fiscalização de Contratos nesta máquina.
#
# 127.0.0.1 de propósito: esta versão não tem login, então o sistema só pode
# atender ao próprio computador. Para pô-lo em rede, coloque-o atrás do SSO ou
# do proxy autenticador do seu órgão (ver comentário em app/main.py).
#
# Cabeçalho dos documentos gerados: defina GESTAO_ORGAO e GESTAO_MUNICIPIO no
# ambiente antes de rodar (ex.: "Prefeitura Municipal de X" e "X").

$ErrorActionPreference = "Stop"

& "$PSScriptRoot\.venv\Scripts\python.exe" -m uvicorn app.main:app --host 127.0.0.1 --port 8004
