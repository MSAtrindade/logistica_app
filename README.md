# App de Controle Logístico

Sistema web em Flask para controle logístico com:
- login
- perfil Administrador
- perfil Usuário Leitura
- cadastro de lançamentos
- lançamento em massa por semana ou mês
- consulta com filtros
- cores por produto
- banco SQLite
- pronto para evoluir com gráficos

## Usuário inicial
Ao rodar pela primeira vez, o sistema cria automaticamente:

- **Usuário:** admin
- **Senha:** admin123

Troque essa senha assim que entrar no sistema.

## Regras de cor por produto
- **Sinter** = azul
- **NPO** = cinza
- **HTT** = laranja

## Como rodar localmente

```bash
python -m venv .venv
# Windows
.venv\Scriptsctivate
# Linux/macOS
source .venv/bin/activate

pip install -r requirements.txt
python app.py
```

Depois abra no navegador:

```text
http://127.0.0.1:5000
```

## Publicar no PythonAnywhere

1. Envie os arquivos para sua conta no PythonAnywhere.
2. Crie um virtualenv.
3. Instale as dependências com `pip install -r requirements.txt`.
4. Configure o WSGI apontando para `app` em `app.py`.
5. Defina a pasta do projeto como working directory.

### Exemplo de WSGI

```python
import sys
path = '/home/seuusuario/logistica_app_v2_estrutura_original'
if path not in sys.path:
    sys.path.append(path)

from app import create_app
application = create_app()
```

## Estrutura do sistema
- `/login` acesso ao sistema
- `/usuarios` cadastro de usuários (somente admin)
- `/registros` listagem de lançamentos
- `/registros/novo` novo lançamento (somente admin)
- `/registros/lancamento-em-massa` lançamento semanal ou mensal (somente admin)
- `/registros/<id>/editar` edição (somente admin)
- `/registros/<id>/excluir` exclusão (somente admin)


## Atualização do dashboard
Esta versão inclui:
- filtros por data inicial e final
- filtros por produto, cliente, terminal e termo
- tabela **Total planejado x Realizado**
- cálculos de Plano, D+1, Real, Diferença e Aderência
