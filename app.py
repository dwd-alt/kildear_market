import os
import re
import random
import string
import secrets
from datetime import datetime, timedelta
from functools import wraps
import pyotp
import bleach
from PIL import Image
import io
import base64

from flask import Flask, render_template, request, jsonify, session, redirect, url_for, flash, abort
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from flask_mail import Mail, Message
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
import re


# Конфигурация
class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'kildear-super-secret-key-2025-change-in-production'

    # База данных PostgreSQL
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        'DATABASE_URL') or 'postgresql://kildear_user:ВАШ_ПАРОЛЬ@dpg-d6ncpsa4d50c73dev6tg-a.singapore-postgres.render.com:5432/kildear_db'
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # Email настройки (используйте реальные в production)
    MAIL_SERVER = 'smtp.gmail.com'
    MAIL_PORT = 587
    MAIL_USE_TLS = True
    MAIL_USERNAME = os.environ.get('MAIL_USERNAME') or 'noreply@kildear.com'
    MAIL_PASSWORD = os.environ.get('MAIL_PASSWORD') or 'your-app-password'
    MAIL_DEFAULT_SENDER = ('Kildear Marketplace', 'noreply@kildear.com')

    # Безопасность
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SECURE = False  # True в production с HTTPS
    SESSION_COOKIE_SAMESITE = 'Lax'
    PERMANENT_SESSION_LIFETIME = timedelta(hours=2)

    # Rate limiting
    RATELIMIT_ENABLED = True
    RATELIMIT_DEFAULT = "100/hour"
    RATELIMIT_STORAGE_URL = "memory://"

    # Загрузка файлов
    MAX_CONTENT_LENGTH = 16 * 1024 * 1024  # 16MB
    UPLOAD_FOLDER = 'static/uploads'
    ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}

    # Настройки маркетплейса
    MAX_LISTINGS_PER_SELLER = 50
    VERIFICATION_REQUIRED = True
    ITEMS_PER_PAGE = 24


# Инициализация приложения
app = Flask(__name__)
app.config.from_object(Config)

# Убедимся, что папка для загрузок существует
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

# Инициализация расширений
db = SQLAlchemy(app)
mail = Mail(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице.'

# Rate limiter для защиты от DDoS и брутфорса
limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)


# Модели базы данных
class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(120), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(200), nullable=False)
    full_name = db.Column(db.String(100), nullable=False)
    phone = db.Column(db.String(20))
    is_verified = db.Column(db.Boolean, default=False)
    verification_code = db.Column(db.String(6))
    code_expiry = db.Column(db.DateTime)
    twofa_secret = db.Column(db.String(32), default=lambda: pyotp.random_base32())
    is_seller = db.Column(db.Boolean, default=False)
    is_pvz_owner = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    last_login = db.Column(db.DateTime)
    login_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime)

    # Отношения
    listings = db.relationship('Listing', backref='seller', lazy=True, foreign_keys='Listing.seller_id')
    orders = db.relationship('Order', backref='buyer', lazy=True)
    pvz_points = db.relationship('PVZPoint', backref='owner', lazy=True)
    cart_items = db.relationship('CartItem', backref='user', lazy=True)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def generate_verification_code(self):
        self.verification_code = ''.join(random.choices(string.digits, k=6))
        self.code_expiry = datetime.utcnow() + timedelta(minutes=10)
        return self.verification_code

    def verify_code(self, code):
        if self.code_expiry and self.code_expiry > datetime.utcnow() and self.verification_code == code:
            self.is_verified = True
            self.verification_code = None
            self.code_expiry = None
            db.session.commit()
            return True
        return False


class SellerProfile(db.Model):
    __tablename__ = 'seller_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), unique=True)
    company_name = db.Column(db.String(200))
    inn = db.Column(db.String(12), unique=True)
    legal_address = db.Column(db.String(500))
    bank_details = db.Column(db.String(500))
    commission_rate = db.Column(db.Float, default=5.0)  # Комиссия маркетплейса %
    is_approved = db.Column(db.Boolean, default=False)
    approved_at = db.Column(db.DateTime)
    total_sales = db.Column(db.Integer, default=0)
    rating = db.Column(db.Float, default=0.0)


