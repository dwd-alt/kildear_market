// ==================== ГЛОБАЛЬНЫЕ ФУНКЦИИ ====================

// Инициализация при загрузке страницы
$(document).ready(function() {
    console.log('Kildear marketplace initialized');

    // Инициализация Bootstrap компонентов
    initBootstrapComponents();

    // Обновление счетчика корзины
    updateCartCount();

    // Обновление счетчика уведомлений
    updateNotificationCount();

    // Инициализация анимаций при скролле
    initScrollAnimations();

    // Инициализация ленивой загрузки изображений
    initLazyLoading();

    // Инициализация поиска в реальном времени
    initLiveSearch();

    // Инициализация обработчиков форм
    initFormHandlers();

    // Инициализация обработчиков корзины
    initCartHandlers();

    // Инициализация рейтинга
    initRatingSystem();
});

// ==================== BOOTSTRAP КОМПОНЕНТЫ ====================

function initBootstrapComponents() {
    // Инициализация всех тултипов
    var tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function(tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });

    // Инициализация всех поповеров
    var popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function(popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });

    // Автоматическое закрытие alert сообщений
    setTimeout(function() {
        $('.alert-dismissible').fadeOut();
    }, 5000);
}

// ==================== КОРЗИНА ====================

function initCartHandlers() {
    // Добавление в корзину
    $(document).on('click', '.add-to-cart', function() {
        var productId = $(this).data('product-id');
        var quantity = $(this).data('quantity') || 1;
        addToCart(productId, quantity);
    });

    // Удаление из корзины
    $(document).on('click', '.remove-from-cart', function() {
        var itemId = $(this).data('item-id');
        removeFromCart(itemId);
    });

    // Изменение количества
    $(document).on('change', '.cart-quantity-input', function() {
        var itemId = $(this).data('item-id');
        var quantity = $(this).val();
        updateCartItemQuantity(itemId, quantity);
    });

    // Кнопки +/-
    $(document).on('click', '.quantity-plus', function() {
        var input = $(this).siblings('.cart-quantity-input');
        var newVal = parseInt(input.val()) + 1;
        input.val(newVal).trigger('change');
    });

    $(document).on('click', '.quantity-minus', function() {
        var input = $(this).siblings('.cart-quantity-input');
        var newVal = parseInt(input.val()) - 1;
        if (newVal >= 1) {
            input.val(newVal).trigger('change');
        }
    });
}

function addToCart(productId, quantity = 1) {
    showLoading();

    $.ajax({
        url: '/api/cart/add',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            product_id: productId,
            quantity: quantity
        }),
        success: function(response) {
            if (response.success) {
                showNotification('Товар добавлен в корзину', 'success');
                updateCartCount();
                updateCartPreview();
            } else {
                showNotification(response.error || 'Ошибка при добавлении товара', 'error');
            }
        },
        error: function(xhr) {
            var error = xhr.responseJSON?.error || 'Ошибка сервера';
            showNotification(error, 'error');
        },
        complete: function() {
            hideLoading();
        }
    });
}

function removeFromCart(itemId) {
    if (!confirm('Удалить товар из корзины?')) return;

    showLoading();

    $.ajax({
        url: '/api/cart/remove/' + itemId,
        method: 'DELETE',
        success: function(response) {
            if (response.success) {
                $('[data-item-id="' + itemId + '"]').fadeOut(300, function() {
                    $(this).remove();
                    updateCartTotals();
                    updateCartCount();

                    if ($('.cart-item').length === 0) {
                        location.reload();
                    }
                });
                showNotification('Товар удален из корзины', 'success');
            }
        },
        error: function() {
            showNotification('Ошибка при удалении товара', 'error');
        },
        complete: function() {
            hideLoading();
        }
    });
}

function updateCartItemQuantity(itemId, quantity) {
    if (quantity < 1) {
        removeFromCart(itemId);
        return;
    }

    $.ajax({
        url: '/api/cart/update/' + itemId,
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ quantity: quantity }),
        success: function(response) {
            if (response.success) {
                updateCartTotals();
                updateCartCount();
            }
        },
        error: function() {
            showNotification('Ошибка при обновлении количества', 'error');
        }
    });
}

