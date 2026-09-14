
# Blockchain P2P para Votacao

Sistema de votacao distribuido onde cada instancia roda como um no independente em uma rede P2P. Os votos sao transacoes assinadas com criptografia ECDSA, minerados em blocos com Proof-of-Work e replicados entre nos via consenso por cadeia mais longa (Nakamoto consensus).

---

## Requisitos

- Python >= 3.10
- Dependencias:
  ```bash
  pip install -r requirements.txt
  ```

Pacotes utilizados: `flask`, `requests`, `ecdsa`, `typer`, `pytest`

---

## Estrutura do Projeto

```
blockchainVotacao/
├── requirements.txt              # Dependencias
├── run_node.py                   # Inicia um no (servidor Flask + sincronizacao)
├── main.py                       # CLI para interagir com o no local via HTTP
├── peers_bootstrap.json.example  # Exemplo de peers para bootstrap automatico
│
├── core/                         # Logica pura — sem rede, sem Flask
│   ├── cripto.py                 # Geracao de chaves ECDSA, assinatura, verificacao
│   ├── transacao.py              # Modelo de transacao (voto assinado)
│   ├── bloco.py                  # Modelo de bloco com campos de PoW
│   ├── cadeia.py                 # Validacao de cadeia, consultas, relatorios
│   ├── validacao.py              # Regras de validacao de transacao e bloco
│   ├── mempool.py                # Pool de transacoes pendentes (thread-safe)
│   └── mineracao.py              # Loop de mineracao com Proof-of-Work
│
├── node/                         # Identidade do no + API HTTP
│   ├── identidade.py             # UUID + par de chaves do no
│   ├── registro_peers.py         # Registro de peers (thread-safe)
│   ├── sessoes.py                # Sessoes de login do frontend (token em memoria)
│   ├── estado.py                 # Estado do no: cadeia, mempool, peers, I/O
│   └── api.py                    # App Flask com todos os endpoints
│
├── network/                      # Coordenacao P2P
│   ├── propagacao.py             # Broadcast de transacoes, blocos e votacoes para peers
│   ├── consenso.py               # Resolucao por cadeia mais longa
│   └── sincronizacao.py          # Sincronizacao na inicializacao do no
│
├── sistema/                      # Gestao de sessoes de votacao
│   ├── armazenamento.py          # Gravacao dos JSON com trava e troca atomica
│   ├── autenticacao.py           # Login, cadastro de usuarios, chaves ECDSA
│   ├── votacao.py                # CRUD de sessoes de votacao
│   └── relatorio.py              # Exportacao de relatorio CSV
│
├── tests/                        # Suite de testes unitarios (pytest)
│   ├── conftest.py               # Fixtures compartilhadas
│   ├── test_core_cripto.py       # Testes de criptografia ECDSA
│   ├── test_core_transacao.py    # Testes do modelo de transacao
│   ├── test_core_bloco.py        # Testes do modelo de bloco
│   ├── test_core_cadeia.py       # Testes de validacao de cadeia
│   ├── test_core_validacao.py    # Testes de regras de validacao
│   ├── test_core_mempool.py      # Testes da mempool (thread-safe)
│   ├── test_core_mineracao.py    # Testes de mineracao PoW
│   ├── test_node_identidade.py   # Testes de identidade do no
│   ├── test_node_registro_peers.py # Testes de registro de peers
│   ├── test_node_estado.py       # Testes do estado do no
│   ├── test_node_api.py          # Testes dos 16 endpoints Flask
│   ├── test_node_api_sistema.py  # Testes dos endpoints usados pelo frontend
│   ├── test_node_sessoes.py      # Testes das sessoes de login
│   ├── test_network_propagacao.py # Testes de propagacao P2P
│   ├── test_network_consenso.py  # Testes de consenso Nakamoto
│   ├── test_network_sincronizacao.py # Testes de sincronizacao
│   ├── test_sistema_armazenamento.py # Testes de gravacao concorrente dos JSON
│   ├── test_sistema_autenticacao.py  # Testes de autenticacao
│   ├── test_sistema_votacao.py   # Testes de sessoes de votacao
│   ├── test_sistema_relatorio.py # Testes de exportacao CSV
│   └── test_integracao_rede.py  # Testes de integracao P2P (3 nos reais)
│
└── data/                         # Dados persistidos por no
    ├── usuarios.json             # Usuarios cadastrados
    ├── votacoes.json             # Sessoes de votacao
    ├── chain.json                # Blockchain
    ├── node_identity.json        # Identidade do no
    └── peers.json                # Peers conhecidos
```

