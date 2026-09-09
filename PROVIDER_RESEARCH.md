# AI Subscription Provider Quota Research

Research for `aiquota`. Public sources only — no logins, no credentials, no live API calls.
Every URL below was fetched; quotes are verbatim from the fetched page.

**Legend**
- **A — Build now**: documented endpoint returning remaining quota + no automation prohibition found
- **B — Build with caveat**: real endpoint, but Enterprise-gated, undocumented/internal, or terms are ambiguous
- **C — EXCLUDE (ToS)**: terms explicitly prohibit automated/scripted access, same class as Midjourney/Suno
- **D — No endpoint**: nothing readable exists

---

## Tier A — Buildable now (VERIFIED endpoint + no prohibition found)

| Provider | Endpoint | Fields | Auth | Notes |
|---|---|---|---|---|
| **DeepSeek** | `GET https://api.deepseek.com/user/balance` | `is_available`, `balance_infos[].total_balance/granted_balance/topped_up_balance`, `currency` | Bearer API key | Cleanest in the whole set. Officially documented. |
| **Poe (Quora)** | `GET https://api.poe.com/usage/current_balance` | `current_point_balance` (int) | Bearer API key | Also `GET /usage/points_history`. Docs literally say "Check remaining Poe API points". |
| **HeyGen** | `GET https://api.heygen.com/v2/user/remaining_quota` | `data.remaining_quota`, `data.used_quota` | `X-Api-Key` header | v1/v2 supported through **Oct 31 2026**; v3 is the active platform — check v3 equivalent before shipping. |
| **Leonardo.ai** | `GET https://cloud.leonardo.ai/api/rest/v1/me` | `user_details[].subscriptionTokens`, `paidTokens`, `subscriptionGptTokens`, `subscriptionModelTrainingTokens`, `tokenRenewalDate` | Bearer | Best creative-tier fit: separates subscription vs paid tokens *and* gives renewal date. |
| **Recraft** | `GET https://external.api.recraft.ai/v1/users/me` | credits balance + plan (OpenAI-compatible client) | Bearer | Documented as "Returns information of the current user including credits balance." |
| **fal.ai** | `GET https://api.fal.ai/v1/account/billing?expand=credits` | `username`, `credits.current_balance`, `credits.currency` | API key | Docs explicitly list use case: "Display balance in custom dashboards." Green-light by design. |
| **Kling AI** | `GET https://api.klingai.com/account/costs?start_time=&end_time=` | `data.resource_pack_subscribe_infos[].resource_pack_name/total_quantity/remaining_quantity/status` | JWT (HS256, AK/SK, ~30min TTL) | Free to call, **QPS ≤ 1** — cache aggressively. JWT minting adds work vs a static key. |
| **Google Antigravity** | `POST https://cloudcode-pa.googleapis.com/v1internal:retrieveUserQuotaSummary` | 2 groups (Gemini; Claude+GPT), each weekly + 5h bucket | OAuth Bearer, **`User-Agent: antigravity` required** (else 403 PERMISSION_DENIED) | Also `POST /v1internal:loadCodeAssist` → `availablePromptCredits`, `planInfo.monthlyPromptCredits`; `POST /v1internal:fetchAvailableModels` → `quotaInfo.remainingFraction`, `resetTime`, `isExhausted`. `v1internal` = **undocumented**, can break without notice. Antigravity CLI ships `/usage` as the sanctioned surface. |
| **Kimi** | `GET https://api.kimi.com/coding/v1/usages` | `usage.limit/remaining/resetTime`, `detail.*`, `totalQuota.limit/used/remaining` | Bearer | ⚠️ Parser trap: `totalQuota.remaining` can be stale — derive exhaustion only from explicit `used`, never `limit - remaining`. |
| **MiniMax / Hailuo** | Coding/Token Plan quota endpoint | `model_remains[].current_interval_remaining_percent`, `current_weekly_remaining_percent`, `remains_time`, `weekly_remains_time`, `current_interval_total_count` | Bearer | Response shape verified from the `quotas` crate; exact path not confirmed in official docs. Console: platform.minimax.io/user-center/payment/coding-plan |
| **Mistral** | `GET /v1/billing/subscription`, `GET /v1/billing/usage?start_date&end_date` | plan, monthly spend, RPM/TPM | API key w/ billing scope | Third-party-attested (openusage). Official docs confirm `GET /v1/admin/usage` + `/v1/admin/spend-limits` (Beta Admin, admin key). Always EUR. |
| **Ideogram** | Credit balance surfaced in API Dashboard (available/consumed/expired/total issued) at `ideogram.ai/manage-api` | — | — | Balance is documented as existing; **no public REST path for it found**. Likely an internal XHR. Endpoint = speculation. |