class PVZPoint(db.Model):
    __tablename__ = 'pvz_points'

    id = db.Column(db.Integer, primary_key=True)
    owner_id = db.Column(db.Integer, db.ForeignKey('users.id'))
    name = db.Column(db.String(200), nullable=False)
    address = db.Column(db.String(500), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Float)
    longitude = db.Column(db.Float)
    working_hours = db.Column(db.String(200))
    phone = db.Column(db.String(20))
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    orders = db.relationship('Order', backref='pvz_point', lazy=True)


class Category(db.Model):
    __tablename__ = 'categories'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    slug = db.Column(db.String(100), unique=True)
    parent_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    image = db.Column(db.String(500))

    children = db.relationship('Category', backref=db.backref('parent', remote_side=[id]))
    listings = db.relationship('Listing', backref='category', lazy=True)


class Listing(db.Model):
    __tablename__ = 'listings'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    category_id = db.Column(db.Integer, db.ForeignKey('categories.id'))
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Float, nullable=False)
    old_price = db.Column(db.Float)
    quantity = db.Column(db.Integer, default=1)
    images = db.Column(db.JSON)  # Список URL изображений
    condition = db.Column(db.String(50))  # new, used, refurbished
    status = db.Column(db.String(20), default='active')  # active, sold, hidden
    views = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    # Модерация
    is_moderated = db.Column(db.Boolean, default=False)
    moderated_at = db.Column(db.DateTime)
    moderation_comment = db.Column(db.String(500))

    order_items = db.relationship('OrderItem', backref='listing', lazy=True)

    def to_dict(self):
        return {
            'id': self.id,
            'title': self.title,
            'price': self.price,
            'old_price': self.old_price,
            'images': self.images,
            'seller_name': self.seller.full_name,
            'created_at': self.created_at.isoformat() if self.created_at else None
        }


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(50), unique=True, nullable=False)
    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    pvz_id = db.Column(db.Integer, db.ForeignKey('pvz_points.id'))
    total_amount = db.Column(db.Float, nullable=False)
    status = db.Column(db.String(50), default='pending')  # pending, paid, shipped, delivered, cancelled
    payment_method = db.Column(db.String(50))
    payment_status = db.Column(db.String(50), default='unpaid')
    shipping_address = db.Column(db.String(500))
    tracking_number = db.Column(db.String(200))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, onupdate=datetime.utcnow)

    items = db.relationship('OrderItem', backref='order', lazy=True)


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    price = db.Column(db.Float, nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'))


class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    added_at = db.Column(db.DateTime, default=datetime.utcnow)

    listing = db.relationship('Listing')


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    listing_id = db.Column(db.Integer, db.ForeignKey('listings.id'), nullable=False)
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    user = db.relationship('User')


# Функции безопасности
def sanitize_html(text):
    """Очистка HTML от опасных тегов"""
    allowed_tags = ['b', 'i', 'u', 'p', 'br', 'strong', 'em', 'h1', 'h2', 'h3', 'ul', 'ol', 'li']
    return bleach.clean(text, tags=allowed_tags, strip=True)


def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in app.config['ALLOWED_EXTENSIONS']


def validate_image(file):
    """Валидация и оптимизация изображения"""
    if file and allowed_file(file.filename):
        filename = secure_filename(file.filename)
        # Генерируем уникальное имя
        ext = filename.rsplit('.', 1)[1].lower()
        new_filename = f"{secrets.token_hex(16)}.{ext}"

        # Оптимизируем изображение
        image = Image.open(file)
        # Изменяем размер если слишком большое
        if image.width > 1200:
            ratio = 1200 / image.width
            new_size = (1200, int(image.height * ratio))
            image = image.resize(new_size, Image.Resampling.LANCZOS)

        # Сохраняем
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], new_filename)
        image.save(save_path, optimize=True, quality=85)

        return new_filename
    return None


def rate_limit_key_prefix():
    """Создает ключ для rate limiting на основе пользователя"""
    if current_user.is_authenticated:
        return f"user:{current_user.id}"
    return f"ip:{get_remote_address()}"


# Декораторы для проверки прав
def seller_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_seller:
            flash('Требуется аккаунт продавца.', 'danger')
            return redirect(url_for('become_seller'))
        return f(*args, **kwargs)

    return decorated_function


def pvz_owner_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or not current_user.is_pvz_owner:
            flash('Требуется аккаунт владельца ПВЗ.', 'danger')
            return redirect(url_for('become_pvz_owner'))
        return f(*args, **kwargs)

    return decorated_function


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(User, int(user_id))


