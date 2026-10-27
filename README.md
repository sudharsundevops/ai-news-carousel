# AI News Carousel

Every morning this builds a "Yesterday in AI" Instagram carousel and sends it to your Telegram:
a cover, the top 10 stories, a closing slide (12 PNGs at 1080×1350), and a ready-to-paste caption.
You check it, download it, and schedule it in Instagram.

**Cost: ₹0.** GitHub Actions (free minutes) + RSS and Hacker News (free) + Gemini API free tier + Telegram bot (free).

How it works: `fetch_news.py` collects the last 30 hours of AI news → `curate.py` asks Gemini to pick and
summarize the top stories (links come from the feeds, never from the model) → `render.py` turns them into
slides with Playwright → `deliver.py` sends them to Telegram. `data/history.json` remembers used links for
7 days so stories don't repeat.

---

## 1. Put the project on your Desktop

Unzip `ai-news-carousel.zip` onto your Desktop, then open a terminal in that folder.

**Windows (PowerShell)**
```powershell
cd $HOME\Desktop\ai-news-carousel
```

**macOS / Linux**
```bash
cd ~/Desktop/ai-news-carousel
```

## 2. Use your personal GitHub account (not the work one)

Set your identity **for this repo only**, so your global work settings stay untouched:

```bash
git init -b main
git config user.name "Sudharsun"
git config user.email "sudharsunr2004@gmail.com"
git config user.email   # should print the gmail address
```

Make sure pushes authenticate as your personal account. The cleanest way is the GitHub CLI (`gh`):

```bash
gh auth login              # choose GitHub.com, sign in with the PERSONAL account in the browser
gh auth status             # lists accounts; the personal one should be "Active"
gh auth switch             # if the work account is still active, switch to the personal one
gh auth setup-git          # make git use gh's login for pushes
```

Then create the repo on your personal account and push:

```bash
git add .
git commit -m "Initial commit: daily AI carousel"
gh repo create ai-news-carousel --private --source . --push
```

Run `git log -1 --format=%ae` and confirm it shows the gmail address before pushing anything else.
Private is fine: a run takes a few minutes a day, well within the free monthly minutes for private repos.

## 3. Get the free keys

**Gemini API key:** sign in at https://aistudio.google.com with a personal Google account, click
*Get API key*, and create one. No card needed.

**Telegram bot:**
1. In Telegram, message **@BotFather**, send `/newbot`, and follow the steps. Copy the token.
2. Send any message (like "hi") to your new bot.
3. Open `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates` in a browser and copy the number at
   `"chat":{"id": ... }`. That's your chat ID.

## 4. Add them to GitHub

Repo → **Settings → Secrets and variables → Actions**

| Type | Name | Value |
|---|---|---|
| Secret | `GEMINI_API_KEY` | your Gemini key |
| Secret | `TELEGRAM_BOT_TOKEN` | the BotFather token |
| Secret | `TELEGRAM_CHAT_ID` | your chat ID |
| Variable | `IG_HANDLE` | your Instagram handle, like `@dailyai.brief` |
| Variable | `TOP_N` | `10` (optional) |

## 5. Test it

Repo → **Actions → Daily AI carousel → Run workflow**. In about 3 to 5 minutes the slides and caption
should arrive in Telegram. They're also saved as a downloadable artifact on the run page for 7 days.

After that it runs automatically every day at about 6:47 am IST. GitHub sometimes starts scheduled
jobs 10 to 30 minutes late.

---

## Run it on your laptop

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate     macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
python -m playwright install chromium

python main.py --sample          # renders sample slides, no keys needed
cp .env.example .env             # then fill in the keys
python main.py --no-send         # real run, files only in output/
python main.py                   # real run + Telegram
```

## Your daily routine (about 5 minutes)

1. Open Telegram and read every slide. **Check each fact against the source link in the caption.**
   Free models sometimes mix up names, numbers, or dates.
2. Download the 12 images and copy the caption.
3. In Instagram, create a post, select the images in order, paste the caption, and schedule it.

If a slide is wrong, fix `output/<date>/stories.json` locally and re-render it, or just drop that slide.

## Customizing

All settings are in `src/config.py`:
- `AUDIENCE`: who you're writing for. This changes which stories get picked and how they're explained.
- `FEEDS`: add or remove RSS sources. Broken feeds are skipped and logged, never fatal.
- `HN_MIN_POINTS`: raise it for fewer, bigger Hacker News stories.
- `GEMINI_MODEL`: if calls fail with "model not found," pick a current free model in AI Studio.

The slide design is `templates/slide.html` (plain HTML/CSS). Run `python main.py --sample` after changes
to preview.

## When something breaks

The bot messages you on Telegram if a run fails. Common causes:
- **Gemini 429 / quota:** the script retries and then tries a lighter model. If both fail, run it again
  later from the Actions tab.
- **"Only N candidate items":** feeds were quiet or failed. Check the log for `[rss] skipped` lines.
- **Workflow stopped running:** GitHub disables schedules in repos with no activity for 60 days. The daily
  history commit normally prevents this; if it happens, re-enable the workflow in the Actions tab.

## Notes

- On the free tier, Google may use prompts and responses to improve its models, and its terms may
  restrict commercial use. Before you monetize, check the current Gemini API terms and consider the
  paid tier.
- Slides use your own design and text only: no logos or news photos.
