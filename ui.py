import sys
import hashlib
from PyQt5.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QPushButton, QLabel, QLineEdit, QTextEdit, QFrame
)
from PyQt5.QtGui import QFont, QColor, QPalette
from PyQt5.QtCore import Qt
from blockchainVotacao import Blockchain  # Supondo que seu código original esteja em um arquivo chamado blockchain.py

class VotingApp(QWidget):
    def __init__(self):
        super().__init__()
        self.bc = Blockchain()
        self.initUI()

    def initUI(self):
        self.setWindowTitle("Sistema de Votação Blockchain")
        self.setGeometry(100, 100, 500, 400)
        self.setStyleSheet("background-color: #2c3e50; color: white;")
        
        layout = QVBoxLayout()
        
        title = QLabel("🗳️ Sistema de Votação Blockchain")
        title.setFont(QFont("Arial", 16, QFont.Bold))
        title.setAlignment(Qt.AlignCenter)
        layout.addWidget(title)
        
        self.label = QLabel("Digite seu ID único para votar:")
        self.label.setFont(QFont("Arial", 10))
        layout.addWidget(self.label)
        
        self.id_input = QLineEdit()
        self.id_input.setStyleSheet("background-color: white; color: black; padding: 5px; border-radius: 5px;")
        layout.addWidget(self.id_input)
        
        self.label_opcao = QLabel("Opção de voto (Sim/Não):")
        self.label_opcao.setFont(QFont("Arial", 10))
        layout.addWidget(self.label_opcao)
        
        self.opcao_input = QLineEdit()
        self.opcao_input.setStyleSheet("background-color: white; color: black; padding: 5px; border-radius: 5px;")
        layout.addWidget(self.opcao_input)
        
        self.votar_button = QPushButton("🗳️ Votar")
        self.votar_button.setStyleSheet("background-color: #27ae60; color: white; font-size: 14px; padding: 10px; border-radius: 5px;")
        self.votar_button.clicked.connect(self.votar)
        layout.addWidget(self.votar_button)
        
        self.consultar_button = QPushButton("🔍 Consultar Meu Voto")
        self.consultar_button.setStyleSheet("background-color: #2980b9; color: white; font-size: 14px; padding: 10px; border-radius: 5px;")
        self.consultar_button.clicked.connect(self.consultar_voto)
        layout.addWidget(self.consultar_button)
        
        self.relatorio_button = QPushButton("📊 Gerar Relatório")
        self.relatorio_button.setStyleSheet("background-color: #f39c12; color: white; font-size: 14px; padding: 10px; border-radius: 5px;")
        self.relatorio_button.clicked.connect(self.gerar_relatorio)
        layout.addWidget(self.relatorio_button)
        
        self.resultado_text = QTextEdit()
        self.resultado_text.setReadOnly(True)
        self.resultado_text.setStyleSheet("background-color: white; color: black; padding: 10px; border-radius: 5px;")
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