# Функции для email
def send_verification_email(user):
    """Отправка кода подтверждения на email"""
    try:
        code = user.generate_verification_code()
        db.session.commit()

        msg = Message('Подтверждение email на Kildear',
                      recipients=[user.email])
        msg.html = f"""
        <h1>Добро пожаловать в Kildear!</h1>
        <p>Ваш код подтверждения: <strong>{code}</strong></p>
        <p>Код действителен в течение 10 минут.</p>
        <p>Если вы не регистрировались на Kildear, просто проигнорируйте это письмо.</p>
        """
        mail.send(msg)
        return True
    except Exception as e:
        print(f"Email error: {e}")
        return False


def send_order_notification(order):
    """Отправка уведомления о заказе"""
    try:
        msg = Message(f'Заказ #{order.order_number} оформлен',
                      recipients=[order.buyer.email])
        msg.html = f"""
        <h1>Спасибо за заказ в Kildear!</h1>
        <p>Номер заказа: <strong>{order.order_number}</strong></p>
        <p>Сумма заказа: {order.total_amount} ₽</p>
        <p>Статус: {order.status}</p>
        <p>Вы можете отслеживать статус заказа в личном кабинете.</p>
        """
        mail.send(msg)
    except Exception as e:
        print(f"Order email error: {e}")


# Маршруты аутентификации
@app.route('/')
def index():
    page = request.args.get('page', 1, type=int)
    category_id = request.args.get('category', type=int)
    search = request.args.get('search', '')

    query = Listing.query.filter_by(status='active', is_moderated=True)

    if category_id:
        query = query.filter_by(category_id=category_id)

    if search:
        search_term = f"%{search}%"
        query = query.filter(
            db.or_(
                Listing.title.ilike(search_term),
                Listing.description.ilike(search_term)
            )
        )

    listings = query.order_by(Listing.created_at.desc()).paginate(
        page=page, per_page=app.config['ITEMS_PER_PAGE'], error_out=False
    )

    categories = Category.query.all()

    return render_template('index.html',
                           listings=listings,
                           categories=categories,
                           search=search)


@app.route('/register', methods=['GET', 'POST'])
@limiter.limit("5/hour")
def register():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        full_name = bleach.clean(request.form.get('full_name', '').strip())
        phone = bleach.clean(request.form.get('phone', '').strip())

        # Валидация
        if not re.match(r"[^@]+@[^@]+\.[^@]+", email):
            flash('Некорректный email адрес', 'danger')
            return redirect(url_for('register'))

        if len(password) < 8:
            flash('Пароль должен быть минимум 8 символов', 'danger')
            return redirect(url_for('register'))

        # Проверка существующего пользователя
        if User.query.filter_by(email=email).first():
            flash('Пользователь с таким email уже существует', 'danger')
            return redirect(url_for('register'))

        # Создание пользователя
        user = User(
            email=email,
            full_name=full_name,
            phone=phone
        )
        user.set_password(password)

        db.session.add(user)
        db.session.commit()

        # Отправка кода подтверждения
        if send_verification_email(user):
            session['verification_email'] = email
            return redirect(url_for('verify'))
        else:
            flash('Ошибка при отправке кода. Попробуйте позже.', 'warning')
            return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/verify', methods=['GET', 'POST'])
