# 📋 Gestão de Contratos

**Os quatro papéis que a Lei 14.133/2021 exige na fiscalização de um contrato trabalham hoje com planilha, e-mail e memória — e o ciclo mensal (folha, guias, certidões, relatórios) não deixa trilha. Este sistema dá a cada papel a sua mesa, e ao ciclo, um registro.**

[![Licença: Apache 2.0](https://img.shields.io/badge/Licen%C3%A7a-Apache%202.0-blue.svg)](LICENSE)
[![Docs: CC BY 4.0](https://img.shields.io/badge/Docs-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/deed.pt-br)
[![Estado: em piloto em um município](https://img.shields.io/badge/Estado-em%20piloto%20em%20um%20munic%C3%ADpio-green.svg)](#-estado-real-do-projeto)
[![Procuram-se parceiros](https://img.shields.io/badge/Procuram--se-munic%C3%ADpios%20parceiros-orange.svg)](#-procuram-se-parceiros)

> A Lei 14.133 obriga a fiscalizar (art. 117) e responsabiliza o fiscal por erro grosseiro. Em contrato com mão de obra exclusiva — limpeza, vigilância, portaria — o município responde subsidiariamente por verba trabalhista não paga (art. 121, § 2º). Ou seja: todo mês alguém precisa conferir se o FGTS e o INSS de cada terceirizado foram recolhidos, se as certidões continuam válidas, se houve ocorrência, e assinar um relatório dizendo isso.
>
> Na prática, o fiscal técnico, o fiscal administrativo, o gestor e o chefe de contratos fazem isso cada um do seu jeito, em planilha própria, sem ver os contratos uns dos outros e sem um lugar onde o prazo do próximo passo esteja escrito.
>
> Este repositório é o sistema que organiza esse ciclo — e é público porque **essa dor é a de qualquer órgão que tenha um contrato de serviço continuado**.

---

## 📌 Sumário

- [Por que isso importa (e por que não é só nosso)](#-por-que-isso-importa-e-por-que-não-é-só-nosso)
- [Como funciona](#️-como-funciona)
- [Estado real do projeto](#-estado-real-do-projeto)
- [Onde entra a Inteligência Artificial](#-onde-entra-a-inteligência-artificial)
- [Reproduza no seu município](#-reproduza-no-seu-município)
- [Roadmap](#️-roadmap)
- [Procuram-se parceiros](#-procuram-se-parceiros)
- [Contexto institucional](#️-contexto-institucional)
- [Licença](#-licença)

---

## 🎯 Por que isso importa (e por que não é só nosso)

| A dor | O que acontece na prática |
|---|---|
| **Quatro papéis, quatro planilhas** | Fiscal técnico, fiscal administrativo, gestor e chefe de contratos são figuras distintas, com atos distintos. Cada um registra o seu onde consegue; ninguém vê o conjunto. |
| **O batimento de FGTS/INSS é feito à mão** | A folha analítica da contratada chega em PDF ou planilha; o fiscal confere trabalhador por trabalhador se o depósito bate com a base. Em contrato de 80 pessoas, é uma tarde por mês — e um erro por mês. |
| **Certidão vence sem ninguém ver** | CNDT vale 180 dias, CRF do FGTS vale 30. Sem um lugar que calcule a validade, a certidão vencida só aparece quando a auditoria pede. |
| **O prazo de prorrogação chega de surpresa** | A notificação à contratada tem antecedência mínima; o relatório final tem forma própria. Quem lembra é a memória de quem está há mais tempo no setor. |
| **A trilha não existe** | Quando o controle externo pergunta "o que o fiscal fez no mês X", a resposta está espalhada em e-mails. O fiscal fica exposto por falha de processo, não de julgamento. |

### A base normativa

- **Lei 14.133/2021** — obrigação de fiscalizar (art. 117), designação de fiscais (art. 7º), recebimento provisório e definitivo (art. 140), responsabilidade em contrato com mão de obra exclusiva (art. 121).
- **IN SEGES/MP nº 5/2017** — as lentes de fiscalização (técnica, administrativa, setorial, público usuário) e o IMR. Não vincula município, mas é a doutrina que todos citam.
- **Decreto Municipal 19.721/2024** (São José dos Campos – SP) — a operacionalização local: quatro figuras (art. 4º), ciclo de 16 itens (Anexo I) e 12 modelos de documento (Anexo 1-A). É a espinha dorsal deste sistema. **Seu município tem um decreto ou IN equivalente**; a lei federal é a mesma e o ciclo mensal também.

Escopo: **prestação de serviços e aquisição de materiais**, incluindo mão de obra exclusiva. Obras e serviços de engenharia (medição, diário de obra) ficam fora — é outro domínio.

### O custo da inação

Verba trabalhista não recolhida vira passivo do município (art. 121, § 2º). Certidão vencida invalida pagamento. Prorrogação fora do prazo derruba o contrato e força contratação emergencial. E em todos os casos há um servidor designado por portaria cujo nome está no processo.

---

## ⚙️ Como funciona

Uma instância local, um banco SQLite, sem internet. O sistema modela o ciclo inteiro, para vários contratos ao mesmo tempo:

```
Contrato + equipe (4 papéis, regras de composição do Decreto)
   │
   ├─ Reunião inicial ──► convocação, ata, termo de designação (documentos gerados)
   ├─ Lista mestra de terceirizados (CSV ou manual)
   ├─ Pendências pré-OS (preposto, documentação inicial)
   │
   └─ Competência mensal ─┬─ Fiscal Técnico: ocorrências, recebimento provisório
                          │                  ──► Relatório Técnico + conclusão sugerida
                          │
                          └─ Fiscal Administrativo: folha do mês (CSV)
                                                    ──► batimento FGTS/INSS, divergências
                                                    ──► checklist documental, validade de certidões
                                                    ──► Relatório Administrativo + conclusão sugerida
   Gestor / Chefe de Contratos
   ├─ Ciclo de prorrogação: prazos configuráveis, notificação à contratada, envio, resposta, desfecho
   ├─ Listagem semestral de marcos e entregas
   ├─ Relatório Final de Consecução de Objetivos
   └─ Painel de alertas antecipados (vigência, prorrogação, certidões)

Export/import geral em .json — backup e portabilidade entre máquinas, nunca rede.
```

O batimento aplica a tabela progressiva do INSS (editável em Parâmetros) e o percentual do FGTS sobre a base de cada trabalhador da folha importada, com tolerância de R$ 0,01, e agrupa as divergências: ausência na folha, fora da lista mestra, valor fora da tolerância, zerado. Falso-positivo de "fora da lista mestra" é suprimido com motivo registrado (CPFs conhecidos). A conclusão de cada relatório mensal é sugerida a partir do que foi apurado e pode ser editada antes da impressão.

---

## 🔍 Estado real do projeto

**Esta seção existe porque vitrine sem honestidade não serve para ninguém.** Se você está avaliando adotar este projeto, precisa saber exatamente onde ele está — inclusive o que ainda não existe.

| Componente | Estado | Observação |
|---|:---:|---|
| Contratos, equipe com 4 papéis, painel de prazos, export/import `.json` | ✅ **Funciona** | Fase 0. Regra de composição do Decreto (um agente acumula fiscal técnico + administrativo, nunca gestor + fiscal do mesmo contrato). |
| Ciclo mensal do fiscal: terceirizados, reunião inicial, pendências, ocorrências, recebimento provisório, folha + batimento FGTS/INSS, checklist documental, relatórios técnico e administrativo | ✅ **Funciona** | Fase 1, 13 incrementos. Validado com três fiscais do município de origem em agosto de 2026. |
| Documentos gerados: convocação de reunião, ata, termo de designação | ✅ **Funciona** | Fase 2. São **3 dos 12** modelos do Anexo 1-A. Cabeçalho (órgão, município) é configuração. |
| Ciclo de prorrogação, notificação, relatório final, listagem semestral, alertas antecipados | ✅ **Funciona** | Fase 3. Prazos de antecedência configuráveis por contrato. |
| Suíte de testes | ✅ **374 testes** | `pytest`, sem dependência de rede. |
| Uso em produção | 🟡 **Piloto** | Em uso por fiscais de um município, em rede, atrás do SSO do órgão. Esta versão pública é a mesma aplicação **sem** a camada de SSO: local, 127.0.0.1, sem login. |
| Multiusuário: secretarias, coordenadores, "meus contratos", autoria dos atos | ❌ **Não existe** | É a próxima spec (ver Roadmap). Hoje uma instância = uma mesa. |
| Os outros 9 modelos do Anexo 1-A (termos de recebimento, relatórios de penalidade…) | ❌ **Não existe** | Dependem de módulos ainda não construídos. |
| IMR, conta vinculada, pisos de CCT, fiscalização setorial, pesquisa de satisfação | ❌ **Não existe** | Fase 4 do plano original; sem data. |
| Módulo ocupacional do terceirizado (ASO, EPI, eSocial) | ❌ **Não existe** | Pedido das fiscais; pré-spec. |

> ### 🚧 O gargalo, dito com todas as letras
>
> O sistema é **uma mesa por máquina**. Funciona para um fiscal ou um pequeno setor; para um município inteiro (dezenas de coordenadores, cada um com seus contratos) falta a camada de organização — secretaria como entidade, papéis internos, visibilidade por pessoa. É o que destrava o resto, e é a próxima coisa a ser feita.

---

## 🧠 Onde entra a Inteligência Artificial

Sejamos precisos: **hoje este projeto não tem IA nenhuma.** Toda regra é determinística — tabela do INSS, percentual do FGTS, validade de certidão em dias, composição de equipe.

Ele importa para uma agenda de IA por outro motivo: cria o **substrato de dado estruturado** que hoje não existe em lugar nenhum da fiscalização — folha mês a mês por trabalhador, divergências classificadas, ocorrências com gravidade, certidões com validade, prazos e desfechos de prorrogação, por contrato e por competência. Sem esse registro não há o que aprender.

| Aplicação | Problema real | Entrada → Saída | Métrica |
|---|---|---|---|
| **Leitura da folha e das guias** | A folha analítica chega em PDF; alguém redigita para CSV. As guias de FGTS/INSS idem. | PDF da folha/guia → CSV no layout do importador, com campo de confiança | % de linhas aceitas sem correção manual |
| **Alerta por padrão histórico** | A contratada que atrasa o FGTS em novembro atrasou em novembro do ano passado. | Série de divergências por contratada → alerta de risco antes do fechamento da competência | Divergências previstas × ocorridas |
| **Rascunho de relatório mensal** | O texto do relatório repete o do mês anterior com os números trocados. | Ocorrências + divergências + checklist do mês → rascunho da conclusão, para o fiscal editar | Tempo até o relatório assinado |
| **Conferência de certidão** | Certidão em PDF, data de validade lida a olho. | PDF da certidão → tipo, emissão, validade preenchidos no checklist | Erros de validade encontrados pela auditoria |

**Nenhuma delas está implementada.** Estão aqui como roadmap e convite.

---

## 🔧 Reproduza no seu município

### Comece sem nada

Linux/macOS:

```bash
git clone https://github.com/maia-andre/gestao-de-contratos.git
cd gestao-de-contratos
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
GESTAO_ORGAO="Prefeitura Municipal de Exemplo" GESTAO_MUNICIPIO="Exemplo" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8004
```

Windows (PowerShell):

```powershell
git clone https://github.com/maia-andre/gestao-de-contratos.git
cd gestao-de-contratos
python -m venv .venv
.venv\Scripts\pip install -r requirements.txt
$env:GESTAO_ORGAO = "Prefeitura Municipal de Exemplo"; $env:GESTAO_MUNICIPIO = "Exemplo"
.\iniciar.ps1
```

Abra `http://127.0.0.1:8004`. O banco SQLite (`gestordecontrato.db`) é criado no primeiro acesso; para apontar outro caminho, defina `GESTORDECONTRATO_DB_PATH`.

Cadastre um contrato, monte a equipe, abra uma competência e importe uma folha. Os layouts de CSV (delimitador `;`) estão na própria tela de importação:

- terceirizados: `cpf;nome;cargo;salario_base;data_admissao` (+ colunas opcionais);
- folha: `cpf;nome;cargo;salario_base;total_vencimentos;base_inss;base_fgts;inss_descontado;fgts_depositado;liquido`.

Use dados fictícios. Não há gerador de demonstração neste repositório (ainda — ver Roadmap).

```bash
.venv/bin/python -m pytest -q    # 374 testes, sem rede
```

### O que você vai precisar trocar

| O que | Como está aqui | O que fazer no seu órgão |
|---|---|---|
| **Identidade / login** | Não há. O servidor escuta só em 127.0.0.1, de propósito: sem autenticação, o sistema não pode atender a rede. | Ponha-o atrás do SSO ou do proxy autenticador da sua casa. No município de origem isso é uma dependência global de rota do FastAPI que valida offline um JWT gravado em cookie pelo portal de acesso único; o comentário em `app/main.py` explica o contrato. Não acrescente tabela de senha nem tela de login. |
| **Cabeçalho dos documentos** | `GESTAO_ORGAO` e `GESTAO_MUNICIPIO` (variáveis de ambiente) | Defina as duas antes de subir. |
| **Norma local** | Os papéis, o ciclo e os modelos seguem o Decreto 19.721/2024 de SJC | A lei federal é a mesma. Compare os itens do seu decreto/IN com o ciclo acima; o que diferir geralmente é nome de documento e prazo — os prazos de prorrogação já são configuráveis por contrato. |
| **Tabela do INSS e % do FGTS** | Em Parâmetros, editáveis na tela | Atualize a cada virada de tabela. |
| **Layout da folha** | CSV com as colunas acima | Se a contratada entrega outro layout, converta antes de importar (ou contribua um adaptador — ver CONTRIBUTING). |

### Ambiente de referência

Python 3.13, FastAPI + Uvicorn, Jinja2 server-side, SQLite. Windows 10/11 e Linux. Nenhum serviço de nuvem, nenhuma chamada de rede externa (há um teste que garante isso).

---

## 🗺️ Roadmap

- [ ] **Multiusuário e organização** — secretaria como entidade, papéis internos (administrador → coordenador → gestor/fiscal), vínculo do membro de equipe com a identidade do SSO, autoria dos atos, visibilidade por pessoa. É a próxima spec.
- [ ] **Painéis por persona** — a página inicial vira a mesa de cada papel: o fiscal vê suas pendências do mês, o gestor suas prorrogações, o coordenador a secretaria inteira. O motor de alertas já existe; falta filtrar por pessoa.
- [ ] **Módulo ocupacional do terceirizado** — ASO, EPI, eventos do eSocial, por trabalhador, ancorado na lista mestra.
- [ ] Os 9 modelos restantes do Anexo 1-A.
- [ ] Gerador de dados de demonstração (contrato, equipe, folha sintética) para avaliar o sistema em cinco minutos.
- [ ] IMR, conta vinculada, pisos de CCT.

---

## 🤝 Procuram-se parceiros

- **Um segundo município** que tenha decreto/IN próprio de fiscalização e queira comparar o ciclo — onde o nosso modelo não encaixa é exatamente o que precisamos saber.
- **Fiscais administrativos** para validar o batimento FGTS/INSS e o checklist contra o que a auditoria de vocês realmente cobra.
- **Quem tenha folha analítica em outro layout** (sistemas de folha das contratadas variam) para escrever adaptadores de importação.
- **Quem já publicou software de servidor público** e passou pelo trâmite de titularidade (Lei 9.609/1998, art. 4º).

Veja [CONTRIBUTING.md](CONTRIBUTING.md).

---

## 🏛️ Contexto institucional

Desenvolvido no **Departamento de Planejamento e Gestão de Recursos (DPGR) da Prefeitura de São José dos Campos - SP**, a partir da necessidade concreta de dar aos fiscais de contrato do departamento um lugar único para o ciclo mensal que o Decreto Municipal 19.721/2024 exige — e de substituir a ferramenta anterior, que atendia um fiscal e um contrato por vez.

O projeto nasceu de iniciativa própria do departamento, com recurso mínimo, e é publicado no espírito do **BBSIA — Banco Brasileiro de Soluções de IA para a Gestão Pública** (ENAP/LIIA): compartilhar soluções organizadas pelo problema que resolvem, para que órgãos públicos parem de reconstruir isoladamente o que já existe.

Faz parte de uma família de soluções do mesmo departamento sobre o ciclo da compra pública: [Patrimônio Inteligente](https://github.com/maia-andre/patrimonio-inteligente) (inventário patrimonial com RFID) e [Dispêndio](https://github.com/maia-andre/dispendio) (limite de contratação direta por valor). Outras — notas fiscais na SEFAZ, expedição de almoxarifado, termos de referência — estão a caminho.

Este repositório é uma versão pública derivada do sistema em uso; o desenvolvimento do dia a dia acontece no repositório interno do município, e as mudanças são trazidas para cá em blocos.

---

## 📜 Licença

**Código:** [Apache License 2.0](LICENSE) — uso, modificação e redistribuição livres, inclusive para fins comerciais, com concessão expressa de patente e exigência de atribuição.

**Documentação:** [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/deed.pt-br).

Escolhemos uma licença permissiva deliberadamente: o objetivo é **remover atrito de adoção**. Um jurídico municipal aprova Apache 2.0 sem discussão, e um fornecedor consegue integrar este código ao sistema já contratado pela sua prefeitura sem conflito de licença. Copyleft protegeria melhor contra apropriação, mas ao custo de reduzir exatamente o alcance que buscamos.

> ⚖️ **Titularidade:** nos termos do art. 4º da Lei nº 9.609/1998, os direitos sobre software desenvolvido por servidor no exercício da função pertencem, em regra, ao ente empregador. A formalização da autorização institucional de publicação está em curso — veja o arquivo [NOTICE](NOTICE) para os detalhes.

---

<div align="center">

**Se no seu órgão a fiscalização de contrato também vive em planilha e na memória de quem está há mais tempo, este repositório é seu.**

</div>
