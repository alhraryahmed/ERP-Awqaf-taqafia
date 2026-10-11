/* Shared runtime for Frappe v15 Custom HTML Blocks. Load this asset before block scripts. */
(function (window) {
  "use strict";
  if (window.GlobalBlock) return;

  var mountedRoots = typeof WeakSet !== "undefined" ? new WeakSet() : null;

  function mount(rootElement) {
    if (!rootElement) return Promise.resolve(null);
    var element = rootElement.nodeType === 1 ? rootElement : null;
    var tree = rootElement.nodeType === 11 ? rootElement : (element && element.getRootNode ? element.getRootNode() : null);
    var host = tree && tree.host ? tree.host : element;
    var direction = window.frappe && frappe.utils && frappe.utils.is_rtl && frappe.utils.is_rtl() ? "rtl" : "ltr";
    if (element && element.classList) element.classList.add("gb-root");
    if (host && host.classList) host.classList.add("gb-root");
    if (element && element.setAttribute) element.setAttribute("dir", direction);
    if (host && host.setAttribute) host.setAttribute("dir", direction);
    if (tree && mountedRoots && !mountedRoots.has(tree)) mountedRoots.add(tree);
    return Promise.resolve(rootElement);
  }

  function call(method, args, options) {
    if (!window.frappe || typeof frappe.call !== "function") return Promise.reject(new Error("Frappe API is unavailable"));
    return frappe.call(Object.assign({}, options || {}, { method: method, args: args || {} })).then(function (response) { return response && response.message !== undefined ? response.message : response; });
  }

  function formatNumber(value, options) {
    var number = Number(value);
    if (!Number.isFinite(number)) number = 0;
    return new Intl.NumberFormat((options && options.locale) || "en-US", options || {}).format(number);
  }

  function formatDate(value, format) {
    if (window.frappe && frappe.datetime && typeof frappe.datetime.str_to_user === "function") return frappe.datetime.str_to_user(value, format);
    return value || "";
  }

  function formatCurrency(value, currency, precision) {
    if (typeof window.format_currency === "function") return window.format_currency(value, currency, precision);
    if (window.frappe && typeof frappe.format === "function") return frappe.format(value, { fieldtype: "Currency", options: currency, precision: precision });
    return formatNumber(value, { maximumFractionDigits: precision == null ? 2 : precision });
  }

  function setState(root, selector, state, message) {
    var node = root && root.querySelector(selector);
    if (!node) return null;
    node.setAttribute("data-gb-state", state);
    if (message !== undefined) node.textContent = message;
    return node;
  }

  window.GlobalBlock = {
    mount: mount,
    call: call,
    formatNumber: formatNumber,
    formatDate: formatDate,
    formatCurrency: formatCurrency,
    setLoading: function (root, selector, message) { return setState(root, selector, "loading", message); },
    setEmpty: function (root, selector, message) { return setState(root, selector, "empty", message); },
    setError: function (root, selector, message) { return setState(root, selector, "error", message); },
    template: function (strings) { var values = Array.prototype.slice.call(arguments, 1); return strings.reduce(function (out, part, index) { return out + part + (values[index] == null ? "" : values[index]); }, ""); }
  };
})(window);
