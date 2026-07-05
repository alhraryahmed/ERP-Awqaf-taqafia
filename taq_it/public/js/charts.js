/* =========================
   TAQ IT - CHARTS MODULE
========================= */

TAQ.registerModule("charts", {

  init() {
    console.log("Charts Module Loaded ✔");
  },

  render(container, data) {

    if (!container) return;

    container.innerHTML = "";

    const canvas = document.createElement("div");

    canvas.style.height = "200px";
    canvas.style.display = "flex";
    canvas.style.alignItems = "center";
    canvas.style.justifyContent = "center";

    canvas.innerText = "📊 Chart Placeholder";

    container.appendChild(canvas);

  }

});