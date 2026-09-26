/*
 * DiaCausal website — account screens: sign in, sign up, forgot password, authenticator app
 * (MFA), waiting for approval, intended use, account, and the admin's approval list.
 * The logic is in auth.js; this file only draws the screens (with h() from app.js).
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use.
 */
"use strict";

window.DiaCausalAccount = (function () {
  const A = () => window.DiaCausalAuth;
  const WANTED = { try: "Try it", evidence: "Evidence" };

  function field(label, attrs, hint) {
    return h("label", {}, label, h("input", attrs), hint ? h("span", { class: "hint" }, hint) : null);
  }

  /** A form whose submit runs `action`; shows friendly errors and disables the button meanwhile. */
  function form(title, intro, fields, button, action, extra = []) {
    const err = h("p", { class: "errors", role: "alert", hidden: true });
    const btn = h("button", { type: "submit", class: "primary" }, button);
    const f = h("form", { class: "card form auth", novalidate: true }, h("h2", {}, title),
      intro ? h("p", { class: "sub" }, intro) : null, ...fields, err, btn, ...extra);
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      btn.disabled = true;
      try {
        await action(f.elements, err);
      } catch (x) {
        err.textContent = x.message;
        err.hidden = false;
      } finally {
        btn.disabled = false;
      }
    });
    return f;
  }

  const links = (...items) => h("p", { class: "auth__links" }, ...items.flatMap((x, i) => (i ? [" · ", x] : [x])));
  const signOutButton = () => {
    const b = h("button", { type: "button", class: "chip" }, "Sign out");
    b.addEventListener("click", () => AUTH.signOut());
    return b;
  };

  function signIn(wanted) {
    const reason = AUTH.state.signedOutReason;
    return [
      reason ? h("p", { class: "notice" }, reason) : null,
      form(wanted ? `Sign in to use ${WANTED[wanted]}` : "Sign in",
        "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.",
        [field("Email", { name: "email", type: "email", autocomplete: "username", required: true, inputmode: "email" }),
          field("Password", { name: "password", type: "password", autocomplete: "current-password", required: true })],
        "Sign in",
        async (el) => {
          AUTH.state.signedOutReason = null;
          await AUTH.signIn({ email: el.email.value.trim(), password: el.password.value });
        },
        [links(h("a", { href: "#signup" }, "Create an account"), h("a", { href: "#forgot" }, "Forgot password?"))]),
    ];
  }

  function signUp() {
    const roles = A().ROLES.map((r) => h("option", { value: r }, r[0].toUpperCase() + r.slice(1)));
    return [form("Create an account",
      "Anyone can ask. You will set up an authenticator app, then the team's admin approves your account.",
      [field("Full name", { name: "fullName", type: "text", autocomplete: "name", required: true, maxlength: "120" }),
        field("Email", { name: "email", type: "email", autocomplete: "email", required: true, inputmode: "email" }),
        field("Password", { name: "password", type: "password", autocomplete: "new-password", required: true, minlength: String(A().MIN_PASSWORD) },
          `At least ${A().MIN_PASSWORD} characters. A short sentence works well.`),
        h("label", {}, "I am a", h("select", { name: "role", required: true }, roles)),
        h("label", { class: "tick" }, h("input", { type: "checkbox", name: "agree", required: true }),
          "I understand DiaCausal is a research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.")],
      "Create account",
      async (el) => {
        const email = el.email.value.trim();
        const problems = [];
        if (!el.fullName.value.trim()) problems.push("full name: required");
        if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) problems.push("email: not a valid address");
        const pw = A().passwordProblems(el.password.value, email);
        if (pw.length) problems.push("password: " + pw.join(", "));
        if (!el.agree.checked) problems.push("please tick the intended-use statement");
        if (problems.length) throw new Error("Please check: " + problems.join("; "));
        const r = await AUTH.signUp({ fullName: el.fullName.value.trim(), email, password: el.password.value, role: el.role.value });
        if (r.needsEmailConfirmation) {
          $("#view-account").replaceChildren(h("div", { class: "card" }, h("h2", {}, "Check your email"),
            h("p", {}, `We sent a link to ${email}. Open it on this device to finish creating your account.`)));
        }
      },
      [links(h("a", { href: "#account" }, "I already have an account"))])];
  }

  function forgot() {
    return [form("Forgot password", "We will email you a link to choose a new password.",
      [field("Email", { name: "email", type: "email", autocomplete: "email", required: true, inputmode: "email" })],
      "Send the link",
      async (el, err) => {
        await AUTH.sendReset(el.email.value.trim());
        err.className = "notice"; err.hidden = false;
        err.textContent = "If an account uses that email, a link is on its way. If nothing arrives, ask the team's admin.";
      },
      [links(h("a", { href: "#account" }, "Back to sign in"))])];
  }

  function newPassword() {
    return [form("Choose a new password", null,
      [field("New password", { name: "password", type: "password", autocomplete: "new-password", required: true },
        `At least ${A().MIN_PASSWORD} characters.`)],
      "Save password",
      async (el) => {
        const pw = A().passwordProblems(el.password.value, AUTH.state.session && AUTH.state.session.user.email);
        if (pw.length) throw new Error("Password: " + pw.join(", "));
        await AUTH.setNewPassword(el.password.value);
      })];
  }

  function mfaSetup() {
    const box = h("div", {});
    const start = h("button", { type: "button", class: "primary" }, "Show my QR code");
    const err = h("p", { class: "errors", role: "alert", hidden: true });
    start.addEventListener("click", async () => {
      start.disabled = true;
      try {
        const m = await AUTH.startMfa();
        box.replaceChildren(
          h("img", { class: "qrcode", src: m.qr, alt: "QR code for your authenticator app", width: "200", height: "200" }),
          h("p", { class: "sub" }, "Can't scan? Type this key into the app instead:"),
          h("p", { class: "key" }, m.secret.match(/.{1,4}/g).join(" ")),
          form("Enter the 6-digit code", "Type the code your app shows for DiaCausal.",
            [field("Code", { name: "code", type: "text", inputmode: "numeric", autocomplete: "one-time-code", pattern: "[0-9]{6}", maxlength: "6", required: true })],
            "Turn on the authenticator", async (el) => AUTH.verifyMfa(el.code.value, m.factorId)));
      } catch (x) {
        err.textContent = x.message; err.hidden = false; start.disabled = false;
      }
    });
    return [h("div", { class: "card" }, h("h2", {}, "Set up your authenticator app"),
      h("p", {}, "Every sign-in needs your password and a 6-digit code from an app such as Google Authenticator or Microsoft Authenticator."),
      h("ol", {}, h("li", {}, "Install the app on your phone."), h("li", {}, "Tap the button below, then scan the QR code with the app."),
        h("li", {}, "Type the 6-digit code it shows.")),
      start, err, box), links(signOutButton())];
  }

  function mfaCode() {
    return [form("Enter your 6-digit code", "Open your authenticator app and type the current code for DiaCausal.",
      [field("Code", { name: "code", type: "text", inputmode: "numeric", autocomplete: "one-time-code", pattern: "[0-9]{6}", maxlength: "6", required: true })],
      "Continue", async (el) => AUTH.verifyMfa(el.code.value), [links(signOutButton())])];
  }

  function status(title, text, more = []) {
    const again = h("button", { type: "button", class: "chip" }, "Check again");
    again.addEventListener("click", () => AUTH.refresh());
    return [h("div", { class: "card" }, h("h2", {}, title), h("p", {}, text), ...more), links(again, signOutButton())];
  }

  function acknowledge() {
    return [form("Before you start", null,
      [h("blockquote", {}, "Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use."),
        h("ul", {}, h("li", {}, "Decision support only: the clinician decides."),
          h("li", {}, "Every number comes from a synthetic India-calibrated cohort, not real patients."),
          h("li", {}, "DiaCausal never shows drug doses.")),
        h("label", { class: "tick" }, h("input", { type: "checkbox", name: "ok", required: true }), "I have read and understood this.")],
      "I understand", async (el) => {
        if (!el.ok.checked) throw new Error("Please tick the box first.");
        await AUTH.acknowledge();
      })];
  }

  function account() {
    const p = AUTH.state.profile || {};
    const rows = [["Name", p.full_name], ["Email", p.email], ["Role", p.role],
      ["Status", p.approved ? "Approved" : p.rejected ? "Not approved" : "Waiting for approval"],
      ["Authenticator app", AUTH.state.verifiedFactors ? "On" : "Not set up"]];
    return [h("div", { class: "card" }, h("h2", {}, "Your account"),
      h("table", {}, h("tbody", {}, rows.map(([k, v]) => h("tr", {}, h("th", {}, k), h("td", {}, v || "—"))))),
      h("p", { class: "sub" }, "DiaCausal stores only these details. Patient details and questions never leave this device.")),
    links(p.is_admin ? h("a", { href: "#admin" }, "Approve accounts (admin)") : null, signOutButton())].filter(Boolean);
  }

  function admin() {
    const list = h("div", {}, h("p", { class: "sub" }, "Loading…"));
    const draw = async () => {
      try {
        const people = await AUTH.listAccounts();
        const pending = people.filter((x) => !x.approved && !x.rejected);
        const decided = people.filter((x) => x.approved || x.rejected);
        const row = (x) => {
          const yes = h("button", { type: "button", class: "chip chip--yes" }, "Approve");
          const no = h("button", { type: "button", class: "chip" }, x.rejected ? "Keep rejected" : x.approved ? "Remove access" : "Reject");
          const decide = (ok) => AUTH.decide(x.id, ok).then(draw, (e) => list.prepend(h("p", { class: "errors" }, e.message)));
          yes.addEventListener("click", () => decide(true));
          no.addEventListener("click", () => decide(false));
          return h("div", { class: "person" },
            h("p", {}, h("strong", {}, x.full_name), ` · ${x.role}`, h("br"), h("span", { class: "sub" }, `${x.email} · asked ${x.created_at.slice(0, 10)}`)),
            x.id === AUTH.state.session.user.id ? h("span", { class: "sub" }, "You")
              : h("div", { class: "actions" }, x.approved ? null : yes, x.rejected ? null : no));
        };
        list.replaceChildren(
          h("h2", {}, `Waiting for approval (${pending.length})`),
          pending.length ? h("div", {}, pending.map(row)) : h("p", { class: "sub" }, "Nobody is waiting."),
          h("h2", {}, "Already decided"), h("div", {}, decided.map(row)));
      } catch (x) {
        list.replaceChildren(h("p", { class: "errors" }, x.message));
      }
    };
    draw();
    return [h("div", { class: "card" }, list), links(h("a", { href: "#account" }, "Back to your account"))];
  }

  function demo() {
    return [h("div", { class: "card" }, h("h2", {}, "Sign-in is off on this copy"),
      h("p", {}, "This copy of the website has no account service configured (no config.json), so every page is open. " +
        "The public website asks people to sign in and be approved first."),
      h("p", {}, h("a", { href: "https://diacausal.netlify.app/#account", rel: "noopener" }, "Open the public website")))];
  }

  let drawn = ""; // what is on screen now, so a background refresh never wipes a half-filled form

  /** Draw the screen for this gate state and page (only when it changed). */
  function render(gate, page) {
    const view = $("#view-account");
    const p = AUTH && AUTH.state.profile;
    const key = [gate, page, AUTH && Boolean(AUTH.state.session), p && [p.full_name, p.approved, p.rejected, p.is_admin].join()].join("|");
    if (key === drawn && view.childNodes.length) return;
    drawn = key;
    let nodes;
    if (gate === "demo") nodes = demo();
    else if (!AUTH.state.session && page === "signup") nodes = signUp();
    else if (!AUTH.state.session && page === "forgot") nodes = forgot();
    else if (gate === "signin") nodes = signIn(WANTED[page] ? page : null);
    else if (gate === "new-password") nodes = newPassword();
    else if (gate === "mfa-setup") nodes = mfaSetup();
    else if (gate === "mfa-code") nodes = mfaCode();
    else if (gate === "loading") nodes = [h("p", { class: "sub" }, "Loading your account…")];
    else if (gate === "error") nodes = status("Could not load your account", AUTH.state.profileError);
    else if (gate === "rejected") nodes = status("Not approved", "The team's admin did not approve this account. Ask them if you think this is a mistake.");
    else if (gate === "pending") {
      const p = AUTH.state.profile;
      nodes = status("Waiting for approval",
        `Thanks, ${p.full_name}. The team's admin must approve your account before Try it and Evidence open. ` +
        "You can close this page; sign in again later.",
        [h("p", { class: "sub" }, `${p.email} · ${p.role}`)]);
    } else if (gate === "acknowledge") nodes = acknowledge();
    else if (page === "admin" && AUTH.state.profile && AUTH.state.profile.is_admin) nodes = admin();
    else nodes = account();
    view.replaceChildren(h("h1", {}, "Your DiaCausal account"), ...nodes.filter(Boolean));
    const first = view.querySelector("input:not([type=checkbox])");
    if (first && window.matchMedia("(min-width: 761px)").matches) first.focus();
  }

  return { render };
})();
