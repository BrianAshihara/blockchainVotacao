import hashlib
import time

class Bloco:
    def __init__(self, index, votos, hash_anterior):
        self.index = index
        self.timestamp = time.time()
        self.votos = votos
        self.hash_anterior = hash_anterior
        self.hash_atual = self.calcular_hash()

    def calcular_hash(self):
        conteudo = f"{self.index}{self.timestamp}{self.votos}{self.hash_anterior}"
        return hashlib.sha256(conteudo.encode()).hexdigest()

class Blockchain:
    def __init__(self, limite_votos=2):  # Reduzi o limite para facilitar os testes
        self.blocos = [self.criar_bloco_genesis()]
        self.votos_pendentes = []
        self.limite_votos = limite_votos
        self.votos_registrados = set()

    def criar_bloco_genesis(self):
        return Bloco(0, [], "0")

    def adicionar_voto(self, eleitor_hash, opcao):
        if eleitor_hash in self.votos_registrados:
            print("⚠️ Voto rejeitado: eleitor já votou.")
            return
        
        voto = {"eleitor_hash": eleitor_hash, "opcao": opcao}
        self.votos_pendentes.append(voto)
        self.votos_registrados.add(eleitor_hash)

        print(f"✅ Voto registrado com sucesso! Hash do voto: {hashlib.sha256(str(voto).encode()).hexdigest()}")

        if len(self.votos_pendentes) >= self.limite_votos:
            self.criar_novo_bloco()

    def criar_novo_bloco(self):
        ultimo_bloco = self.blocos[-1]
        novo_bloco = Bloco(len(self.blocos), self.votos_pendentes[:], ultimo_bloco.hash_atual)
        self.blocos.append(novo_bloco)
        self.votos_pendentes.clear()
        print(f"🆕 Novo bloco {novo_bloco.index} criado com {len(novo_bloco.votos)} votos.")

    def verificar_integridade(self):
        for i in range(1, len(self.blocos)):
            bloco_atual = self.blocos[i]
            bloco_anterior = self.blocos[i - 1]
            if bloco_atual.hash_anterior != bloco_anterior.hash_atual or bloco_atual.calcular_hash() != bloco_atual.hash_atual:
                return False
        return True

    def consultar_voto(self, eleitor_hash):
        # Procurar nos blocos já criados
        for bloco in self.blocos:
            for voto in bloco.votos:
                if voto["eleitor_hash"] == eleitor_hash:
                    print(f"✅ Seu voto foi registrado no bloco {bloco.index}: {voto['opcao']}")
                    return
        
        # Procurar na lista de votos pendentes
        for voto in self.votos_pendentes:
            if voto["eleitor_hash"] == eleitor_hash:
                print(f"✅ Seu voto foi registrado (ainda não adicionado a um bloco): {voto['opcao']}")
                return

        print("❌ Voto não encontrado.")

    def gerar_relatorio(self):
        if not self.blocos or (len(self.blocos) == 1 and not self.blocos[0].votos):
            print("⚠️ Nenhum voto registrado ainda.")
            return

        contagem_votos = {}

        # Contar votos nos blocos
        for bloco in self.blocos:
            for voto in bloco.votos:
                opcao = voto["opcao"]
                contagem_votos[opcao] = contagem_votos.get(opcao, 0) + 1

        # Contar votos pendentes (não minerados)
        for voto in self.votos_pendentes:
            opcao = voto["opcao"]
            contagem_votos[opcao] = contagem_votos.get(opcao, 0) + 1

        print("\n📊 **Relatório de Votação**")
        print("----------------------------")
        total_votos = sum(contagem_votos.values())
        print(f"Total de votos: {total_votos}\n")

        for opcao, quantidade in contagem_votos.items():
            print(f"🗳️ {opcao}: {quantidade} votos")

        # Encontrar a opção vencedora
        max_votos = max(contagem_votos.values())
        vencedores = [opcao for opcao, qtd in contagem_votos.items() if qtd == max_votos]

        print("\n🏆 **Resultado Final:**")
        if len(vencedores) == 1:
            print(f"🎉 Vencedor: {vencedores[0]} com {max_votos} votos!")
        else:
            print(f"⚖️ Houve um empate entre: {', '.join(vencedores)} com {max_votos} votos cada.")
# -----------------------
# Exemplo de uso
# -----------------------
bc = Blockchain()

# Simulando votos
hash_eleitor1 = hashlib.sha256("eleitor1".encode()).hexdigest()
bc.adicionar_voto(hash_eleitor1, "Sim")

hash_eleitor2 = hashlib.sha256("eleitor2".encode()).hexdigest()
bc.adicionar_voto(hash_eleitor2, "Não")

# Tentando votar novamente
bc.adicionar_voto(hash_eleitor1, "Sim")

# Consultar um voto
bc.consultar_voto(hash_eleitor1)

bc.gerar_relatorio()
