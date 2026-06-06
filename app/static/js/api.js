/**
 * api.js — Vanilla JS обёртка над Fetch API для работы с REST-эндпоинтами FastAPI.
 * Автоматически добавляет JWT-токен из localStorage в заголовок Authorization.
 */
const api = (() => {
  function getToken() {
    return localStorage.getItem('token');
  }

  function headers(extra = {}) {
    const h = { 'Content-Type': 'application/json', ...extra };
    const token = getToken();
    if (token) h['Authorization'] = `Bearer ${token}`;
    return h;
  }

  async function handleResponse(resp) {
    if (resp.status === 401) {
      // Token expired or invalid — redirect to login
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/auth/login';
      return;
    }
    const data = await resp.json().catch(() => ({}));
    if (!resp.ok) {
      throw new Error(data.detail || `Ошибка ${resp.status}`);
    }
    return data;
  }

  return {
    async get(url) {
      const resp = await fetch(url, { headers: headers() });
      return handleResponse(resp);
    },

    async post(url, body) {
      const resp = await fetch(url, {
        method: 'POST',
        headers: headers(),
        body: JSON.stringify(body),
      });
      return handleResponse(resp);
    },

    async put(url, body) {
      const resp = await fetch(url, {
        method: 'PUT',
        headers: headers(),
        body: JSON.stringify(body),
      });
      return handleResponse(resp);
    },

    async patch(url, body) {
      const resp = await fetch(url, {
        method: 'PATCH',
        headers: headers(),
        body: JSON.stringify(body),
      });
      return handleResponse(resp);
    },

    async delete(url) {
      const resp = await fetch(url, {
        method: 'DELETE',
        headers: headers(),
      });
      return handleResponse(resp);
    },
  };
})();