---

## Como Rodar

### 1. Instalar dependencias

```bash
pip install -r requirements.txt
```

### 2. Iniciar um no

```bash
python run_node.py --porta 5000 --dados data
```

O no inicia um servidor HTTP na porta indicada e cria os arquivos de dados no diretorio especificado.

Parametros disponiveis:

| Parametro | Default | Descricao |
|-----------|---------|-----------|
| `--porta` | `5000` | Porta HTTP do no |
| `--host` | `localhost` | Endereco visivel para outros nos (IP ou hostname) |
| `--dados` | `data` | Diretorio de dados |
| `--peers` | `[]` | Lista de peers iniciais (`host:porta`) |
| `--tls-cert` | `None` | Caminho do certificado TLS (PEM) para HTTPS |
| `--tls-key` | `None` | Caminho da chave privada TLS (PEM) para HTTPS |
| `--require-auth` | `false` | Exigir assinatura ECDSA no registro de peers |
| `--intervalo-mineracao` | `10` | Segundos entre as tentativas de mineracao automatica |
| `--nos-confiaveis` | `[]` | Chaves publicas dos nos que podem enviar sessoes de votacao (ficam salvas em `nos_confiaveis.json`) |
| `--mostrar-chave` | — | Mostra a chave publica do no e sai (cria a identidade se ainda nao existir) |

### Descoberta automatica de peers (`peers_bootstrap.json`)

Se `--peers` nao for informado na linha de comando, o no procura automaticamente um arquivo `peers_bootstrap.json` na raiz do projeto. O arquivo deve conter uma lista JSON de enderecos `"host:porta"`:

```json
["192.168.1.10:5000", "192.168.1.11:5000", "192.168.1.12:5000"]
```

**Regras:**
- O argumento `--peers` tem **sempre prioridade** — se qualquer peer for passado via CLI, o arquivo e ignorado.
- O endereco do proprio no e automaticamente excluido da lista.
- Se o arquivo nao existir, o no inicia normalmente sem peers.
- Se o arquivo for malformado (JSON invalido ou formato incorreto), um aviso e registrado no log e o no continua.
- O arquivo `peers_bootstrap.json` esta no `.gitignore` para que IPs reais nunca sejam commitados.

**Como usar:**

```bash
# Copiar o exemplo e editar com os enderecos reais dos peers
cp peers_bootstrap.json.example peers_bootstrap.json

# Iniciar o no — peers serao carregados automaticamente do arquivo
python run_node.py --host 192.168.1.10 --porta 5000 --dados data
```

### TLS (HTTPS)

Para habilitar comunicacao criptografada entre nos, forneca um certificado e chave TLS:

```bash
# Gerar certificado auto-assinado para desenvolvimento
openssl req -x509 -newkey rsa:2048 -keyout node.key -out node.crt -days 365 -nodes -subj "/CN=blockchain-node"

# Iniciar no com TLS
python run_node.py --host 192.168.1.10 --porta 5000 --tls-cert node.crt --tls-key node.key
```

Quando TLS esta ativado, toda comunicacao entre peers usa `https://`. Sem os parametros, o no funciona normalmente em HTTP (retrocompativel).

### Autenticacao de peers

Cada no possui um par de chaves ECDSA (SECP256k1) gerado automaticamente. Ao registrar-se em um peer, o no assina o payload com sua chave privada. O peer receptor verifica a assinatura antes de aceitar o registro.

Para **exigir** autenticacao (rejeitar peers sem assinatura):

```bash
python run_node.py --host 192.168.1.10 --porta 5000 --require-auth
```

Sem `--require-auth`, peers com e sem assinatura sao aceitos (retrocompativel).

### Nos confiaveis (sessoes de votacao)

Criar, autorizar e encerrar votacoes altera as sessoes em todos os nos, entao essas mensagens sao aceitas apenas de nos conhecidos. Cada no assina com a sua chave as sessoes que envia (`POST /votacao`) e as que devolve na sincronizacao (`GET /votacoes`). Quem recebe confere a assinatura, se o timestamp tem no maximo 5 minutos e se a chave publica esta em `nos_confiaveis.json`. Mensagem sem assinatura, alterada, antiga ou de no fora da lista e recusada.

A lista e montada uma vez por no:

