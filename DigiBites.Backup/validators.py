"""
validators.py - DigiBites Input Validation & Sanitization Layer
Python equivalent of the PHP HandlesValidations trait.
"""

import re
import html


class ValidationError(Exception):
    """Raised when one or more fields fail validation."""

    def __init__(self, errors):
        self.errors = errors
        super().__init__(str(errors))

    def to_response(self):
        return {"success": False, "message": "Validation failed.", "errors": self.errors}


class ValidationHelper:

    # ------------------------------------------------------------------
    # 1. STRING NORMALIZATION
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_string(value):
        """Trim and collapse internal spaces. 'hello   world' -> 'hello world'."""
        if not value:
            return ""
        return re.sub(r"\s+", " ", str(value).strip())

    @staticmethod
    def title_case_name(value):
        """
        Capitalize first letter after start, space, hyphen, or apostrophe.
        'mary-jane' -> 'Mary-Jane', "o'brien" -> "O'Brien"
        """
        value = ValidationHelper.normalize_string(value)
        if not value:
            return ""

        def _cap(m):
            return m.group(1) + m.group(2).upper()

        return re.sub(r"(^|[\s\-'])([a-z])", _cap, value, flags=re.IGNORECASE)

    # ------------------------------------------------------------------
    # 2. PH MOBILE NORMALIZATION
    # ------------------------------------------------------------------

    @staticmethod
    def normalize_ph_mobile(phone):
        """
        Reduce PH mobile to 10-digit local form.
        '+63 912 345 6789' -> '9123456789'
        '09123456789'      -> '9123456789'
        """
        if not phone:
            return ""
        digits = re.sub(r"\D+", "", str(phone))
        if len(digits) == 12 and digits.startswith("63"):
            digits = digits[2:]
        elif len(digits) == 11 and digits.startswith("0"):
            digits = digits[1:]
        return digits

    # ------------------------------------------------------------------
    # 3. INPUT SANITIZATION
    # ------------------------------------------------------------------

    @staticmethod
    def sanitize(value, input_type="text"):
        """
        Sanitize input by type.
        Types: name, email, phone, price, int, url, html, text (default)
        """
        if value is None:
            return None
        value = str(value)

        if input_type == "name":
            value = re.sub(r"[^\w\s\-'.]", "", value)
            value = re.sub(r"\d+", "", value)
            return ValidationHelper.normalize_string(value)

        if input_type == "email":
            return ValidationHelper.normalize_string(value).lower()

        if input_type == "phone":
            return re.sub(r"[^0-9+\s\-()]", "", value).strip()

        if input_type == "price":
            return ValidationHelper.clean_price(value)

        if input_type == "int":
            return re.sub(r"\D", "", value)

        if input_type == "url":
            return re.sub(r"[^\w\-._~:/?#\[\]@!$&'()*+,;=%]", "", value)

        if input_type == "html":
            return html.escape(value)

        # Default: text
        value = value.replace("\x00", "")
        return ValidationHelper.normalize_string(value)

    # ------------------------------------------------------------------
    # 4. SUSPICIOUS PATTERN DETECTION
    # ------------------------------------------------------------------

    _SUSPICIOUS_PATTERNS = [
        (
            r"(?i)(--|;|\/\*|\*\/|xp_|exec\s*\(|select\s+.+\s+from|insert\s+into"
            r"|delete\s+from|drop\s+table|union\s+select|or\s+1\s*=\s*1"
            r"|and\s+1\s*=\s*1|sleep\s*\(|benchmark\s*\(|load_file\s*\("
            r"|outfile\s+|into\s+dumpfile)",
            "Suspicious SQL pattern detected.",
        ),
        (
            r"(?i)(<script|<\/script|javascript:|vbscript:|on\w+\s*=|<iframe"
            r"|<object|<embed|<link\s+href|<img\s+src|data:text\/html"
            r"|data:application\/)",
            "Suspicious script or HTML tag detected.",
        ),
        (
            r"(?i)(<\?php|\$\{|eval\s*\(|base64_decode\s*\(|system\s*\("
            r"|passthru\s*\(|shell_exec\s*\(|popen\s*\()",
            "Suspicious code injection pattern detected.",
        ),
        (r"(\.\./|\.\.\\|%2e%2e%2f|%2e%2e\/|\.\.%2f)", "Path traversal pattern detected."),
        (r"\x00", "Null byte character detected."),
    ]

    @staticmethod
    def detect_suspicious_patterns(value, field_name="input"):
        """Scan string for SQLi, XSS, path traversal. Returns list of issue strings."""
        issues = []
        for pattern, message in ValidationHelper._SUSPICIOUS_PATTERNS:
            if re.search(pattern, value):
                issues.append(message)
        return issues

    @staticmethod
    def validate_no_suspicious(fields):
        """
        Check all string fields for suspicious patterns.
        Raises ValidationError with first issue per field.
        """
        issues = {}
        for field_name, value in fields.items():
            if isinstance(value, str):
                found = ValidationHelper.detect_suspicious_patterns(value, field_name)
                if found:
                    issues[field_name] = found[0]
        if issues:
            raise ValidationError(issues)

    # ------------------------------------------------------------------
    # 5. PHONE & PRICE CLEANERS
    # ------------------------------------------------------------------

    @staticmethod
    def clean_phone(phone):
        """Strip everything except digits and '+'. Returns None for empty."""
        if not phone:
            return None
        return re.sub(r"[^0-9+]", "", str(phone))

    @staticmethod
    def clean_price(price):
        """
        Keep digits and one decimal point only.
        '1..2.3' -> '1.23'. Returns None for empty.
        """
        if price is None or price == "":
            return None
        cleaned = re.sub(r"[^0-9.]", "", str(price))
        parts = cleaned.split(".")
        if len(parts) > 2:
            cleaned = parts[0] + "." + "".join(parts[1:])
        return cleaned if cleaned else None

    # ------------------------------------------------------------------
    # 6. OUTPUT ESCAPING
    # ------------------------------------------------------------------

    @staticmethod
    def escape_output(value):
        """HTML-encode for safe display. '<script>' -> '&lt;script&gt;'"""
        if value is None:
            return None
        return html.escape(str(value), quote=True)


