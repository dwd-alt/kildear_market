import os
import random
import string
from datetime import datetime
from flask import Flask, render_template, request, jsonify, flash, redirect, url_for, session
from flask_sqlalchemy import SQLAlchemy
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from dotenv import load_dotenv
import pytz

load_dotenv()

# Инициализация приложения
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'dev-key-change-in-production'

# Настройки PostgreSQL
app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get('DATABASE_URL') or \
                                        'postgresql://localhost/kildear_dev'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Настройки загрузки файлов
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB
app.config['UPLOAD_FOLDER'] = 'static/uploads'

# Настройки для Render
if os.environ.get('RENDER'):
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'
    app.config['REMEMBER_COOKIE_SECURE'] = True
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True

# Инициализация расширений
db = SQLAlchemy(app)
login_manager = LoginManager(app)
login_manager.login_view = 'login'
login_manager.login_message = 'Пожалуйста, войдите для доступа к этой странице'


# ==================== МОДЕЛИ БАЗЫ ДАННЫХ ====================

class User(UserMixin, db.Model):
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    password_hash = db.Column(db.String(200), nullable=False)
    first_name = db.Column(db.String(50))
    last_name = db.Column(db.String(50))
    phone = db.Column(db.String(20))
    avatar = db.Column(db.String(200))
    bio = db.Column(db.Text)
    rating = db.Column(db.Float, default=0.0)
    is_verified = db.Column(db.Boolean, default=False)
    is_admin = db.Column(db.Boolean, default=False)
    is_seller = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Отношения
    products = db.relationship('Product', backref='seller', lazy='dynamic')
    orders_as_buyer = db.relationship('Order', foreign_keys='Order.buyer_id', backref='buyer', lazy='dynamic')
    orders_as_seller = db.relationship('Order', foreign_keys='Order.seller_id', backref='seller', lazy='dynamic')
    reviews_given = db.relationship('Review', foreign_keys='Review.author_id', backref='author', lazy='dynamic')
    reviews_received = db.relationship('Review', foreign_keys='Review.user_id', backref='user', lazy='dynamic')
    cart = db.relationship('Cart', backref='user', uselist=False)
    notifications = db.relationship('Notification', backref='user', lazy='dynamic')

    @property
    def full_name(self):
        return f"{self.first_name} {self.last_name}".strip() or self.username

    @property
    def products_count(self):
        return self.products.filter_by(status='active').count()

    @property
    def completed_orders_count(self):
        return self.orders_as_seller.filter_by(status='completed').count()

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)


class Product(db.Model):
    __tablename__ = 'products'

    id = db.Column(db.Integer, primary_key=True)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    title = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text, nullable=False)
    price = db.Column(db.Numeric(10, 2), nullable=False)
    old_price = db.Column(db.Numeric(10, 2))
    category = db.Column(db.String(50), nullable=False)
    condition = db.Column(db.String(20), nullable=False)
    status = db.Column(db.String(20), default='pending')
    views = db.Column(db.Integer, default=0)
    sales_count = db.Column(db.Integer, default=0)

    # Характеристики (JSON поле)
    specifications = db.Column(db.JSON, default={})

    # Опции
    bargain = db.Column(db.Boolean, default=False)
    warranty = db.Column(db.Boolean, default=False)
    original = db.Column(db.Boolean, default=False)
    delivery_available = db.Column(db.Boolean, default=True)
    pickup_available = db.Column(db.Boolean, default=True)

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    published_at = db.Column(db.DateTime)

    # Отношения
    images = db.relationship('ProductImage', backref='product', cascade='all, delete-orphan')
    reviews = db.relationship('Review', backref='product', lazy='dynamic')
    cart_items = db.relationship('CartItem', backref='product', cascade='all, delete-orphan')
    order_items = db.relationship('OrderItem', backref='product', lazy='dynamic')

    @property
    def main_image(self):
        return self.images[0].url if self.images else '/static/img/no-image.jpg'

    @property
    def all_images(self):
        return [img.url for img in self.images]


class ProductImage(db.Model):
    __tablename__ = 'product_images'

    id = db.Column(db.Integer, primary_key=True)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    url = db.Column(db.String(500), nullable=False)
    is_main = db.Column(db.Boolean, default=False)
    order = db.Column(db.Integer, default=0)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Cart(db.Model):
    __tablename__ = 'carts'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False, unique=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    items = db.relationship('CartItem', backref='cart', cascade='all, delete-orphan')

    @property
    def subtotal(self):
        return sum(item.subtotal for item in self.items)

    @property
    def total_items(self):
        return sum(item.quantity for item in self.items)

    @property
    def items_count(self):
        return len(self.items)


