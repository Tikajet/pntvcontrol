import os
import sqlite3
from functools import wraps
from flask import Flask, render_template, request, jsonify, redirect, url_for, session
from waitress import serve

app = Flask(__name__)
app.secret_key = 'pntvcontrol_secret_key_prod'

USUARIO_ADMIN = "admin"
SENHA_ADMIN = "admin123"
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
            data_servico TEXT,
            pago INTEGER DEFAULT 0,
            data_registro TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')

    # Garantir que a coluna 'pago' exista em bancos pré-existentes
    cursor.execute("PRAGMA table_info(ordens)")
    colunas = [col[1] for col in cursor.fetchall()]
    if 'pago' not in colunas:
        cursor.execute('ALTER TABLE ordens ADD COLUMN pago INTEGER DEFAULT 0')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS terceiros (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nome TEXT UNIQUE
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS servicos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            terceiro TEXT,
            nome_servico TEXT,
            valor REAL
        )
    ''')

    cursor.execute('SELECT COUNT(*) FROM terceiros')
    if cursor.fetchone()[0] == 0:
        terceiros_iniciais = ["PADRAO", "ELIENE", "LEANDRO", "STEVAN", "DENIS", "CLEIDE"]
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

    if request.method == 'DELETE':
        nome = request.json.get('nome')
        cursor.execute('DELETE FROM terceiros WHERE nome = ?', (nome,))
        cursor.execute('DELETE FROM servicos WHERE terceiro = ?', (nome,))
        conn.commit()
        conn.close()
        return jsonify({"status": "sucesso"})

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
    data_servico = data.get('data_servico')
    pago = 1 if data.get('pago') else 0
    valor_total = valor_unitario * qtd

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT INTO ordens (terceiro, servico, quantidade, valor_unitario, valor_total, data_servico, pago)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    ''', (terceiro, servico, qtd, valor_unitario, valor_total, data_servico, pago))
    conn.commit()
    conn.close()

    return jsonify({"status": "sucesso"})

@app.route('/listar')
@login_required
def listar():
    terceiro = request.args.get('terceiro', '')
    data_inicio = request.args.get('data_inicio', '')
    data_fim = request.args.get('data_fim', '')
    pago = request.args.get('pago', '')

    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    query = 'SELECT id, terceiro, servico, quantidade, valor_unitario, valor_total, data_servico, pago FROM ordens WHERE 1=1'
    params = []

    if terceiro:
        query += ' AND terceiro = ?'
        params.append(terceiro)
    
    if data_inicio:
        query += ' AND data_servico >= ?'
        params.append(data_inicio)

    if data_fim:
        query += ' AND data_servico <= ?'
        params.append(data_fim)

    if pago != '':
        query += ' AND pago = ?'
        params.append(int(pago))

    query += ' ORDER BY data_servico DESC, id DESC'

    cursor.execute(query, params)
    registros = cursor.fetchall()
    conn.close()
    return jsonify(registros)

@app.route('/alterar_status_pago/<int:os_id>', methods=['POST'])
@login_required
def alterar_status_pago(os_id):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('UPDATE ordens SET pago = CASE WHEN pago = 1 THEN 0 ELSE 1 END WHERE id = ?', (os_id,))
    conn.commit()
    conn.close()
    return jsonify({"status": "sucesso"})

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