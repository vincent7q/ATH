# Project Overview — In Plain English

*A non-technical guide to what this project does and why. No coding or math knowledge needed.*

---

## What is this project?

We're building a tool that tests a **stock-trading strategy** against **years of real past
market data** — before we ever risk real money.

Think of it like a flight simulator for trading. Instead of buying stocks for real and hoping
for the best, we replay the last five years of the market, apply our buying-and-selling rules
exactly as written, and see what *would* have happened. That tells us whether the strategy is
worth trusting — and lets us improve it safely.

This kind of historical replay has a name in finance: **backtesting**.

---

## The core idea, in one paragraph

The strategy follows a simple, time-tested principle: **buy strength, cut losses quickly, and
protect your winners.** We buy stocks that are climbing to new highs (a sign of momentum), we
set a safety net to limit the damage if a trade goes wrong, and we use a second, smarter net
that rises along with the price to lock in profit as a winner keeps climbing. It's the trading
version of *"let your winners run, but never let a small loss become a big one."*

---

## How we decide to BUY

A stock has to pass **two tests on the same day** before we buy it:

1. **It hits a new high.** Specifically, its price reaches the highest level it's been in the
   past year (52 weeks). A stock making new highs is showing strength — that's the momentum
   we want to ride. *(For brand-new companies that haven't been listed for a full year yet,
   we use a shorter history so they can still qualify.)*

2. **It's actively traded.** We only buy stocks where a healthy amount of money changes hands
   each day. This matters for a practical reason: if a stock barely trades, we couldn't reliably
   buy or sell it without moving the price against ourselves. This is called a **liquidity filter**.

If both are true, we buy.

---

## How we decide to SELL

This is where the strategy protects us. Once we own a stock, **three safety nets** watch over the
trade. We sell the moment the price drops to whichever net is currently highest.

1. **The hard floor (stop-loss).** The instant we buy, we draw a line a few percent below our
   purchase price. If the stock falls to that line, we sell — accepting a small, controlled loss.
   This is the rule that stops a bad trade from becoming a disaster.

2. **The break-even lock.** If the stock rises far enough above our purchase price, we slide that
   floor *up* to just above what we paid. From that point on, the trade can no longer turn into a
   loss — worst case, we walk away with a small gain. We've "locked in" being safe.

3. **The trailing net.** As a winner keeps climbing, a third net follows underneath it, rising as
   the stock's peak rises (but never falling back down). How far below the price it sits depends on
   how jumpy that particular stock is — calmer stocks get a tighter net, wilder stocks get more
   room. When the stock finally turns and falls to this net, we sell and bank the profit.

The key point: **these nets only ever move up, never down.** That's how we ride a winner higher
while making sure we never give back more than necessary.

---

## The new "cool-down" rule (the freeze)

We recently added one more rule. **After a trade loses money, we sit that stock out for a set
number of days** before we're allowed to buy it again.

Why? Sometimes a stock keeps bouncing up and down, repeatedly tripping our buy signal and then
stopping us out for small losses — a frustrating, money-leaking pattern called "whipsaw." The
cool-down (we call it the **freeze**) forces us to step back and let things settle instead of
jumping right back in. How long the freeze lasts is a setting we can dial up or down (and we can
turn it off entirely).

---

## A worked example

Let's follow one stock, "XYZ," to see all the rules working together. (Numbers are just for
illustration.)

- **Day 1 — Buy.** XYZ climbs to a new one-year high at **\$100**, and it's heavily traded. Both
  tests pass, so we buy at \$100. Right away we set our hard floor at **\$95** (5% below). If it
  drops there, we're out for a small loss.
- **It rises to \$106.** Now we're up enough to trigger the **break-even lock** — we slide the
  floor up to **\$101**. The trade is now safe: even if XYZ reverses, we keep a small gain.
- **It keeps climbing to \$120.** The **trailing net** has been rising underneath the whole way,
  now sitting around, say, **\$113**. The break-even floor (\$101) is still there too, but we
  always use the higher of the two — so \$113 is the line that matters.
- **It turns and falls to \$113 — Sell.** We exit at \$113, banking a solid gain on a stock we
  bought at \$100.

**The other outcome:** if XYZ had instead dropped to \$95 early on, we'd have sold for a small
loss — and then the **freeze** would keep us from re-buying XYZ for the next several days.

---

## How we judge whether the strategy is any good

After replaying five years of history, the tool reports a scorecard. The main numbers:

- **Total profit** — how much money the strategy made (or lost) overall.
- **Win rate** — out of all trades, what percentage were winners.
- **Profit factor** — total winnings divided by total losses. Above 1 means we made more than we
  lost; the higher, the better.
- **Worst drop (drawdown)** — the most painful peak-to-bottom decline along the way. This measures
  how much stomach-churning we'd have had to endure. A strategy can be profitable but still have a
  scary drawdown.
- **Number of trades** — how often the strategy actually traded, which tells us how trustworthy the
  other numbers are (a strategy "proven" on three trades means little).

---

## Why we test many different settings

Several of our rules have dials: *how far below is the stop-loss? how big a gain triggers the
break-even lock? how long is the freeze?* and so on. Rather than guess, the tool automatically
runs the whole five-year test **over and over with many combinations** of these dials and compares
the scorecards.

There's an important trap to avoid here, called **curve-fitting**. It's easy to find one magic
combination of settings that looks amazing on *past* data purely by luck — like a key cut to fit
one specific lock that opens nothing else. Those settings then fall apart in real life. So we don't
chase the single best-looking result. Instead we look for *broad neighborhoods* of settings that
all perform reasonably well together. If many nearby settings are good, the strategy is probably
**genuinely robust**, not just lucky.

---

## Honest limitations

To keep expectations grounded:

- **It's a simulation.** It assumes we can buy and sell at clean, exact prices. In the real world
  there's a little slippage, and prices can jump overnight — small frictions this early version
  doesn't model.
- **It looks at the stocks we have data for.** The strategy is judged on a fixed list of companies,
  which can flatter the results compared with the messier real world.
- **Past results don't guarantee the future.** Backtesting tells us whether an idea *was* sound
  historically. It cannot promise what tomorrow's market will do. It's a tool for building
  confidence and weeding out bad ideas — not a crystal ball.

---

## Mini-glossary

| Term | In one line |
|------|-------------|
| **Backtest** | Replaying past market data to see how a strategy would have performed. |
| **52-week high** | The highest price a stock has reached in the past year. |
| **Entry / Exit** | The moment we buy (entry) and the moment we sell (exit). |
| **Stop-loss** | A pre-set price at which we sell to cap a loss. |
| **Break-even lock** | Moving the stop up so a trade that was winning can't turn into a loss. |
| **Trailing stop** | A sell-line that rises with the price to protect growing profit. |
| **Liquidity** | How easily a stock can be bought or sold without moving its price. |
| **Drawdown** | The worst peak-to-bottom drop in value along the way. |
| **Win rate** | The share of trades that ended in profit. |
| **Curve-fitting** | Tuning a strategy so perfectly to the past that it fails in the future. |
| **Freeze** | Our cool-down rule: pausing a stock for a while after it loses money. |
