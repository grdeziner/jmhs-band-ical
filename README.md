# JMHS Band Calendar (Auto-Updating iCal)

Scrapes the [JMHS Band calendar](https://jmhsband.org/index.php/calendar) and generates a subscribable `.ics` file, updated daily via GitHub Actions.

## Quick Setup

### 1. Create the GitHub Repo

1. Go to [github.com/new](https://github.com/new) and create a **public** repo (e.g., `jmhs-band-calendar`)
2. Clone it locally and copy these files into it:

```
jmhs-band-calendar/
âââ scrape_jmhs_band.py
âââ requirements.txt
âââ README.md
âââ .github/
    âââ workflows/
        âââ update-calendar.yml
```

3. Push to GitHub:

```bash
git add .
git commit -m "Initial setup"
git push origin main
```

### 2. Enable GitHub Pages

1. Go to your repo â **Settings** â **Pages**
2. Under **Source**, select **Deploy from a branch**
3. Set branch to `main` and folder to `/ (root)`
4. Click **Save**

The workflow will run automatically on the first push. After a minute or two, your `.ics` file will be live at:

```
https://YOUR_USERNAME.github.io/jmhs-band-calendar/jmhs_band_calendar.ics
```

### 3. Subscribe in Google Calendar

1. Open [Google Calendar](https://calendar.google.com)
2. Click the **+** next to "Other calendars" â **From URL**
3. Paste the GitHub Pages URL above
4. Click **Add calendar**

Google Calendar refreshes subscribed calendars roughly every 12â24 hours, so any changes the band makes to their calendar will show up the next day.

### 4. (Optional) Run Manually

You can trigger an update anytime from the GitHub repo:

1. Go to **Actions** â **Update JMHS Band Calendar**
2. Click **Run workflow**

Or run locally:

```bash
pip install -r requirements.txt
python scrape_jmhs_band.py
```

## Configuration

Edit the top of `scrape_jmhs_band.py` to adjust:

| Setting | Default | Description |
|---------|---------|-------------|
| `MONTHS_AHEAD` | 6 | How many months ahead to fetch |
| `MONTHS_BEHIND` | 1 | How many past months to include |
| `OUTPUT_FILE` | `jmhs_band_calendar.ics` | Output filename |
| `CALENDAR_NAME` | `JMHS Band` | Name shown in your calendar app |

## How It Works

1. The scraper hits the DPCalendar JSON API on jmhsband.org (the same API the website itself uses)
2. It fetches all events across all band sub-calendars (rehearsals, concerts, trips, color guard, etc.)
3. Events are converted to standard iCalendar (RFC 5545) format with proper timezone handling
4. GitHub Actions commits the updated `.ics` file daily
5. GitHub Pages serves it as a static file that any calendar app can subscribe to

Each event gets a stable UID based on its DPCalendar ID, so when the band updates an event's time or details, your calendar app will pick up the change on the next refresh.
