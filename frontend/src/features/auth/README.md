# auth — login page (not built yet)

**What goes here:** `LoginPage.tsx`, built from `design/login.html`
(`design/login-desktop.png`): user ID, password, 6-digit code, CAPTCHA with "New image"
and "Play audio", and the intended-use notice.

**How it will connect:** `src/App.tsx` shows `<LoginPage />` until the backend says the
clinician is signed in (see `backend/app/auth/README.md`), then `<ChatPage />`. The top
bar (`src/components/chat/TopBar.tsx`) then shows the clinician's name and "Sign out".

**Rules:** the browser never stores the password or code; the session lives in an
`HttpOnly` cookie the page cannot read.
