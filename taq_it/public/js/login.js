/* =========================
   TAQ IT - LOGIN MODULE
========================= */

TAQ.registerModule("login", {

  init() {
    console.log("Login Module Loaded ✔");
    this.bindEvents();
  },

  bindEvents() {

    const form = document.querySelector(".login-form");

    if (!form) return;

    form.addEventListener("submit", function (e) {
      e.preventDefault();

      const btn = form.querySelector("button");

      if (btn) {
        btn.innerText = "جاري الدخول...";
        btn.disabled = true;
      }

      setTimeout(() => {

        alert("Login simulation ✔");

        btn.innerText = "دخول";
        btn.disabled = false;

      }, 1000);

    });

  }

});