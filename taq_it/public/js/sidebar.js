/* =========================
   TAQ IT - SIDEBAR MODULE
   sidebar.js
   Navigation Controller
   ========================= */


/* =========================
   REGISTER MODULE
========================= */

TAQ.registerModule("sidebar", {
  
  items: [],

  init() {
    console.log("Sidebar Module Loaded ✔");

    this.cacheDOM();
    this.bindEvents();
    this.initState();
  },

  /* =========================
     CACHE DOM ELEMENTS
  ========================= */

  cacheDOM() {
    this.sidebar = document.querySelector(".sidebar");
    this.toggleBtn = document.querySelector(".sidebar-toggle");
    this.navItems = document.querySelectorAll(".nav-item");
  },

  /* =========================
     INITIAL STATE
  ========================= */

  initState() {
    this.setActiveFromRoute();

    TAQ.events.on("route:change", (page) => {
      this.setActive(page);
    });
  },

  /* =========================
     EVENT BINDING
  ========================= */

  bindEvents() {
    if (this.toggleBtn) {
      this.toggleBtn.addEventListener("click", () => {
        TAQ.toggleSidebar();
      });
    }

    this.navItems.forEach(item => {
      item.addEventListener("click", (e) => {
        const page = item.getAttribute("data-page");

        if (page) {
          TAQ.navigate(page);
        }
      });
    });
  },

  /* =========================
     SET ACTIVE ITEM
  ========================= */

  setActive(page) {
    this.navItems.forEach(item => {
      item.classList.remove("active");

      if (item.getAttribute("data-page") === page) {
        item.classList.add("active");
      }
    });
  },

  /* =========================
     AUTO DETECT ACTIVE PAGE
  ========================= */

  setActiveFromRoute() {
    const current = TAQ.state.currentPage;

    if (current) {
      this.setActive(current);
    }
  }
});