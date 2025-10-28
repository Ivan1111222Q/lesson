// API Configuration
const API_BASE = {
    products: 'http://localhost:8001',
    orders: 'http://localhost:8002',
    users: 'http://localhost:8003',
    reviews: 'http://localhost:8004'
};

// Helper function to make API requests
async function apiRequest(url, options = {}) {
    try {
        const response = await fetch(url, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'API request failed');
        }

        return await response.json();
    } catch (error) {
        console.error('API Error:', error);
        throw error;
    }
}

// Products API
const ProductsAPI = {
    getAll: (category = null) => {
        const url = category
            ? `${API_BASE.products}/products?category=${category}`
            : `${API_BASE.products}/products`;
        return apiRequest(url);
    },

    getById: (id) => {
        return apiRequest(`${API_BASE.products}/products/${id}`);
    },

    create: (product) => {
        return apiRequest(`${API_BASE.products}/products`, {
            method: 'POST',
            body: JSON.stringify(product)
        });
    },

    getPopular: (limit = 10) => {
        return apiRequest(`${API_BASE.products}/products/popular?limit=${limit}`);
    }
};

// Orders API
const OrdersAPI = {
    create: (order) => {
        return apiRequest(`${API_BASE.orders}/orders`, {
            method: 'POST',
            body: JSON.stringify(order)
        });
    },

    getAll: (userId = null) => {
        const url = userId
            ? `${API_BASE.orders}/orders?user_id=${userId}`
            : `${API_BASE.orders}/orders`;
        return apiRequest(url);
    },

    getById: (id) => {
        return apiRequest(`${API_BASE.orders}/orders/${id}`);
    },

    getDetails: (id) => {
        return apiRequest(`${API_BASE.orders}/orders/${id}/details`);
    },

    updateStatus: (id, status) => {
        return apiRequest(`${API_BASE.orders}/orders/${id}/status?status=${status}`, {
            method: 'PATCH'
        });
    },

    cancel: (id) => {
        return apiRequest(`${API_BASE.orders}/orders/${id}/cancel`, {
            method: 'POST'
        });
    }
};

// Users API
const UsersAPI = {
    register: (userData) => {
        return apiRequest(`${API_BASE.users}/register`, {
            method: 'POST',
            body: JSON.stringify(userData)
        });
    },

    login: (credentials) => {
        return apiRequest(`${API_BASE.users}/login`, {
            method: 'POST',
            body: JSON.stringify(credentials)
        });
    },

    getProfile: (token) => {
        return apiRequest(`${API_BASE.users}/me`, {
            headers: {
                'Authorization': `Bearer ${token}`
            }
        });
    },

    getById: (id) => {
        return apiRequest(`${API_BASE.users}/users/${id}`);
    },

    getOrders: (id) => {
        return apiRequest(`${API_BASE.users}/users/${id}/orders`);
    },

    getStats: (id) => {
        return apiRequest(`${API_BASE.users}/users/${id}/stats`);
    }
};

// Reviews API
const ReviewsAPI = {
    create: async (formData) => {
        try {
            const response = await fetch(`${API_BASE.reviews}/reviews`, {
                method: 'POST',
                body: formData // FormData для загрузки файлов
            });

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.detail || 'Failed to create review');
            }

            return await response.json();
        } catch (error) {
            console.error('Review creation error:', error);
            throw error;
        }
    },

    getAll: (params = {}) => {
        const queryParams = new URLSearchParams();
        if (params.product_id) queryParams.append('product_id', params.product_id);
        if (params.user_id) queryParams.append('user_id', params.user_id);
        if (params.sort_by) queryParams.append('sort_by', params.sort_by);
        if (params.limit) queryParams.append('limit', params.limit);
        if (params.offset) queryParams.append('offset', params.offset);

        const url = `${API_BASE.reviews}/reviews?${queryParams.toString()}`;
        return apiRequest(url);
    },

    getById: (id) => {
        return apiRequest(`${API_BASE.reviews}/reviews/${id}`);
    },

    delete: (id) => {
        return apiRequest(`${API_BASE.reviews}/reviews/${id}`, {
            method: 'DELETE'
        });
    },

    getProductReviews: (productId) => {
        return apiRequest(`${API_BASE.reviews}/products/${productId}/reviews`);
    },

    getProductRating: (productId) => {
        return apiRequest(`${API_BASE.reviews}/products/${productId}/rating`);
    },

    getPhotoUrl: (reviewId, filename) => {
        return `${API_BASE.reviews}/reviews/${reviewId}/photos/${filename}`;
    }
};

// Local Storage helpers
const Storage = {
    getToken: () => localStorage.getItem('token'),
    setToken: (token) => localStorage.setItem('token', token),
    clearToken: () => localStorage.removeItem('token'),

    getUser: () => {
        const user = localStorage.getItem('user');
        return user ? JSON.parse(user) : null;
    },
    setUser: (user) => localStorage.setItem('user', JSON.stringify(user)),
    clearUser: () => localStorage.removeItem('user'),

    getCart: () => {
        const cart = localStorage.getItem('cart');
        return cart ? JSON.parse(cart) : [];
    },
    setCart: (cart) => localStorage.setItem('cart', JSON.stringify(cart)),
    clearCart: () => localStorage.removeItem('cart'),

    addToCart: (product, quantity = 1) => {
        const cart = Storage.getCart();
        const existing = cart.find(item => item.product_id === product.id);

        if (existing) {
            existing.quantity += quantity;
        } else {
            cart.push({
                product_id: product.id,
                name: product.name,
                price: product.price,
                quantity: quantity
            });
        }

        Storage.setCart(cart);
        return cart;
    },

    removeFromCart: (productId) => {
        let cart = Storage.getCart();
        cart = cart.filter(item => item.product_id !== productId);
        Storage.setCart(cart);
        return cart;
    },

    updateCartQuantity: (productId, quantity) => {
        const cart = Storage.getCart();
        const item = cart.find(item => item.product_id === productId);
        if (item) {
            item.quantity = quantity;
            Storage.setCart(cart);
        }
        return cart;
    },

    getCartTotal: () => {
        const cart = Storage.getCart();
        return cart.reduce((total, item) => total + (item.price * item.quantity), 0);
    }
};