```bash
# 1. Em cada maquina, obter a chave publica do no
python run_node.py --dados data --mostrar-chave

# 2. Iniciar cada no informando as chaves dos outros nos (ficam salvas em data/nos_confiaveis.json)
python run_node.py --host 192.168.1.10 --porta 5000 --dados data --nos-confiaveis <chave_no_b> <chave_no_c>
```

Nas inicializacoes seguintes as chaves ja estao salvas e o parametro pode ser omitido. Um no sem nenhuma chave na lista avisa no log e recusa todas as sessoes vindas de peers (os blocos e transacoes continuam sendo recebidos, mas os votos de sessoes desconhecidas sao recusados).

`POST /votacao/propagar`, usado pela CLI, so aceita chamadas da propria maquina do no. O corpo informa apenas `id_votacao`: o no rele a sessao do seu `votacoes.json` e a assina antes de enviar.

### Resiliencia de peers

O no executa automaticamente:
- **Retry com backoff**: propagacao de transacoes, blocos e votacoes faz ate 3 tentativas com backoff exponencial (1s, 2s, 4s) antes de desistir.
- **Verificacao periodica**: a cada 60 segundos, o no pinga todos os peers. Se um peer que estava fora volta a responder, o no re-registra automaticamente.

### 3. Usar a CLI

Em outro terminal, execute a CLI que se comunica com o no local:

```bash
python main.py login
```

Para conectar a um no remoto, defina a variavel de ambiente `NODE_URL`:

```bash
NODE_URL=http://192.168.1.10:5000 python main.py login
```

---

## Rodando Multiplos Nos

### Na mesma maquina (desenvolvimento)

Para testar a rede P2P localmente, inicie cada no em um terminal separado com porta e diretorio de dados diferentes. Antes, obtenha a chave de cada no para montar a lista de nos confiaveis:

```bash
python run_node.py --dados data_node_a --mostrar-chave   # → CHAVE_A
python run_node.py --dados data_node_b --mostrar-chave   # → CHAVE_B
python run_node.py --dados data_node_c --mostrar-chave   # → CHAVE_C

# Terminal 1 — No A
python run_node.py --porta 5000 --dados data_node_a --nos-confiaveis CHAVE_B CHAVE_C

# Terminal 2 — No B (conecta ao A)
python run_node.py --porta 5001 --dados data_node_b --nos-confiaveis CHAVE_A CHAVE_C --peers localhost:5000

# Terminal 3 — No C (conecta ao A e B)
python run_node.py --porta 5002 --dados data_node_c --nos-confiaveis CHAVE_A CHAVE_B --peers localhost:5000 localhost:5001
```

### Em maquinas diferentes (cluster)

Quando os nos estao em maquinas diferentes, cada no precisa informar seu **endereco IP real** via `--host`. Isso e necessario porque `localhost` sempre aponta para a propria maquina — se o No A disser aos peers que esta em `localhost:5000`, os peers tentarao acessar a si mesmos em vez do No A.

```bash
# Em cada maquina, antes da primeira execucao
python run_node.py --dados data --mostrar-chave

# Maquina 192.168.1.10 — No A
python run_node.py --host 192.168.1.10 --porta 5000 --dados data --nos-confiaveis CHAVE_B CHAVE_C

# Maquina 192.168.1.11 — No B (conecta ao A)
python run_node.py --host 192.168.1.11 --porta 5001 --dados data --nos-confiaveis CHAVE_A CHAVE_C --peers 192.168.1.10:5000

# Maquina 192.168.1.12 — No C (conecta ao A e B)
python run_node.py --host 192.168.1.12 --porta 5002 --dados data --nos-confiaveis CHAVE_A CHAVE_B --peers 192.168.1.10:5000 192.168.1.11:5001
```

Para usar a CLI em uma maquina conectando a um no remoto:

```bash
NODE_URL=http://192.168.1.10:5000 python main.py login
```

Os nos se registram mutuamente, sincronizam a cadeia e sessoes de votacao, e propagam transacoes, blocos e votacoes automaticamente.

> **Dica:** Em um cluster onde os nos sao sempre os mesmos, use `peers_bootstrap.json` para evitar repetir os enderecos de peers em cada inicializacao. Basta copiar `peers_bootstrap.json.example`, editar com os IPs reais e iniciar os nos sem `--peers`.

### Como testar a rede P2P

Para verificar que os nos estao se comunicando corretamente:

