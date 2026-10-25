(function () {
  var header = document.querySelector("header.site");
  var burger = document.getElementById("burger");
  function setMenu(open) {
    header.classList.toggle("open", open);
    burger.setAttribute("aria-expanded", open ? "true" : "false");
    burger.textContent = open ? "Close" : "Menu";
  }
  burger && burger.addEventListener("click", function () { setMenu(!header.classList.contains("open")); });
  document.addEventListener("keydown", function (e) { if (e.key === "Escape") setMenu(false); });
  document.querySelectorAll("#menu a").forEach(function (a) { a.addEventListener("click", function () { setMenu(false); }); });
  var theme = document.getElementById("theme");
  theme && theme.addEventListener("click", function () {
    var next = document.documentElement.getAttribute("data-theme") === "light" ? "dark" : "light";
    document.documentElement.setAttribute("data-theme", next);
    try { localStorage.setItem("theme", next); } catch (e) {}
  });
})();
