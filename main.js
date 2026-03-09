// main.js - Полный клиентский код для маркетплейса Kildear

// Конфигурация
const API_URL = window.location.origin + '/api';
let currentUser = null;
let authToken = localStorage.getItem('authToken');

// DOM элементы
const elements = {
    // Навигация
    navAuth: document.getElementById('nav-auth'),
    userMenu: document.getElementById('user-menu'),
    userName: document.getElementById('user-name'),

    // Модалки
    authModal: document.getElementById('auth-modal'),
    registerModal: document.getElementById('register-modal'),
    verifyModal: document.getElementById('verify-modal'),
    sellerModal: document.getElementById('seller-modal'),
    pvzModal: document.getElementById('pvz-modal'),
    productModal: document.getElementById('product-modal'),

    // Формы
    loginForm: document.getElementById('login-form'),
    registerForm: document.getElementById('register-form'),
    verifyForm: document.getElementById('verify-form'),

    // Контейнеры
    productsContainer: document.getElementById('products-container'),
    pvzContainer: document.getElementById('pvz-container'),

    // Кнопки
    becomeSellerBtn: document.getElementById('become-seller'),
    createProductBtn: document.getElementById('create-product'),
    createPvzBtn: document.getElementById('create-pvz'),

    // Фильтры
    categoryFilter: document.getElementById('category-filter'),
    priceFilter: document.getElementById('price-filter'),
    searchInput: document.getElementById('search-input'),
    searchBtn: document.getElementById('search-btn')
};

// Класс для работы с API
class KildearAPI {
    constructor(baseURL) {
        this.baseURL = baseURL;
    }

    async request(endpoint, options = {}) {
        const url = `${this.baseURL}${endpoint}`;
        const headers = {
            'Content-Type': 'application/json',
            ...options.headers
        };

        if (authToken) {
            headers['Authorization'] = `Bearer ${authToken}`;
        }

        const config = {
            ...options,
            headers,
            credentials: 'same-origin'
        };

        try {
            const response = await fetch(url, config);
            const data = await response.json();

            if (!response.ok) {
                throw new Error(data.error || 'Произошла ошибка');
            }

            return data;
        } catch (error) {
            console.error('API Error:', error);
            throw error;
        }
    }

