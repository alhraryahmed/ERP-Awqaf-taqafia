/* =========================
   TAQ IT - FORMS MODULE
========================= */

TAQ.registerModule("forms", {

  init() {
    console.log("Forms Module Loaded ✔");
    this.bindEvents();
  },

  bindEvents() {

    document.querySelectorAll(".form").forEach(form => {

      const inputs = form.querySelectorAll("input, select, textarea");

      inputs.forEach(input => {

        input.addEventListener("focus", () => {
          input.classList.add("focused");
        });

        input.addEventListener("blur", () => {
          input.classList.remove("focused");
        });

      });

    });

  }

});