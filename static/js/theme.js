(function () {
  var t = null;
  try { t = localStorage.getItem("theme"); } catch (e) {}
  if (!t) t = window.matchMedia && matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", t);
})();
