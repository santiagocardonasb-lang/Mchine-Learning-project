// The saved theme is applied by the inline script in base.html <head> before paint.
(function () {
  const root = document.documentElement;
  const toggle = document.getElementById('theme-toggle');

  function syncIcon() {
    toggle.querySelector('i').className = root.classList.contains('dark') ? 'bi bi-sun' : 'bi bi-moon';
  }

  toggle.addEventListener('click', function () {
    const dark = root.classList.toggle('dark');
    try {
      localStorage.setItem('theme', dark ? 'dark' : 'light');
    } catch (e) {
      // Storage can be blocked (private mode); the toggle still works for this page.
    }
    syncIcon();
    // Maps listen to this to swap tiles and line colors.
    document.dispatchEvent(new CustomEvent('themechange', {detail: {dark: dark}}));
  });
  syncIcon();

  const nav = document.querySelector('.nav');
  const menuButton = document.getElementById('menu-toggle');
  menuButton.addEventListener('click', function () {
    const open = nav.classList.toggle('open');
    menuButton.setAttribute('aria-expanded', String(open));
  });
})();
