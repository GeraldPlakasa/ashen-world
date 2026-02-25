/**
 * Ashen World - Light Mode Only
 * Theme system simplified - no toggle needed
 */

(function() {
  'use strict';

  // Force light mode on page load
  function init() {
    document.documentElement.removeAttribute('data-theme');
    localStorage.removeItem('aw-theme');
  }

  // Run on DOMContentLoaded
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }
})();