```bash
# 1. Iniciar 2 nos (na mesma maquina, usando IP real em vez de localhost)
python run_node.py --dados data_node_a --mostrar-chave   # → CHAVE_A
python run_node.py --dados data_node_b --mostrar-chave   # → CHAVE_B
python run_node.py --host 127.0.0.1 --porta 5000 --dados data_node_a --nos-confiaveis CHAVE_B
python run_node.py --host 127.0.0.1 --porta 5001 --dados data_node_b --nos-confiaveis CHAVE_A --peers 127.0.0.1:5000

# 2. Verificar que os peers se registraram com IPs reais (nao localhost)
curl http://127.0.0.1:5000/no/info
# → "peers": ["127.0.0.1:5001"]
curl http://127.0.0.1:5001/no/info
# → "peers": ["127.0.0.1:5000"]

# 3. Fazer login na CLI e criar uma votacao + votar
NODE_URL=http://127.0.0.1:5000 python main.py login

# 4. Minerar o bloco (via CLI admin ou curl)
curl -X POST http://127.0.0.1:5000/minerar

# 5. Verificar que o bloco propagou para o outro no
curl http://127.0.0.1:5000/chain/comprimento
curl http://127.0.0.1:5001/chain/comprimento
# → ambos devem mostrar o mesmo comprimento

# 6. Verificar saude do no e conectividade com peers
curl http://127.0.0.1:5000/no/saude
# → "status": "ok", "peers_conhecidos": 1, "peers_alcancaveis": 1
```

---

## API HTTP

Cada no expoe os seguintes endpoints:

| Metodo | Endpoint | Descricao |
|--------|----------|-----------|
| GET | `/chain` | Cadeia completa em JSON |
| GET | `/chain/comprimento` | Comprimento da cadeia |
| GET | `/chain/integridade` | Verificacao de integridade |
| POST | `/transacao` | Receber transacao assinada (do CLI ou de peers) |
| GET | `/mempool` | Transacoes pendentes |
| POST | `/minerar` | Minerar bloco com transacoes da mempool |
| POST | `/bloco` | Receber bloco minerado (de peers) |
| GET | `/peers` | Listar peers conhecidos |
| POST | `/peers/registrar` | Registrar novo peer |
| GET | `/votacoes` | Listar sessoes de votacao (resposta assinada pelo no, para sync entre nos) |
| POST | `/votacao` | Receber sessao de votacao de peer (exige assinatura de no confiavel) |
| POST | `/votacao/propagar` | Broadcast de uma sessao gravada no no (`{"id_votacao"}`, apenas da propria maquina) |
| GET | `/votacao/relatorio/<id>` | Relatorio de votacao (slim com sessao ativa, completo apos encerramento) |
| GET | `/votacao/contagem/<id>` | Contagem leve de votos confirmados on-chain (publico, qualquer estado) |
| GET | `/no/info` | Informacoes do no |
| GET | `/no/saude` | Health check com status de peers alcancaveis |

### Endpoints usados pelo frontend

| Metodo | Endpoint | Acesso | Descricao |
|--------|----------|--------|-----------|
| POST | `/usuario/login` | publico | Login; retorna `token`, `tipo`, `chave_publica` e `chave_privada_cifrada` |
| POST | `/usuario/logout` | logado | Encerra a sessao do token |
| POST | `/usuario/autorregistrar` | publico | Auto-cadastro de eleitor (chave publica + chave privada cifrada, geradas no navegador) |
| GET | `/usuarios` | admin/master | Lista eleitores e admins |
| POST | `/usuario/promover` | admin/master | Promove eleitor a admin |
| POST | `/usuario/rebaixar` | master | Rebaixa admin a eleitor |
| POST | `/votacao/criar` | admin/master | Cria sessao e propaga para os peers |
| POST | `/votacao/encerrar` | admin/master | Mine-on-close, encerra e propaga |
| POST | `/votacao/autorizar` | admin/master | Autoriza um eleitor em uma sessao |
| GET | `/votacao/<id>/eleitores` | admin/master | Eleitores autorizados na sessao |
| GET | `/eleitor/votacoes` | eleitor | Sessoes em que o eleitor logado esta autorizado |

As rotas com acesso restrito exigem o header `Authorization: Bearer <token>` recebido no login. Os tokens ficam so em memoria (reiniciar o no exige novo login) e o papel do usuario e conferido no `usuarios.json` a cada requisicao, entao uma promocao vale na hora.

O no usa o `usuarios.json` do seu diretorio de dados (`--dados`); a CLI continua usando `data/usuarios.json`. Eleitores cadastrados pelo frontend nao tem chave privada guardada no no, entao so votam pelo frontend. As respostas saem com CORS liberado para o navegador chamar o no diretamente.

