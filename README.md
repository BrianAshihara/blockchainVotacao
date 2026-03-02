
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
│   ├── estado.py                 # Estado do no: cadeia, mempool, peers, I/O
│   └── api.py                    # App Flask com todos os endpoints
│
├── network/                      # Coordenacao P2P
│   ├── propagacao.py             # Broadcast de transacoes, blocos e votacoes para peers
│   ├── consenso.py               # Resolucao por cadeia mais longa
│   └── sincronizacao.py          # Sincronizacao na inicializacao do no
│
├── sistema/                      # Gestao de sessoes de votacao
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
│   ├── test_node_api.py          # Testes dos 14 endpoints Flask
│   ├── test_network_propagacao.py # Testes de propagacao P2P
│   ├── test_network_consenso.py  # Testes de consenso Nakamoto
│   ├── test_network_sincronizacao.py # Testes de sincronizacao
│   ├── test_sistema_autenticacao.py  # Testes de autenticacao
│   ├── test_sistema_votacao.py   # Testes de sessoes de votacao
│   └── test_sistema_relatorio.py # Testes de exportacao CSV
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

### 3. Usar a CLI

Em outro terminal, execute a CLI que se comunica com o no local:

```bash
python main.py login
```

---

## Rodando Multiplos Nos

Para testar a rede P2P localmente, inicie cada no em um terminal separado com porta e diretorio de dados diferentes:

```bash
# Terminal 1 — No A
python run_node.py --porta 5000 --dados data_node_a

# Terminal 2 — No B (conecta ao A)
python run_node.py --porta 5001 --dados data_node_b --peers localhost:5000

# Terminal 3 — No C (conecta ao A e B)
python run_node.py --porta 5002 --dados data_node_c --peers localhost:5000 localhost:5001
```

Os nos se registram mutuamente, sincronizam a cadeia e sessoes de votacao, e propagam transacoes, blocos e votacoes automaticamente.

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
| GET | `/votacoes` | Listar sessoes de votacao (para sync entre nos) |
| POST | `/votacao` | Receber sessao de votacao (de peers) |
| POST | `/votacao/propagar` | Broadcast de sessao de votacao para peers |
| GET | `/votacao/relatorio/<id>` | Relatorio de votacao |
| GET | `/no/info` | Informacoes do no |

---

## Tipos de Usuarios

- **Administrador**: cadastra usuarios, cria/encerra votacoes, autoriza eleitores, minera blocos.
- **Eleitor**: visualiza votacoes ativas e vota (voto assinado com chave privada ECDSA).
- **Auditor**: visualiza resultados, exporta relatorios CSV, verifica integridade da cadeia.

> **Login de desenvolvimento:** O sistema inclui um login admin embutido (`login: admin` / `senha: admin`) para facilitar o acesso durante desenvolvimento e debug. Esse login funciona sem necessidade de cadastro em `usuarios.json`.

---

## Fluxo de Votacao

1. **Admin** cria uma sessao de votacao com ID e opcoes.
   - A sessao e **propagada automaticamente** para todos os peers da rede.
2. **Admin** autoriza eleitores para a sessao (local por no).
3. **Eleitor** faz login, escolhe uma opcao e submete o voto.
   - O CLI **assina a transacao localmente** com a chave privada do eleitor (ECDSA).
   - A chave privada **nunca sai do processo local** — o no recebe apenas a transacao ja assinada.
   - O no valida a assinatura, verifica voto duplicado e adiciona a mempool.
   - A transacao e propagada para todos os peers.
4. **Admin** (ou qualquer no) minera um bloco, incluindo as transacoes pendentes.
   - O bloco minerado e propagado para a rede.
5. **Admin** encerra a votacao.
   - O encerramento e **propagado para todos os peers**.
6. **Auditor** consulta o resultado ou exporta CSV.

---

## Seguranca

- **Assinatura digital ECDSA (SECP256k1)**: cada voto e assinado com a chave privada do eleitor e verificado por qualquer no antes de ser aceito.
- **Assinatura client-side**: a chave privada do eleitor nunca trafega pela rede — a assinatura e feita localmente no CLI.
- **Proof-of-Work**: blocos exigem hash com 4 zeros iniciais, impedindo alteracao retroativa da cadeia.
- **Consenso por cadeia mais longa**: em caso de divergencia, a cadeia valida mais longa prevalece.
- **Prevencao de voto duplo**: verificada tanto na mempool quanto na cadeia, em cada no independentemente.
- **Identidade on-chain por chave publica**: o login do eleitor nao aparece na blockchain — apenas a chave publica.
- **Hash determinístico**: blocos usam `json.dumps(sort_keys=True)` para garantir consistencia entre nos.

---

## Testes Unitarios

O projeto possui uma suite completa de **255 testes unitarios** cobrindo todos os 16 modulos do sistema, organizada com `pytest`.

### Executar os testes

```bash
# Rodar todos os testes
python -m pytest tests/ -v

# Rodar testes de um modulo especifico
python -m pytest tests/test_core_cripto.py -v

# Rodar com relatorio de cobertura (requer pytest-cov)
pip install pytest-cov
python -m pytest tests/ -v --cov=core --cov=node --cov=network --cov=sistema
```

### Cobertura por camada

| Camada | Arquivos de Teste | Testes | O que cobre |
|--------|-------------------|--------|-------------|
| `core/` | 7 arquivos | 111 | Criptografia ECDSA, transacoes, blocos, cadeia, validacao, mempool, mineracao PoW |
| `node/` | 4 arquivos | 66 | Identidade, registro de peers, estado do no, todos os 14 endpoints da API Flask |
| `network/` | 3 arquivos | 36 | Propagacao HTTP, consenso Nakamoto, sincronizacao com recuperacao de txs orfas |
| `sistema/` | 3 arquivos | 42 | Autenticacao (incl. admin hardcoded), CRUD de votacoes, exportacao CSV |
| **Total** | **17 arquivos** | **255** | **Cobertura completa de todos os modulos** |

### Estrategia de testes

- **Criptografia real**: todos os testes usam chaves ECDSA reais (sem mocks de criptografia), exercitando o fluxo completo de assinatura e verificacao.
- **Isolamento de arquivos**: testes usam `tmp_path` do pytest para I/O em diretorios temporarios, sem efeitos colaterais.
- **Mineracao rapida**: testes usam `dificuldade=1` para que a mineracao seja instantanea.
- **Thread-safety**: testes de concorrencia com 50 threads simultaneas validam que `Mempool`, `RegistroPeers` e `EstadoNo` sao seguros.
- **Mocks de rede**: chamadas HTTP em `network/` sao mockadas com `unittest.mock`, e threads de propagacao em `api.py` sao interceptadas.
- **Flask test_client**: todos os endpoints sao testados via `test_client` do Flask, sem necessidade de servidor real.

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
| `node/estado.py` | Estado centralizado do no |
| `network/propagacao.py` | Broadcast de transacoes, blocos e votacoes para peers |
| `network/consenso.py` | Consenso por cadeia mais longa |
| `network/sincronizacao.py` | Sincronizacao de chain e votacoes ao iniciar |
| `sistema/autenticacao.py` | Login, cadastro, chaves |
| `sistema/votacao.py` | CRUD de sessoes de votacao com propagacao entre nos |
| `sistema/relatorio.py` | Exportacao CSV |