# ---------------------------------------------------------------------------
# Rule handlers
# ---------------------------------------------------------------------------

def _rule_required(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return "This field is required."
    return None


def _rule_min(value, arg, _all):
    try:
        n = int(arg)
        if value is not None and len(str(value)) < n:
            return f"Must be at least {n} characters."
    except (ValueError, TypeError):
        pass
    return None


def _rule_max(value, arg, _all):
    try:
        n = int(arg)
        if value is not None and len(str(value)) > n:
            return f"Must not exceed {n} characters."
    except (ValueError, TypeError):
        pass
    return None


def _rule_email(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return None
    if not re.match(r"^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$", str(value).strip()):
        return "Must be a valid email address."
    return None


def _rule_gmail(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return None
    val = str(value).strip()
    if not re.match(r"^[a-zA-Z0-9._%+\-]+@gmail\.com$", val, re.IGNORECASE):
        return "Only @gmail.com email addresses are accepted."
    return None


def _rule_alphanum(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return None
    if not re.match(r"^[a-zA-Z0-9_]+$", str(value)):
        return "Only letters, numbers, and underscores are allowed."
    return None


def _rule_numeric(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return None
    try:
        float(str(value))
    except ValueError:
        return "Must be a numeric value."
    return None


def _rule_name(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return None
    if not re.match(r"^[\w\s\-'.]+$", str(value)):
        return "Only letters, spaces, hyphens, and apostrophes are allowed."
    if re.search(r"\d", str(value)):
        return "Name must not contain numbers."
    return None


def _rule_ph_mobile(value, _arg, _all):
    if value is None or str(value).strip() == "":
        return None
    normalized = ValidationHelper.normalize_ph_mobile(str(value))
    if len(normalized) != 10 or not re.match(r"^9\d{9}$", normalized):
        return "Must be a valid Philippine mobile number (09xxxxxxxxx)."
    return None


_RULE_HANDLERS = {
    "required": _rule_required,
    "min": _rule_min,
    "max": _rule_max,
    "email": _rule_email,
    "gmail": _rule_gmail,
    "alphanum": _rule_alphanum,
    "numeric": _rule_numeric,
    "name": _rule_name,
    "ph_mobile": _rule_ph_mobile,
}


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def validate_fields(data, rules, messages=None, check_suspicious=True):
    """
    Validate data against rules. Returns (errors, cleaned_data).

    errors       -- { field: first_error_message } empty = passed
    cleaned_data -- values after string stripping

    Rules per field (list of strings):
        'required', 'min:N', 'max:N', 'email',
        'alphanum', 'numeric', 'name', 'ph_mobile'
    """
    messages = messages or {}
    errors = {}
    cleaned = {}

    for field, value in data.items():
        cleaned[field] = value.strip() if isinstance(value, str) else value

    for field, field_rules in rules.items():
        value = cleaned.get(field)
        for rule_str in field_rules:
            parts = rule_str.split(":", 1)
            rule_name = parts[0].strip()
            rule_arg = parts[1].strip() if len(parts) > 1 else ""
            handler = _RULE_HANDLERS.get(rule_name)
            if not handler:
                continue
            error = handler(value, rule_arg, cleaned)
            if error:
                msg_key = f"{field}.{rule_name}"
                errors[field] = messages.get(msg_key, messages.get(field, error))
                break

    if check_suspicious and not errors:
        for field, value in cleaned.items():
            if isinstance(value, str) and value:
                found = ValidationHelper.detect_suspicious_patterns(value, field)
                if found:
                    errors[field] = found[0]

    return errors, cleaned


def secure_validate(data, rules, messages=None):
    """
    Validate and raise ValidationError on failure. Returns cleaned data on success.

    try:
        cleaned = secure_validate(request.get_json() or {}, {
            'username': ['required', 'alphanum', 'min:3'],
            'password': ['required', 'min:4'],
        })
    except ValidationError as e:
        return jsonify(e.to_response()), 422
    """
    errors, cleaned = validate_fields(data, rules, messages)
    if errors:
        raise ValidationError(errors)
    return cleaned