## Tier B — Real endpoint, but gated or internal

| Provider | Endpoint | Blocker |
|---|---|---|
| **Devin (Cognition)** | `docs.devin.ai` → Get Team Credit Balance; `/api-reference/v2/user-usage/...`; `/api-reference/v3/consumption/consumption-daily-users` | Enterprise/org-scoped. Also: Cognition **retired ACU billing for all self-serve tiers on 2026-04-14** — Free/Pro/Max users have no ACU to read. Only Enterprise. |
| **Windsurf (Codeium)** | `POST https://server.codeium.com/api/v1/TeamCreditBalance` | Enterprise service-key only; team-level, not individual. Individual/Pro ToS fetched — **no automation prohibition found**, so terms are not the blocker; access tier is. |
| **Augment Code** | `GET /analytics/v0/credit-usage-by-user` | Preview feature, **Enterprise customers only**. Docs name the CBP Dashboard as authoritative source for "remaining Credit balance" — dashboard, not API, for individuals. |
| **Tabnine** | Platform API — org usage metrics (`/usage`, audit) | Admin/team console scope. Per-seat individual remaining quota not exposed. |
| **JetBrains AI** | Central Console Analytics API v1/v2 — "credits consumption" | Org-level admin analytics. No individual-subscriber quota endpoint. |
| **Replit** | Admin API, `rpl_` bearer, Usage scope (usage + gross ledger cost, budgets) | **Enterprise account admins only** — explicitly not available to workspace admins or members. Beta. Note Replit ToS separately bans scraping (see Tier C reasoning) so the *dashboard* route is closed; the Admin API is the only lawful path. |
| **Together.ai** | Credit balance exists (prepaid, suspends at zero, auto-recharge thresholds) | No documented public balance endpoint found. Balance clearly exists server-side; path unverified. |
| **Sourcegraph Amp** | Sourcegraph Analytics API (usage metrics, access tokens) | That's the enterprise Sourcegraph analytics product, not Amp per-user credit balance. No Amp balance endpoint found. **Note: search results for "Amp credits" are polluted by ArangoDB's unrelated "AMP" product — don't trust them.** |
| **Freepik** | Credits shown in top nav; `freepik-cli` claims `freepik credits` + rate-limit headers | Community CLI implies readable headers/endpoint; no official documented balance path found. |

## Tier C — EXCLUDE on ToS grounds (same class as Midjourney / Suno)

These have explicit automation/scraping prohibitions. Quotes verbatim.

| Provider | Clause | URL |
|---|---|---|
| **Udio** | "use any **automated process of any sort to query, access, retrieve, scrape, data-mine or copy** any Material on UDIO" | udiosystems.com/terms |
| **Luma (Dream Machine)** | "access the APIs through **any automated means, scripts, bots, scrapers, or other tools** other than those expressly authorized by Luma's Documentation and through Luma's documented API methods and endpoints"; separately "**scrape, data mine, systematically extract**, or otherwise collect data from the Services beyond the Output generated in direct response to authorized API requests" | lumalabs.ai/legal/api-terms-of-use |
| **Descript** | "use any **data mining, robots or similar data gathering or extraction methods designed to scrape or extract data** from the Descript Service; **develop or use any applications that interact with the Descript Service without our prior written consent**" | descript.com/terms |
| **Bolt.new (StackBlitz)** | "use any **automated tool (e.g., robots, spiders) to access or use our Services**"; also "use any Services or StackBlitz Content for any purpose except for your own personal use" | stackblitz.com/terms-of-service |
| **Lovable** | "use **automated tools (such as bots, scrapers, or crawlers) to access or interact with the Services without our written permission**" | lovable.dev/terms |
| **Replit** (dashboard route only) | "**Scraping or otherwise obtaining content**, whether for training or extracting data for machine learning models... or for any other purpose"; also bans "Creating accounts with automation" | replit.com/terms-of-service |

**Luma is the sharpest exclusion**: its clause is narrower and stricter than most — it permits automation *only* through documented API methods. There is no documented Luma credit-balance endpoint, so any balance read would be via an undocumented path, which the clause forbids by name. Treat Luma as a hard no, on par with Midjourney.

