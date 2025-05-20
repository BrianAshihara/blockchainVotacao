
# 🗳️ Blockchain para Registro de Votos em Pequenas Decisões

Sistema de votação em terminal (CLI) com persistência **on-chain** via arquivos `.json`, autenticação simples, anonimização dos votos e funcionalidades para **administração**, **votação** e **auditoria**.

---

## ✅ Requisitos

- Python >= 3.10
- Biblioteca `typer`:
  ```bash
  pip install typer
  ```

---

## 📁 Estrutura do Projeto

```
blockchainVotacao/
│
├── main.py                  # Interface CLI
├── sistema.py               # Regras de negócio
├── blockchain.py            # Módulo da blockchain
├── data/                    # Armazena dados persistentes
│   ├── usuarios.json
│   ├── votacoes.json
│   ├── blockchain_votacao_<id>.json
│   └── relatorio_<id>.csv
```

---

## 🚀 Como Rodar

1. Clone ou copie o projeto.
2. Instale dependências:
   ```bash
   pip install typer
   ```
3. Crie a pasta de dados:
   ```bash
   mkdir data
   ```
4. Execute o sistema:
   ```bash
   python main.py login
   ```

---

## 👥 Tipos de Usuários

- **Administrador**: cadastra usuários, cria/encerra votações, autoriza eleitores.
- **Eleitor**: visualiza e vota nas votações ativas para as quais foi autorizado.
- **Auditor**: visualiza resultados e exporta relatórios das votações encerradas.

---

## 🔒 Autenticação

- Login e senha simples com hash SHA-256.
- Exemplo de criação de usuário admin:
  ```
  login: admin1
  senha: 123
  tipo: admin
  ```

---

## 🧩 Fluxo de Votação

1. Admin cria a votação com ID e opções.
2. Admin autoriza eleitores.
3. Eleitores logam e votam.
4. Admin encerra a votação.
5. Auditor visualiza ou exporta o resultado.

---

## 📦 Funcionalidades por Arquivo

| Arquivo         | Função                                              |
|-----------------|-----------------------------------------------------|
| `blockchain.py` | Cria a blockchain, registra votos, gera relatórios |
| `sistema.py`    | Regras de negócio (login, autorização, criação)    |
| `main.py`       | Interface de linha de comando                      |

---

## 📄 Casos de Teste Sugeridos

- Cadastro de usuários com sucesso
- Criação de votação e persistência correta
- Autorização de eleitores
- Voto com anonimização
- Bloqueio de votos duplicados
- Encerramento e auditoria
- Geração de CSV de resultado

---

## 🔐 Segurança e Privacidade

- Anonimização com SHA-256
- Hash de blocos vincula histórico de votos
- Alterações manuais corrompem cadeia

---

## 💾 Persistência

- Tudo salvo via arquivos JSON:
  - Usuários
  - Votações
  - Blockchain individual por votação

---

## 📌 Considerações Finais

Este projeto simula um ambiente de votação seguro, confiável e rastreável para uso em pequenas decisões. Pode ser expandido futuramente com:

- Interface Web
- Assinaturas digitais
- Integração com blockchains reais via Web3 ou Solidity
