// fetch + CSRF + anonymous voter key helpers
(function () {
  "use strict";

  function getCookie(name) {
    const match = document.cookie.match(new RegExp("(?:^|; )" + name + "=([^;]*)"));
    return match ? decodeURIComponent(match[1]) : "";
  }

  let memoryKey = null;
  function voterKey() {
    try {
      let key = localStorage.getItem("voter_key");
      if (!key) {
        key = crypto.randomUUID();
        localStorage.setItem("voter_key", key);
      }
      return key;
    } catch (e) {
      memoryKey = memoryKey || crypto.randomUUID();
      return memoryKey;
    }
  }

  async function request(method, path, body) {
    const headers = { Accept: "application/json" };
    if (body !== undefined) headers["Content-Type"] = "application/json";
    if (method !== "GET") headers["X-CSRFToken"] = getCookie("csrftoken");
    // anonymous voter key travels in a header (not the URL) so it stays out of logs and history
    else headers["X-Voter-Key"] = voterKey();
    try {
      const res = await fetch(path, {
        method,
        headers,
        credentials: "same-origin",
        body: body === undefined ? undefined : JSON.stringify(body),
      });
      let data = {};
      try { data = await res.json(); } catch (e) { /* non-JSON error page */ }
      return { ok: res.ok, status: res.status, data };
    } catch (e) {
      return { ok: false, status: 0, data: { errors: { __all__: ["Bağlantı hatası. İnternetini kontrol edip tekrar dene."] } } };
    }
  }

  window.api = {
    voterKey,
    get: (path) => request("GET", path),
    post: (path, body) => request("POST", path, body || {}),
  };
})();