def verify():
    email = session.get('verification_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if not user:
        return redirect(url_for('login'))

    if request.method == 'POST':
        code = request.form.get('code', '')

        if user.verify_code(code):
            flash('Email успешно подтвержден! Теперь вы можете войти.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Неверный или просроченный код', 'danger')

    return render_template('verify.html', email=email)


@app.route('/login', methods=['GET', 'POST'])
@limiter.limit("10/hour")
def login():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember', False)

        user = User.query.filter_by(email=email).first()

        # Проверка блокировки
        if user and user.locked_until and user.locked_until > datetime.utcnow():
            flash(f'Аккаунт заблокирован до {user.locked_until}', 'danger')
            return redirect(url_for('login'))

        if user and user.check_password(password):
            if app.config['VERIFICATION_REQUIRED'] and not user.is_verified:
                session['verification_email'] = email
                send_verification_email(user)
                flash('Пожалуйста, подтвердите email', 'warning')
                return redirect(url_for('verify'))

            # Сброс попыток входа
            user.login_attempts = 0
            user.locked_until = None
            user.last_login = datetime.utcnow()
            db.session.commit()

            login_user(user, remember=remember)

            # Перенаправление на следующую страницу или на главную
            next_page = request.args.get('next')
            return redirect(next_page) if next_page else redirect(url_for('index'))
        else:
            if user:
                user.login_attempts += 1
                if user.login_attempts >= 5:
                    user.locked_until = datetime.utcnow() + timedelta(minutes=15)
                db.session.commit()

            flash('Неверный email или пароль', 'danger')

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    logout_user()
    flash('Вы вышли из аккаунта', 'info')
    return redirect(url_for('index'))


@app.route('/resend-code')
@limiter.limit("3/hour")
def resend_code():
    email = session.get('verification_email')
    if not email:
        return redirect(url_for('login'))

    user = User.query.filter_by(email=email).first()
    if user and not user.is_verified:
        send_verification_email(user)
        flash('Новый код отправлен на вашу почту', 'success')

    return redirect(url_for('verify'))


# Маршруты для профиля
@app.route('/profile')
@login_required
def profile():
    user_listings = Listing.query.filter_by(seller_id=current_user.id).count()
    user_orders = Order.query.filter_by(buyer_id=current_user.id).all()

    return render_template('profile.html',
                           listings_count=user_listings,
                           orders=user_orders)


@app.route('/profile/edit', methods=['POST'])
@login_required
def edit_profile():
    current_user.full_name = bleach.clean(request.form.get('full_name', current_user.full_name))
    current_user.phone = bleach.clean(request.form.get('phone', current_user.phone))

    db.session.commit()
    flash('Профиль обновлен', 'success')
    return redirect(url_for('profile'))


# Маршруты для продавцов
@app.route('/become-seller', methods=['GET', 'POST'])
@login_required
def become_seller():
    if current_user.is_seller:
        return redirect(url_for('seller_dashboard'))

    if request.method == 'POST':
        company_name = bleach.clean(request.form.get('company_name', ''))
        inn = bleach.clean(request.form.get('inn', ''))
        legal_address = bleach.clean(request.form.get('legal_address', ''))
        bank_details = bleach.clean(request.form.get('bank_details', ''))

        # Проверка ИНН
        if not re.match(r'^\d{10}$|^\d{12}$', inn):
            flash('Некорректный ИНН', 'danger')
            return redirect(url_for('become_seller'))

        seller_profile = SellerProfile(
            user_id=current_user.id,
            company_name=company_name,
            inn=inn,
            legal_address=legal_address,
            bank_details=bank_details
        )

        current_user.is_seller = True
        db.session.add(seller_profile)
        db.session.commit()

        flash('Заявка на статус продавца отправлена на проверку', 'success')
        return redirect(url_for('seller_dashboard'))

    return render_template('become_seller.html')


@app.route('/seller/dashboard')
@login_required
@seller_required
def seller_dashboard():
    listings = Listing.query.filter_by(seller_id=current_user.id).order_by(Listing.created_at.desc()).all()
    orders_count = OrderItem.query.filter_by(seller_id=current_user.id).count()
    total_sales = db.session.query(db.func.sum(OrderItem.price * OrderItem.quantity)) \
                      .filter(OrderItem.seller_id == current_user.id).scalar() or 0

    return render_template('seller_dashboard.html',
                           listings=listings,
                           orders_count=orders_count,
                           total_sales=total_sales)


@app.route('/listing/create', methods=['GET', 'POST'])
@login_required
@seller_required
def create_listing():
    if request.method == 'POST':
        title = bleach.clean(request.form.get('title', '').strip())
        description = sanitize_html(request.form.get('description', ''))
        price = float(request.form.get('price', 0))
        category_id = int(request.form.get('category_id', 0))
        quantity = int(request.form.get('quantity', 1))
        condition = request.form.get('condition', 'new')

        # Проверка лимита объявлений
        current_listings = Listing.query.filter_by(seller_id=current_user.id).count()
        if current_listings >= app.config['MAX_LISTINGS_PER_SELLER']:
            flash(f'Достигнут лимит объявлений ({app.config["MAX_LISTINGS_PER_SELLER"]})', 'danger')
            return redirect(url_for('seller_dashboard'))

        # Обработка изображений
        images = []
        files = request.files.getlist('images')
        for file in files[:5]:  # Максимум 5 изображений
            if file and file.filename:
                filename = validate_image(file)
                if filename:
                    images.append(f'/static/uploads/{filename}')

        listing = Listing(
            seller_id=current_user.id,
            category_id=category_id,
            title=title,
            description=description,
            price=price,
            quantity=quantity,
            condition=condition,
            images=images
        )

        db.session.add(listing)
        db.session.commit()

        flash('Объявление создано и отправлено на модерацию', 'success')
        return redirect(url_for('seller_dashboard'))

    categories = Category.query.all()
    return render_template('create_listing.html', categories=categories)


@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)

    # Увеличиваем счетчик просмотров
    listing.views += 1
    db.session.commit()

    similar_listings = Listing.query.filter(
        Listing.category_id == listing.category_id,
        Listing.id != listing.id,
        Listing.status == 'active'
    ).limit(4).all()

    return render_template('listing_detail.html',
                           listing=listing,
                           similar=similar_listings)


