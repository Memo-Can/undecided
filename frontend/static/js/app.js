(function () {
  "use strict";

  const GENERIC_ERROR = "Bir şeyler ters gitti. Lütfen tekrar dene.";

  // ---------- helpers ----------
  function el(tag, props, ...children) {
    const node = document.createElement(tag);
    for (const [key, value] of Object.entries(props || {})) {
      if (key === "class") node.className = value;
      else if (key === "text") node.textContent = value;
      else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
      else node.setAttribute(key, value);
    }
    for (const child of children) if (child) node.append(child);
    return node;
  }

  function firstError(data) {
    const errors = (data && data.errors) || {};
    const all = Object.values(errors).flat();
    return all.length ? all.join(" ") : GENERIC_ERROR;
  }

  function timeAgo(iso) {
    const seconds = (Date.now() - new Date(iso).getTime()) / 1000;
    if (seconds < 60) return "az önce";
    const minutes = Math.floor(seconds / 60);
    if (minutes < 60) return minutes + " dakika önce";
    const hours = Math.floor(minutes / 60);
    if (hours < 24) return hours + " saat önce";
    const days = Math.floor(hours / 24);
    if (days < 30) return days + " gün önce";
    return new Date(iso).toLocaleDateString("tr-TR");
  }

  // only same-site paths, to avoid open redirects
  function safeNext() {
    const next = new URLSearchParams(location.search).get("next") || "";
    return next.startsWith("/") && !next.startsWith("//") ? next : "/";
  }

  let mePromise = null;
  function getMe() {
    if (!mePromise) mePromise = api.get("/api/auth/me/").then((r) => (r.ok ? r.data.user : null));
    return mePromise;
  }

  // ---------- header ----------
  async function initHeader() {
    const nav = document.getElementById("nav");
    const user = await getMe();
    nav.replaceChildren();
    if (user) {
      nav.append(
        el("a", { class: "btn btn-small btn-primary", href: "/yeni/", text: "+ Anket" }),
        el("span", { class: "nav-user", text: "@" + user.username }),
        el("button", {
          class: "btn btn-small btn-ghost",
          type: "button",
          text: "Çıkış",
          onclick: async () => {
            await api.post("/api/auth/logout/");
            location.href = "/";
          },
        })
      );
    } else {
      const next = encodeURIComponent(location.pathname + location.search);
      nav.append(
        el("a", { class: "btn btn-small btn-ghost", href: "/giris/?next=" + next, text: "Giriş" }),
        el("a", { class: "btn btn-small btn-primary", href: "/kayit/?next=" + next, text: "Kayıt ol" })
      );
    }
  }

  // ---------- poll card ----------
  function buildPoll(poll, asLink) {
    const card = el("article", { class: "card poll" });
    fillPoll(card, poll, asLink, false);
    return card;
  }

  function fillPoll(card, poll, asLink, animate) {
    const title = asLink
      ? el("a", { href: "/anket/" + poll.id + "/", text: poll.question })
      : document.createTextNode(poll.question);
    const hasVoted = poll.my_vote !== null && poll.my_vote !== undefined;
    const body = el("div", { class: hasVoted ? "results" : "choices" });
    const message = el("p", { class: "error", role: "alert" });
    const fills = [];

    poll.options.forEach((option, index) => {
      const color = "c" + (index % 5);
      if (!hasVoted) {
        body.append(
          el("button", {
            class: "choice " + color,
            type: "button",
            text: option.text,
            onclick: (event) => vote(card, poll, option.id, asLink, message, event.currentTarget),
          })
        );
        return;
      }
      const percent = poll.total_votes ? Math.round((option.votes * 100) / poll.total_votes) : 0;
      const mine = option.id === poll.my_vote;
      const fill = el("div", { class: "bar-fill " + color });
      fill.style.width = animate ? "0%" : percent + "%";
      fills.push([fill, percent]);
      body.append(
        el("div", { class: "result" + (mine ? " mine" : "") },
          el("div", { class: "result-head" },
            el("span", { class: "result-text", text: (mine ? "✓ " : "") + option.text }),
            el("span", { class: "result-pct", text: "%" + percent + " · " + option.votes })
          ),
          el("div", { class: "bar" }, fill)
        )
      );
    });

    card.replaceChildren(
      el("h2", { class: "poll-question" }, title),
      el("p", { class: "meta" },
        el("span", { class: "author", text: "@" + poll.author }),
        el("span", { text: timeAgo(poll.created_at) }),
        el("span", { text: poll.total_votes + " oy" })
      ),
      body,
      message
    );

    if (animate) {
      requestAnimationFrame(() =>
        requestAnimationFrame(() => fills.forEach(([fill, percent]) => (fill.style.width = percent + "%")))
      );
    }
  }

  async function vote(card, poll, optionId, asLink, message, button) {
    card.querySelectorAll(".choice").forEach((b) => (b.disabled = true));
    message.textContent = "";
    const res = await api.post("/api/polls/" + poll.id + "/vote/", {
      option_id: optionId,
      voter_key: api.voterKey(),
    });
    if (res.ok) return fillPoll(card, res.data, asLink, true);
    if (res.status === 409) {
      // already voted (e.g. in another tab): just show the results
      const fresh = await api.get(api.withKey("/api/polls/" + poll.id + "/"));
      if (fresh.ok) return fillPoll(card, fresh.data, asLink, true);
    }
    message.textContent = firstError(res.data);
    card.querySelectorAll(".choice").forEach((b) => (b.disabled = false));
  }

  // ---------- pages ----------
  function initHome() {
    const feed = document.getElementById("feed");
    const more = document.getElementById("more");
    const empty = document.getElementById("empty");
    const error = document.getElementById("feed-error");
    let page = 0;

    async function loadNext() {
      more.disabled = true;
      error.textContent = "";
      const res = await api.get(api.withKey("/api/polls/?page=" + (page + 1)));
      more.disabled = false;
      if (!res.ok) {
        error.textContent = firstError(res.data);
        return;
      }
      page = res.data.page;
      res.data.results.forEach((poll) => feed.append(buildPoll(poll, true)));
      more.hidden = !res.data.has_next;
      empty.hidden = feed.children.length > 0;
    }

    more.addEventListener("click", loadNext);
    loadNext();
  }

  async function initPoll() {
    const id = document.body.dataset.pollId;
    const holder = document.getElementById("poll");
    const res = await api.get(api.withKey("/api/polls/" + id + "/"));
    if (!res.ok) {
      document.getElementById("poll-error").textContent =
        res.status === 404 ? "Bu anket bulunamadı." : firstError(res.data);
      return;
    }
    holder.append(buildPoll(res.data, false));
    document.title = res.data.question + " · kararsızım";
  }

  function clearErrors(form) {
    form.querySelectorAll("[data-error]").forEach((p) => (p.textContent = ""));
  }

  function showErrors(form, errors) {
    for (const [key, messages] of Object.entries(errors)) {
      const target = form.querySelector('[data-error="' + key + '"]') || form.querySelector('[data-error="__all__"]');
      target.textContent = [target.textContent, messages.join(" ")].filter(Boolean).join(" ");
    }
  }

  function bindForm(form, url, getBody, onSuccess) {
    form.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearErrors(form);
      const submit = form.querySelector('[type="submit"]');
      submit.disabled = true;
      const res = await api.post(url, getBody());
      if (res.ok) return onSuccess(res.data);
      submit.disabled = false;
      showErrors(form, res.data.errors || { __all__: [GENERIC_ERROR] });
    });
  }

  function value(form, name) {
    return form.elements[name].value;
  }

  function initLogin() {
    const form = document.getElementById("login-form");
    document.getElementById("register-link").href = "/kayit/" + location.search;
    bindForm(form, "/api/auth/login/",
      () => ({ email: value(form, "email"), password: value(form, "password") }),
      () => (location.href = safeNext()));
  }

  function initRegister() {
    const form = document.getElementById("register-form");
    document.getElementById("login-link").href = "/giris/" + location.search;
    bindForm(form, "/api/auth/register/",
      () => ({ email: value(form, "email"), username: value(form, "username"), password: value(form, "password") }),
      () => (location.href = safeNext()));
  }

  async function initNew() {
    if (!(await getMe())) {
      location.replace("/giris/?next=" + encodeURIComponent("/yeni/"));
      return;
    }
    const form = document.getElementById("new-form");
    const list = document.getElementById("options");
    const add = document.getElementById("add-option");
    const MIN = 2, MAX = 5;

    function refresh() {
      const rows = list.querySelectorAll(".option-row");
      rows.forEach((row, i) => {
        row.querySelector("input").setAttribute("aria-label", "Seçenek " + (i + 1));
        row.querySelector("button").hidden = rows.length <= MIN;
      });
      add.disabled = rows.length >= MAX;
    }

    function addRow() {
      const row = el("div", { class: "option-row" },
        el("input", { type: "text", maxlength: "100", placeholder: "Seçenek" }),
        el("button", {
          class: "icon-btn",
          type: "button",
          "aria-label": "Seçeneği sil",
          text: "✕",
          onclick: () => { row.remove(); refresh(); },
        })
      );
      list.append(row);
      refresh();
    }

    for (let i = 0; i < MIN; i++) addRow();
    add.addEventListener("click", () => { addRow(); list.lastChild.querySelector("input").focus(); });

    bindForm(form, "/api/polls/",
      () => ({
        question: value(form, "question"),
        options: [...list.querySelectorAll("input")].map((i) => i.value.trim()).filter(Boolean),
      }),
      (poll) => (location.href = "/anket/" + poll.id + "/"));
  }

  // ---------- start ----------
  const pages = { home: initHome, poll: initPoll, new: initNew, login: initLogin, register: initRegister };
  initHeader();
  const start = pages[document.body.dataset.page];
  if (start) start();
})();
