import os
from flask import Flask, render_template, request, jsonify
import sqlite3

app = Flask(__name__)

# Preços Padrão
PRECOS_PADRAO = {
    "INSTALAÇÃO": 90.00,
    "ADEQUACAO DE REDE": 7.00,
    "VISTORIA": 19.00,
    "LOSS": 50.00,
    "CONFIGURAÇÃO ONT": 25.00,
    "NINGUÉM EM CASA": 19.00,
    "METRO EXCEDIDO": 0.25,
    "TROCA ONT": 38.00,
    "VISTORIA DE CTO": 19.00,
    "MANUTENÇÃO": 38.00,
    "RETIRADA": 25.00,
    "CONECTADA": 38.00,
    "CUSTO DIARIA": 40.00
}

# Preços específicos da Eliene
PRECOS_ELIENE = {
    "TROCA/CONFIG/CONECTOR": 20.00,
    "NINGUEM EM CASA": 9.50
}

TERCEIROS = ["ELIENE", "LEANDRO", "STEVAN", "Denis", "CLEIDE"]

DB_FILE = 'ordens.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS ordens (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            terceiro TEXT,
            servico TEXT,
            quantidade REAL,
            valor_unitario REAL,
            valor_total REAL,
            data TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.route('/')
def index():
    return render_template('index.html', terceiros=TERCEIROS)

@app.route('/api/precos/<terceiro>')
def get_precos(terceiro):
    if terceiro.upper() == "ELIENE":
        return jsonify(PRECOS_ELIENE)
    return jsonify(PRECOS_PADRAO)

@app.route('/salvar', methods=['POST'])
def salvar():
    data = request.json
    terceiro = data.get('terceiro')
    servico = data.get('servico')
    qtd = float(data.get('quantidade', 1))
    
    precos = PRECOS_ELIENE if terceiro.upper() == "ELIENE" else PRECOS_PADRAO
    valor_unitario = precos.get(servico, 0.0)
    valor_total = valor_unitario * qtd

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ordens (terceiro, servico, quantidade, valor_unitario, valor_total)
        VALUES (?, ?, ?, ?, ?)
    ''', (terceiro, servico, qtd, valor_unitario, valor_total))
    conn.commit()
    conn.close()

    return jsonify({"status": "sucesso", "valor_total": valor_total})

@app.route('/listar')
def listar():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT terceiro, servico, quantidade, valor_unitario, valor_total, strftime("%d/%m/%Y %H:%M", data, "localtime") FROM ordens ORDER BY id DESC')
    registros = cursor.fetchall()
    conn.close()
    return jsonify(registros)

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)