# Маршруты для ПВЗ
@app.route('/become-pvz-owner', methods=['GET', 'POST'])
@login_required
def become_pvz_owner():
    if current_user.is_pvz_owner:
        return redirect(url_for('pvz_dashboard'))

    if request.method == 'POST':
        name = bleach.clean(request.form.get('name', ''))
        address = bleach.clean(request.form.get('address', ''))
        city = bleach.clean(request.form.get('city', ''))
        working_hours = bleach.clean(request.form.get('working_hours', ''))
        phone = bleach.clean(request.form.get('phone', ''))

        pvz = PVZPoint(
            owner_id=current_user.id,
            name=name,
            address=address,
            city=city,
            working_hours=working_hours,
            phone=phone
        )

        current_user.is_pvz_owner = True
        db.session.add(pvz)
        db.session.commit()

        flash('ПВЗ успешно создан', 'success')
        return redirect(url_for('pvz_dashboard'))

    return render_template('become_pvz_owner.html')


@app.route('/pvz/dashboard')
@login_required
@pvz_owner_required
def pvz_dashboard():
    pvz_points = PVZPoint.query.filter_by(owner_id=current_user.id).all()
    pvz_ids = [p.id for p in pvz_points]

    incoming_orders = Order.query.filter(
        Order.pvz_id.in_(pvz_ids),
        Order.status.in_(['paid', 'shipped'])
    ).order_by(Order.created_at.desc()).all()

    return render_template('pvz_dashboard.html',
                           pvz_points=pvz_points,
                           incoming_orders=incoming_orders)


# Корзина и заказы
@app.route('/cart')
@login_required
def cart():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    total = sum(item.listing.price * item.quantity for item in cart_items)

    return render_template('cart.html', cart_items=cart_items, total=total)


@app.route('/cart/add/<int:listing_id>', methods=['POST'])
@login_required
def add_to_cart(listing_id):
    listing = db.session.get(Listing, listing_id)
    if not listing or listing.status != 'active':
        return jsonify({'error': 'Товар не найден'}), 404

    quantity = int(request.json.get('quantity', 1))

    cart_item = CartItem.query.filter_by(
        user_id=current_user.id,
        listing_id=listing_id
    ).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(
            user_id=current_user.id,
            listing_id=listing_id,
            quantity=quantity
        )
        db.session.add(cart_item)

    db.session.commit()

    cart_count = CartItem.query.filter_by(user_id=current_user.id).count()

    return jsonify({
        'success': True,
        'cart_count': cart_count,
        'message': 'Товар добавлен в корзину'
    })


@app.route('/cart/remove/<int:item_id>', methods=['POST'])
@login_required
def remove_from_cart(item_id):
    cart_item = db.session.get(CartItem, item_id)
    if cart_item and cart_item.user_id == current_user.id:
        db.session.delete(cart_item)
        db.session.commit()

    return redirect(url_for('cart'))


@app.route('/checkout', methods=['POST'])
@login_required
def checkout():
    cart_items = CartItem.query.filter_by(user_id=current_user.id).all()
    if not cart_items:
        flash('Корзина пуста', 'warning')
        return redirect(url_for('cart'))

    # Создание заказа
    total = sum(item.listing.price * item.quantity for item in cart_items)
    order_number = f"ORD-{datetime.utcnow().strftime('%Y%m%d')}-{secrets.token_hex(4).upper()}"

    order = Order(
        order_number=order_number,
        buyer_id=current_user.id,
        pvz_id=request.form.get('pvz_id', type=int),
        total_amount=total,
        status='pending'
    )

    db.session.add(order)
    db.session.flush()

    # Создание позиций заказа
    for item in cart_items:
        order_item = OrderItem(
            order_id=order.id,
            listing_id=item.listing_id,
            quantity=item.quantity,
            price=item.listing.price,
            seller_id=item.listing.seller_id
        )
        db.session.add(order_item)

        # Уменьшаем количество товара
        item.listing.quantity -= item.quantity
        if item.listing.quantity <= 0:
            item.listing.status = 'sold'

        db.session.delete(item)  # Удаляем из корзины

    db.session.commit()

    # Отправка уведомлений
    send_order_notification(order)

    flash(f'Заказ #{order_number} успешно оформлен', 'success')
    return redirect(url_for('profile'))