function updateCartCount() {
    $.ajax({
        url: '/api/cart/totals',
        method: 'GET',
        success: function(data) {
            $('.cart-count').text(data.count || 0);
            if (data.count > 0) {
                $('.cart-count').show();
            } else {
                $('.cart-count').hide();
            }
        }
    });
}

function updateCartTotals() {
    $.ajax({
        url: '/api/cart/totals',
        method: 'GET',
        success: function(data) {
            $('#subtotal').text(data.subtotal + ' ₽');
            $('#total').text(data.total + ' ₽');
            $('#cartCount').text(data.count);

            if (data.discount > 0) {
                $('#discount').text('-' + data.discount + ' ₽').parent().show();
            } else {
                $('#discount').parent().hide();
            }
        }
    });
}

function updateCartPreview() {
    // Обновление превью корзины в шапке
    $.ajax({
        url: '/api/cart/preview',
        method: 'GET',
        success: function(data) {
            // Обновление HTML превью
        }
    });
}

// ==================== УВЕДОМЛЕНИЯ ====================

function updateNotificationCount() {
    $.ajax({
        url: '/api/notifications',
        method: 'GET',
        success: function(notifications) {
            var count = notifications.length;
            $('.notification-count').text(count);

            if (count > 0) {
                $('.notification-count').show();
                updateNotificationDropdown(notifications);
            } else {
                $('.notification-count').hide();
            }
        }
    });
}

function updateNotificationDropdown(notifications) {
    var dropdown = $('.notification-dropdown .dropdown-menu');
    dropdown.empty();

    if (notifications.length > 0) {
        notifications.forEach(function(n) {
            dropdown.append(`
                <a class="dropdown-item notification-item" href="#" data-id="${n.id}">
                    <div class="d-flex align-items-center">
                        <div class="notification-icon me-2">
                            <i class="fas fa-${getNotificationIcon(n.type)} text-primary"></i>
                        </div>
                        <div class="flex-grow-1">
                            <div class="fw-bold small">${n.title}</div>
                            <div class="small text-muted">${n.message}</div>
                            <small class="text-muted">${n.created_at}</small>
                        </div>
                    </div>
                </a>
            `);
        });

        dropdown.append('<div class="dropdown-divider"></div>');
        dropdown.append('<a class="dropdown-item text-center small" href="/notifications">Все уведомления</a>');
    } else {
        dropdown.append('<span class="dropdown-item text-muted text-center">Нет новых уведомлений</span>');
    }
}

function getNotificationIcon(type) {
    var icons = {
        'new_order': 'shopping-bag',
        'payment_received': 'credit-card',
        'order_status': 'truck',
        'order_cancelled': 'times-circle',
        'listing_approved': 'check-circle',
        'listing_rejected': 'exclamation-circle',
        'review': 'star'
    };
    return icons[type] || 'bell';
}

$(document).on('click', '.notification-item', function(e) {
    e.preventDefault();
    var notificationId = $(this).data('id');

    $.ajax({
        url: '/api/notifications/' + notificationId + '/read',
        method: 'POST',
        success: function() {
            updateNotificationCount();
        }
    });
});

// ==================== ПОИСК ====================

function initLiveSearch() {
    var searchInput = $('#searchInput');
    var searchResults = $('#searchResults');
    var searchTimeout;

    searchInput.on('input', function() {
        var query = $(this).val();

        clearTimeout(searchTimeout);

        if (query.length < 3) {
            searchResults.hide();
            return;
        }

        searchTimeout = setTimeout(function() {
            liveSearch(query);
        }, 300);
    });

    // Закрытие результатов при клике вне
    $(document).on('click', function(e) {
        if (!$(e.target).closest('.search-container').length) {
            searchResults.hide();
        }
    });
}

function liveSearch(query) {
    $.ajax({
        url: '/api/search',
        method: 'GET',
        data: { q: query },
        success: function(data) {
            displaySearchResults(data);
        }
    });
}

