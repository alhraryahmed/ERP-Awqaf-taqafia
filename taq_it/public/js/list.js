/* =========================
   TAQ IT - LIST MODULE
========================= */

TAQ.registerModule("list", {

  init() {
    console.log("List Module Loaded ✔");
    this.initSearch();
  },

  initSearch() {

    document.querySelectorAll(".list-search input").forEach(input => {

      input.addEventListener("input", function () {

        const value = this.value.toLowerCase();
        const table = this.closest(".list-view")?.querySelector("table");

        if (!table) return;

        table.querySelectorAll("tbody tr").forEach(row => {

          const text = row.innerText.toLowerCase();

          row.style.display = text.includes(value) ? "" : "none";

        });

      });

    });

  }

});