# API для поиска и фильтрации
@app.route('/api/search')
def api_search():
    query = request.args.get('q', '')
    category = request.args.get('category', type=int)
    min_price = request.args.get('min_price', type=float)
    max_price = request.args.get('max_price', type=float)
    sort = request.args.get('sort', 'newest')

    listings_query = Listing.query.filter_by(status='active', is_moderated=True)

    if query:
        search_term = f"%{query}%"
        listings_query = listings_query.filter(
            db.or_(
                Listing.title.ilike(search_term),
                Listing.description.ilike(search_term)
            )
        )

    if category:
        listings_query = listings_query.filter_by(category_id=category)

    if min_price:
        listings_query = listings_query.filter(Listing.price >= min_price)

    if max_price:
        listings_query = listings_query.filter(Listing.price <= max_price)

    # Сортировка
    if sort == 'price_asc':
        listings_query = listings_query.order_by(Listing.price.asc())
    elif sort == 'price_desc':
        listings_query = listings_query.order_by(Listing.price.desc())
    elif sort == 'popular':
        listings_query = listings_query.order_by(Listing.views.desc())
    else:  # newest
        listings_query = listings_query.order_by(Listing.created_at.desc())

    listings = listings_query.limit(50).all()

    return jsonify([l.to_dict() for l in listings])


# Административные маршруты (упрощенно)
@app.route('/admin/moderate')
@login_required
def moderate_listings():
    # В реальном проекте здесь должна быть проверка на администратора
    if current_user.email != 'admin@kildear.com':
        abort(403)

    pending = Listing.query.filter_by(is_moderated=False).all()
    return render_template('moderate.html', listings=pending)


@app.route('/admin/moderate/<int:listing_id>/<action>', methods=['POST'])
@login_required
def moderate_action(listing_id, action):
    if current_user.email != 'admin@kildear.com':
        abort(403)

    listing = db.session.get(Listing, listing_id)
    if not listing:
        abort(404)

    if action == 'approve':
        listing.is_moderated = True
        listing.moderated_at = datetime.utcnow()
        flash(f'Объявление "{listing.title}" одобрено', 'success')
    elif action == 'reject':
        comment = request.json.get('comment', '')
        listing.is_moderated = False
        listing.moderation_comment = comment
        flash(f'Объявление "{listing.title}" отклонено', 'warning')

    db.session.commit()
    return jsonify({'success': True})


# Обработчики ошибок
@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html'), 500


@app.errorhandler(429)
def ratelimit_error(error):
    return render_template('429.html', error=error), 429


# Создание таблиц и начальных данных
@app.cli.command("init-db")
def init_db():
    """Инициализация базы данных"""
    db.create_all()

    # Создание категорий
    categories = [
        {'name': 'Электроника', 'slug': 'electronics'},
        {'name': 'Одежда', 'slug': 'clothing'},
        {'name': 'Обувь', 'slug': 'shoes'},
        {'name': 'Аксессуары', 'slug': 'accessories'},
        {'name': 'Дом и сад', 'slug': 'home'},
        {'name': 'Красота', 'slug': 'beauty'},
        {'name': 'Спорт', 'slug': 'sports'},
        {'name': 'Детские товары', 'slug': 'kids'},
    ]

    for cat in categories:
        if not Category.query.filter_by(slug=cat['slug']).first():
            category = Category(name=cat['name'], slug=cat['slug'])
            db.session.add(category)

    # Создание тестового администратора
    if not User.query.filter_by(email='admin@kildear.com').first():
        admin = User(
            email='admin@kildear.com',
            full_name='Admin',
            is_verified=True,
            is_seller=True
        )
        admin.set_password('Admin123!')
        db.session.add(admin)

    db.session.commit()
    print("База данных инициализирована")


if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)
