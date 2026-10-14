# Taste Radar

**Free stuff from the brands you'd actually like.** Built for the [Qloo Agentic Hackathon](https://qloo.devpost.com/).

Plenty of brands give away stickers, samples, fan packs and catalogs to anyone who asks, but you only hear about the
ones that freebie sites happen to list, and those lists are full of sweepstakes, sign-up traps and expired offers.
Taste Radar starts from you instead:

1. **Your taste (Qloo).** Name a few artists, shows, places or brands you love. Qloo's `/search` turns them into
   entities, and `/v2/insights` with `filter.type=urn:entity:brand` returns the brands people with that taste also like.
2. **The brand's own site (agent).** For each brand, the agent finds its official website and looks there, and only
   there, for a free-item page. When a page draws its form with JavaScript, it opens the page in a headless browser.
3. **Five guard questions (typed decision model).** Before showing an offer, a typed decision model (Jev) answers:
   is this a real free offer for the public? a sweepstakes? a political, religious or fundraising sign-up? members or
   businesses only? outside where you live? Anything doubtful is left out, with the reason shown.

Nothing is ever filled in or submitted for you. Each result links to the brand's own request page and says how to ask:
a form, a letter with a self-addressed envelope, or an email.

The guards come from a form-filling agent whose questions were tuned on 48 hand-labelled pages, with a held-out check
(see [field-notes demo 07](https://github.com/jalil-dini/field-notes/tree/main/07-self-harness-guards)).

## Run it

```bash
cp .env.example .env        # add QLOO_API_KEY and JEV_API_KEY
pip install ddgs            # web search; everything else is the standard library
npm install                 # playwright-core, for pages that build their form with JavaScript
python3 -m radar.server     # open http://127.0.0.1:8790
```

`QLOO_MOCK=1 python3 -m radar.server` runs the app on sample brand data without a Qloo key.
`python3 -m unittest discover tests` runs the offline tests.

## What it does not do

- It does not submit anything. You decide which offers to ask for.
- It does not cover sweepstakes or contests; those are left out on purpose.
- A brand with no free-item page on its own site shows "nothing free", even if a freebie site lists one.

## Licence

MIT
