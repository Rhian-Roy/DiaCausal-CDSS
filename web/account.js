/*
 * DiaCausal website — account screens, drawn as design/screens-v2: sign in (01), details not
 * matched (02), locked (03), authenticator set-up (06), intended use (07); plus sign up, forgot
 * password, waiting for approval, account and the admin's approval list in the same style.
 * The logic is in auth.js; this file only draws the screens (with h() and icon() from app.js).
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use.
 */
"use strict";

window.DiaCausalAccount = (function () {
  const A = () => window.DiaCausalAuth;
  const WANTED = { try: "Patient Details", evidence: "Investigate" };
  let flash = null; // "mismatch" (screen 02) or "locked" (screen 03), shown on the next sign-in screen
  let busy = false; // a sign-in is in progress: do not redraw half-way through it

  const lede = (text) => h("p", { class: "lede" }, text);
  const head = (title, intro, step) => h("div", { class: "stack" }, step ? h("p", { class: "stepnote" }, step) : null, h("h1", {}, title), intro ? lede(intro) : null);

  function input(id, label, attrs, hint) {
    const hintId = hint ? `${id}-hint` : null;
    return h("div", { class: "field" }, h("label", { class: "field__label", for: id }, label),
      hint ? h("span", { class: "field__hint", id: hintId }, hint) : null,
      h("input", { class: "input", id, name: id, "aria-describedby": hintId, ...attrs }));
  }

  function alertBox(kind, word, text) {
    return h("div", { class: `alert alert--${kind}`, role: "alert" }, icon(kind === "danger" ? "stop" : "lock", 24, kind === "danger" ? "c-danger" : "c-check"),
      h("div", { class: "stack" }, h("span", { class: "alert__word" }, word), h("p", {}, text)));
  }

  /** A form whose submit runs `action`; shows friendly errors and disables the button meanwhile. */
  function form(nodes, button, action) {
    const err = h("div", { hidden: true });
    const btn = h("button", { type: "submit", class: "btn btn--primary" }, button);
    const f = h("form", { class: "col", novalidate: true }, ...nodes, err, h("div", { class: "row" }, btn));
    f.addEventListener("submit", async (e) => {
      e.preventDefault();
      err.hidden = true;
      btn.disabled = true;
      try {
        await action(f.elements, err);
      } catch (x) {
        err.replaceChildren(alertBox("danger", "Please check", x.message));
        err.hidden = false;
      } finally {
        btn.disabled = false;
      }
    });
    return f;
  }

  const ghostLink = (href, text) => h("a", { class: "btn btn--ghost", href }, text);
  const signOutButton = () => {
    const b = h("button", { type: "button", class: "btn btn--ghost" }, "Sign out");
    b.addEventListener("click", () => AUTH.signOut());
    return b;
  };

  // ── 01 / 02: one form — email, password and the 6-digit code ──
  function signIn(wanted) {
    const reason = AUTH.state.signedOutReason;
    const mismatch = flash === "mismatch";
    const bad = mismatch ? { "aria-invalid": "true" } : {};
    const fields = [
      input("email", "Email", { type: "email", autocomplete: "username", inputmode: "email", placeholder: "name@hospital.example", required: true, ...bad }),
      input("password", "Password", { type: "password", autocomplete: "current-password", required: true, ...bad }),
      input("otp", "6-digit code", { type: "text", inputmode: "numeric", pattern: "[0-9]{6}", maxlength: "6", autocomplete: "one-time-code",
        placeholder: "000000", class: "input input--otp", ...bad },
        "From your authenticator app. It changes every 30 seconds. The first time, leave it empty: you set up the app next."),
    ];
    const f = form([
      head("Sign in", wanted ? `Sign in to use ${WANTED[wanted]}. Compares three second-line options for adults with type 2 diabetes already taking metformin.`
        : "Compares three second-line options for adults with type 2 diabetes already taking metformin."),
      reason ? alertBox("check", "Signed out", reason) : null,
      mismatch ? alertBox("danger", "Those details did not match", "Check your email, password and the current 6-digit code, then try again.") : null,
      ...fields,
    ].filter(Boolean), "Sign in", async (el) => {
      const email = el.email.value.trim();
      const password = el.password.value;
      const code = el.otp.value.trim();
      if (!email || !password) throw new Error("Enter your email and password.");
      AUTH.state.signedOutReason = null;
      flash = null;
      busy = true;
      try {
        await AUTH.signIn({ email, password });
        if (AUTH.state.verifiedFactors) {
          if (!/^[0-9]{6}$/.test(code)) throw Object.assign(new Error("code"), { kind: "other" });
          await AUTH.verifyMfa(code);
        }
        flash = null;
      } catch (x) {
        flash = x.kind === "rate_limit" ? "locked" : "mismatch";
        if (AUTH.state.session) await AUTH.signOut(); // never leave a half-signed-in session behind
      } finally {
        busy = false;
        drawn = "";
        await AUTH.refresh();
      }
    });
    return [f, h("div", { class: "row" }, ghostLink("#forgot", "Trouble signing in?"), ghostLink("#signup", "First time? Request an account"))];
  }

  // ── 03: locked after too many attempts (Supabase's rate limit) ──
  function locked() {
    const back = h("button", { type: "button", class: "btn btn--ghost" }, "Back to sign in");
    back.addEventListener("click", () => { flash = null; drawn = ""; render("signin", "account"); });
    return [h("div", { class: "col" }, h("div", {}, h("h1", {}, "Sign in")),
      alertBox("check", "Signing in is locked", "Too many attempts. Try again in a few minutes or ask your administrator."),
      h("div", { class: "card card--flat" }, h("h3", {}, "What to do now"), h("ul", { class: "list" },
        h("li", {}, icon("clock", 22, "c-muted"), h("span", {}, "Wait a few minutes and sign in again. The lock clears on its own.")),
        h("li", {}, icon("info", 22, "c-muted"), h("span", {}, "If you need access sooner, ask the team's admin.")))),
      h("div", { class: "row" }, h("button", { class: "btn btn--primary", type: "button", disabled: true }, "Sign in"), back))];
  }

  function signUp() {
    const roles = A().ROLES.map((r) => h("option", { value: r }, r[0].toUpperCase() + r.slice(1)));
    return [form([
      head("Request an account", "Anyone can ask. You will set up an authenticator app, then the team's admin approves your account."),
      input("fullName", "Full name", { type: "text", autocomplete: "name", required: true, maxlength: "120" }),
      input("email", "Email", { type: "email", autocomplete: "email", required: true, inputmode: "email" }),
      input("password", "Password", { type: "password", autocomplete: "new-password", required: true, minlength: String(A().MIN_PASSWORD) },
        `At least ${A().MIN_PASSWORD} characters. A short sentence works well.`),
      h("div", { class: "field" }, h("label", { class: "field__label", for: "role" }, "I am a"), h("select", { class: "select", id: "role", name: "role", required: true }, roles)),
      h("div", { class: "checkrow" }, h("input", { type: "checkbox", id: "agree", name: "agree", required: true }),
        h("label", { for: "agree" }, "I understand DiaCausal is a research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.")),
    ], "Create account", async (el) => {
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
        $("#account-main").replaceChildren(h("div", { class: "col" }, head("Check your email", `We sent a link to ${email}. Open it on this device to finish creating your account.`)));
      }
    }), h("div", { class: "row" }, ghostLink("#account", "I already have an account"))];
  }

  function forgot() {
    return [form([head("Trouble signing in?", "We will email you a link to choose a new password. For a lost authenticator app, ask the team's admin."),
      input("email", "Email", { type: "email", autocomplete: "email", required: true, inputmode: "email" })],
    "Send the link", async (el, err) => {
      await AUTH.sendReset(el.email.value.trim());
      err.replaceChildren(alertBox("check", "Sent", "If an account uses that email, a link is on its way. If nothing arrives, ask the team's admin."));
      err.hidden = false;
    }), h("div", { class: "row" }, ghostLink("#account", "Back to sign in"))];
  }

  function newPassword() {
    return [form([head("Choose a new password"),
      input("password", "New password", { type: "password", autocomplete: "new-password", required: true }, `At least ${A().MIN_PASSWORD} characters.`)],
    "Save password", async (el) => {
      const pw = A().passwordProblems(el.password.value, AUTH.state.session && AUTH.state.session.user.email);
      if (pw.length) throw new Error("Password: " + pw.join(", "));
      await AUTH.setNewPassword(el.password.value);
    })];
  }

  // ── 06: first-time authenticator set-up ──
  function mfaSetup() {
    const qr = h("div", { class: "qr" }, "Loading…");
    const key = h("div", { class: "key" });
    const copy = h("button", { class: "btn btn--ghost", type: "button", disabled: true }, icon("copy", 18), " Copy key");
    let factorId = null;
    let secret = "";
    AUTH.startMfa().then((m) => {
      factorId = m.factorId;
      secret = m.secret;
      qr.replaceWith(h("img", { class: "qrimg", src: m.qr, alt: "QR code for your authenticator app", width: "220", height: "220" }));
      key.replaceChildren(...m.secret.match(/.{1,4}/g).map((part) => h("span", {}, part)));
      copy.disabled = false;
    }, (x) => { qr.textContent = x.message; });
    copy.addEventListener("click", async () => {
      try { await navigator.clipboard.writeText(secret); copy.replaceChildren(icon("check", 18), " Copied"); } catch { /* the key stays on screen */ }
    });
    const confirm = form([
      h("h3", {}, "What to do on your phone"),
      h("ol", { class: "steps" },
        h("li", {}, "Install ", h("strong", {}, "Google Authenticator"), " or ", h("strong", {}, "Microsoft Authenticator"), " from your phone's app store."),
        h("li", {}, "Open the app and choose ", h("strong", {}, "Add account"), ", then ", h("strong", {}, "Scan a QR code"), "."),
        h("li", {}, "Point your camera at the code on this page."),
        h("li", {}, "The app shows a 6-digit number that changes every 30 seconds.")),
      input("confirm", "Enter the 6-digit code to confirm", { type: "text", inputmode: "numeric", pattern: "[0-9]{6}", maxlength: "6",
        autocomplete: "one-time-code", placeholder: "000000", class: "input input--otp", required: true }),
    ], "Confirm and finish setup", async (el) => {
      if (!/^[0-9]{6}$/.test(el.confirm.value.trim())) throw new Error("Type the 6 digits your app shows.");
      await AUTH.verifyMfa(el.confirm.value, factorId);
    });
    return [h("div", { class: "col" },
      head("Set up your authenticator app", "You do this once. After today you sign in with your email, password and a 6-digit code.", "First-time setup"),
      h("div", { class: "twocol" },
        h("div", { class: "card card--flat" }, h("h3", {}, "1. Scan this code"), qr, h("h3", {}, "Cannot scan? Enter this key by hand"), key,
          h("div", { class: "row" }, copy), h("p", { class: "field__hint" }, "Keep this key private. Anyone with it can generate your codes.")),
        h("div", { class: "card card--flat" }, confirm))),
    h("div", { class: "row" }, signOutButton())];
  }

  /** A saved session that still needs today's code (e.g. the page was reloaded half-way). */
  function mfaCode() {
    return [form([head("Enter your 6-digit code", "Open your authenticator app and type the current code for DiaCausal."),
      input("code", "6-digit code", { type: "text", inputmode: "numeric", pattern: "[0-9]{6}", maxlength: "6", autocomplete: "one-time-code",
        placeholder: "000000", class: "input input--otp", required: true })],
    "Continue", async (el) => AUTH.verifyMfa(el.code.value)), h("div", { class: "row" }, signOutButton())];
  }

  function status(title, text, more = []) {
    const again = h("button", { type: "button", class: "btn btn--ghost" }, "Check again");
    again.addEventListener("click", () => AUTH.refresh());
    return [h("div", { class: "col" }, head(title, text), ...more), h("div", { class: "row" }, again, signOutButton())];
  }

  // ── 07: intended use, acknowledged once ──
  function acknowledge() {
    const ok = (text) => h("li", {}, icon("check", 22, "c-safe"), h("span", {}, text));
    const no = (text) => h("li", {}, icon("cross", 22, "c-danger"), h("span", {}, text));
    return [form([
      head("How to use DiaCausal", "Read this once, and again each time the tool is updated.", "Before you start"),
      h("div", { class: "card card--flat" }, h("h2", {}, "What DiaCausal does"), h("ul", { class: "list" },
        ok("Compares three second-line options — SGLT2 inhibitor, DPP-4 inhibitor and sulfonylurea — for an adult with type 2 diabetes already on metformin."),
        ok("Removes unsafe options with cited rules before estimating anything."),
        ok("Shows every estimate with a 95% interval, never a bare number."),
        ok("Cites the source, version and section behind every clinical statement."),
        ok("Says “insufficient evidence” and stops when it cannot support an answer."))),
      h("div", { class: "card card--flat" }, h("h2", {}, "What DiaCausal does not do"), h("ul", { class: "list" },
        no("It does not tell you which option to add. You decide."),
        no("It does not show doses, prescribe or place orders."),
        no("It does not cover type 1 diabetes, pregnancy, under-18s or starting insulin."),
        no("It does not accept patient identifiers. Do not type names, Aadhaar, phone, PAN or email."),
        no("It is not a marketed medical device, and its numbers come from synthetic data."))),
      h("div", { class: "checkrow" }, h("input", { id: "ack", name: "ack", type: "checkbox", required: true }), h("label", { for: "ack" }, "I understand")),
    ], "Continue", async (el) => {
      if (!el.ack.checked) throw new Error("Please tick “I understand” first.");
      await AUTH.acknowledge();
    })];
  }

  function account() {
    const p = AUTH.state.profile || {};
    const rows = [["Name", p.full_name], ["Email", p.email], ["Role", p.role],
      ["Status", p.approved ? "Approved" : p.rejected ? "Not approved" : "Waiting for approval"],
      ["Authenticator app", AUTH.state.verifiedFactors ? "On" : "Not set up"]];
    return [h("div", { class: "col" }, head("Your account"),
      h("div", { class: "card card--flat" }, h("table", {}, h("tbody", {}, rows.map(([k, v]) => h("tr", {}, h("th", {}, k), h("td", {}, v || "—"))))),
        h("p", { class: "field__hint" }, "DiaCausal stores only these details. Patient details and questions never leave this device."))),
    h("div", { class: "row" }, p.is_admin ? ghostLink("#admin", "Approve accounts (admin)") : null, signOutButton())];
  }

  function admin() {
    const list = h("div", { class: "card card--flat" }, h("p", { class: "field__hint" }, "Loading…"));
    const draw = async () => {
      try {
        const people = await AUTH.listAccounts();
        const pending = people.filter((x) => !x.approved && !x.rejected);
        const decided = people.filter((x) => x.approved || x.rejected);
        const row = (x) => {
          const yes = h("button", { type: "button", class: "btn btn--primary" }, "Approve");
          const no = h("button", { type: "button", class: "btn btn--ghost" }, x.rejected ? "Keep rejected" : x.approved ? "Remove access" : "Reject");
          const decide = (ok) => AUTH.decide(x.id, ok).then(draw, (e) => list.prepend(alertBox("danger", "Could not save", e.message)));
          yes.addEventListener("click", () => decide(true));
          no.addEventListener("click", () => decide(false));
          return h("div", { class: "acctrow" },
            h("p", {}, h("strong", {}, x.full_name), ` · ${x.role}`, h("br"), h("span", { class: "field__hint" }, `${x.email} · asked ${x.created_at.slice(0, 10)}`)),
            x.id === AUTH.state.session.user.id ? h("span", { class: "field__hint" }, "You")
              : h("div", { class: "row" }, x.approved ? null : yes, x.rejected ? null : no));
        };
        list.replaceChildren(
          h("h2", {}, `Waiting for approval (${pending.length})`),
          pending.length ? h("div", {}, pending.map(row)) : h("p", { class: "field__hint" }, "Nobody is waiting."),
          h("h2", {}, "Already decided"), h("div", {}, decided.map(row)));
      } catch (x) {
        list.replaceChildren(alertBox("danger", "Could not load the list", x.message));
      }
    };
    draw();
    return [h("div", { class: "col" }, head("Approve accounts"), list), h("div", { class: "row" }, ghostLink("#account", "Back to your account"))];
  }

  function demo() {
    return [h("div", { class: "col" }, head("Sign-in is off on this copy",
      "This copy of the website has no account service configured (no config.json), so every page is open. The public website asks people to sign in and be approved first."),
    h("div", { class: "row" }, h("a", { class: "btn btn--ghost", href: "https://diacausal.netlify.app/#account", rel: "noopener" }, "Open the public website")))];
  }

  let drawn = ""; // what is on screen now, so a background refresh never wipes a half-filled form

  /** Draw the screen for this gate state and page (only when it changed). */
  function render(gate, page) {
    if (busy) return;
    const view = $("#account-main");
    const p = AUTH && AUTH.state.profile;
    const key = [gate, page, flash, AUTH && Boolean(AUTH.state.session), p && [p.full_name, p.approved, p.rejected, p.is_admin].join()].join("|");
    if (key === drawn && view.childNodes.length) return;
    drawn = key;
    view.classList.toggle("authmain--wide", gate === "mfa-setup");
    let nodes;
    if (gate === "demo") nodes = demo();
    else if (!AUTH.state.session && page === "signup") nodes = signUp();
    else if (!AUTH.state.session && page === "forgot") nodes = forgot();
    else if (gate === "signin") nodes = flash === "locked" ? locked() : signIn(WANTED[page] ? page : null);
    else if (gate === "new-password") nodes = newPassword();
    else if (gate === "mfa-setup") nodes = mfaSetup();
    else if (gate === "mfa-code") nodes = mfaCode();
    else if (gate === "loading") nodes = [h("p", { class: "field__hint" }, "Loading your account…")];
    else if (gate === "error") nodes = status("Could not load your account", AUTH.state.profileError);
    else if (gate === "rejected") nodes = status("Not approved", "The team's admin did not approve this account. Ask them if you think this is a mistake.");
    else if (gate === "pending") {
      nodes = status("Waiting for approval",
        `Thanks, ${p.full_name}. The team's admin must approve your account before Patient Details and Investigate open. ` +
        "You can close this page; sign in again later.",
        [h("p", { class: "field__hint" }, `${p.email} · ${p.role}`)]);
    } else if (gate === "acknowledge") nodes = acknowledge();
    else if (page === "admin" && p && p.is_admin) nodes = admin();
    else nodes = account();
    view.replaceChildren(...nodes.filter(Boolean));
    const first = view.querySelector("input:not([type=checkbox])");
    if (first && window.matchMedia("(min-width: 901px)").matches) first.focus();
  }

  return { render };
})();