function displaySearchResults(results) {
    var container = $('#searchResults');
    container.empty();

    if (results.length > 0) {
        results.forEach(function(item) {
            container.append(`
                <a href="/listing/${item.id}" class="search-result-item d-flex align-items-center p-2 text-decoration-none">
                    <img src="${item.image}" class="rounded-3 me-2" width="40" height="40" style="object-fit: cover;">
                    <div class="flex-grow-1">
                        <div class="small fw-bold text-dark">${item.title}</div>
                        <div class="small text-primary">${item.price} ₽</div>
                    </div>
                </a>
            `);
        });
        container.show();
    } else {
        container.html('<div class="p-3 text-muted text-center">Ничего не найдено</div>').show();
    }
}

// ==================== ФИЛЬТРАЦИЯ ТОВАРОВ ====================

function initFilters() {
    $('#filterForm input, #filterForm select').on('change', function() {
        filterProducts();
    });

    $('#priceRange').on('input', function() {
        $('#priceValue').text($(this).val());
    });
}

function filterProducts() {
    var formData = $('#filterForm').serialize();

    $.ajax({
        url: '/api/filter',
        method: 'GET',
        data: formData,
        success: function(data) {
            $('#productsGrid').html(data.html);
            updatePagination(data.pagination);
        }
    });
}

function updatePagination(pagination) {
    // Обновление пагинации
}

// ==================== ФОРМЫ И ВАЛИДАЦИЯ ====================

function initFormHandlers() {
    // Валидация форм
    $('form[data-validate]').on('submit', function(e) {
        if (!validateForm($(this))) {
            e.preventDefault();
        }
    });

    // Маски для полей
    initInputMasks();

    // Превью изображений
    initImagePreview();

    // Загрузка аватара
    initAvatarUpload();
}

function validateForm($form) {
    var isValid = true;

    $form.find('[required]').each(function() {
        if (!$(this).val().trim()) {
            $(this).addClass('is-invalid');
            isValid = false;
        } else {
            $(this).removeClass('is-invalid');
        }
    });

    // Валидация email
    var $email = $form.find('input[type="email"]');
    if ($email.length && $email.val()) {
        var emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;
        if (!emailRegex.test($email.val())) {
            $email.addClass('is-invalid');
            isValid = false;
        }
    }

    // Валидация пароля
    var $password = $form.find('input[type="password"]');
    if ($password.length && $password.val()) {
        if ($password.val().length < 6) {
            $password.addClass('is-invalid');
            isValid = false;
        }
    }

    return isValid;
}

function initInputMasks() {
    // Маска для телефона
    $(document).on('input', 'input[type="tel"]', function(e) {
        var x = e.target.value.replace(/\D/g, '').match(/(\d{0,1})(\d{0,3})(\d{0,3})(\d{0,2})(\d{0,2})/);
        e.target.value = !x[2] ? x[1] : '+' + x[1] + ' (' + x[2] + ') ' + x[3] + (x[4] ? '-' + x[4] : '') + (x[5] ? '-' + x[5] : '');
    });

    // Маска для цены
    $(document).on('input', 'input[type="number"]', function() {
        var value = parseFloat($(this).val());
        if (value < 0) $(this).val(0);
    });

    // Маска для карты
    $(document).on('input', '#cardNumber', function(e) {
        var value = e.target.value.replace(/\D/g, '');
        var formattedValue = '';

        for (var i = 0; i < value.length; i++) {
            if (i > 0 && i % 4 === 0) {
                formattedValue += ' ';
            }
            formattedValue += value[i];
        }

        e.target.value = formattedValue;
    });

    // Маска для срока действия карты
    $(document).on('input', '#cardExpiry', function(e) {
        var value = e.target.value.replace(/\D/g, '');

        if (value.length >= 2) {
            e.target.value = value.slice(0, 2) + '/' + value.slice(2, 4);
        } else {
            e.target.value = value;
        }
    });

    // Маска для CVV
    $(document).on('input', '#cardCvv', function(e) {
        e.target.value = e.target.value.replace(/\D/g, '').slice(0, 3);
    });
}

// ==================== ЗАГРУЗКА ИЗОБРАЖЕНИЙ ====================

function initImagePreview() {
    $(document).on('change', 'input[type="file"][data-preview]', function() {
        previewImages(this);
    });
}

