from flask import Flask, render_template, request, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps
from datetime import datetime
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

# Função para enviar e-mail
def enviar_email(destinatario, assunto, mensagem):
    servidor_smtp = 'smtp.gmail.com'
    porta = 587
    usuario = 'seu_email@gmail.com'
    senha = 'sua_senha'

    email = MIMEMultipart()
    email['From'] = usuario
    email['To'] = destinatario
    email['Subject'] = assunto
    email.attach(MIMEText(mensagem, 'plain'))

    try:
        servidor = smtplib.SMTP(servidor_smtp, porta)
        servidor.starttls()
        servidor.login(usuario, senha)
        servidor.sendmail(usuario, destinatario, email.as_string())
        servidor.quit()
        print(f"E-mail enviado para {destinatario} com sucesso!")
    except Exception as e:
        print(f"Falha ao enviar e-mail: {str(e)}")

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
    role = db.Column(db.String(10), nullable=False, default='user')  # 'user' ou 'admin'

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
    status = db.Column(db.String(10), nullable=False, default='pending')  # 'pending' ou 'approved'
    result = db.Column(db.String(5))  # 'yes' ou 'no' ou None
    total_yes_bets = db.Column(db.Float, default=0.0)  # Valor total apostado no "Sim"
    total_no_bets = db.Column(db.Float, default=0.0)   # Valor total apostado no "Não"

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

# Função para proteger rotas de administrador
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect('/')
        user = User.query.get(session['user_id'])
        if user.role != 'admin':
            return redirect('/home')
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
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            message = 'Usuário ou email já cadastrado.'
        else:
            try:
                new_user = User(username=username, email=email)
                new_user.set_password(password)
                db.session.add(new_user)
                db.session.commit()
                message = 'Usuário registrado com sucesso!'
            except Exception as e:
                message = "Erro ao registrar o usuário."

    return render_template('signup.html', message=message)

@app.route('/welcome')
def welcome():
    return render_template('welcome.html')

@app.route('/home')
@login_required
def home():
    user = User.query.get(session['user_id'])
    events = Event.query.filter_by(status='approved').all()  # Pegar todos os eventos aprovados do banco de dados
    user_bets = Transaction.query.filter_by(user_id=user.id, type='bet').all()  # Filtrar apenas transações de apostas do usuário
    
    return render_template('home.html', user=user, events=events, user_bets=user_bets)

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

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    message = ''
    if request.method == 'POST':
        try:
            title = request.form['title']
            description = request.form['description']
            value = float(request.form['value'])
            start_date = request.form['start_date']
            end_date = request.form['end_date']
            event_date = request.form['event_date']

            # Validações
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
                # Criar um novo evento com status 'pending'
                new_event = Event(
                    title=title,
                    description=description,
                    value=value,
                    start_date=start_date,
                    end_date=end_date,
                    event_date=event_date,
                    status='pending'  # Certifique-se de que o status seja 'pending'
                )

                # Adicionar ao banco de dados
                db.session.add(new_event)
                db.session.commit()
                
                # Print para verificar o evento criado
                print(f"Evento criado: {new_event}")

                message = "Evento criado com sucesso! Aguardando aprovação do administrador."
                return redirect('/home')

        except ValueError:
            message = 'Por favor, insira valores válidos para as datas e valor da cota.'

    return render_template('create_event.html', message=message)

@app.route('/approve_events', methods=['GET', 'POST'])
@login_required
@admin_required
def approve_events():
    # Pegar todos os eventos que estão pendentes
    events = Event.query.filter_by(status='pending').all()

    if request.method == 'POST':
        event_id = request.form.get('event_id')
        action = request.form.get('action')

        # Buscar o evento correspondente
        event = Event.query.get(event_id)
        if event:
            if action == 'approve':
                event.status = 'approved'
            elif action == 'reject':
                db.session.delete(event)
            db.session.commit()

    return render_template('approve_events.html', events=events)

