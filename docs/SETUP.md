# Setting up "Train Times" on your Echo — step by step

You don't need to write any code. The code is already in this repo. Your job is to
click through Amazon's website once so Alexa knows about it. Budget about 20 minutes.

Words you'll see on Amazon's site:
- **Skill** = an app for Alexa. Ours is called "Train Times".
- **Developer console** = the website where skills are created. It's free.
- **Alexa-hosted** = Amazon runs our code on their computers for free.

---

## Part 1 — Sign in to the developer console (5 min)

1. Open https://developer.amazon.com/alexa/console/ask in a browser on your computer.
2. Sign in with **the same Amazon account your Echo is signed into**. This matters:
   a skill only shows up on Echos that use the account that created it.
   (Not sure which account? Open the Alexa app on your phone → More → Settings →
   scroll to the bottom; it shows the signed-in email.)
3. The first time, Amazon asks you to fill in a short developer profile
   (name, address, whether you'll accept payments → choose No). Finish it.

## Part 2 — Create the skill by importing this repo (5 min)

1. On the console's home page click **Create Skill**.
2. **Skill name:** `Train Times`. **Primary locale:** English (US). Click **Next**.
3. **Choose a type of experience:** pick **Other**. **Choose a model:** **Custom**.
   **Hosting services:** **Alexa-hosted (Python)**. Click **Next**.
4. **Templates:** click **Import skill** (top right). Paste this address:

       https://github.com/AdminJBI/mta-alexa

   Click **Import**, then **Create Skill**.
5. Wait. The page shows a progress bar for 2–4 minutes while Amazon copies the code
   and installs the pieces it needs. Don't close the tab.
6. When it finishes you're on the **Build** page. At the top right click
   **Save Model**, then **Build Model**. Wait for the green "Build Successful" banner.

## Part 3 — Try it in the browser (2 min)

1. Click the **Test** tab at the top.
2. In the dropdown that says "Off", choose **Development**.
3. In the text box type `open franklin board` and press Enter. Alexa should answer
   with the next trains. Try `ask franklin board when's the A train at nostrand`.
4. If it answers, you're done with the hard part. Your Echo already has the skill.

## Part 4 — Say it to the Echo

The skill's spoken name is **"franklin board"**. Two earlier names failed in
testing (2026-10-26): Alexa's built-in transit feature grabs "train times", and its
radio feature grabs anything with "station" in it, before a private skill is heard.


- "Alexa, open franklin board"
- "Alexa, ask franklin board when's the C train at Franklin"
- "Alexa, ask franklin board when's the A train at Nostrand"
- "Alexa, ask franklin board for the C train toward Euclid at Franklin"

Add it to a routine (Alexa app → More → Routines) so it reads out automatically
after your morning alarm or when you say "good morning".

---

## Changing how it behaves

Everything you'd want to tweak is in one small file: `lambda/config.py`.
- which station pair (`CORRIDOR`)
- Manhattan-bound only, Brooklyn-bound only, or both (`DEFAULT_DIRECTION`)
- which stations the opening summary covers and in what order
- how many trains to read out

Tell Claude what to change. The change is pushed here and then applied to the
skill in one of two ways:
- **Easy:** Code tab in the console → open `config.py` → paste the new file →
  **Deploy**. Takes 30 seconds.
- **Automatic:** once the ASK command-line tool is installed on the Mac and linked
  to your account (a one-time browser sign-in), Claude can push changes straight to
  the skill without you doing anything.

## If something goes wrong

- **"Import failed"** → the repo must be public and the address must be exact.
- **Build fails** → click the error; usually a typo in the voice model. Tell Claude
  what it says.
- **Alexa says "something went wrong reading the train times"** → the MTA feed was
  slow or down for a moment. Try again in a minute. If it keeps happening, the
  console's **Code** tab → **Logs** shows why; copy that to Claude.
- **The Echo says "I don't know that one"** → the Echo is on a different Amazon
  account than the console, or the Test dropdown is still "Off".
