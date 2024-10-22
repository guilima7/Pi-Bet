from flask import Flask, render_template, request, redirect, session, url_for
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

# Inicializar o Flask
app = Flask(__name__)

# Configurações do Banco de Dados SQLite
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///instance/events.db'
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

# Função para proteger rotas
def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'user_id' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Rotas do aplicativo
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        # Verificar se o usuário existe e se a senha está correta
        user = User.query.filter_by(username=username).first()
        if user and user.check_password(password):
            session['user_id'] = user.id
            return redirect(url_for('home'))
        else:
            message = 'Usuário ou senha incorretos.'

    return render_template('login.html', message=message)

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    message = ''
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']

        # Verificar se o email ou username já existem
        existing_user = User.query.filter((User.username == username) | (User.email == email)).first()
        if existing_user:
            message = 'Usuário ou email já cadastrado.'
        else:
            new_user = User(username=username, email=email)
            new_user.set_password(password)
            db.session.add(new_user)
            db.session.commit()
            message = 'Usuário registrado com sucesso!'
            return redirect(url_for('login'))

    return render_template('signup.html', message=message)

@app.route('/home')
@login_required
def home():
    return render_template('home.html')

@app.route('/create_event', methods=['GET', 'POST'])
@login_required
def create_event():
    message = ''
    if request.method == 'POST':
        title = request.form['title']
        description = request.form['description']
        value = request.form['value']
        start_date = request.form['start_date']
        end_date = request.form['end_date']
        event_date = request.form['event_date']

        # Criar um novo evento
        new_event = Event(
            title=title,
            description=description,
            value=value,
            start_date=start_date,
            end_date=end_date,
            event_date=event_date
        )

        # Adicionar ao banco de dados
        db.session.add(new_event)
        db.session.commit()

        message = "Evento criado com sucesso!"
        return redirect(url_for('home'))

    return render_template('create_event.html', message=message)

# Rota para logout
@app.route('/logout')
@login_required
def logout():
    session.pop('user_id', None)
    return redirect(url_for('login'))

# Iniciar o servidor Flask
if __name__ == "__main__":
    with app.app_context():
        db.create_all()  # Cria as tabelas se ainda não existirem
    app.run(debug=True)