@app.route('/bet/<int:event_id>', methods=['GET', 'POST'])
@login_required
def place_bet(event_id):
    event = Event.query.get_or_404(event_id)
    message = ''
    if request.method == 'POST':
        bet_option = request.form['bet_option']  # "yes" ou "no"
        amount = float(request.form['amount'])
        user = User.query.get(session['user_id'])

        if user.balance >= amount:
            # Subtrair valor da aposta do saldo do usuário
            user.balance -= amount

            # Registrar a aposta no evento específico
            if bet_option == 'yes':
                event.total_yes_bets += amount
            elif bet_option == 'no':
                event.total_no_bets += amount

            # Salvar as mudanças no banco de dados
            db.session.commit()

            # Registrar a transação
            new_transaction = Transaction(user_id=user.id, type='bet', amount=-amount)
            db.session.add(new_transaction)
            db.session.commit()

            # Enviar um e-mail de confirmação para o usuário
            assunto = 'Confirmação da Aposta'
            mensagem = f'Obrigado por apostar no evento "{event.title}"! A sua aposta foi concluída com sucesso. Valor da aposta: R$ {amount:.2f}. Sua aposta foi no "{bet_option.upper()}".'
            enviar_email(user.email, assunto, mensagem)

            message = "Aposta realizada com sucesso! Um e-mail de confirmação foi enviado."
        else:
            message = "Saldo insuficiente para realizar a aposta."

    return render_template('bet.html', event=event, message=message)

@app.route('/wallet', methods=['GET', 'POST'])
@login_required
def wallet():
    user = User.query.get(session['user_id'])
    message = ''

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'deposit':
            try:
                amount = float(request.form['amount'])
                if amount > 0:
                    user.balance += amount
                    # Registrar a transação de depósito no banco de dados
                    db.session.add(Transaction(user_id=user.id, type='deposit', amount=amount))
                    db.session.commit()  # Commit para salvar as alterações no banco de dados
                    message = "Saldo adicionado com sucesso!"
                else:
                    message = "O valor deve ser maior que zero."
            except ValueError:
                message = "Por favor, insira um valor numérico válido."

        elif action == 'withdraw':
            try:
                amount = float(request.form['withdraw_amount'])
                if amount > 0 and amount <= user.balance:
                    user.balance -= amount
                    # Registrar a transação de saque no banco de dados
                    db.session.add(Transaction(user_id=user.id, type='withdraw', amount=amount))
                    db.session.commit()  # Commit para salvar as alterações no banco de dados
                    message = f"Saque de R$ {amount:.2f} realizado com sucesso!"
                else:
                    message = "O valor deve ser maior que zero e menor ou igual ao saldo disponível."
            except ValueError:
                message = "Por favor, insira um valor numérico válido."

    transactions = Transaction.query.filter_by(user_id=user.id).all()
    return render_template('wallet.html', user=user, message=message, transactions=transactions)

@app.route('/approve_result/<int:event_id>', methods=['GET', 'POST'])
@login_required
@admin_required
def approve_result(event_id):
    # Busca o evento pelo ID
    event = Event.query.get_or_404(event_id)
    
    if request.method == 'POST':
        result = request.form.get('result')

        if result not in ['yes', 'no']:
            message = 'Resultado inválido.'
            return render_template('approve_result.html', event=event, message=message)

        # Define o resultado do evento
        event.result = result
        db.session.commit()

        # Distribuir ganhos para os vencedores
        distribute_winnings(event)

        message = 'Resultado aprovado e ganhos distribuídos com sucesso!'
        return redirect(url_for('approve_events'))

    return render_template('approve_result.html', event=event)

def distribute_winnings(event):
    if event.result == 'yes':
        winning_amount = event.total_yes_bets
    else:
        winning_amount = event.total_no_bets

    total_amount = event.total_yes_bets + event.total_no_bets

    # Se houver um valor a ser distribuído
    if winning_amount > 0:
        payout_ratio = total_amount / winning_amount

        # Obter todos os usuários que apostaram no resultado correto
        bets = Transaction.query.filter_by(type='bet', event_id=event.id).all()

        for bet in bets:
            user = User.query.get(bet.user_id)
            if (event.result == 'yes' and bet.amount > 0) or (event.result == 'no' and bet.amount < 0):
                user.balance += abs(bet.amount) * payout_ratio
                db.session.add(user)

        db.session.commit()

@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    return redirect('/')

# Iniciar o servidor Flask
if __name__ == "__main__":
    app.run(debug=True)
