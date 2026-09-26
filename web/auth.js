/*
 * DiaCausal website accounts: who may use "Try it" and "Evidence".
 *
 * Research prototype for clinician evaluation; not a marketed medical device;
 * not for unsupervised clinical use.
 *
 * Anyone may sign up. Each person then (1) sets up an authenticator app (MFA), (2) waits for an
 * admin to approve the account, and (3) confirms the intended-use statement. Accounts live in
 * Supabase (supabase/migrations/). Only names, emails, roles and approval dates are stored there:
 * patient details, questions and results never leave this device.
 *
 * gateView() is a pure function (tested in Node by tests/web); createController() talks to
 * Supabase in the browser. Without web/config.js (a local copy or the tests) sign-in is off
 * and the page says so.
 */
(function (root, factory) {
  if (typeof module === "object" && module.exports) module.exports = factory();
  else root.DiaCausalAuth = factory();
})(typeof self !== "undefined" ? self : this, function () {
  "use strict";

  const PROTECTED = ["try", "evidence"];
  const IDLE_MS = 15 * 60 * 1000; // same idle limit as the chat app (backend/app/settings.py)
  const MIN_PASSWORD = 12; // NIST SP 800-63B / the chat app's rule (app/auth/passwords.py)
  const MAX_PASSWORD = 72;
  const ROLES = ["clinician", "student", "examiner"];

  /** Which screen a person sees before the app. Order: sign in → MFA → approval → intended use. */
  function gateView(s) {
    if (!s.configured) return "demo";
    if (s.recovery) return "new-password";
    if (!s.session) return "signin";
    if (!s.verifiedFactors) return "mfa-setup";
    if (s.aal !== "aal2") return "mfa-code";
    if (!s.profile) return s.profileError ? "error" : "loading";
    if (s.profile.rejected) return "rejected";
    if (!s.profile.approved) return "pending";
    if (!s.profile.intended_use_ack_at) return "acknowledge";
    return "app";
  }

  // The chat app's list of passwords that are refused (backend/app/auth/passwords.py).
  const COMMON = `123456789012 password1234 passwordpassword qwertyuiop12 111111111111 123123123123
    iloveyou1234 adminadmin12 welcome12345 letmein12345 abc123456789 1q2w3e4r5t6y qwerty123456
    password@123 password#123 doctor123456 hospital1234 diabetes1234 metformin123 000000000000
    changeme1234 administrator p@ssw0rd1234 india1234567 sunshine1234 football1234`.split(/\s+/);

  function passwordProblems(password, email) {
    const p = [];
    const lower = password.toLowerCase();
    const name = (email || "").split("@")[0].toLowerCase();
    if (password.length < MIN_PASSWORD) p.push(`at least ${MIN_PASSWORD} characters (a short sentence works well)`);
    if (password.length > MAX_PASSWORD) p.push(`at most ${MAX_PASSWORD} characters`);
    if (name.length >= 4 && lower.includes(name)) p.push("must not contain your email name");
    if (COMMON.includes(lower) || /^(.)\1+$/.test(password) || lower.includes("diacausal")) p.push("too easy to guess");
    return p;
  }

  /** Friendly wording for Supabase errors (never shows passwords or codes). */
  function friendly(error) {
    const m = String((error && (error.message || error.msg)) || error || "");
    if (/invalid login credentials/i.test(m)) return "Those details did not match. Check your email and password.";
    if (/email not confirmed/i.test(m)) return "Please confirm your email first (check your inbox), or ask the admin.";
    if (/already registered|already exists/i.test(m)) return "An account with this email already exists. Try signing in.";
    if (/invalid.*(totp|code)|expired/i.test(m)) return "That code did not work. Enter the current 6-digit code from your authenticator app.";
    if (/rate limit|too many/i.test(m)) return "Too many tries. Please wait a few minutes and try again.";
    if (/failed to fetch|network/i.test(m)) return "No internet connection. Please try again when you are online.";
    return m || "Something went wrong. Please try again.";
  }

  /** Browser only: the Supabase side. `lib` is window.supabase, `config` is window.DIACAUSAL_CONFIG. */
  function createController(lib, config, storage) {
    const client = lib.createClient(config.supabaseUrl, config.supabaseKey, {
      auth: { persistSession: true, autoRefreshToken: true, detectSessionInUrl: true, flowType: "implicit", storageKey: "diacausal-auth" },
    });
    const state = { configured: true, session: null, verifiedFactors: 0, aal: null, profile: null, profileError: null, recovery: false };
    const listeners = new Set();
    let lastActive = Date.now();

    const cacheKey = (uid) => `diacausal.profile.${uid}`;
    const readCache = (uid) => { try { return JSON.parse(storage.getItem(cacheKey(uid))); } catch { return null; } };
    const writeCache = (uid, p) => { try { storage.setItem(cacheKey(uid), JSON.stringify(p)); } catch { /* private mode */ } };

    function emit() { for (const f of listeners) f(api.view(), state); }

    async function refresh() {
      const { data } = await client.auth.getSession();
      state.session = data.session;
      if (!state.session) {
        Object.assign(state, { verifiedFactors: 0, aal: null, profile: null, profileError: null });
        return emit();
      }
      const user = state.session.user;
      let factors = (user.factors || []).filter((f) => f.factor_type === "totp" && f.status === "verified");
      try {
        const listed = await client.auth.mfa.listFactors();
        if (!listed.error) factors = listed.data.totp.filter((f) => f.status === "verified");
      } catch { /* offline: use the factors in the saved session */ }
      state.verifiedFactors = factors.length;
      state.factorId = factors.length ? factors[0].id : null;
      const aal = await client.auth.mfa.getAuthenticatorAssuranceLevel();
      state.aal = aal.data ? aal.data.currentLevel : null;
      try {
        const res = await client.from("profiles").select("full_name,email,role,approved,rejected,is_admin,intended_use_ack_at,created_at").eq("id", user.id).single();
        if (res.error) throw res.error;
        state.profile = res.data;
        state.profileError = null;
        writeCache(user.id, res.data);
      } catch (e) {
        state.profile = readCache(user.id); // offline: the last status this device saw
        state.profileError = state.profile ? null : friendly(e);
      }
      emit();
    }

    const api = {
      client,
      state,
      view: () => gateView(state),
      onChange(f) { listeners.add(f); return () => listeners.delete(f); },
      refresh,
      async signUp({ fullName, email, password, role }) {
        const { data, error } = await client.auth.signUp({
          email, password,
          options: { data: { full_name: fullName, role }, emailRedirectTo: location.origin + location.pathname },
        });
        if (error) throw new Error(friendly(error));
        await refresh();
        return { needsEmailConfirmation: !data.session };
      },
      async signIn({ email, password }) {
        const { error } = await client.auth.signInWithPassword({ email, password });
        if (error) throw new Error(friendly(error));
        lastActive = Date.now();
        await refresh();
      },
      async signOut(reason) {
        await client.auth.signOut({ scope: "local" });
        state.recovery = false;
        state.signedOutReason = reason || null;
        await refresh();
      },
      async sendReset(email) {
        const { error } = await client.auth.resetPasswordForEmail(email, { redirectTo: location.origin + location.pathname });
        if (error) throw new Error(friendly(error));
      },
      async setNewPassword(password) {
        const { error } = await client.auth.updateUser({ password });
        if (error) throw new Error(friendly(error));
        state.recovery = false;
        await refresh();
      },
      /** Start authenticator setup: returns the QR code (SVG data URL) and the key to type by hand. */
      async startMfa() {
        const listed = await client.auth.mfa.listFactors();
        for (const f of (listed.data && listed.data.all) || []) {
          if (f.status !== "verified") await client.auth.mfa.unenroll({ factorId: f.id });
        }
        const { data, error } = await client.auth.mfa.enroll({ factorType: "totp", friendlyName: `DiaCausal ${new Date().toISOString().slice(0, 10)}` });
        if (error) throw new Error(friendly(error));
        return { factorId: data.id, qr: data.totp.qr_code, secret: data.totp.secret };
      },
      async verifyMfa(code, factorId) {
        const { error } = await client.auth.mfa.challengeAndVerify({ factorId: factorId || state.factorId, code: code.trim() });
        if (error) throw new Error(friendly(error));
        lastActive = Date.now();
        await refresh();
      },
      async acknowledge() {
        const { error } = await client.rpc("acknowledge_intended_use");
        if (error) throw new Error(friendly(error));
        await refresh();
      },
      async listAccounts() {
        const { data, error } = await client.from("profiles").select("id,full_name,email,role,approved,rejected,created_at,approved_at").order("created_at", { ascending: false });
        if (error) throw new Error(friendly(error));
        return data;
      },
      async decide(id, approve) {
        const { error } = await client.rpc("approve_user", { target: id, approve });
        if (error) throw new Error(friendly(error));
      },
      touch() { lastActive = Date.now(); },
      idleCheck() {
        if (state.session && Date.now() - lastActive > IDLE_MS) api.signOut("You were signed out after 15 minutes without activity.");
      },
    };

    client.auth.onAuthStateChange((event) => {
      if (event === "PASSWORD_RECOVERY") state.recovery = true;
      // Never call Supabase inside this callback (it can deadlock); refresh on the next tick.
      setTimeout(refresh, 0);
    });
    return api;
  }

  return { gateView, passwordProblems, friendly, createController, PROTECTED, IDLE_MS, MIN_PASSWORD, ROLES };
});