    // Аутентификация
    async register(userData) {
        return this.request('/auth/register', {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    }

    async verifyEmail(email, code, password, userInfo) {
        return this.request('/auth/verify', {
            method: 'POST',
            body: JSON.stringify({ email, code, password, ...userInfo })
        });
    }

    async resendCode(email) {
        return this.request('/auth/resend-code', {
            method: 'POST',
            body: JSON.stringify({ email })
        });
    }

    async login(credentials) {
        const data = await this.request('/auth/login', {
            method: 'POST',
            body: JSON.stringify(credentials)
        });

        if (data.token) {
            authToken = data.token;
            localStorage.setItem('authToken', data.token);
            currentUser = data.user;
        }

        return data;
    }

    async logout() {
        await this.request('/auth/logout', { method: 'POST' });
        authToken = null;
        currentUser = null;
        localStorage.removeItem('authToken');
    }

    // Профиль
    async getProfile() {
        return this.request('/user/profile');
    }

    async updateProfile(userData) {
        return this.request('/user/profile', {
            method: 'PUT',
            body: JSON.stringify(userData)
        });
    }

    async becomeSeller() {
        return this.request('/user/become-seller', { method: 'POST' });
    }

    // Товары
    async getProducts(params = {}) {
        const queryString = new URLSearchParams(params).toString();
        return this.request(`/products?${queryString}`);
    }

    async getProduct(id) {
        return this.request(`/products/${id}`);
    }

    async createProduct(productData) {
        return this.request('/products', {
            method: 'POST',
            body: JSON.stringify(productData)
        });
    }

    async updateProduct(id, productData) {
        return this.request(`/products/${id}`, {
            method: 'PUT',
            body: JSON.stringify(productData)
        });
    }

    async updateProductStatus(id, status) {
        return this.request(`/products/${id}/status`, {
            method: 'POST',
            body: JSON.stringify({ status })
        });
    }

    // ПВЗ
    async getPVZ(city = '') {
        const params = city ? `?city=${encodeURIComponent(city)}` : '';
        return this.request(`/pvz${params}`);
    }

    async createPVZ(pvzData) {
        return this.request('/pvz', {
            method: 'POST',
            body: JSON.stringify(pvzData)
        });
    }

    async updatePVZ(id, pvzData) {
        return this.request(`/pvz/${id}`, {
            method: 'PUT',
            body: JSON.stringify(pvzData)
        });
    }

    async deletePVZ(id) {
        return this.request(`/pvz/${id}`, {
            method: 'DELETE'
        });
    }

    // Заказы
    async createOrder(orderData) {
        return this.request('/orders', {
            method: 'POST',
            body: JSON.stringify(orderData)
        });
    }

    async getOrders(page = 1) {
        return this.request(`/orders?page=${page}`);
    }

    // Отзывы
    async createReview(reviewData) {
        return this.request('/reviews', {
            method: 'POST',
            body: JSON.stringify(reviewData)
        });
    }
}

// Инициализация API
const api = new KildearAPI(API_URL);

// Утилиты
const utils = {
    showModal(modal) {
        if (modal) {
            modal.classList.add('show');
            document.body.style.overflow = 'hidden';
        }
    },

    hideModal(modal) {
        if (modal) {
            modal.classList.remove('show');
            document.body.style.overflow = '';
        }
    },

    showNotification(message, type = 'info') {
        const notification = document.createElement('div');
        notification.className = `notification notification-${type}`;
        notification.textContent = message;
        notification.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 15px 25px;
            background: ${type === 'error' ? '#f44336' : type === 'success' ? '#4caf50' : '#2196f3'};
            color: white;
            border-radius: 8px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
            z-index: 10000;
            animation: slideIn 0.3s ease;
        `;
        document.body.appendChild(notification);
        setTimeout(() => {
            notification.remove();
        }, 5000);
    },

    formatPrice(price) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB',
            minimumFractionDigits: 0
        }).format(price);
    },

    sanitizeHTML(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    debounce(func, wait) {
        let timeout;
        return function executedFunction(...args) {
            const later = () => {
                clearTimeout(timeout);
                func(...args);
            };
            clearTimeout(timeout);
            timeout = setTimeout(later, wait);
        };
    }
};

// Обработчики аутентификации
class AuthHandler {
    static async handleLogin(event) {
        event.preventDefault();
        const form = event.target;
        const email = form.querySelector('[name="email"]').value;
        const password = form.querySelector('[name="password"]').value;

        try {
            const result = await api.login({ email, password });
            utils.showNotification('Вход выполнен успешно!', 'success');
            utils.hideModal(elements.authModal);
            AuthHandler.updateUI();
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }

    static async handleRegister(event) {
        event.preventDefault();
        const form = event.target;
        const email = form.querySelector('[name="email"]').value;
        const password = form.querySelector('[name="password"]').value;
        const confirmPassword = form.querySelector('[name="confirm-password"]').value;

        if (password !== confirmPassword) {
            utils.showNotification('Пароли не совпадают', 'error');
            return;
        }

        const userData = {
            email,
            password,
            first_name: form.querySelector('[name="first-name"]').value,
            last_name: form.querySelector('[name="last-name"]').value,
            phone: form.querySelector('[name="phone"]').value
        };

        try {
            const result = await api.register(userData);
            utils.showNotification('Код подтверждения отправлен на email', 'success');
            utils.hideModal(elements.registerModal);

            // Показываем модалку верификации
            const verifyEmail = document.getElementById('verify-email');
            if (verifyEmail) verifyEmail.value = email;
            if (elements.verifyModal) {
                elements.verifyModal.dataset.userData = JSON.stringify(userData);
                utils.showModal(elements.verifyModal);
            }
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }

    static async handleVerify(event) {
        event.preventDefault();
        const form = event.target;
        const email = form.querySelector('[name="email"]').value;
        const code = form.querySelector('[name="code"]').value;

        const userDataStr = elements.verifyModal?.dataset.userData;
        if (!userDataStr) {
            utils.showNotification('Ошибка: данные не найдены', 'error');
            return;
        }

        const userData = JSON.parse(userDataStr);
        const password = userData.password;

        try {
            const result = await api.verifyEmail(email, code, password, {
                first_name: userData.first_name,
                last_name: userData.last_name,
                phone: userData.phone
            });

            utils.showNotification('Регистрация завершена!', 'success');
            utils.hideModal(elements.verifyModal);
            AuthHandler.updateUI();
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }

    static async handleResendCode() {
        const emailInput = document.querySelector('#verify-email');
        if (!emailInput) return;

        try {
            await api.resendCode(emailInput.value);
            utils.showNotification('Новый код отправлен на email', 'success');
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }

    static async handleLogout() {
        try {
            await api.logout();
            AuthHandler.updateUI();
            utils.showNotification('Выход выполнен', 'info');
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }

    static updateUI() {
        const authLinks = document.querySelectorAll('.auth-link');
        const userMenu = document.querySelector('.user-menu');

        if (currentUser) {
            // Пользователь авторизован
            authLinks.forEach(el => el.style.display = 'none');
            if (userMenu) {
                userMenu.style.display = 'block';
                const userNameEl = document.getElementById('user-name-display');
                if (userNameEl) {
                    userNameEl.textContent = currentUser.first_name || currentUser.email;
                }
            }
        } else {
            // Не авторизован
            authLinks.forEach(el => el.style.display = 'block');
            if (userMenu) userMenu.style.display = 'none';
        }
    }

    static async checkAuth() {
        if (authToken) {
            try {
                const profile = await api.getProfile();
                currentUser = profile;
                AuthHandler.updateUI();
            } catch (error) {
                // Токен недействителен
                authToken = null;
                localStorage.removeItem('authToken');
            }
        }
    }
}

// Обработчики товаров
class ProductHandler {
    static currentPage = 1;
    static filters = {
        category: '',
        min_price: '',
        max_price: '',
        search: '',
        sort: 'newest'
    };

    static async loadProducts(resetPage = true) {
        if (resetPage) this.currentPage = 1;

        const params = {
            page: this.currentPage,
            ...this.filters
        };

        // Удаляем пустые параметры
        Object.keys(params).forEach(key => {
            if (!params[key] && params[key] !== 0) delete params[key];
        });

        try {
            const data = await api.getProducts(params);
            this.renderProducts(data);
            this.renderPagination(data);
        } catch (error) {
            utils.showNotification('Ошибка загрузки товаров: ' + error.message, 'error');
        }
    }

    static renderProducts(data) {
        const container = elements.productsContainer;
        if (!container) return;

        if (data.items.length === 0) {
            container.innerHTML = '<div class="no-products">Товары не найдены</div>';
            return;
        }

        container.innerHTML = data.items.map(product => `
            <div class="product-card" data-id="${product.id}">
                <div class="product-image">
                    <img src="${product.images[0]}" alt="${utils.sanitizeHTML(product.title)}" loading="lazy">
                    ${product.old_price ? '<span class="product-discount">-20%</span>' : ''}
                </div>
                <div class="product-info">
                    <h3 class="product-title">${utils.sanitizeHTML(product.title)}</h3>
                    <div class="product-price">
                        ${utils.formatPrice(product.price)}
                        ${product.old_price ? `<span class="old-price">${utils.formatPrice(product.old_price)}</span>` : ''}
                    </div>
                    <div class="product-meta">
                        <span class="product-seller">${utils.sanitizeHTML(product.seller_name)}</span>
                        <span class="product-likes">❤️ ${product.likes || 0}</span>
                    </div>
                </div>
            </div>
        `).join('');

        // Добавляем обработчики клика на карточки
        container.querySelectorAll('.product-card').forEach(card => {
            card.addEventListener('click', () => {
                const productId = card.dataset.id;
                window.location.href = `/product/${productId}`;
            });
        });
    }

    static renderPagination(data) {
        const pagination = document.getElementById('pagination');
        if (!pagination) return;

        if (data.pages <= 1) {
            pagination.innerHTML = '';
            return;
        }

        let html = '<div class="pagination">';

        if (data.page > 1) {
            html += `<button class="page-btn" data-page="${data.page - 1}">←</button>`;
        }

        for (let i = 1; i <= data.pages; i++) {
            if (i === 1 || i === data.pages || Math.abs(i - data.page) <= 2) {
                html += `<button class="page-btn ${i === data.page ? 'active' : ''}" data-page="${i}">${i}</button>`;
            } else if (i === data.page - 3 || i === data.page + 3) {
                html += '<span class="page-dots">...</span>';
            }
        }

        if (data.page < data.pages) {
            html += `<button class="page-btn" data-page="${data.page + 1}">→</button>`;
        }

        html += '</div>';
        pagination.innerHTML = html;

        // Добавляем обработчики
        pagination.querySelectorAll('.page-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                this.currentPage = parseInt(btn.dataset.page);
                this.loadProducts(false);
            });
        });
    }

    static async handleCreateProduct(event) {
        event.preventDefault();
        const form = event.target;

        const formData = new FormData(form);
        const productData = {
            title: formData.get('title'),
            description: formData.get('description'),
            price: parseFloat(formData.get('price')),
            old_price: parseFloat(formData.get('old_price')) || null,
            category: formData.get('category'),
            condition: formData.get('condition'),
            brand: formData.get('brand'),
            quantity: parseInt(formData.get('quantity')) || 1,
            images: formData.get('images').split(',').map(url => url.trim()).filter(url => url),
            attributes: {}
        };

        try {
            const result = await api.createProduct(productData);
            utils.showNotification('Товар создан и отправлен на модерацию', 'success');
            utils.hideModal(elements.productModal);
            form.reset();
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }

    static updateFilters() {
        const category = elements.categoryFilter?.value;
        const priceRange = elements.priceFilter?.value;
        const search = elements.searchInput?.value;

        this.filters.category = category || '';
        this.filters.search = search || '';

        if (priceRange) {
            const [min, max] = priceRange.split('-').map(Number);
            this.filters.min_price = min;
            this.filters.max_price = max;
        }

        this.loadProducts();
    }
}

// Обработчики ПВЗ
class PVZHandler {
    static async loadPVZ(city = '') {
        try {
            const points = await api.getPVZ(city);
            this.renderPVZ(points);
        } catch (error) {
            utils.showNotification('Ошибка загрузки ПВЗ: ' + error.message, 'error');
        }
    }

    static renderPVZ(points) {
        const container = elements.pvzContainer;
        if (!container) return;

        if (points.length === 0) {
            container.innerHTML = '<div class="no-pvz">Пункты выдачи не найдены</div>';
            return;
        }

        container.innerHTML = points.map(pvz => `
            <div class="pvz-card" data-id="${pvz.id}">
                <h3 class="pvz-name">${utils.sanitizeHTML(pvz.name)}</h3>
                <p class="pvz-address">📍 ${utils.sanitizeHTML(pvz.address)}</p>
                <p class="pvz-phone">📞 ${pvz.phone || 'Не указан'}</p>
                <div class="pvz-hours">
                    🕒 ${pvz.working_hours ? Object.entries(pvz.working_hours).map(([day, hours]) =>
                        `<span class="pvz-hour">${day}: ${hours}</span>`
                    ).join('') : 'Режим работы не указан'}
                </div>
                ${pvz.services && pvz.services.length ? `
                    <div class="pvz-services">
                        ${pvz.services.map(service =>
                            `<span class="pvz-service">✓ ${service}</span>`
                        ).join('')}
                    </div>
                ` : ''}
            </div>
        `).join('');
    }

    static async handleCreatePVZ(event) {
        event.preventDefault();
        const form = event.target;

        const formData = new FormData(form);
        const workingHours = {};
        ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday'].forEach(day => {
            const hours = formData.get(`hours_${day}`);
            if (hours) workingHours[day] = hours;
        });

        const pvzData = {
            name: formData.get('name'),
            address: formData.get('address'),
            city: formData.get('city'),
            latitude: parseFloat(formData.get('latitude')) || null,
            longitude: parseFloat(formData.get('longitude')) || null,
            phone: formData.get('phone'),
            email: formData.get('email'),
            working_hours: workingHours,
            services: formData.getAll('services')
        };

        try {
            const result = await api.createPVZ(pvzData);
            utils.showNotification('ПВЗ успешно создан', 'success');
            utils.hideModal(elements.pvzModal);
            form.reset();
            this.loadPVZ();
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }
}

// Корзина
class CartHandler {
    static items = JSON.parse(localStorage.getItem('cart')) || [];

    static addItem(product) {
        const existing = this.items.find(item => item.id === product.id);
        if (existing) {
            existing.quantity += 1;
        } else {
            this.items.push({
                id: product.id,
                title: product.title,
                price: product.price,
                quantity: 1,
                image: product.images[0]
            });
        }
        this.save();
        this.updateUI();
        utils.showNotification('Товар добавлен в корзину', 'success');
    }

    static removeItem(productId) {
        this.items = this.items.filter(item => item.id !== productId);
        this.save();
        this.updateUI();
    }

    static updateQuantity(productId, quantity) {
        const item = this.items.find(item => item.id === productId);
        if (item) {
            item.quantity = Math.max(1, quantity);
            this.save();
            this.updateUI();
        }
    }

    static getTotal() {
        return this.items.reduce((sum, item) => sum + (item.price * item.quantity), 0);
    }

    static save() {
        localStorage.setItem('cart', JSON.stringify(this.items));
    }

    static updateUI() {
        const counter = document.getElementById('cart-counter');
        if (counter) {
            const count = this.items.reduce((sum, item) => sum + item.quantity, 0);
            counter.textContent = count;
            counter.style.display = count > 0 ? 'block' : 'none';
        }
    }

    static clear() {
        this.items = [];
        this.save();
        this.updateUI();
    }
}

// Заказы
class OrderHandler {
    static async createOrder(pvzId = null, shippingAddress = null) {
        const cartItems = CartHandler.items;
        if (cartItems.length === 0) {
            utils.showNotification('Корзина пуста', 'error');
            return;
        }

        const orderData = {
            items: cartItems.map(item => ({
                product_id: item.id,
                quantity: item.quantity
            })),
            pvz_id: pvzId,
            shipping_address: shippingAddress
        };

        try {
            const result = await api.createOrder(orderData);
            utils.showNotification(`Заказ №${result.order_number} создан`, 'success');
            CartHandler.clear();
            window.location.href = `/order/${result.order_number}`;
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    }
}

// Инициализация приложения
document.addEventListener('DOMContentLoaded', async () => {
    // Проверяем авторизацию
    await AuthHandler.checkAuth();

    // Загружаем товары
    if (elements.productsContainer) {
        await ProductHandler.loadProducts();
    }

    // Загружаем ПВЗ
    if (elements.pvzContainer) {
        await PVZHandler.loadPVZ();
    }

    // Инициализируем корзину
    CartHandler.updateUI();

    // Обработчики событий
    initEventListeners();
});

function initEventListeners() {
    // Авторизация
    document.getElementById('login-btn')?.addEventListener('click', () => utils.showModal(elements.authModal));
    document.getElementById('register-btn')?.addEventListener('click', () => utils.showModal(elements.registerModal));
    document.getElementById('logout-btn')?.addEventListener('click', AuthHandler.handleLogout);

    // Закрытие модалок
    document.querySelectorAll('.modal-close').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const modal = e.target.closest('.modal');
            utils.hideModal(modal);
        });
    });

    // Формы
    elements.loginForm?.addEventListener('submit', AuthHandler.handleLogin);
    elements.registerForm?.addEventListener('submit', AuthHandler.handleRegister);
    elements.verifyForm?.addEventListener('submit', AuthHandler.handleVerify);

    document.getElementById('resend-code')?.addEventListener('click', AuthHandler.handleResendCode);

    // Стать продавцом
    elements.becomeSellerBtn?.addEventListener('click', async () => {
        try {
            await api.becomeSeller();
            utils.showNotification('Теперь вы продавец!', 'success');
            await AuthHandler.checkAuth();
        } catch (error) {
            utils.showNotification(error.message, 'error');
        }
    });

    // Создание товара
    elements.createProductBtn?.addEventListener('click', () => utils.showModal(elements.productModal));
    elements.productModal?.querySelector('form')?.addEventListener('submit', ProductHandler.handleCreateProduct);

    // Создание ПВЗ
    elements.createPvzBtn?.addEventListener('click', () => utils.showModal(elements.pvzModal));
    elements.pvzModal?.querySelector('form')?.addEventListener('submit', PVZHandler.handleCreatePVZ);

    // Фильтры
    const debouncedLoad = utils.debounce(() => ProductHandler.updateFilters(), 500);
    elements.categoryFilter?.addEventListener('change', () => ProductHandler.updateFilters());
    elements.priceFilter?.addEventListener('change', () => ProductHandler.updateFilters());
    elements.searchInput?.addEventListener('input', debouncedLoad);
    elements.searchBtn?.addEventListener('click', () => ProductHandler.updateFilters());

    // Закрытие модалок по клику вне
    window.addEventListener('click', (e) => {
        if (e.target.classList.contains('modal')) {
            utils.hideModal(e.target);
        }
    });

    // Защита от XSS во всех input
    document.querySelectorAll('input[type="text"], input[type="email"], textarea').forEach(input => {
        input.addEventListener('input', function() {
            this.value = this.value.replace(/[<>]/g, '');
        });
    });
}

// Экспорт для использования в других модулях
window.Kildear = {
    api,
    utils,
    AuthHandler,
    ProductHandler,
    PVZHandler,
    CartHandler,
    OrderHandler
};