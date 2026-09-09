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
}

DEFAULT = ("manual", "No public quota API; values are entered by hand.", "")


def policy_for(key: str):
    """Return (policy, why, source) for a catalog key."""
    return LOGIN_POLICY.get(key, DEFAULT)


def may_browser_login(key: str) -> bool:
    return policy_for(key)[0] == "browser"
