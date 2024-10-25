from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime



# Inicializar o Flask
app = Flask(__name__)

# Configurações do Banco de Dados SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///events.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.secret_key = 'sua_chave_secreta_aqui'

# Inicializar o Banco de Dados
db = SQLAlchemy(app)

# Modelo de Usuário
class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(50), unique=True, nullable=False)
    email = db.Column(db.String(100), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    balance = db.Column(db.Float, default=0.0)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return f'<User {self.username}>'

# Modelo de Evento
class Event(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(50), nullable=False)
    description = db.Column(db.String(150), nullable=False)
    value = db.Column(db.Float, nullable=False)
    start_date = db.Column(db.String(10), nullable=False)
    end_date = db.Column(db.String(10), nullable=False)
    event_date = db.Column(db.String(10), nullable=False)

    def __repr__(self):
        return f'<Event {self.title}>'

# Modelo de Transação
class Transaction(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    type = db.Column(db.String(50), nullable=False)
    amount = db.Column(db.Float, nullable=False)
    timestamp = db.Column(db.DateTime, server_default=db.func.current_timestamp())

    def __repr__(self):
        return f'<Transaction {self.type} - {self.amount}>'

# Função para proteger rotas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        return f(*args, **kwargs)
    return decorated_function

# Rotas do aplicativo
@app.route('/', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Verificar se o usuário existe e se a senha está correta
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect('/home')
        else:
            message = 'Usuário ou senha incorretos.'

    return render_template('login.html', message=message)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    message = ''
    if request.method == 'POST':
        try:
            username = request.form['username']
            email = request.form['email']
            password = request.form['password']
        except KeyError as e:
            message = f'Erro no campo: {e}'
            return render_template('signup.html', message=message)

        # Verificar se o email ou username já existem
        print(f"Tentando registrar usuário: {username}, email: {email}")
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            message = 'Usuário ou email já cadastrado.'
            print("Usuário já existe no banco de dados")
        else:
            try:
                new_user = User(username=username, email=email)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                message = 'Usuário registrado com sucesso!'
                print("Usuário registrado com sucesso!")
            except Exception as e:
                message = "Erro ao registrar o usuário."
                print("Erro ao registrar o usuário:", e)

    return render_template('signup.html', message=message)

@app.route('/home')
@login_required
def home():
    user = User.query.get(session['user_id'])
    events = Event.query.all()  # Pegar todos os eventos do banco de dados
    return render_template('home.html', user=user, events=events)


@app.route('/search', methods=['GET'])
@login_required
def search():
    query = request.args.get('query', '')
    if query:
        results = Event.query.filter(
            Event.title.ilike(f"%{query}%") | Event.description.ilike(f"%{query}%")
        ).all()
    else:
        results = []

    return render_template('search_results.html', query=query, results=results)


# Código em app.py (parte de criação de evento)

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    message = ''
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form['description']
            value = float(request.form['value'])
            start_date = datetime.strptime(request.form['start_date'], "%Y-%m-%d %H:%M")
            end_date = datetime.strptime(request.form['end_date'], "%Y-%m-%d %H:%M")
            event_date = datetime.strptime(request.form['event_date'], "%Y-%m-%d").date()
            
            if len(title) > 50:
                message = 'O título deve ter no máximo 50 caracteres.'
            elif len(description) > 150:
                message = 'A descrição deve ter no máximo 150 caracteres.'
            elif value < 1:
                message = 'O valor de cada cota deve ser no mínimo R$ 1,00.'
            elif start_date >= end_date:
                message = 'A data de início deve ser antes da data de término.'
            elif end_date >= event_date:
                message = 'A data do evento deve ser após o período de recebimento das apostas.'
            else:
                # Criar um novo evento
                new_event = Event(
                    title=title,
                    description=description,
                    value=value,
                    start_date=start_date.strftime("%Y-%m-%d %H:%M"),
                    end_date=end_date.strftime("%Y-%m-%d %H:%M"),
                    event_date=event_date.strftime("%Y-%m-%d")
                )

                # Adicionar ao banco de dados
                db.session.add(new_event)
                db.session.commit()
                message = "Evento criado com sucesso!"
                return redirect('/home')

        except ValueError:
            message = 'Por favor, insira valores válidos para as datas e valor da cota.'

    return render_template('create_event.html', message=message)


@app.route('/bet/<int:event_id>', methods=['GET', 'POST'])
@login_required
def place_bet(event_id):
    event = Event.query.get_or_404(event_id)
    message = ''
    if request.method == 'POST':
        amount = float(request.form['amount'])
        user = User.query.get(session['user_id'])

        if user.balance >= amount:
            # Subtrair valor da aposta do saldo do usuário
            user.balance -= amount

            # Registrar a aposta (neste exemplo, apenas imprimindo no console)
            print(f"Usuário {user.username} apostou R$ {amount} no evento {event.title}")

            # Salvar as mudanças no banco de dados
            db.session.commit()

            # Registrar a transação
            new_transaction = Transaction(user_id=user.id, type='bet', amount=-amount)
            db.session.add(new_transaction)
            db.session.commit()

            message = "Aposta realizada com sucesso!"
        else:
            message = "Saldo insuficiente para realizar a aposta."

    return render_template('bet.html', event=event, message=message)

# Código em app.py
@app.route('/wallet', methods=['GET', 'POST'])
@login_required
def wallet():
    user = User.query.get(session['user_id'])
    message = ''

    if request.method == 'POST':
        action = request.form.get('action')
        
        if action == 'deposit':
            # Depósito
            try:
                amount = float(request.form['amount'])
                if amount > 0:
                    user.balance += amount
                    db.session.add(Transaction(user_id=user.id, type='deposit', amount=amount))
                    db.session.commit()
                    message = "Saldo adicionado com sucesso!"
                else:
                    message = "O valor deve ser maior que zero."
            except ValueError:
                message = "Por favor, insira um valor numérico válido."

        elif action == 'withdraw':
            # Saque
            try:
                amount = float(request.form['withdraw_amount'])
                if amount > 0 and amount <= user.balance:
                    if amount > 101000:
                        message = "O valor máximo de saque por dia é de R$ 101.000,00."
                    else:
                        # Calculando a taxa
                        if amount <= 100:
                            fee = amount * 0.04
                        elif amount <= 1000:
                            fee = amount * 0.03
                        elif amount <= 5000:
                            fee = amount * 0.02
                        elif amount <= 100000:
                            fee = amount * 0.01
                        else:
                            fee = 0.0

                        total_withdraw = amount + fee
                        
                        if total_withdraw > user.balance:
                            message = f"Saldo insuficiente para realizar o saque com a taxa aplicada de R$ {fee:.2f}."
                        else:
                            user.balance -= total_withdraw
                            db.session.add(Transaction(user_id=user.id, type='withdraw', amount=amount, fee=fee))
                            db.session.commit()
                            message = f"Saque de R$ {amount:.2f} realizado com sucesso! Taxa de R$ {fee:.2f} aplicada."
                else:
                    message = "O valor deve ser maior que zero e menor ou igual ao saldo disponível."
            except ValueError:
                message = "Por favor, insira um valor numérico válido."

    transactions = Transaction.query.filter_by(user_id=user.id).all()
    return render_template('wallet.html', user=user, message=message, transactions=transactions)


@app.route('/welcome', methods=['GET'])
def welcome():
    return render_template('welcome.html')

from flask import send_from_directory

@app.route('/static/images/<path:filename>')
def custom_static(filename):
    return send_from_directory('static/images', filename)

@app.route('/withdraw', methods=['POST'])
@login_required
def withdraw():
    user = User.query.get(session['user_id'])
    message = ''

    if request.method == 'POST':
        try:
            withdraw_amount = float(request.form['withdraw_amount'])
            if withdraw_amount <= 0:
                message = "O valor do saque deve ser maior que zero."
            elif withdraw_amount > user.balance:
                message = "Saldo insuficiente para realizar o saque."
            else:
                # Calcular a taxa com base na tabela fornecida
                if withdraw_amount <= 100:
                    fee_rate = 0.04
                elif withdraw_amount <= 1000:
                    fee_rate = 0.03
                elif withdraw_amount <= 5000:
                    fee_rate = 0.02
                elif withdraw_amount <= 100000:
                    fee_rate = 0.01
                else:
                    fee_rate = 0.0

                fee = withdraw_amount * fee_rate
                total_withdraw = withdraw_amount + fee

                if total_withdraw > user.balance:
                    message = "Saldo insuficiente para realizar o saque e pagar a taxa."
                else:
                    user.balance -= total_withdraw
                    db.session.commit()
                    message = f"Saque de R$ {withdraw_amount:.2f} realizado com sucesso! Taxa aplicada: R$ {fee:.2f}."

        except ValueError:
            message = "Por favor, insira um valor numérico válido."

    return redirect(url_for('wallet', message=message))

@app.route('/logout')
@login_required
def logout():
    # Limpar a sessão do usuário
    session.pop('user_id', None)
    return redirect('/')




# Iniciar o servidor Flask
if __name__ == "__main__":
    app.run(debug=True)
