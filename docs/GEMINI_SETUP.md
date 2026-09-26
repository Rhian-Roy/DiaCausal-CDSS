# Switching on "Explain with Gemini" (free, about 5 minutes)

> Research prototype for clinician evaluation; not a marketed medical device; not for unsupervised clinical use.

Until this is done the website still works: the Evidence tab shows **quoted** explanations
(offline, cannot invent anything). The Gemini button only rewords those passages in plain English.

**Never paste the key into a chat, an email, GitHub or any file in this repository.** It goes in one
place only: Supabase's secret store.

## 1. Get a free Gemini API key (Google AI Studio)

1. Open https://aistudio.google.com and sign in with your Google account.
2. Click **Get API key** (left menu) → **Create API key** → choose or create a Google Cloud project
   (e.g. "diacausal"). Stay on the **free tier**: do not add billing.
3. Copy the key (it starts with `AIza…`). Keep the tab open.

The free tier has daily limits. If they are used up, the website says so and shows the quotes.
A Google AI Pro subscription is a different product: it does not raise these API limits and is not needed.

## 2. Store it in Supabase as a secret

1. Open https://supabase.com/dashboard → project **diacausal**.
2. Left menu **Edge Functions** → **Secrets** (or *Project Settings → Edge Functions*).
3. **Add new secret**: name `GEMINI_API_KEY`, value = the key → **Save**.
4. Optional: `GEMINI_MODEL` (default `gemini-flash-latest`) if Google renames its models.

No redeploy is needed; the function reads the secret on the next call.

## 3. Check it

Sign in on https://diacausal.netlify.app (password + authenticator code, approved account) →
**Evidence** → tap **SGLT2i and ketoacidosis** → **Explain in plain words with Gemini (online)**.
The heading changes to "Explanation (Gemini, checked against the passages below)". If a sentence
failed the check, you see the quotes with a note saying why — that is the safety net working.

## What is sent, and what is not

- Sent to Google: the question and the text of the passages (rebuilt on the server from their IDs).
- Never sent: patient details, the Try it form, your email or name.
- Only approved accounts with a verified authenticator can call the function
  (`supabase/functions/explain/index.ts`); nothing about the question is logged.

To switch it off: delete the `GEMINI_API_KEY` secret.
