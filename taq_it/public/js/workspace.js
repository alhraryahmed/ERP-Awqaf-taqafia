/* ==========================================================
   TAQ IT - Workspace Module
   workspace.js
   Compatible with Frappe / ERPNext v15
========================================================== */

TAQ.registerModule("workspace", (function () {

    let currentWorkspace = null;

    /* ==========================================
       PUBLIC
    ========================================== */

    function init() {

        console.log("Workspace Module Loaded ✔");

        bindEvents();

        detectWorkspace();

    }

    /* ==========================================
       EVENTS
    ========================================== */

    function bindEvents() {

        TAQ.events.on("route:change", function () {

            detectWorkspace();

        });

    }

    /* ==========================================
       DETECT ACTIVE WORKSPACE
    ========================================== */

    function detectWorkspace() {

        if (!window.frappe)
            return;

        currentWorkspace = frappe.get_route();

        render();

    }

    /* ==========================================
       MAIN RENDER
    ========================================== */

    function render() {

        enhanceWorkspace();

        initCards();

        initWidgets();

        initStatistics();

    }

    /* ==========================================
       ENHANCE EXISTING ERP WORKSPACE
    ========================================== */

    function enhanceWorkspace() {

        const page = document.querySelector(".layout-main-section");

        if (!page)
            return;

        page.classList.add("taq-workspace");

    }

    /* ==========================================
       DASHBOARD CARDS
    ========================================== */

    function initCards() {

        document.querySelectorAll(".card").forEach(card => {

            card.classList.add("hover-lift");

        });

    }

    /* ==========================================
       WIDGETS
    ========================================== */

    function initWidgets() {

        document.querySelectorAll(".widget").forEach(widget => {

            widget.classList.add("fade-in");

        });

    }

    /* ==========================================
       STATISTICS
    ========================================== */

    function initStatistics() {

        document.querySelectorAll(".card-stat-value").forEach(item => {

            animateNumber(item);

        });

    }

    /* ==========================================
       NUMBER ANIMATION
    ========================================== */

    function animateNumber(element) {

        const value = parseInt(element.innerText);

        if (isNaN(value))
            return;

        let current = 0;

        const increment = Math.max(1, Math.ceil(value / 40));

        const timer = setInterval(() => {

            current += increment;

            if (current >= value) {

                current = value;

                clearInterval(timer);

            }

            element.innerText = current.toLocaleString();

        }, 20);

    }

    /* ==========================================
       PUBLIC API
    ========================================== */

    return {

        init,

        render,

        refresh() {

            render();

        }

    };
    function enhanceWorkspace() {

    const page = document.querySelector(".layout-main-section");

    if (!page) return;

    page.classList.add("taq-workspace");

    // Inject hero if exists
    if (window.frappe && frappe.get_route_str) {

        console.log("TAQ Workspace Enhancing ERP Page ✔");

    }
}

})());