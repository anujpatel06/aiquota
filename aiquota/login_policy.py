"""Per-platform rules about how aiquota is allowed to authenticate.

Not every provider treats third-party sign-in the same way, and the difference
is not cosmetic — in April 2026 Anthropic began banning accounts belonging to
users of third-party tools that logged in with Claude subscription OAuth.

So the login method is a policy decision per platform, recorded here with the
source that justifies it, rather than a UI convenience decided per-adapter.

Values
------
``browser``
    aiquota may open a sign-in window and read the resulting session. Use only
    where the provider does not prohibit third-party access to a user's own
    account.

``own-credential``
    The user must point aiquota at a credential they already hold (an API key
    they created, or a token file they explicitly nominate). aiquota must not
    obtain the credential itself. This is the honest option where a provider
    restricts OAuth to its own applications: the user is still choosing to
    read their own data, but aiquota is not impersonating a first-party client.

``manual``
    No machine-readable quota exists. The user types the numbers.
"""

# key -> (policy, why, source)
LOGIN_POLICY = {
    "claude": (
        "own-credential",
        "Anthropic restricts OAuth to Claude Code and its own applications. "
        "Third-party tools using subscription OAuth had accounts banned in "
        "April 2026. Point aiquota at a token you already have instead.",
        "https://code.claude.com/docs/en/legal-and-compliance",
    ),
    "chatgpt": (
        "own-credential",
        "Codex CLI's login is issued to Codex. aiquota reads the credential "
        "it already wrote, only with your explicit consent.",
        "https://developers.openai.com/codex/auth",
    ),
    "copilot": (
        "own-credential",
        "Reuses your existing `gh` CLI login, which you performed yourself.",
        "https://docs.github.com/en/copilot",
    ),
    "openrouter": (
        "browser",
        "OpenRouter publishes an OAuth PKCE flow explicitly for third-party "
        "applications.",
        "https://openrouter.ai/docs/use-cases/oauth-pkce",
    ),
    "elevenlabs": (
        "own-credential",
        "No third-party OAuth; a user-created API key is the supported route.",
        "https://elevenlabs.io/docs/api-reference/authentication",
    ),

    # --- session-based: no developer API, but no prohibition either ---
    # These dashboards read quota from an internal endpoint that answers to a
    # signed-in session. Probed unauthenticated, each returns 401 (the route
    # exists and wants a login) rather than 404. None of these providers
    # restrict third-party access to a user's own account the way Anthropic
    # does, so a browser sign-in the user performs themselves is legitimate.
    "cursor": (
        "browser",
        "Quota lives behind the dashboard session; no ToS restriction on "
        "reading your own account.",
        "https://cursor.com/dashboard",
    ),
    "grok": (
        "browser",
        "Subscription tier is exposed to the signed-in session only.",
        "https://grok.com",
    ),
    "runway": (
        "browser",
        "Credit balance is exposed to the signed-in session only.",
        "https://app.runwayml.com",
    ),
    "perplexity": (
        "browser",
        "Quota is exposed to the signed-in dashboard only; Cloudflare blocks "
        "plain HTTP clients, so the reading is taken inside the browser.",
        "https://www.perplexity.ai/settings/account",
    ),

    # --- refused: the provider forbids automated access outright ---
    # These have working endpoints and adapters could read them, but their
    # terms prohibit it in language that has been enforced with bans. A quota
    # number is not worth someone's account.
    "midjourney": (
        "manual",
        "Midjourney prohibits automated access outright — \"automating "
        "interactions with Midjourney service is strictly prohibited\", listed "
        "as one of four Community Guidelines rules, enforced with account "
        "blocks. aiquota will not read it for you.",
        "https://docs.midjourney.com/hc/en-us/articles/32013696484109-Community-Guidelines",
    ),
    "suno": (
        "manual",
        "Suno's terms forbid \"any data mining, robots, scraping, or similar "
        "data gathering or extraction methods\" (clause 13). Reading the "
        "billing endpoint on a schedule is exactly that.",
        "https://suno.com/legal/terms",
    ),
    # --- documented, key-authenticated balance APIs ---
    # The safest class in the catalog: the provider publishes the endpoint,
    # you create the key yourself in their dashboard, and reading your own
    # balance is what the endpoint is for. Each was probed unauthenticated
    # and answered 401 with a JSON error (2026-09-09), so the routes are real.
    "deepseek": ("own-credential",
        "Documented balance endpoint; you create the key.",
        "https://api-docs.deepseek.com/api/get-user-balance"),
    "poe": ("own-credential",
        "Documented points-balance endpoint; you create the key.",
        "https://creator.poe.com/docs/external-applications/openai-compatible-api"),
    "fal": ("own-credential",
        "Documented billing endpoint; you create the key.",
        "https://docs.fal.ai/"),
    "heygen": ("own-credential",
        "Documented remaining-quota endpoint; you create the key.",
        "https://docs.heygen.com/reference/remaining-quota"),
    "leonardo": ("own-credential",
        "Documented /me endpoint returns token balance; you create the key.",
        "https://docs.leonardo.ai/reference/getuserself"),
    "recraft": ("own-credential",
        "Documented users/me endpoint; you create the key.",
        "https://www.recraft.ai/docs"),
    "kling": ("own-credential",
        "Documented account costs endpoint; you create the key.",
        "https://app.klingai.com/global/dev/document-api"),
    "zai": ("own-credential",
        "Documented quota endpoint with 5h/weekly/monthly windows.",
        "https://docs.z.ai/"),
    # --- providers that prohibit automated access ---
    # Same class as Midjourney and Suno: their terms forbid automated or
    # scripted access, with no carve-out for reading your own account. An
    # adapter for these would put the user's account at risk, so none exists.
    "udio": ("manual",
        "Terms forbid \"any automated process of any sort to query, access, "
        "retrieve, scrape, data-mine\" the service.",
        "https://www.udio.com/terms"),
    "luma": ("manual",
        "Terms allow automated access only via means \"expressly authorized "
        "by Luma's Documentation\", and no balance endpoint is documented.",
        "https://lumalabs.ai/legal/tos"),
    "descript": ("manual",
        "Terms ban scraping and building applications that interact with the "
        "service without prior written consent.",
        "https://www.descript.com/terms"),
    "bolt": ("manual",
        "StackBlitz terms forbid access by \"automated tool (e.g., robots, "
        "spiders)\".",
        "https://bolt.new/terms"),
}

DEFAULT = ("manual", "No public quota API; values are entered by hand.", "")


def policy_for(key: str):
    """Return (policy, why, source) for a catalog key."""
    return LOGIN_POLICY.get(key, DEFAULT)


def may_browser_login(key: str) -> bool:
    return policy_for(key)[0] == "browser"
