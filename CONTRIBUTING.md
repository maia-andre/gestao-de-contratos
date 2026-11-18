# Como contribuir

Obrigado pelo interesse. Este projeto nasceu de uma necessidade concreta de um município brasileiro, e existe em aberto porque **a mesma dor se repete em centenas de órgãos públicos**. Toda contribuição que reduza esse retrabalho coletivo é bem-vinda.

Antes de qualquer coisa: **você não precisa escrever código para contribuir.** As contribuições mais valiosas para este projeto, hoje, não são pull requests.

---

## O que mais precisamos, em ordem de urgência

### 1. 📋 Relatos de uso — inclusive de fracasso

Se você tentou usar isto no seu órgão e não funcionou, **queremos saber mais do que se funcionou**. O que muda de órgão para órgão aqui é o decreto ou IN local de fiscalização (nomes de documentos, prazos, quem assina o quê), o layout da folha analítica que a contratada entrega e o que a auditoria de cada casa realmente cobra no checklist. Relate o que tentou, o que quebrou e o que teve de adaptar.

### 2. 🏛️ Validação por quem entende do assunto

Se você trabalha com fiscalização de contratos, gestão de contratos ou controle interno, sua revisão vale mais que otimização de código:

- O batimento FGTS/INSS e as divergências que ele classifica batem com o que você confere todo mês?
- O checklist documental (CNDT, CRF, RFB/PGFN, guias, holerites, comprovantes) e as validades automáticas correspondem ao que a sua auditoria cobra?
- Os prazos e desfechos do ciclo de prorrogação fazem sentido no seu decreto/IN?
- Que campo ou regra indispensável no seu órgão nós ignoramos?

### 3. ⚖️ Orientação sobre publicação de software público

Estamos formalizando a autorização institucional de publicação (veja [NOTICE](NOTICE)). Se você já passou por esse trâmite em outro órgão, sua experiência nos poupa meses.

### 4. 💻 Código

Veja o [roadmap no README](README.md). Está livre agora: adaptadores de importação de folha em outros layouts, o gerador de dados de demonstração e os modelos restantes do Anexo 1-A. A camada multiusuário está em spec — alinhe antes de tocar.

---

## Antes de abrir um Pull Request

1. **Abra uma issue primeiro** para mudanças não triviais. É um projeto pequeno e mantido por servidor público em tempo limitado — alinhar antes evita trabalho jogado fora.
2. **Uma mudança por PR.** Facilita revisão e reversão.
3. **Descreva como testou.**

## Padrões do projeto

- Código, comentários, commits e documentação **em português**. Este projeto é lido por servidores públicos brasileiros, e a barreira de idioma é uma barreira de adoção real.
- Preferimos **clareza didática a elegância**. Comentário explicando o "porquê" é bem-vindo.
- Sem overengineering. Não introduza uma camada de abstração para um caso de uso que ainda não existe.
- Python 3.13, FastAPI, Jinja2 server-side, SQLite. Sem JavaScript de framework, sem bundler, sem chamada de rede externa (há um teste que garante isso).
- Toda regra de negócio nasce com teste em `tests/`. Rode `pytest -q` antes do PR.

### Mudanças no banco (Alembic)

Cada instância tem o próprio banco SQLite, e a aplicação aplica as migrações sozinha ao subir (`app/database.py:init_db`). Por isso, **toda mudança em `app/models*.py` precisa vir com uma migração** em `app/migrations/versions/`. Há um teste que falha se models e migrações divergirem.

```bash
# depois de alterar os models:
.venv/bin/alembic revision --autogenerate -m "descreve a mudança"
# revise o arquivo gerado: o autogenerate não detecta renomeação (vira apagar + criar,
# perdendo os dados) e não preenche dados em coluna nova NOT NULL
.venv/bin/python -m pytest -q
```

- Use um banco descartável ao gerar: `GESTORDECONTRATO_DB_PATH=/caminho/descartavel.db` (o `alembic.ini` usa o mesmo banco da aplicação).
- Nunca edite uma migração que já foi publicada. Se precisar corrigir, crie uma nova.
- Se dois PRs criarem migração a partir da mesma revisão, haverá duas "heads" e um teste falha. Rebaseie e ajuste o `down_revision` da sua.

---

## ⚠️ Nunca inclua dados reais

**Nunca faça commit de:**
- Folhas analíticas, guias de FGTS/INSS, certidões, contratos ou terceirizados reais — CPF, salário e situação fiscal são dado pessoal
- Nomes de servidores, matrículas ou qualquer dado pessoal
- Endpoints internos, credenciais, chaves de API, certificados ou dumps de banco

Use **exclusivamente dados fictícios** em exemplos, testes e capturas de tela. CPFs de exemplo devem ter dígito verificador inválido, de propósito.

Se encontrar algum dado real que tenha escapado, **não abra issue pública** — entre em contato de forma reservada.

---

## Licença das contribuições

Ao contribuir, você concorda que sua contribuição será licenciada sob a [Apache License 2.0](LICENSE), nos mesmos termos do restante do projeto. Contribuições em documentação seguem a CC BY 4.0.

---

## Código de conduta

Seja direto e seja respeitoso — as duas coisas ao mesmo tempo. Crítica técnica dura é bem-vinda; desqualificação pessoal não. Muita gente aqui é servidor público aprendendo tecnologia fora da sua formação original, e essa é exatamente a audiência que queremos alcançar.