class CartItem(db.Model):
    __tablename__ = 'cart_items'

    id = db.Column(db.Integer, primary_key=True)
    cart_id = db.Column(db.Integer, db.ForeignKey('carts.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    quantity = db.Column(db.Integer, default=1)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def subtotal(self):
        return self.product.price * self.quantity


class Order(db.Model):
    __tablename__ = 'orders'

    id = db.Column(db.Integer, primary_key=True)
    order_number = db.Column(db.String(20), unique=True, nullable=False)

    buyer_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    seller_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)

    status = db.Column(db.String(20), default='pending')
    payment_status = db.Column(db.String(20), default='pending')
    payment_method = db.Column(db.String(50))
    payment_id = db.Column(db.String(100))

    subtotal = db.Column(db.Numeric(10, 2), nullable=False)
    delivery_price = db.Column(db.Numeric(10, 2), default=0)
    discount = db.Column(db.Numeric(10, 2), default=0)
    total = db.Column(db.Numeric(10, 2), nullable=False)

    # Информация о доставке
    delivery_method = db.Column(db.String(50))
    delivery_address = db.Column(db.Text)
    delivery_city = db.Column(db.String(100))
    delivery_postal_code = db.Column(db.String(20))
    delivery_phone = db.Column(db.String(20))
    delivery_email = db.Column(db.String(120))
    recipient_name = db.Column(db.String(200))
    tracking_number = db.Column(db.String(100))
    delivery_notes = db.Column(db.Text)

    promo_code = db.Column(db.String(50))

    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    paid_at = db.Column(db.DateTime)
    shipped_at = db.Column(db.DateTime)
    delivered_at = db.Column(db.DateTime)
    completed_at = db.Column(db.DateTime)
    cancelled_at = db.Column(db.DateTime)

    items = db.relationship('OrderItem', backref='order', cascade='all, delete-orphan')
    status_history = db.relationship('OrderStatusHistory', backref='order', cascade='all, delete-orphan')

    def generate_order_number(self):
        timestamp = datetime.utcnow().strftime('%y%m%d')
        random_part = ''.join(random.choices(string.ascii_uppercase + string.digits, k=6))
        return f"ORD-{timestamp}-{random_part}"

    @property
    def status_color(self):
        colors = {
            'pending': 'warning',
            'paid': 'info',
            'processing': 'primary',
            'shipped': 'primary',
            'delivered': 'success',
            'completed': 'success',
            'cancelled': 'danger',
            'refunded': 'secondary'
        }
        return colors.get(self.status, 'secondary')

    @property
    def can_cancel(self):
        return self.status in ['pending', 'paid']

    @property
    def can_review(self):
        return self.status == 'completed' and not any(item.reviewed for item in self.items)


class OrderItem(db.Model):
    __tablename__ = 'order_items'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    product_title = db.Column(db.String(200), nullable=False)
    product_price = db.Column(db.Numeric(10, 2), nullable=False)
    quantity = db.Column(db.Integer, nullable=False)
    reviewed = db.Column(db.Boolean, default=False)

    @property
    def subtotal(self):
        return self.product_price * self.quantity


class OrderStatusHistory(db.Model):
    __tablename__ = 'order_status_history'

    id = db.Column(db.Integer, primary_key=True)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'), nullable=False)
    status = db.Column(db.String(20), nullable=False)
    comment = db.Column(db.Text)
    created_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


class Review(db.Model):
    __tablename__ = 'reviews'

    id = db.Column(db.Integer, primary_key=True)
    author_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    product_id = db.Column(db.Integer, db.ForeignKey('products.id'), nullable=False)
    order_id = db.Column(db.Integer, db.ForeignKey('orders.id'))
    rating = db.Column(db.Integer, nullable=False)
    comment = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    @property
    def rating_stars(self):
        return range(self.rating)


class PromoCode(db.Model):
    __tablename__ = 'promo_codes'

    id = db.Column(db.Integer, primary_key=True)
    code = db.Column(db.String(50), unique=True, nullable=False)
    discount_type = db.Column(db.String(20), nullable=False)
    discount_value = db.Column(db.Numeric(10, 2), nullable=False)
    min_order_amount = db.Column(db.Numeric(10, 2), default=0)
    max_uses = db.Column(db.Integer)
    used_count = db.Column(db.Integer, default=0)
    valid_from = db.Column(db.DateTime, default=datetime.utcnow)
    valid_to = db.Column(db.DateTime)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def is_valid(self):
        now = datetime.utcnow()
        return (self.is_active and
                now >= self.valid_from and
                (self.valid_to is None or now <= self.valid_to) and
                (self.max_uses is None or self.used_count < self.max_uses))


class Notification(db.Model):
    __tablename__ = 'notifications'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    type = db.Column(db.String(50))
    title = db.Column(db.String(200))
    message = db.Column(db.Text)
    data = db.Column(db.JSON)
    is_read = db.Column(db.Boolean, default=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)


# ==================== ЗАГРУЗЧИК ПОЛЬЗОВАТЕЛЯ ====================

@login_manager.user_loader
def load_user(user_id):
    return User.query.get(int(user_id))


# ==================== КОНТЕКСТНЫЙ ПРОЦЕССОР ====================

@app.context_processor
def utility_processor():
    def get_cart_count():
        if current_user.is_authenticated and current_user.cart:
            return current_user.cart.items_count
        return 0

    def get_notifications_count():
        if current_user.is_authenticated:
            return Notification.query.filter_by(user_id=current_user.id, is_read=False).count()
        return 0

    return dict(
        get_cart_count=get_cart_count,
        get_notifications_count=get_notifications_count,
        now=datetime.utcnow
    )


# ==================== ОСНОВНЫЕ МАРШРУТЫ ====================

@app.route('/')
def index():
    """Главная страница"""
    popular_products = Product.query.filter_by(status='active').order_by(Product.views.desc()).limit(8).all()
    new_products = Product.query.filter_by(status='active').order_by(Product.created_at.desc()).limit(8).all()

    return render_template('index.html',
                           popular_products=popular_products,
                           new_products=new_products)


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Регистрация пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        first_name = request.form.get('first_name')
        last_name = request.form.get('last_name')
        phone = request.form.get('phone')

        # Проверка существования пользователя
        if User.query.filter_by(username=username).first():
            flash('Имя пользователя уже занято', 'danger')
            return redirect(url_for('register'))

        if User.query.filter_by(email=email).first():
            flash('Email уже зарегистрирован', 'danger')
            return redirect(url_for('register'))

        # Создание нового пользователя
        user = User(
            username=username,
            email=email,
            first_name=first_name,
            last_name=last_name,
            phone=phone
        )
        user.set_password(password)

        db.session.add(user)
        db.session.flush()

        # Создание корзины для пользователя
        cart = Cart(user_id=user.id)
        db.session.add(cart)

        db.session.commit()

        flash('Регистрация успешна! Теперь вы можете войти', 'success')
        return redirect(url_for('login'))

    return render_template('register.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Вход пользователя"""
    if current_user.is_authenticated:
        return redirect(url_for('index'))

    if request.method == 'POST':
        email = request.form.get('email')
        password = request.form.get('password')
        remember = True if request.form.get('remember') else False

        user = User.query.filter_by(email=email).first()

        if not user or not user.check_password(password):
            flash('Проверьте email и пароль', 'danger')
            return redirect(url_for('login'))

        login_user(user, remember=remember)

        next_page = request.args.get('next')
        return redirect(next_page) if next_page else redirect(url_for('index'))

    return render_template('login.html')


@app.route('/logout')
@login_required
def logout():
    """Выход пользователя"""
    logout_user()
    flash('Вы вышли из системы', 'success')
    return redirect(url_for('index'))


@app.route('/profile')
@login_required
def profile():
    """Профиль пользователя"""
    user = current_user
    favorite_products = []  # Здесь должна быть логика избранного
    active_orders = Order.query.filter_by(buyer_id=user.id, status='pending').all()

    return render_template('profile.html',
                           user=user,
                           favorite_products=favorite_products,
                           active_orders=active_orders)


@app.route('/profile/update', methods=['POST'])
@login_required
def update_profile():
    """Обновление профиля"""
    user = current_user

    user.first_name = request.form.get('first_name')
    user.last_name = request.form.get('last_name')
    user.phone = request.form.get('phone')
    user.bio = request.form.get('bio')

    db.session.commit()

    flash('Профиль обновлен', 'success')
    return redirect(url_for('profile'))


# ==================== ТОВАРЫ И ОБЪЯВЛЕНИЯ ====================

@app.route('/create-listing', methods=['GET', 'POST'])
@login_required
def create_listing():
    """Создание объявления"""
    if request.method == 'POST':
        title = request.form.get('title')
        description = request.form.get('description')
        price = request.form.get('price')
        category = request.form.get('category')
        condition = request.form.get('condition')

        product = Product(
            seller_id=current_user.id,
            title=title,
            description=description,
            price=price,
            category=category,
            condition=condition,
            status='pending'  # На модерацию
        )

        # Характеристики
        spec_keys = request.form.getlist('spec_key[]')
        spec_values = request.form.getlist('spec_value[]')
        specifications = {}
        for key, value in zip(spec_keys, spec_values):
            if key and value:
                specifications[key] = value
        product.specifications = specifications

        # Опции
        product.bargain = 'bargain' in request.form
        product.warranty = 'warranty' in request.form
        product.original = 'original' in request.form
        product.delivery_available = 'delivery_available' in request.form
        product.pickup_available = 'pickup_available' in request.form

        db.session.add(product)
        db.session.flush()

        # Обработка изображений (упрощенно)
        files = request.files.getlist('photos')
        for i, file in enumerate(files):
            if file and file.filename:
                filename = secure_filename(file.filename)
                # Здесь должна быть загрузка файла
                image = ProductImage(
                    product_id=product.id,
                    url=f'/uploads/{filename}',
                    is_main=(i == 0),
                    order=i
                )
                db.session.add(image)

        db.session.commit()

        flash('Объявление отправлено на модерацию', 'success')
        return redirect(url_for('profile'))

    return render_template('create_listing.html')


@app.route('/listing/<int:listing_id>')
def listing_detail(listing_id):
    """Детальная страница товара"""
    product = Product.query.get_or_404(listing_id)

    # Увеличиваем счетчик просмотров
    product.views += 1
    db.session.commit()

    # Похожие товары
    similar_products = Product.query.filter_by(
        category=product.category,
        status='active'
    ).filter(Product.id != product.id).limit(4).all()

    return render_template('listing_detail.html',
                           product=product,
                           similar_products=similar_products)


# ==================== КОРЗИНА И ЗАКАЗЫ ====================

@app.route('/cart')
@login_required
def cart():
    """Страница корзины"""
    cart = current_user.cart
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.commit()

    return render_template('cart.html', cart=cart)


@app.route('/api/cart/add', methods=['POST'])
@login_required
def add_to_cart():
    """Добавление товара в корзину"""
    data = request.get_json()
    product_id = data.get('product_id')
    quantity = int(data.get('quantity', 1))

    product = Product.query.get_or_404(product_id)

    if product.status != 'active':
        return jsonify({'success': False, 'error': 'Товар недоступен для покупки'})

    if product.seller_id == current_user.id:
        return jsonify({'success': False, 'error': 'Нельзя добавить свой товар в корзину'})

    cart = current_user.cart
    if not cart:
        cart = Cart(user_id=current_user.id)
        db.session.add(cart)
        db.session.flush()

    cart_item = CartItem.query.filter_by(cart_id=cart.id, product_id=product_id).first()

    if cart_item:
        cart_item.quantity += quantity
    else:
        cart_item = CartItem(cart_id=cart.id, product_id=product_id, quantity=quantity)
        db.session.add(cart_item)

    db.session.commit()

    return jsonify({
        'success': True,
        'cart_count': cart.items_count,
        'cart_total': float(cart.subtotal)
    })


@app.route('/api/cart/update/<int:item_id>', methods=['POST'])
@login_required
def update_cart_item(item_id):
    """Обновление количества товара"""
    data = request.get_json()
    quantity = int(data.get('quantity', 1))

    cart_item = CartItem.query.get_or_404(item_id)

    if cart_item.cart.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    if quantity < 1:
        db.session.delete(cart_item)
    else:
        cart_item.quantity = quantity

    db.session.commit()

    cart = current_user.cart
    return jsonify({
        'success': True,
        'subtotal': float(cart.subtotal),
        'total_items': cart.total_items,
        'items_count': cart.items_count
    })


@app.route('/api/cart/remove/<int:item_id>', methods=['DELETE'])
@login_required
def remove_from_cart(item_id):
    """Удаление товара из корзины"""
    cart_item = CartItem.query.get_or_404(item_id)

    if cart_item.cart.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    db.session.delete(cart_item)
    db.session.commit()

    return jsonify({'success': True})


@app.route('/api/cart/clear', methods=['POST'])
@login_required
def clear_cart():
    """Очистка корзины"""
    cart = current_user.cart
    if cart:
        CartItem.query.filter_by(cart_id=cart.id).delete()
        db.session.commit()

    return jsonify({'success': True})


@app.route('/api/cart/apply-promo', methods=['POST'])
@login_required
def apply_promo():
    """Применение промокода"""
    data = request.get_json()
    promo_code = data.get('promo')

    promo = PromoCode.query.filter_by(code=promo_code.upper(), is_active=True).first()

    if not promo or not promo.is_valid():
        return jsonify({'success': False, 'error': 'Неверный или просроченный промокод'})

    cart = current_user.cart
    if not cart or cart.items_count == 0:
        return jsonify({'success': False, 'error': 'Корзина пуста'})

    if cart.subtotal < promo.min_order_amount:
        return jsonify({
            'success': False,
            'error': f'Минимальная сумма заказа для этого промокода: {promo.min_order_amount} ₽'
        })

    if promo.discount_type == 'percent':
        discount = float(cart.subtotal) * float(promo.discount_value) / 100
    else:
        discount = float(promo.discount_value)

    session['promo_code'] = promo.code
    session['promo_discount'] = discount

    return jsonify({
        'success': True,
        'discount': discount,
        'total': float(cart.subtotal) - discount
    })


@app.route('/api/cart/totals')
@login_required
def cart_totals():
    """Получение актуальных сумм корзины"""
    cart = current_user.cart
    discount = session.get('promo_discount', 0)

    if not cart:
        return jsonify({
            'subtotal': 0,
            'discount': 0,
            'total': 0,
            'count': 0
        })

    return jsonify({
        'subtotal': float(cart.subtotal),
        'discount': float(discount),
        'total': float(cart.subtotal) - float(discount),
        'count': cart.items_count
    })


@app.route('/checkout', methods=['GET', 'POST'])
@login_required
def checkout():
    """Оформление заказа"""
    cart = current_user.cart

    if not cart or cart.items_count == 0:
        flash('Корзина пуста', 'warning')
        return redirect(url_for('cart'))

    if request.method == 'POST':
        delivery_method = request.form.get('delivery_method')
        delivery_address = request.form.get('delivery_address')
        delivery_city = request.form.get('delivery_city')
        delivery_postal_code = request.form.get('delivery_postal_code')
        delivery_phone = request.form.get('delivery_phone')
        delivery_email = request.form.get('delivery_email')
        recipient_name = request.form.get('recipient_name')
        delivery_notes = request.form.get('delivery_notes')
        payment_method = request.form.get('payment_method')

        delivery_prices = {
            'standard': 300,
            'express': 500,
            'pickup': 0
        }
        delivery_price = delivery_prices.get(delivery_method, 0)

        discount = session.get('promo_discount', 0)
        promo_code = session.get('promo_code')

        # Группируем по продавцам
        seller_orders = {}
        for item in cart.items:
            seller_id = item.product.seller_id
            if seller_id not in seller_orders:
                seller_orders[seller_id] = []
            seller_orders[seller_id].append(item)

        orders = []
        for seller_id, items in seller_orders.items():
            subtotal = sum(float(item.product.price) * item.quantity for item in items)

            item_discount = (subtotal / float(cart.subtotal)) * discount if float(cart.subtotal) > 0 else 0

            order = Order(
                order_number=Order().generate_order_number(),
                buyer_id=current_user.id,
                seller_id=seller_id,
                subtotal=subtotal,
                delivery_price=delivery_price if len(seller_orders) == 1 else 0,
                discount=item_discount,
                total=subtotal + (delivery_price if len(seller_orders) == 1 else 0) - item_discount,
                delivery_method=delivery_method,
                delivery_address=delivery_address,
                delivery_city=delivery_city,
                delivery_postal_code=delivery_postal_code,
                delivery_phone=delivery_phone,
                delivery_email=delivery_email,
                recipient_name=recipient_name,
                delivery_notes=delivery_notes,
                payment_method=payment_method,
                promo_code=promo_code,
                status='pending',
                payment_status='pending'
            )

            db.session.add(order)
            db.session.flush()

            for item in items:
                order_item = OrderItem(
                    order_id=order.id,
                    product_id=item.product_id,
                    product_title=item.product.title,
                    product_price=float(item.product.price),
                    quantity=item.quantity
                )
                db.session.add(order_item)

                item.product.sales_count += item.quantity

            status_history = OrderStatusHistory(
                order_id=order.id,
                status='pending',
                comment='Заказ создан',
                created_by=current_user.id
            )
            db.session.add(status_history)

            notification = Notification(
                user_id=seller_id,
                type='new_order',
                title='Новый заказ!',
                message=f'Покупатель {current_user.username} оформил заказ #{order.order_number}',
                data={'order_id': order.id, 'order_number': order.order_number}
            )
            db.session.add(notification)

            orders.append(order)

        CartItem.query.filter_by(cart_id=cart.id).delete()
        session.pop('promo_code', None)
        session.pop('promo_discount', None)

        db.session.commit()

        if len(orders) > 1:
            flash('Заказы успешно оформлены!', 'success')
            return redirect(url_for('orders_list'))
        else:
            return redirect(url_for('payment', order_id=orders[0].id))

    return render_template('checkout.html', cart=cart)


@app.route('/payment/<int:order_id>')
@login_required
def payment(order_id):
    """Страница оплаты"""
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    if order.payment_status != 'pending':
        flash('Этот заказ уже оплачен', 'info')
        return redirect(url_for('order_detail', order_id=order.id))

    return render_template('payment.html', order=order)


@app.route('/api/process-payment/<int:order_id>', methods=['POST'])
@login_required
def process_payment(order_id):
    """Обработка платежа"""
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    payment_method = data.get('payment_method')

    payment_id = f"PAY-{datetime.utcnow().strftime('%y%m%d')}-{''.join(random.choices(string.digits, k=8))}"

    order.payment_status = 'paid'
    order.payment_id = payment_id
    order.paid_at = datetime.utcnow()
    order.status = 'paid'

    status_history = OrderStatusHistory(
        order_id=order.id,
        status='paid',
        comment='Заказ оплачен',
        created_by=current_user.id
    )
    db.session.add(status_history)

    notification = Notification(
        user_id=order.seller_id,
        type='payment_received',
        title='Заказ оплачен!',
        message=f'Заказ #{order.order_number} оплачен. Сумма: {order.total} ₽',
        data={'order_id': order.id, 'order_number': order.order_number}
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({
        'success': True,
        'payment_id': payment_id,
        'redirect_url': url_for('order_detail', order_id=order.id)
    })


@app.route('/orders')
@login_required
def orders_list():
    """Список заказов покупателя"""
    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    buyer_orders = Order.query.filter_by(buyer_id=current_user.id)

    if status != 'all':
        buyer_orders = buyer_orders.filter_by(status=status)

    buyer_orders = buyer_orders.order_by(Order.created_at.desc())
    pagination = buyer_orders.paginate(page=page, per_page=10, error_out=False)
    orders = pagination.items

    return render_template('orders_list.html',
                           orders=orders,
                           pagination=pagination,
                           current_status=status)


@app.route('/order/<int:order_id>')
@login_required
def order_detail(order_id):
    """Детальная страница заказа"""
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    return render_template('order_detail.html', order=order)


@app.route('/seller/orders')
@login_required
def seller_orders():
    """Список заказов для продавца"""
    if not current_user.is_seller and not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'all')

    seller_orders = Order.query.filter_by(seller_id=current_user.id)

    if status != 'all':
        seller_orders = seller_orders.filter_by(status=status)

    seller_orders = seller_orders.order_by(Order.created_at.desc())
    pagination = seller_orders.paginate(page=page, per_page=10, error_out=False)
    orders = pagination.items

    return render_template('seller_orders.html',
                           orders=orders,
                           pagination=pagination,
                           current_status=status)


@app.route('/api/order/<int:order_id>/status', methods=['POST'])
@login_required
def update_order_status(order_id):
    """Обновление статуса заказа"""
    order = Order.query.get_or_404(order_id)

    if order.seller_id != current_user.id and not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    new_status = data.get('status')
    comment = data.get('comment', '')
    tracking_number = data.get('tracking_number')

    valid_transitions = {
        'pending': ['paid', 'cancelled'],
        'paid': ['processing', 'cancelled'],
        'processing': ['shipped', 'cancelled'],
        'shipped': ['delivered', 'cancelled'],
        'delivered': ['completed']
    }

    if order.status in valid_transitions and new_status in valid_transitions[order.status]:
        order.status = new_status

        if tracking_number:
            order.tracking_number = tracking_number

        if new_status == 'shipped':
            order.shipped_at = datetime.utcnow()
            if not order.tracking_number:
                order.tracking_number = f"TRACK-{''.join(random.choices(string.ascii_uppercase + string.digits, k=10))}"
        elif new_status == 'delivered':
            order.delivered_at = datetime.utcnow()
        elif new_status == 'completed':
            order.completed_at = datetime.utcnow()
        elif new_status == 'cancelled':
            order.cancelled_at = datetime.utcnow()
            order.payment_status = 'refunded'

        status_history = OrderStatusHistory(
            order_id=order.id,
            status=new_status,
            comment=comment,
            created_by=current_user.id
        )
        db.session.add(status_history)

        notification = Notification(
            user_id=order.buyer_id,
            type='order_status',
            title=f'Статус заказа #{order.order_number} обновлен',
            message=f'Статус изменен на: {new_status}',
            data={'order_id': order.id, 'status': new_status}
        )
        db.session.add(notification)

        db.session.commit()

        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Недопустимый переход статуса'})


@app.route('/api/order/<int:order_id>/cancel', methods=['POST'])
@login_required
def cancel_order(order_id):
    """Отмена заказа покупателем"""
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    if not order.can_cancel:
        return jsonify({'success': False, 'error': 'Этот заказ уже нельзя отменить'})

    order.status = 'cancelled'
    order.cancelled_at = datetime.utcnow()
    order.payment_status = 'refunded' if order.payment_status == 'paid' else 'cancelled'

    status_history = OrderStatusHistory(
        order_id=order.id,
        status='cancelled',
        comment='Заказ отменен покупателем',
        created_by=current_user.id
    )
    db.session.add(status_history)

    notification = Notification(
        user_id=order.seller_id,
        type='order_cancelled',
        title=f'Заказ #{order.order_number} отменен',
        message='Покупатель отменил заказ',
        data={'order_id': order.id, 'order_number': order.order_number}
    )
    db.session.add(notification)

    db.session.commit()

    return jsonify({'success': True})


@app.route('/api/order/<int:order_id>/track')
@login_required
def track_order(order_id):
    """Получение информации об отслеживании"""
    order = Order.query.get_or_404(order_id)

    if order.buyer_id != current_user.id and order.seller_id != current_user.id:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    history = OrderStatusHistory.query.filter_by(order_id=order.id).order_by(OrderStatusHistory.created_at).all()

    status_history = [{
        'status': h.status,
        'comment': h.comment,
        'created_at': h.created_at.strftime('%d.%m.%Y %H:%M')
    } for h in history]

    return jsonify({
        'success': True,
        'order_number': order.order_number,
        'current_status': order.status,
        'tracking_number': order.tracking_number,
        'status_history': status_history,
        'estimated_delivery': (order.shipped_at.strftime('%d.%m.%Y') if order.shipped_at else None)
    })


# ==================== ОТЗЫВЫ ====================

@app.route('/api/reviews', methods=['POST'])
@login_required
def add_review():
    """Добавление отзыва"""
    data = request.get_json()
    product_id = data.get('product_id')
    rating = int(data.get('rating'))
    comment = data.get('comment')
    order_id = data.get('order_id')

    product = Product.query.get_or_404(product_id)

    # Проверяем, что пользователь не оставляет отзыв на свой товар
    if product.seller_id == current_user.id:
        return jsonify({'success': False, 'error': 'Нельзя оставить отзыв на свой товар'})

    # Проверяем, что пользователь еще не оставлял отзыв
    existing_review = Review.query.filter_by(
        author_id=current_user.id,
        product_id=product_id
    ).first()

    if existing_review:
        return jsonify({'success': False, 'error': 'Вы уже оставляли отзыв на этот товар'})

    review = Review(
        author_id=current_user.id,
        user_id=product.seller_id,
        product_id=product_id,
        order_id=order_id,
        rating=rating,
        comment=comment
    )

    db.session.add(review)

    # Обновляем рейтинг продавца
    seller = product.seller
    reviews = Review.query.filter_by(user_id=seller.id).all()
    if reviews:
        seller.rating = sum(r.rating for r in reviews) / len(reviews)

    # Отмечаем товар в заказе как оцененный
    if order_id:
        order_item = OrderItem.query.filter_by(order_id=order_id, product_id=product_id).first()
        if order_item:
            order_item.reviewed = True

    db.session.commit()

    return jsonify({'success': True})


# ==================== ПАНЕЛЬ ПРОДАВЦА ====================

@app.route('/seller/dashboard')
@login_required
def seller_dashboard():
    """Панель продавца"""
    if not current_user.is_seller and not current_user.is_admin:
        flash('Станьте продавцом, чтобы получить доступ к панели', 'warning')
        return redirect(url_for('become_seller'))

    # Статистика
    stats = {
        'active_products': Product.query.filter_by(seller_id=current_user.id, status='active').count(),
        'monthly_sales': 0,  # Здесь должна быть реальная статистика
        'active_orders': Order.query.filter_by(seller_id=current_user.id, status='paid').count(),
        'rating': current_user.rating
    }

    # Последние заказы
    recent_orders = Order.query.filter_by(seller_id=current_user.id).order_by(Order.created_at.desc()).limit(5).all()

    # Товары продавца
    products = Product.query.filter_by(seller_id=current_user.id).order_by(Product.created_at.desc()).all()

    # Данные для графика (пример)
    chart = {
        'labels': ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'],
        'data': [65, 59, 80, 81, 56, 55, 40]
    }

    return render_template('seller_dashboard.html',
                           stats=stats,
                           recent_orders=recent_orders,
                           products=products,
                           chart=chart)


@app.route('/become-seller')
@login_required
def become_seller():
    """Стать продавцом"""
    if current_user.is_seller:
        return redirect(url_for('seller_dashboard'))

    return render_template('become_pvz_owner.html')


# ==================== МОДЕРАЦИЯ ====================

@app.route('/moderate')
@login_required
def moderate():
    """Панель модератора"""
    if not current_user.is_admin:
        flash('Доступ запрещен', 'danger')
        return redirect(url_for('index'))

    page = request.args.get('page', 1, type=int)
    status = request.args.get('status', 'pending')

    query = Product.query

    if status != 'all':
        query = query.filter_by(status=status)

    listings = query.order_by(Product.created_at.desc()).paginate(page=page, per_page=20, error_out=False)

    # Статистика
    stats = {
        'pending': Product.query.filter_by(status='pending').count(),
        'approved_today': Product.query.filter(
            Product.status == 'active',
            Product.published_at >= datetime.utcnow().date()
        ).count(),
        'rejected_today': 0,  # Здесь должна быть реальная статистика
        'active_moderators': 1
    }

    return render_template('moderate.html',
                           listings=listings.items,
                           pagination=listings,
                           stats=stats,
                           pending_count=stats['pending'])


@app.route('/api/moderate/listing/<int:listing_id>', methods=['POST'])
@login_required
def moderate_listing(listing_id):
    """Модерация объявления"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    data = request.get_json()
    status = data.get('status')
    reason = data.get('reason', '')

    product = Product.query.get_or_404(listing_id)

    if status == 'approved':
        product.status = 'active'
        product.published_at = datetime.utcnow()

        # Уведомление продавцу
        notification = Notification(
            user_id=product.seller_id,
            type='listing_approved',
            title='Объявление одобрено!',
            message=f'Ваше объявление "{product.title}" опубликовано',
            data={'product_id': product.id}
        )
        db.session.add(notification)

    elif status == 'rejected':
        product.status = 'rejected'

        notification = Notification(
            user_id=product.seller_id,
            type='listing_rejected',
            title='Объявление отклонено',
            message=f'Ваше объявление "{product.title}" отклонено. Причина: {reason}',
            data={'product_id': product.id, 'reason': reason}
        )
        db.session.add(notification)

    db.session.commit()

    return jsonify({'success': True})


@app.route('/api/moderate/stats')
@login_required
def moderate_stats():
    """Статистика для модерации"""
    if not current_user.is_admin:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    return jsonify({
        'pending': Product.query.filter_by(status='pending').count()
    })


# ==================== УВЕДОМЛЕНИЯ ====================

@app.route('/api/notifications')
@login_required
def get_notifications():
    """Получение уведомлений"""
    notifications = Notification.query.filter_by(
        user_id=current_user.id,
        is_read=False
    ).order_by(Notification.created_at.desc()).limit(20).all()

    return jsonify([{
        'id': n.id,
        'type': n.type,
        'title': n.title,
        'message': n.message,
        'data': n.data,
        'created_at': n.created_at.strftime('%d.%m.%Y %H:%M')
    } for n in notifications])


@app.route('/api/notifications/<int:notification_id>/read', methods=['POST'])
@login_required
def mark_notification_read(notification_id):
    """Отметить уведомление как прочитанное"""
    notification = Notification.query.get_or_404(notification_id)

    if notification.user_id != current_user.id:
        return jsonify({'success': False, 'error': 'Доступ запрещен'}), 403

    notification.is_read = True
    db.session.commit()

    return jsonify({'success': True})


# ==================== ОБРАБОТЧИКИ ОШИБОК ====================

@app.errorhandler(404)
def not_found_error(error):
    return render_template('404.html'), 404


@app.errorhandler(500)
def internal_error(error):
    db.session.rollback()
    return render_template('500.html', error_id=random.randint(1000, 9999)), 500


@app.errorhandler(429)
def too_many_requests(error):
    return render_template('429.html', retry_after=60), 429


# ==================== ИНИЦИАЛИЗАЦИЯ БАЗЫ ДАННЫХ ====================

@app.before_first_request
def create_tables():
    """Создание таблиц при первом запросе"""
    db.create_all()

    # Создание тестового админа если нет пользователей
    if User.query.count() == 0:
        admin = User(
            username='admin',
            email='admin@kildear.ru',
            first_name='Admin',
            last_name='System',
            is_admin=True,
            is_seller=True,
            is_verified=True
        )
        admin.set_password('admin123')
        db.session.add(admin)

        # Тестовый промокод
        promo = PromoCode(
            code='WELCOME10',
            discount_type='percent',
            discount_value=10,
            min_order_amount=1000,
            valid_to=datetime(2025, 12, 31)
        )
        db.session.add(promo)

        db.session.commit()


# ==================== ЗАПУСК ПРИЛОЖЕНИЯ ====================

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)