/**
 * auth.js — утилиты аутентификации для Vanilla JS фронтенда.
 * Используется во всех защищённых страницах.
 */

/**
 * Проверяет наличие токена, загружает текущего пользователя.
 * Если не авторизован — редиректит на /auth/login.
 * @returns {Promise<object>} объект пользователя
 */
async function requireAuth() {
  const token = localStorage.getItem('token');
  if (!token) {
    window.location.href = '/auth/login';
    return;
  }
  try {
    const user = await api.get('/auth/me');
    renderNavbar(user);
    return user;
  } catch (e) {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    window.location.href = '/auth/login';
  }
}

function renderNavbar(user) {
  const usernameEl = document.getElementById('nav-username');
  const roleEl = document.getElementById('nav-role');
  const logoutBtn = document.getElementById('btn-logout');

  if (usernameEl) usernameEl.textContent = user.username;
  if (roleEl) {
    const ROLE_LABELS = { manager: 'Менеджер', developer: 'Разработчик', observer: 'Наблюдатель' };
    roleEl.textContent = ROLE_LABELS[user.role] || user.role;
    roleEl.className = `nav-role badge badge--role-${user.role}`;
  }
  if (logoutBtn) {
    logoutBtn.style.display = 'inline-flex';
    logoutBtn.addEventListener('click', async () => {
      await api.post('/auth/logout', {}).catch(() => {});
      localStorage.removeItem('token');
      localStorage.removeItem('user');
      window.location.href = '/auth/login';
    });
  }
}