function previewImages(input) {
    var preview = $(input).data('preview');
    var $preview = $(preview);
    $preview.empty();

    if (input.files) {
        $.each(input.files, function(i, file) {
            if (file.type.startsWith('image/')) {
                var reader = new FileReader();

                reader.onload = function(e) {
                    $preview.append(`
                        <div class="preview-item position-relative d-inline-block m-2">
                            <img src="${e.target.result}" class="rounded-3"
                                 style="width: 100px; height: 100px; object-fit: cover;">
                            <button type="button" class="btn-close position-absolute top-0 end-0 m-1 bg-white rounded-circle"
                                    onclick="removePreview(this)"></button>
                        </div>
                    `);
                };

                reader.readAsDataURL(file);
            }
        });
    }
}

function removePreview(btn) {
    $(btn).closest('.preview-item').remove();
}

function initAvatarUpload() {
    $('#avatarInput').on('change', function(e) {
        var file = e.target.files[0];
        if (!file) return;

        var formData = new FormData();
        formData.append('avatar', file);

        $.ajax({
            url: '/api/upload-avatar',
            method: 'POST',
            data: formData,
            processData: false,
            contentType: false,
            success: function(response) {
                if (response.success) {
                    $('.user-avatar').attr('src', response.url);
                    showNotification('Аватар обновлен', 'success');
                }
            },
            error: function() {
                showNotification('Ошибка при загрузке аватара', 'error');
            }
        });
    });
}

// ==================== РЕЙТИНГ И ОТЗЫВЫ ====================

function initRatingSystem() {
    $(document).on('mouseover', '.rating-input i', function() {
        var rating = $(this).data('rating');
        highlightStars(rating, $(this).closest('.rating-input'));
    });

    $(document).on('mouseleave', '.rating-input', function() {
        var currentRating = $(this).find('input[type="hidden"]').val();
        highlightStars(currentRating, $(this));
    });

    $(document).on('click', '.rating-input i', function() {
        var rating = $(this).data('rating');
        var $container = $(this).closest('.rating-input');
        $container.find('input[type="hidden"]').val(rating);
        highlightStars(rating, $container);
    });
}

function highlightStars(rating, $container) {
    $container.find('i').each(function() {
        var starRating = $(this).data('rating');
        if (starRating <= rating) {
            $(this).removeClass('far').addClass('fas');
        } else {
            $(this).removeClass('fas').addClass('far');
        }
    });
}

function submitReview(formId) {
    var $form = $('#' + formId);
    var formData = {
        product_id: $form.find('[name="product_id"]').val(),
        rating: $form.find('[name="rating"]').val(),
        comment: $form.find('[name="comment"]').val(),
        order_id: $form.find('[name="order_id"]').val()
    };

    if (!formData.rating) {
        showNotification('Пожалуйста, поставьте оценку', 'warning');
        return;
    }

    $.ajax({
        url: '/api/reviews',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify(formData),
        success: function(response) {
            if (response.success) {
                showNotification('Спасибо за отзыв!', 'success');
                setTimeout(function() {
                    location.reload();
                }, 1500);
            } else {
                showNotification(response.error || 'Ошибка при отправке отзыва', 'error');
            }
        },
        error: function() {
            showNotification('Ошибка сервера', 'error');
        }
    });
}

// ==================== ПРОМОКОДЫ ====================

function applyPromo() {
    var promo = $('#promoInput').val();

    if (!promo) {
        showNotification('Введите промокод', 'warning');
        return;
    }

    $.ajax({
        url: '/api/cart/apply-promo',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ promo: promo }),
        success: function(response) {
            if (response.success) {
                updateCartTotals();
                showNotification('Промокод применен! Скидка: ' + response.discount + ' ₽', 'success');
            } else {
                showNotification(response.error || 'Неверный промокод', 'error');
            }
        },
        error: function() {
            showNotification('Ошибка при применении промокода', 'error');
        }
    });
}

// ==================== ЗАКАЗЫ ====================

