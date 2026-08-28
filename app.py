import os
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
import sqlite3
from functools import wraps
from waitress import serve

app = Flask(__name__)
app.secret_key = 'pntvcontrol_secret_key_prod'

# Credenciais Padrão
USUARIO_ADMIN = "admin"
SENHA_ADMIN = "admin123"

DB_FILE = 'ordens.db'

def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Tabela de Ordens de Serviço
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
    
    # Tabela de Terceiros
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS terceiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE
        )
    ''')
    
    # Tabela de Serviços por Terceiro
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            terceiro TEXT,
            nome_servico TEXT,
            valor REAL
        )
    ''')

    # Popular Terceiros se o banco for recém-criado
    cursor.execute('SELECT COUNT(*) FROM terceiros')
    if cursor.fetchone()[0] == 0:
        terceiros_iniciais = ["PADRAO", "ELIENE", "LEANDRO", "STEVAN", "Denis", "CLEIDE"]
        for t in terceiros_iniciais:
            cursor.execute('INSERT OR IGNORE INTO terceiros (nome) VALUES (?)', (t,))

        precos_padrao = {
            "INSTALAÇÃO": 90.00, "ADEQUACAO DE REDE": 7.00, "VISTORIA": 19.00,
            "LOSS": 50.00, "CONFIGURAÇÃO ONT": 25.00, "NINGUÉM EM CASA": 19.00,
            "METRO EXCEDIDO": 0.25, "TROCA ONT": 38.00, "VISTORIA DE CTO": 19.00,
            "MANUTENÇÃO": 38.00, "RETIRADA": 25.00, "CONECTADA": 38.00, "CUSTO DIARIA": 40.00
        }
        for s, v in precos_padrao.items():
            cursor.execute('INSERT INTO servicos (terceiro, nome_servico, valor) VALUES (?, ?, ?)', ("PADRAO", s, v))

        precos_eliene = {
            "TROCA/CONFIG/CONECTOR": 20.00, "NINGUEM EM CASA": 9.50
        }
        for s, v in precos_eliene.items():
            cursor.execute('INSERT INTO servicos (terceiro, nome_servico, valor) VALUES (?, ?, ?)', ("ELIENE", s, v))

    conn.commit()
    conn.close()

init_db()

# Decorator de Login
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/login', methods=['GET', 'POST'])
def login():
    erro = None
    if request.method == 'POST':
        usuario = request.form.get('usuario')
        senha = request.form.get('senha')
        if usuario == USUARIO_ADMIN and senha == SENHA_ADMIN:
            session['logged_in'] = True
            return redirect(url_for('index'))
        erro = "Usuário ou senha incorretos."
    return render_template('login.html', erro=erro)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/api/terceiros', methods=['GET', 'POST', 'DELETE'])
@login_required
def gerenciar_terceiros():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    if request.method == 'POST':
        nome = request.json.get('nome', '').strip().upper()
        if nome:
            cursor.execute('INSERT OR IGNORE INTO terceiros (nome) VALUES (?)', (nome,))
            conn.commit()
            conn.close()
            return jsonify({"status": "sucesso"})
        return jsonify({"status": "erro"}), 400

    cursor.execute('SELECT nome FROM terceiros WHERE nome != "PADRAO" ORDER BY nome ASC')
    terceiros = [row[0] for row in cursor.fetchall()]
    conn.close()
    return jsonify(terceiros)

@app.route('/api/servicos/<terceiro>', methods=['GET', 'POST'])
@login_required
def gerenciar_servicos(terceiro):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    if request.method == 'POST':
        data = request.json
        nome_servico = data.get('nome_servico', '').strip().upper()
        valor = float(data.get('valor', 0.0))
        cursor.execute('INSERT INTO servicos (terceiro, nome_servico, valor) VALUES (?, ?, ?)', (terceiro.upper(), nome_servico, valor))
        conn.commit()
        conn.close()
        return jsonify({"status": "sucesso"})

    cursor.execute('SELECT id, nome_servico, valor FROM servicos WHERE terceiro = ?', (terceiro.upper(),))
    servicos = cursor.fetchall()
    
    if not servicos and terceiro.upper() != "PADRAO":
        cursor.execute('SELECT id, nome_servico, valor FROM servicos WHERE terceiro = "PADRAO"')
        servicos = cursor.fetchall()

    conn.close()
    return jsonify([{"id": s[0], "nome": s[1], "valor": s[2]} for s in servicos])

@app.route('/salvar', methods=['POST'])
@login_required
def salvar():
    data = request.json
    terceiro = data.get('terceiro')
    servico = data.get('servico')
    qtd = float(data.get('quantidade', 1))
    valor_unitario = float(data.get('valor_unitario', 0))
    valor_total = valor_unitario * qtd

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ordens (terceiro, servico, quantidade, valor_unitario, valor_total)
        VALUES (?, ?, ?, ?, ?)
    ''', (terceiro, servico, qtd, valor_unitario, valor_total))
    conn.commit()
    conn.close()

    return jsonify({"status": "sucesso"})

@app.route('/listar')
@login_required
def listar():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT id, terceiro, servico, quantidade, valor_unitario, valor_total, strftime("%d/%m/%Y %H:%M", data, "localtime") FROM ordens ORDER BY id DESC')
    registros = cursor.fetchall()
    conn.close()
    return jsonify(registros)

@app.route('/deletar_os/<int:os_id>', methods=['DELETE'])
@login_required
def deletar_os(os_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM ordens WHERE id = ?', (os_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "sucesso"})

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    serve(app, host='0.0.0.0', port=port)