---

## Mudancas de Escopo (Atualizacao)

Esta secao resume as mudancas de escopo aplicadas sobre o sistema base. Todas mantem retrocompatibilidade com `chain.json`, `votacoes.json` e `usuarios.json` existentes.

### Hierarquia de papeis (3 papeis)

| Papel | Origem | Permissoes |
|---|---|---|
| **master** | Hardcoded (`login: admin` / `senha: admin`) | Todas as acoes de admin e rebaixar admin a eleitor. Nao pode ser cadastrado, removido, promovido nem rebaixado. |
| **admin** | Eleitor promovido por outro admin ou pelo master | Criar votacoes, autorizar eleitores, encerrar votacoes, minerar, promover outros eleitores, ver relatorios. |
| **eleitor** | Auto-cadastro via CLI | Listar suas votacoes ativas, votar, ver resultado de sessoes encerradas em que participou. |

> **Rebaixamento so pelo master.** Qualquer admin promove um eleitor, mas so o master volta um admin para eleitor — um admin nao mexe no papel de outro admin. O rebaixado perde o acesso de administrador na hora e volta a votar nas sessoes em que estiver autorizado. O papel `auditor` foi removido — registros existentes com `tipo=auditor` em `usuarios.json` simplesmente nao tem menu disponivel.

### Auto-cadastro de eleitor

Ao executar `python main.py login`, digite `REGISTRAR` no campo de login para iniciar o auto-cadastro. O eleitor escolhe login + senha e o sistema gera um par de chaves ECDSA SECP256k1 automaticamente. Nenhum admin precisa intervir.

### Promocao de eleitor para admin

Disponivel no menu admin (opcao 1). O master ou qualquer admin pode promover um eleitor existente para admin. Master e identificado pelo login hardcoded `admin` e nao aparece em `usuarios.json`.

### Autorizacao de eleitores replicada