**Descript is also unusually broad** — "develop or use any applications that interact with the Descript Service without our prior written consent" bans the integration itself, not just scraping.

## Tier D — No readable quota endpoint found

| Provider | Finding |
|---|---|
| **v0 (Vercel)** | Ships a Usage & Activity Dashboard (per-day credits, per-message cost) as of 2026. No public API. Internal XHR presumed but unverified. |
| **Zed** | Pro = $5/mo token credit + 2,000 accepted edit predictions. Usage is in-app only; no account/usage API found. |
| **Qwen Code** | **Qwen OAuth free tier discontinued 2026-04-15.** Users now route via Alibaba Cloud Coding Plan / OpenRouter / Fireworks / BYO key — so quota lives at whichever provider they picked, not at Qwen. Don't build a "Qwen" provider; build the underlying ones. |
| **Google Gemini (consumer AI Pro/Ultra)** | No consumer-facing quota API. AI Pro/Ultra entitlements flow into Gemini CLI / Code Assist via `cloudcode-pa` — the Antigravity endpoints above are the *only* readable surface, and they report Code-Assist quota, not the consumer Gemini app's limits. A standing feature request ("Allow AI Pro subscription quota to be used for Gemini API") confirms the gap. |
| **Pika** | Has an API + separate API ToS. No credit-balance endpoint found. |
| **Krea** | ToS fetched; no automation clause found, but also no balance API found. |
| **Captions** | Mirage API is "credits-based billing" per marketing. No documented balance endpoint. |
| **Synthesia** | Credits documented extensively in help center; ToS pages fetched, no automation clause surfaced. No balance endpoint found. Third-party analysis claims their AUP prohibits scraping — **unverified, treat as risk**. |
| **Notion AI** | Credit system exists ($10/1,000 credits, launched 2026-05-04). No credit-balance API found in the public Notion API. |
| **You.com** | ToS fetched (JS-rendered, low signal). No quota endpoint found. |
| **Replicate** | Prepaid credit balance exists per billing docs. No documented balance endpoint in the public HTTP API; third-party trackers claim to read it but the path is unverified. |

---

## Recommended build order

1. **DeepSeek, Poe, fal.ai** — trivial: static key, single GET, one integer. fal.ai's docs explicitly bless dashboard use.
2. **Leonardo.ai, Recraft, HeyGen** — creative tier, clean documented fields. Leonardo is the strongest creative addition (subscription vs paid split + renewal date).
3. **Kling** — worth it for video coverage, but budget effort for JWT minting and respect QPS ≤ 1.
4. **Kimi, MiniMax, Mistral** — good coverage, but MiniMax's exact path needs confirmation and Kimi needs the `totalQuota` staleness guard.
5. **Antigravity** — high user value (it's how Gemini/Claude quota is actually visible), but `v1internal` is undocumented and UA-gated. Ship it flagged as best-effort.

## Blunt caveats

- **The `quotas` Rust crate (docs.rs/quotas) is the single most useful source found** — it has working, test-covered parsers for antigravity, deepseek, kimi, minimax, zai, siliconflow, mimo, plus the providers aiquota already supports. Its unit-test fixtures contain real response shapes. Worth reading before implementing any of these. Bonus finds not on the task list: **Z.ai** (`GET https://api.z.ai/api/monitor/usage/quota/limit` → `data.limits[].usage/currentValue/remaining/nextResetTime/percentage`, 5h + weekly + monthly_mcp windows), plus SiliconFlow and MiMo.
- **Ideogram, Together, Replicate, Freepik, v0**: balance provably exists in-product, but I could not verify a public path. Anything I'd write down is a guess. Confirming these requires observing your own logged-in session's network traffic — out of scope here, and for v0/Replit that route is ToS-barred anyway.
- **Enterprise-gated ≠ buildable for aiquota's audience.** Devin, Windsurf, Augment, Replit, Tabnine and JetBrains all have credit APIs that an individual subscriber cannot call. Listing them as "supported" would mislead most users.
- **Devin's ACU retirement (2026-04-14) is a real trap** — plenty of stale docs still describe ACU balance for Pro/Max. Those users have nothing to read.
- **Synthesia's automation stance is unresolved.** A third-party analyser asserts their AUP "prohibits scraping any content or data"; I could not surface that clause from synthesia.io directly. Don't ship Synthesia without reading the AUP in full.
- Terms change. The Tier C quotes are point-in-time as fetched; re-verify before each release.