function updateOrderStatus(orderId) {
    var status = $('#orderStatus').val();
    var comment = $('#statusComment').val();
    var trackingNumber = $('#trackingNumber').val();

    $.ajax({
        url: '/api/order/' + orderId + '/status',
        method: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({
            status: status,
            comment: comment,
            tracking_number: trackingNumber
        }),
        success: function(response) {
            if (response.success) {
                showNotification('Статус заказа обновлен', 'success');
                setTimeout(function() {
                    location.reload();
                }, 1500);
            } else {
                showNotification(response.error || 'Ошибка при обновлении статуса', 'error');
            }
        },
        error: function() {
            showNotification('Ошибка сервера', 'error');
        }
    });
}

function cancelOrder(orderId) {
    if (!confirm('Вы уверены, что хотите отменить заказ?')) return;

    $.ajax({
        url: '/api/order/' + orderId + '/cancel',
        method: 'POST',
        success: function(response) {
            if (response.success) {
                showNotification('Заказ отменен', 'success');
                setTimeout(function() {
                    location.reload();
                }, 1500);
            } else {
                showNotification(response.error || 'Ошибка при отмене заказа', 'error');
            }
        },
        error: function() {
            showNotification('Ошибка сервера', 'error');
        }
    });
}

function trackOrder(orderId) {
    $.ajax({
        url: '/api/order/' + orderId + '/track',
        method: 'GET',
        success: function(response) {
            if (response.success) {
                displayTrackingInfo(response);
            }
        }
    });
}

function displayTrackingInfo(data) {
    var modal = `
        <div class="modal fade" id="trackingModal" tabindex="-1">
            <div class="modal-dialog">
                <div class="modal-content">
                    <div class="modal-header">
                        <h5 class="modal-title">Отслеживание заказа #${data.order_number}</h5>
                        <button type="button" class="btn-close" data-bs-dismiss="modal"></button>
                    </div>
                    <div class="modal-body">
                        <div class="tracking-info">
                            <p><strong>Текущий статус:</strong> ${data.current_status}</p>
                            ${data.tracking_number ? '<p><strong>Трек-номер:</strong> ' + data.tracking_number + '</p>' : ''}
                            ${data.estimated_delivery ? '<p><strong>Ожидаемая дата:</strong> ' + data.estimated_delivery + '</p>' : ''}

                            <h6 class="mt-4">История статусов:</h6>
                            <div class="timeline">
                                ${data.status_history.map(function(item) {
                                    return `
                                        <div class="timeline-item d-flex gap-3 mb-3">
                                            <div class="timeline-dot"></div>
                                            <div>
                                                <div class="fw-bold">${item.status}</div>
                                                <div class="small text-muted">${item.created_at}</div>
                                                ${item.comment ? '<div class="small">' + item.comment + '</div>' : ''}
                                            </div>
                                        </div>
                                    `;
                                }).join('')}
                            </div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `;

    $('body').append(modal);
    $('#trackingModal').modal('show');
    $('#trackingModal').on('hidden.bs.modal', function() {
        $(this).remove();
    });
}

// ==================== ИЗБРАННОЕ ====================

function toggleFavorite(productId) {
    $.ajax({
        url: '/api/favorites/' + productId + '/toggle',
        method: 'POST',
        success: function(response) {
            if (response.success) {
                var $btn = $('[data-product-id="' + productId + '"].favorite-btn');
                if (response.is_favorite) {
                    $btn.find('i').removeClass('far').addClass('fas');
                    showNotification('Добавлено в избранное', 'success');
                } else {
                    $btn.find('i').removeClass('fas').addClass('far');
                    showNotification('Удалено из избранного', 'info');
                }
            }
        }
    });
}

// ==================== УВЕДОМЛЕНИЯ (TOAST) ====================

function showNotification(message, type = 'info') {
    var icon = {
        'success': 'check-circle',
        'error': 'exclamation-circle',
        'warning': 'exclamation-triangle',
        'info': 'info-circle'
    };

    var toast = `
        <div class="toast-notification position-fixed top-0 end-0 m-3 p-3 bg-white rounded-3 shadow-lg"
             style="z-index: 9999; min-width: 300px; animation: slideIn 0.3s;">
            <div class="d-flex align-items-center">
                <i class="fas fa-${icon[type]} text-${type} fa-2x me-3"></i>
                <div class="flex-grow-1">
                    <div class="fw-bold">${message}</div>
                </div>
                <button type="button" class="btn-close" onclick="this.closest('.toast-notification').remove()"></button>
            </div>
        </div>
    `;

    $('body').append(toast);

    setTimeout(function() {
        $('.toast-notification').fadeOut(300, function() {
            $(this).remove();
        });
    }, 3000);
}

