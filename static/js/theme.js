/**
 * Ashen World Theme Switcher
 * Handles dark/light mode toggle with localStorage persistence
 */

(function() {
  'use strict';

  // Get saved theme or default to dark
  function getSavedTheme() {
    return localStorage.getItem('aw-theme') || 'dark';
  }

  // Save theme preference
  function saveTheme(theme) {
    localStorage.setItem('aw-theme', theme);
  }

  // Apply theme to document
  function applyTheme(theme) {
    document.documentElement.setAttribute('data-theme', theme);
    
    // Update toggle buttons
    document.querySelectorAll('.theme-toggle').forEach(toggle => {
      const icon = toggle.querySelector('.theme-toggle-icon');
      const label = toggle.querySelector('.theme-toggle-label');
      
      if (icon) {
        icon.textContent = theme === 'dark' ? '🌙' : '☀️';
      }
      if (label) {
        label.textContent = theme === 'dark' ? 'Dark' : 'Light';
      }
    });
  }

  // Toggle theme
  function toggleTheme() {
    const currentTheme = getSavedTheme();
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
    saveTheme(newTheme);
    applyTheme(newTheme);
  }

  // Initialize on page load
  function init() {
    // Apply saved theme immediately
    applyTheme(getSavedTheme());

    // Attach click handlers to all theme toggles
    document.querySelectorAll('.theme-toggle').forEach(toggle => {
      toggle.addEventListener('click', toggleTheme);
    });
  }

  // Run on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose for external use
  window.AWTheme = {
    toggle: toggleTheme,
    get: getSavedTheme,
    set: function(theme) {
      saveTheme(theme);
      applyTheme(theme);
    }
  };
})();
