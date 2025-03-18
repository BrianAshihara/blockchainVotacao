import sys
import hashlib
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QTextEdit
from blockchainVotacao import Blockchain

class VotingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.bc = Blockchain()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Sistema de Votação Blockchain")
        self.setGeometry(100, 100, 400, 300)
        layout = QVBoxLayout()
        
        self.label = QLabel("Digite seu ID único para votar:")
        layout.addWidget(self.label)
        
        self.id_input = QLineEdit()
        layout.addWidget(self.id_input)
        
        self.label_opcao = QLabel("Opção de voto (Sim/Não):")
        layout.addWidget(self.label_opcao)
        
        self.opcao_input = QLineEdit()
        layout.addWidget(self.opcao_input)
        
        self.votar_button = QPushButton("Votar")
        self.votar_button.clicked.connect(self.votar)
        layout.addWidget(self.votar_button)
        
        self.consultar_button = QPushButton("Consultar Meu Voto")
        self.consultar_button.clicked.connect(self.consultar_voto)
        layout.addWidget(self.consultar_button)
        
        self.relatorio_button = QPushButton("Gerar Relatório")
        self.relatorio_button.clicked.connect(self.gerar_relatorio)
        layout.addWidget(self.relatorio_button)
        
        self.resultado_text = QTextEdit()
        self.resultado_text.setReadOnly(True)
        layout.addWidget(self.resultado_text)
        
        self.setLayout(layout)
    
    def votar(self):
        eleitor_id = self.id_input.text().strip()
        opcao = self.opcao_input.text().strip()
        if not eleitor_id or not opcao:
            self.resultado_text.setText("⚠️ Preencha todos os campos!")
            return
        
        eleitor_hash = hashlib.sha256(eleitor_id.encode()).hexdigest()
        self.bc.adicionar_voto(eleitor_hash, opcao)
        self.resultado_text.setText("✅ Voto registrado com sucesso!")
    
    def consultar_voto(self):
        eleitor_id = self.id_input.text().strip()
        if not eleitor_id:
            self.resultado_text.setText("⚠️ Informe seu ID único!")
            return
        
        eleitor_hash = hashlib.sha256(eleitor_id.encode()).hexdigest()
        self.resultado_text.setText(self.bc.consultar_voto(eleitor_hash) or "❌ Voto não encontrado.")
    
    def gerar_relatorio(self):
        relatorio = self.bc.gerar_relatorio()
        self.resultado_text.setText(relatorio)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = VotingApp()
    window.show()
    sys.exit(app.exec_())