// ==================== ЗАГРУЗКА ====================

function showLoading() {
    if ($('#loading-overlay').length === 0) {
        $('body').append(`
            <div id="loading-overlay" class="position-fixed top-0 start-0 w-100 h-100"
                 style="background: rgba(255,255,255,0.8); z-index: 99999;">
                <div class="position-absolute top-50 start-50 translate-middle text-center">
                    <div class="spinner-border text-primary" role="status" style="width: 3rem; height: 3rem;">
                        <span class="visually-hidden">Загрузка...</span>
                    </div>
                </div>
            </div>
        `);
    }
}

function hideLoading() {
    $('#loading-overlay').fadeOut(300, function() {
        $(this).remove();
    });
}

// ==================== АНИМАЦИИ ====================

function initScrollAnimations() {
    var elements = document.querySelectorAll('.animate-on-scroll');

    var observer = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                entry.target.classList.add('fade-in');
            }
        });
    }, { threshold: 0.1 });

    elements.forEach(function(element) {
        observer.observe(element);
    });
}

// ==================== ЛЕНИВАЯ ЗАГРУЗКА ====================

function initLazyLoading() {
    var images = document.querySelectorAll('img[data-src]');

    var imageObserver = new IntersectionObserver(function(entries) {
        entries.forEach(function(entry) {
            if (entry.isIntersecting) {
                var img = entry.target;
                img.src = img.dataset.src;
                img.classList.add('loaded');
                imageObserver.unobserve(img);
            }
        });
    });

    images.forEach(function(img) {
        imageObserver.observe(img);
    });
}

// ==================== ГАЛЕРЕЯ ТОВАРОВ ====================

function initProductGallery() {
    var mainImage = $('#mainImage');
    var thumbnails = $('.thumbnail');

    thumbnails.on('click', function() {
        var src = $(this).attr('src');
        mainImage.attr('src', src);
        thumbnails.removeClass('active');
        $(this).addClass('active');
    });

    // Навигация
    $('#prevImage').on('click', function() {
        var current = $('.thumbnail.active');
        var prev = current.closest('.col-3').prev().find('.thumbnail');
        if (prev.length) {
            prev.click();
        }
    });

    $('#nextImage').on('click', function() {
        var current = $('.thumbnail.active');
        var next = current.closest('.col-3').next().find('.thumbnail');
        if (next.length) {
            next.click();
        }
    });
}

// ==================== ЧАТ ====================

function initChat() {
    $('#chatForm').on('submit', function(e) {
        e.preventDefault();
        var message = $('#chatMessage').val();

        if (!message.trim()) return;

        $.ajax({
            url: '/api/chat/send',
            method: 'POST',
            contentType: 'application/json',
            data: JSON.stringify({
                recipient_id: $(this).data('recipient'),
                message: message
            }),
            success: function(response) {
                if (response.success) {
                    $('#chatMessage').val('');
                    appendMessage(response.message);
                }
            }
        });
    });
}

function appendMessage(message) {
    var html = `
        <div class="chat-message my-2 d-flex justify-content-end">
            <div class="bg-primary text-white rounded-3 p-3" style="max-width: 70%;">
                ${message}
                <div class="small text-white-50">Только что</div>
            </div>
        </div>
    `;
    $('#chatMessages').append(html);
    $('#chatMessages').scrollTop($('#chatMessages')[0].scrollHeight);
}

// ==================== ЭКСПОРТ ФУНКЦИЙ ====================

// Делаем функции глобально доступными
window.addToCart = addToCart;
window.removeFromCart = removeFromCart;
window.updateCartItemQuantity = updateCartItemQuantity;
window.applyPromo = applyPromo;
window.toggleFavorite = toggleFavorite;
window.updateOrderStatus = updateOrderStatus;
window.cancelOrder = cancelOrder;
window.trackOrder = trackOrder;
window.submitReview = submitReview;
window.showNotification = showNotification;