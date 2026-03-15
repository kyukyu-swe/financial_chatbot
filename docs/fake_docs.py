"""
Fake Omise API documentation entries for the RAG knowledge base.
12 entries covering common topics: errors, charges, refunds, currencies,
webhooks, tokenization, and rate limits.
"""

OMISE_DOCS = [
    {
        "id": "doc_001",
        "title": "Error 401 – Unauthorized",
        "topic": "errors",
        "content": (
            "HTTP 401 Unauthorized is returned when your API key is missing, invalid, or has been revoked. "
            "Each request to the Omise API must include a valid secret key via HTTP Basic Auth. "
            "Pass your secret key as the username and leave the password blank. "
            "Example header: Authorization: Basic base64(sk_live_xxxx:). "
            "If you receive a 401, verify that: (1) you are using the correct key type (secret key for server-side, "
            "public key for tokenization only), (2) the key has not been rolled in the Omise Dashboard, "
            "and (3) you are hitting the correct environment (live vs. test)."
        ),
    },
    {
        "id": "doc_002",
        "title": "Error 402 – Payment Required / Card Declined",
        "topic": "errors",
        "content": (
            "HTTP 402 Payment Required indicates the charge was declined by the card issuer or Omise's risk engine. "
            "Common decline reasons include insufficient funds, do-not-honor responses, incorrect CVV, "
            "and velocity limits triggered. The response body contains a 'failure_code' field "
            "(e.g., 'insufficient_funds', 'stolen_card', 'failed_fraud_check') and a human-readable "
            "'failure_message'. Merchants should display a generic decline message to cardholders and "
            "never expose the raw failure_code. Instruct the cardholder to contact their bank or try a "
            "different payment method."
        ),
    },
    {
        "id": "doc_003",
        "title": "Error 422 – Unprocessable Entity / Validation Error",
        "topic": "errors",
        "content": (
            "HTTP 422 Unprocessable Entity is returned when the request body is syntactically valid JSON "
            "but fails semantic validation. Common causes: amount below the minimum charge threshold "
            "(THB 2000 satangs / 20 THB), unsupported currency, missing required fields (amount, currency, "
            "source or card token), or an expired token. The response body includes an 'object' field set to "
            "'error' and a 'message' describing the specific validation failure. Fix the request parameters "
            "and retry — do NOT retry the same request unchanged as it will keep failing."
        ),
    },
    {
        "id": "doc_004",
        "title": "Error 500 – Internal Server Error",
        "topic": "errors",
        "content": (
            "HTTP 500 Internal Server Error indicates an unexpected problem on Omise's servers. "
            "These are rare and typically transient. Recommended handling: implement exponential backoff "
            "with jitter, retry up to 3 times with delays of 1s, 2s, and 4s. "
            "If the error persists beyond 3 retries, log the full response body (including the 'request_id' "
            "field) and contact Omise support at support@omise.co with the request_id. "
            "Do not create duplicate charges — check idempotency keys and query the charge status before retrying."
        ),
    },
    {
        "id": "doc_005",
        "title": "Creating a Charge",
        "topic": "charges",
        "content": (
            "To create a charge, POST to https://api.omise.co/charges with your secret key. "
            "Required parameters: 'amount' (integer in smallest currency unit, e.g. satangs for THB), "
            "'currency' (ISO 4217 lowercase, e.g. 'thb'), and either 'card' (a card token from Omise.js) "
            "or 'source' (a payment source ID for alternative payments). "
            "Optional parameters: 'description', 'metadata' (key-value object), 'capture' (boolean, default true). "
            "A successful response returns a Charge object with 'status' = 'successful'. "
            "Minimum charge: 2000 satangs (THB 20). Maximum charge: 15,000,000 satangs per transaction."
        ),
    },
    {
        "id": "doc_006",
        "title": "Refunding a Charge",
        "topic": "refunds",
        "content": (
            "To refund a charge, POST to https://api.omise.co/charges/{charge_id}/refunds. "
            "Required parameter: 'amount' (integer in satangs). Omise supports partial refunds — "
            "you can refund less than the original charge amount. Multiple partial refunds are allowed "
            "until the fully refunded amount equals the original charge. "
            "A charge can only be refunded if its status is 'successful'. Pending and failed charges "
            "cannot be refunded. Refunds typically settle back to the cardholder within 5–10 business days "
            "depending on the issuing bank. Refund fees are not returned by Omise."
        ),
    },
    {
        "id": "doc_007",
        "title": "Supported Currencies",
        "topic": "currencies",
        "content": (
            "Omise supports the following currencies: THB (Thai Baht), JPY (Japanese Yen), "
            "SGD (Singapore Dollar), USD (US Dollar), EUR (Euro), GBP (British Pound), "
            "HKD (Hong Kong Dollar), MYR (Malaysian Ringgit), and IDR (Indonesian Rupiah). "
            "Amounts must be provided in the smallest unit: satangs for THB (1 THB = 100 satangs), "
            "cents for USD/SGD/EUR/GBP/HKD, sen for MYR, and yen for JPY (zero-decimal). "
            "IDR is also zero-decimal. Currency conversion is not provided by Omise — "
            "the currency must match the merchant's account settlement currency or an enabled currency."
        ),
    },
    {
        "id": "doc_008",
        "title": "Webhooks and Event Notifications",
        "topic": "webhooks",
        "content": (
            "Omise sends webhook notifications to your registered endpoint for key events including: "
            "charge.complete, charge.create, refund.create, transfer.create, and dispute.create. "
            "Configure webhook URLs in the Omise Dashboard under Settings > Webhooks. "
            "Each webhook POST contains an Event object with 'key' (event type), 'data' (the affected object), "
            "and 'created' (ISO 8601 timestamp). "
            "To verify authenticity, check that the request originates from Omise's IP ranges and validate "
            "the HMAC-SHA256 signature in the X-Omise-Signature header using your webhook secret. "
            "Respond with HTTP 200 within 30 seconds; otherwise Omise retries up to 5 times."
        ),
    },
    {
        "id": "doc_009",
        "title": "Card Tokenization with Omise.js",
        "topic": "tokenization",
        "content": (
            "Never send raw card data to your server. Use Omise.js (or the iOS/Android SDK) to tokenize "
            "card details directly from the browser/app to Omise's PCI-DSS compliant vault. "
            "Include Omise.js via CDN: <script src='https://cdn.omise.co/omise.js'></script>. "
            "Call OmiseCard.open({ publicKey: 'pkey_live_xxxx', onCreateTokenSuccess: fn }) to open the "
            "payment form. The callback receives a one-time token (tok_xxxx) that expires in 3 minutes. "
            "Pass this token as the 'card' parameter when creating a charge on your server. "
            "Tokens are single-use and tied to a specific public key."
        ),
    },
    {
        "id": "doc_010",
        "title": "API Rate Limits",
        "topic": "rate_limits",
        "content": (
            "The Omise API enforces rate limits to ensure fair usage. Default limits: "
            "100 requests per second per API key in live mode, 20 requests per second in test mode. "
            "When a limit is exceeded, the API returns HTTP 429 Too Many Requests with a "
            "Retry-After header indicating the number of seconds to wait. "
            "Best practices: implement client-side throttling, use idempotency keys to safely retry, "
            "and batch operations where the API allows it. "
            "Contact Omise support to request higher limits for high-volume merchants."
        ),
    },
    {
        "id": "doc_011",
        "title": "Listing and Filtering Charges",
        "topic": "charges",
        "content": (
            "To retrieve a list of charges, GET https://api.omise.co/charges. "
            "Supported query parameters: 'limit' (1–100, default 20), 'offset', "
            "'from' (ISO 8601 datetime), 'to' (ISO 8601 datetime), 'status' (successful/failed/pending). "
            "The response is a paginated List object with 'data' (array of Charge objects), "
            "'total' (total matching records), 'limit', and 'offset'. "
            "To retrieve a specific charge: GET https://api.omise.co/charges/{charge_id}. "
            "Charges are scoped to the authenticated merchant — you can only see your own charges."
        ),
    },
    {
        "id": "doc_012",
        "title": "Idempotency Keys",
        "topic": "charges",
        "content": (
            "Omise supports idempotency keys to safely retry failed requests without risk of creating "
            "duplicate charges. Include the header Idempotency-Key: <unique_string> on any POST request. "
            "If a request with the same idempotency key is retried within 24 hours, Omise returns the "
            "original response instead of processing the request again. "
            "Use a UUID v4 per charge attempt as the idempotency key. "
            "Keys expire after 24 hours. This is especially important when handling network timeouts "
            "or 500 errors where you are unsure whether the original request was processed."
        ),
    },
]
