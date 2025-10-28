// Common app functionality
const App = {
    init() {
        this.updateHeader();
        this.updateCartCount();
    },

    updateHeader() {
        const user = Storage.getUser();
        const userInfo = document.querySelector('.user-info');

        if (user && userInfo) {
            userInfo.innerHTML = `
                <span>Привет, ${user.name}!</span>
                <button onclick="App.logout()">Выйти</button>
            `;
        } else if (userInfo) {
            userInfo.innerHTML = `
                <a href="/profile.html" class="btn">Войти</a>
            `;
        }
    },

    updateCartCount() {
        const cart = Storage.getCart();
        const cartCountEl = document.getElementById('cart-count');
        if (cartCountEl) {
            const totalItems = cart.reduce((sum, item) => sum + item.quantity, 0);
            cartCountEl.textContent = totalItems;
        }
    },

    logout() {
        Storage.clearToken();
        Storage.clearUser();
        window.location.href = '/index.html';
    },

    showError(message) {
        const errorDiv = document.createElement('div');
        errorDiv.className = 'error';
        errorDiv.textContent = message;
        document.querySelector('.container').prepend(errorDiv);
        setTimeout(() => errorDiv.remove(), 5000);
    },

    showSuccess(message) {
        const successDiv = document.createElement('div');
        successDiv.className = 'success';
        successDiv.textContent = message;
        document.querySelector('.container').prepend(successDiv);
        setTimeout(() => successDiv.remove(), 5000);
    },

    showLoading(element) {
        element.innerHTML = '<div class="loading">Загрузка...</div>';
    },

    formatPrice(price) {
        return new Intl.NumberFormat('ru-RU', {
            style: 'currency',
            currency: 'RUB'
        }).format(price);
    },

    formatDate(dateString) {
        const date = new Date(dateString);
        return date.toLocaleDateString('ru-RU', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
    },

    renderStars(rating) {
        const fullStars = Math.floor(rating);
        const hasHalfStar = rating % 1 >= 0.5;
        let stars = '';

        for (let i = 0; i < fullStars; i++) {
            stars += '★';
        }
        if (hasHalfStar) {
            stars += '☆';
        }
        for (let i = stars.length; i < 5; i++) {
            stars += '☆';
        }

        return stars;
    },

    requireAuth() {
        const user = Storage.getUser();
        if (!user) {
            alert('Необходимо войти в систему');
            window.location.href = '/profile.html';
            return false;
        }
        return true;
    }
};

// Initialize app on page load
document.addEventListener('DOMContentLoaded', () => {
    App.init();
});