Ao autorizar um eleitor, o no guarda o login (local, usado so para listar as votacoes daquele eleitor) e a **chave publica** dele em `chaves_autorizadas`, que e propagada para todos os peers junto com a sessao. A validacao da transacao (check #6) recusa voto de chave que nao esteja nessa lista, entao a regra passa a valer em qualquer no.

Antes desta mudanca a autorizacao existia apenas no no onde foi feita: `validar_transacao` nao conferia autorizacao nenhuma e o relatorio publico mostrava um numero de eleitores autorizados diferente em cada no.

Limites conhecidos: a propagacao de sessoes nao e autenticada, e `validar_bloco` nao reconfere a autorizacao (checa assinatura, indice, hash e PoW). Fechar isso exigiria transformar a autorizacao numa transacao assinada na propria cadeia.

### Visibilidade do resultado

- **Sessao ativa:** `GET /votacao/relatorio/<id>` retorna apenas a contagem total de votos confirmados on-chain (sem breakdown por candidato, sem vencedor). O endpoint leve `GET /votacao/contagem/<id>` tambem expoe esse total.
- **Sessao encerrada:** `GET /votacao/relatorio/<id>` retorna o relatorio completo (percentuais por candidato, vencedor, blocos com votos, hash do ultimo bloco com voto, total de eleitores autorizados).
- **Apos votar:** o eleitor ve apenas `"Seu voto foi computado."`, o `tx_hash` como comprovante, e o total atual de votos confirmados — nunca o seu proprio voto ou o breakdown.

### Ciclo de vida da sessao (ja implementado)

- Sessoes possuem `inicio` e `fim` em ISO 8601 UTC.
- Encerramento manual (admin) ou automatico (daemon a cada 30s detecta `fim <= agora`).
- **Mine-on-close:** antes de marcar `ativa=False`, o no minera quaisquer transacoes pendentes da sessao para que nenhum voto valido seja perdido.
- Encerramento e criacao sao propagados a todos os peers via `POST /votacao`.

### Mineracao automatica (ja implementado)

Todo no roda um daemon que, a cada 10 segundos (configuravel com `--intervalo-mineracao`), minera as transacoes pendentes da mempool e propaga o bloco aos peers. Thread-safe via `_mining_lock` (exclusao mutua entre daemon, mine-on-close e `POST /minerar`). A prova de trabalho na dificuldade 4 leva em torno de 0,2 s, entao o intervalo e dominado pela espera, nao pela mineracao.

### Bifurcacao da cadeia

Como cada no minera no seu proprio relogio, dois nos podem minerar os mesmos votos ao mesmo tempo e gerar blocos diferentes com o mesmo indice. Quanto menor o intervalo de mineracao, mais provavel. O tratamento segue o consenso por cadeia mais longa:

- **Bloco que encaixa na ponta local:** entra na cadeia. A checagem e a insercao acontecem sob o mesmo lock (`adicionar_bloco_se_ponta`), entao dois blocos disputando a mesma altura nunca entram os dois.
- **Bloco na mesma altura da ponta, ou mais baixo:** recusado; vale o que chegou primeiro.
- **Bloco mais alto que nao encaixa** (gap ou outro ramo): o peer tem uma cadeia mais longa, entao o no ressincroniza e adota a cadeia mais longa valida. Antes disso o conteudo do bloco e validado (hash, PoW e assinaturas), para um peer nao forcar o download da cadeia mandando bloco invalido.
- **Bloco minerado localmente que ficou velho:** se chegar um bloco de outro no durante a prova de trabalho, o bloco local e descartado e os votos continuam na mempool.
- **Votos orfaos:** na ressincronizacao, votos do ramo perdedor voltam para a mempool, exceto de eleitor que ja tem voto no ramo vencedor (evita voto duplo). A mineracao tambem descarta da mempool voto de quem ja votou na cadeia.

### Gravacao concorrente dos arquivos de dados

`votacoes.json` e `usuarios.json` sao lidos, alterados e gravados por varias threads do Flask ao mesmo tempo (por exemplo, varias propagacoes de sessao chegando juntas). Sem protecao, uma gravacao truncava a outra e o arquivo ficava corrompido ("Extra data" no JSON), derrubando todas as rotas que o leem. O modulo `sistema/armazenamento.py` resolve com:

- **Trava por arquivo** em volta de todo ler-modificar-gravar, para as threads nao se atropelarem.
- **Troca atomica**: grava num arquivo temporario na mesma pasta e troca pelo definitivo com `os.replace`, entao quem le ve o arquivo antigo ou o novo, nunca pela metade, mesmo se o processo cair no meio.

A trava vale entre threads do mesmo processo; a CLI rodando ao mesmo tempo que o no continua protegida contra arquivo pela metade, mas nao contra uma gravacao sobrescrever a outra.

---

## Tipos de Usuarios (resumo)

- **Master** (hardcoded `admin`/`admin`): mesmo menu do admin, e o unico que rebaixa admin a eleitor. Nao pode ser removido.
- **Admin**: cria/encerra votacoes (com `inicio`/`fim`), autoriza eleitores, minera, promove outros eleitores, ve relatorios.
- **Eleitor**: auto-cadastro, lista suas votacoes ativas autorizadas, vota, ve resultado de sessoes encerradas em que participou.

---

## Fluxo de Votacao

1. **Eleitor** se auto-cadastra na CLI (digitando `REGISTRAR` no campo login).
2. **Admin** (ou master) cria uma sessao com ID, opcoes, `inicio` e `fim`.
   - A sessao e **propagada automaticamente** para todos os peers.
3. **Admin** autoriza eleitores para a sessao — a chave publica autorizada e propagada para todos os nos.
4. **Eleitor** faz login, lista suas votacoes ativas, escolhe uma e submete o voto.
   - O CLI **assina a transacao localmente** com a chave privada (ECDSA SECP256k1).
   - A chave privada **nunca sai do processo local**.
   - O no valida (7 checks: campos, assinatura, sem voto duplo na cadeia, sem voto pendente na mempool, sessao ativa+periodo, chave autorizada, opcao existente) e adiciona a mempool.
   - A transacao e propagada para todos os peers.
   - O eleitor ve `"Seu voto foi computado."` + `tx_hash` + total atual de votos confirmados.
5. **Auto-miner** (daemon, 10s por padrao) minera o bloco e propaga aos peers — sem acao manual.
6. **Encerramento:**
   - Manual: admin escolhe a opcao no menu (executa mine-on-close antes).
   - Automatico: daemon detecta `fim <= agora`, minera pendentes da sessao, encerra e propaga.
7. **Relatorio publico:** apos encerramento, qualquer no expoe o relatorio completo via `GET /votacao/relatorio/<id>`.

---

## Seguranca

- **Assinatura digital ECDSA (SECP256k1)**: cada voto e assinado com a chave privada do eleitor e verificado por qualquer no antes de ser aceito.
- **Assinatura client-side**: a chave privada do eleitor nunca trafega pela rede — a assinatura e feita localmente no CLI.
- **Proof-of-Work**: blocos exigem hash com 4 zeros iniciais, impedindo alteracao retroativa da cadeia. Blocos que declaram dificuldade abaixo do minimo (`DIFICULDADE_MINIMA = 4`) sao recusados.
- **Consenso por cadeia mais longa**: em caso de divergencia, a cadeia valida mais longa prevalece. A cadeia remota so e adotada se a estrutura e todos os votos forem validos.
- **Prevencao de voto duplo**: verificada na mempool, na cadeia, nos blocos recebidos de peers e nas cadeias avaliadas pelo consenso, em cada no independentemente.
- **Eleitor autorizado e opcao valida**: o voto so entra na mempool se a chave publica estiver na lista de autorizados da sessao (replicada entre os nos) e a escolha estiver entre as opcoes. As mesmas regras sao reconferidas nos blocos recebidos (`POST /bloco`) e no consenso, entao um no nao consegue minerar um voto que os outros recusariam.
- **Identidade on-chain por chave publica**: o login do eleitor nao aparece na blockchain — apenas a chave publica.
- **Hash determinístico**: blocos usam `json.dumps(sort_keys=True)` para garantir consistencia entre nos.
- **TLS (HTTPS) opcional**: comunicacao entre nos pode ser criptografada via `--tls-cert` e `--tls-key`, protegendo votos e blocos em transito.
- **Autenticacao de peers (ECDSA)**: registro de peers assinado com a chave privada do no, com protecao contra replay (timestamp max 5 min). Ativavel com `--require-auth`.
- **Sessoes de votacao so de nos confiaveis**: `POST /votacao` e a resposta de `GET /votacoes` sao assinadas pelo no de origem e aceitas apenas de chaves em `nos_confiaveis.json`, com timestamp de no maximo 5 minutos; os dados da sessao tambem tem o formato validado antes do merge. Ninguem de fora da rede consegue criar sessoes, inserir chaves autorizadas ou encerrar uma votacao.
- **Resiliencia de rede**: propagacao com retry e backoff exponencial (3 tentativas); verificacao periodica de peers com reconexao automatica a cada 60 segundos.

---

## Testes

O projeto possui **471 testes** (457 unitarios + 14 de integracao), organizados com `pytest`.

### Executar os testes

```bash
# Rodar todos os testes (unitarios + integracao) — ~15s
python -m pytest tests/

# Com saida verbosa
python -m pytest tests/ -v

# Rodar apenas testes unitarios (rapido, ~5s)
python -m pytest tests/ --ignore=tests/test_integracao_rede.py

# Rodar apenas testes de integracao (inicia 3 nos reais, ~6s)
python -m pytest tests/test_integracao_rede.py -v

# Rodar testes de um modulo especifico
python -m pytest tests/test_core_cripto.py -v

# Rodar com relatorio de cobertura (requer pytest-cov)
pip install pytest-cov
python -m pytest tests/ --cov=core --cov=node --cov=network --cov=sistema
```

### Cobertura por camada — Testes Unitarios (457)

| Camada | Arquivos de Teste | Testes | O que cobre |
|--------|-------------------|--------|-------------|
| `core/` | 7 arquivos | 144 | Criptografia ECDSA, transacoes, blocos, cadeia (incluindo `contar_votos` e relatorio enriquecido), validacao (sessao ativa, chave autorizada, opcao existente, dificuldade minima, votos em blocos e cadeias recebidos), mempool, mineracao PoW |
| `node/` | 6 arquivos | 163 | Identidade e mensagens assinadas entre nos, lista de nos confiaveis, registro de peers, sessoes de login, estado do no com `_mining_lock`, endpoints Flask de blockchain/P2P (inclui bifurcacao, blocos com votos invalidos e sessoes sem assinatura) e do frontend |
| `network/` | 3 arquivos | 48 | Propagacao HTTP (sessao assinada), consenso Nakamoto (recusa cadeia com voto invalido), sincronizacao com recuperacao de txs orfas, sessoes antes da cadeia e sessoes so de nos confiaveis |
| `sistema/` | 4 arquivos | 102 | Autenticacao (master hardcoded, auto-cadastro, promocao, rebaixamento), CRUD de votacoes (com inicio/fim, chaves autorizadas e validacao de sessao recebida), gravacao segura dos JSON, exportacao CSV com percentual |
| **Total** | **20 arquivos** | **457** | **Cobertura completa de todos os modulos** |

### Testes de Integracao (14)

O arquivo `tests/test_integracao_rede.py` testa a rede P2P de ponta a ponta, **sem mocks**. Ele inicia 3 nos reais como subprocessos na mesma maquina (portas 5050-5052) com `--host 127.0.0.1` e executa um fluxo completo de votacao:

| Teste | O que verifica |
|-------|---------------|
| `test_01_peers_registrados_com_ip_real` | Peers usam IP real (127.0.0.1), nao localhost |
| `test_02_todos_nos_conhecem_todos` | Handshake bidirecional — cada no conhece os outros 2 |
| `test_03_votacao_propaga_para_todos_nos` | Sessao criada e eleitor autorizado no A (pela API com token) aparecem em B e C |
| `test_03b_sessao_sem_assinatura_recusada_em_todos_nos` | Encerramento enviado sem assinatura de no confiavel e recusado pelos 3 nos |
| `test_04_transacao_aceita_e_na_mempool` | Voto assinado e aceito e adicionado a mempool |
| `test_04b_chave_nao_autorizada_rejeitada_em_todos_nos` | Voto de chave nao autorizada e recusado pelos 3 nos |
| `test_05_transacao_propaga_para_peers` | Transacao submetida ao A aparece na mempool de B e C |
| `test_06_minerar_bloco_e_propaga` | Bloco minerado no A propaga para B e C |
| `test_07_mempool_vazia_apos_mineracao` | Mempool limpa em todos os nos apos mineracao |
| `test_08a_relatorio_slim_durante_sessao_ativa` | Relatorio slim (sem breakdown) enquanto sessao esta ativa |
| `test_08b_contagem_endpoint_publico` | `/votacao/contagem/<id>` retorna total em qualquer estado |
| `test_08c_relatorio_completo_apos_encerramento` | Apos encerrar e propagar, relatorio completo expoe breakdown e vencedor |
| `test_09_integridade_chain_todos_nos` | Chain valida e integra em todos os nos |
| `test_10_chains_identicas_em_todos_nos` | Todos os nos tem exatamente a mesma blockchain |

### Estrategia de testes

- **Criptografia real**: todos os testes usam chaves ECDSA reais (sem mocks de criptografia), exercitando o fluxo completo de assinatura e verificacao.
- **Isolamento de arquivos**: testes usam `tmp_path` do pytest para I/O em diretorios temporarios, sem efeitos colaterais.
- **Mineracao rapida**: testes unitarios usam `dificuldade=1` para que a mineracao seja instantanea; uma fixture `autouse` do `conftest.py` rebaixa `DIFICULDADE_MINIMA` durante esses testes.
- **Thread-safety**: testes de concorrencia com 50 threads simultaneas validam que `Mempool`, `RegistroPeers` e `EstadoNo` sao seguros.
- **Mocks de rede**: chamadas HTTP em `network/` sao mockadas com `unittest.mock`, e threads de propagacao em `api.py` sao interceptadas.
- **Flask test_client**: todos os endpoints sao testados via `test_client` do Flask, sem necessidade de servidor real.
- **Integracao real**: testes de integracao iniciam 3 processos `run_node.py` reais e comunicam via HTTP, validando o ciclo completo de votacao P2P.

---

## Funcionalidades por Modulo

| Modulo | Funcao |
|--------|--------|
| `core/cripto.py` | Geracao de chaves, assinatura e verificacao ECDSA |
| `core/transacao.py` | Modelo de transacao (voto assinado) |
| `core/bloco.py` | Modelo de bloco com PoW |
| `core/cadeia.py` | Validacao de cadeia, consulta de votos, relatorios |
| `core/validacao.py` | Regras de validacao de transacao e bloco |
| `core/mempool.py` | Pool de transacoes pendentes |
| `core/mineracao.py` | Mineracao com Proof-of-Work |
| `node/api.py` | API HTTP (Flask) |
| `node/estado.py` | Estado centralizado do no (chain, mempool, peers, TLS, autenticacao) |
| `network/propagacao.py` | Broadcast com retry e backoff exponencial, TLS-aware |
| `network/consenso.py` | Consenso por cadeia mais longa |
| `network/sincronizacao.py` | Sincronizacao ao iniciar, verificacao periodica de peers, reconexao automatica |
| `sistema/autenticacao.py` | Login, cadastro, chaves |
| `sistema/votacao.py` | CRUD de sessoes de votacao com propagacao entre nos |
| `sistema/relatorio.py` | Exportacao CSV |
