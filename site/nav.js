(function () {
  function closeAll() {
    document.querySelectorAll(".nav .dropdown.open").forEach(function (dd) {
      dd.classList.remove("open");
      dd.querySelector(".dropdown-toggle").setAttribute("aria-expanded", "false");
    });
  }
  document.querySelectorAll(".nav .dropdown").forEach(function (dd) {
    var btn = dd.querySelector(".dropdown-toggle");
    btn.addEventListener("click", function (e) {
      e.stopPropagation();
      var willOpen = !dd.classList.contains("open");
      closeAll();
      if (willOpen) {
        dd.classList.add("open");
        btn.setAttribute("aria-expanded", "true");
      }
    });
  });
  document.addEventListener("click", closeAll);
  document.addEventListener("keydown", function (e) {
    if (e.key === "Escape") closeAll();
  });
})();
