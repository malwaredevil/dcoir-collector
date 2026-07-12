RISK_SENTINEL_FINDING_TERMS: dict[str, tuple[str, ...]] = {
    "PowerShell Invoke-Expression": (
        "invoke-expression",
        "constructed text",
        "command injection",
        "code execution",
    ),
    "PowerShell process launch": (
        "start-process",
        "process",
        "command execution",
        "allowlist",
    ),
    "PowerShell unsafe archive extraction": (
        "expand-archive",
        "archive",
        "extraction",
        "path traversal",
        "containment",
    ),
    "PowerShell outbound request or download": (
        "invoke-webrequest",
        "web request",
        "ssrf",
        "exfiltration",
        "outbound",
    ),
    "PowerShell broad ACL grant": (
        "acl",
        "set-acl",
        "everyone",
        "fullcontrol",
        "permission",
    ),
    "Node.js command execution": (
        "exec",
        "spawn",
        "child process",
        "command injection",
    ),
    "dynamic code evaluation": (
        "eval",
        "function",
        "dynamic code",
        "code execution",
    ),
    "TypeScript/JavaScript unsafe path construction": (
        "path traversal",
        "path construction",
        "root containment",
        "file write",
    ),
    "TypeScript/JavaScript unsafe file write": (
        "writefile",
        "file write",
        "root containment",
        "path traversal",
    ),
    "raw SQL/query string interpolation": (
        "sql",
        "query",
        "interpolation",
        "parameter",
    ),
    "shell=True subprocess invocation": (
        "shell=true",
        "shell true",
        "shell execution",
        "subprocess",
        "command injection",
    ),
    "Python unsafe archive extraction": (
        "archive",
        "tar",
        "unpack",
        "extract",
        "path traversal",
    ),
    "outbound request or SSRF primitive": (
        "ssrf",
        "outbound",
        "url",
        "request",
        "exfiltration",
    ),
    "CI token exfiltration primitive": (
        "token",
        "secret",
        "authorization",
        "exfiltration",
    ),
    "GitHub Actions privileged PR context": (
        "pull_request_target",
        "privileged",
        "untrusted",
        "write token",
        "checkout",
    ),
    "GitHub Actions untrusted metadata shell execution": (
        "pull request title",
        "pull request body",
        "shell",
        "untrusted metadata",
    ),
    "Kubernetes privileged container setting": (
        "kubernetes",
        "privileged",
        "runasuser",
        "hostnetwork",
        "allowprivilegeescalation",
    ),
    "Kubernetes host filesystem exposure": (
        "hostpath",
        "host filesystem",
        "mount",
        "node",
    ),
    "unsafe deserialization primitive": (
        "deserialization",
        "pickle",
        "yaml.load",
        "code execution",
    ),
    "truthy literal branch condition": (
        "truthy",
        "always true",
        "literal branch",
        "bypass",
    ),
    "recursive delete primitive": (
        "recursive delete",
        "remove-item",
        "rmtree",
        "deletion",
        "path root",
    ),
    "PowerShell unsafe file-write path": (
        "powershell",
        "file write",
        "set-content",
        "out-file",
        "root containment",
        "request",
        "path",
    ),
    "environment dump or exfiltration primitive": (
        "environment",
        "os.environ",
        "get-childitem env",
        "secret",
        "exfiltration",
    ),
    "unsafe file-write path construction": (
        "path traversal",
        "file write",
        "arbitrary overwrite",
        "root containment",
        "dynamic path",
    ),
}

RISK_SENTINEL_HIGH_SEVERITY_LABELS = {
    "unsafe deserialization primitive",
    "PowerShell Invoke-Expression",
    "PowerShell process launch",
    "PowerShell unsafe archive extraction",
    "PowerShell outbound request or download",
    "PowerShell broad ACL grant",
    "Node.js command execution",
    "dynamic code evaluation",
    "TypeScript/JavaScript unsafe path construction",
    "TypeScript/JavaScript unsafe file write",
    "raw SQL/query string interpolation",
    "shell=True subprocess invocation",
    "Python unsafe archive extraction",
    "outbound request or SSRF primitive",
    "CI token exfiltration primitive",
    "GitHub Actions privileged PR context",
    "GitHub Actions untrusted metadata shell execution",
    "Kubernetes privileged container setting",
    "Kubernetes host filesystem exposure",
    "environment dump or exfiltration primitive",
    "PowerShell unsafe file-write path",
    "unsafe file-write path construction",
}

RISK_SENTINEL_LABEL_PRIORITY = {
    label: index
    for index, label in enumerate(
        (
            "unsafe deserialization primitive",
            "PowerShell Invoke-Expression",
            "PowerShell process launch",
            "PowerShell unsafe archive extraction",
            "PowerShell outbound request or download",
            "PowerShell broad ACL grant",
            "Node.js command execution",
            "TypeScript/JavaScript unsafe path construction",
            "TypeScript/JavaScript unsafe file write",
            "shell=True subprocess invocation",
            "dynamic code evaluation",
            "raw SQL/query string interpolation",
            "GitHub Actions privileged PR context",
            "CI token exfiltration primitive",
            "GitHub Actions untrusted metadata shell execution",
            "unsafe file-write path construction",
            "PowerShell unsafe file-write path",
            "Python unsafe archive extraction",
            "outbound request or SSRF primitive",
            "Kubernetes privileged container setting",
            "Kubernetes host filesystem exposure",
            "environment dump or exfiltration primitive",
            "recursive delete primitive",
            "truthy literal branch condition",
        )
    )
}


OPTIONAL_RISK_SENTINEL_LABEL_PREFIXES = (
    "TypeScript/JavaScript ",
    "Kubernetes ",
)
OPTIONAL_RISK_SENTINEL_LABELS = {
    "Node.js command execution",
}
YAML_REQUIRED_RISK_SENTINEL_LABEL_PREFIXES = (
    "GitHub Actions ",
)
YAML_REQUIRED_RISK_SENTINEL_LABELS = {
    "CI token exfiltration primitive",
}
PROJECT_TARGET_RISK_SENTINEL_EXTENSIONS = {
    ".ps1",
    ".psd1",
    ".psm1",
    ".py",
}


POWERSHELL_REQUEST_PATH_ASSIGNMENT = re.compile(
    r"^\s*\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*=\s*"
    r"(?P<value>.*(?:\bJoin-Path\b[^\n]*\$Request\.|\$Request\.(?:Path|RelativePath|FilePath|OutputPath|Destination)\b).*)$",
    re.IGNORECASE,
)
POWERSHELL_WRITE_PATH_VARIABLE = re.compile(
    r"\b(?:Set-Content|Add-Content|Out-File|Export-Clixml|Export-Csv|Copy-Item|Move-Item|New-Item)\b"
    r"[^\n]*\s-(?:Path|LiteralPath|FilePath|Destination)\s+\$(?P<name>[A-Za-z_][A-Za-z0-9_]*)\b",
    re.IGNORECASE,
)


NON_ACTIONABLE_FINDING_PATTERNS: tuple[tuple[re.Pattern[str], str], ...] = (
    (
        re.compile(r"\b(?:downgrades?|downgraded)\b.{0,120}\binformational\b", re.IGNORECASE | re.DOTALL),
        "finding downgrades itself to informational",
    ),
    (
        re.compile(r"\binformational\b.{0,120}\b(?:note|signal|finding|only)\b", re.IGNORECASE | re.DOTALL),
        "finding describes itself as informational",
    ),
    (
        re.compile(
            r"\b(?:risk|signal|finding)\b.{0,120}\b(?:not realized|is not realized|was not realized)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "finding says the risk is not realized",
    ),
    (
        re.compile(
            r"\bdoes not(?: itself)?\s+(?:introduce|create|pose|add)\b.{0,120}"
            r"\b(?:risk|issue|problem|defect|vulnerability|injection path)\b",
            re.IGNORECASE | re.DOTALL,
        ),
        "finding says the changed code does not introduce the risk",
    ),
    (
        re.compile(r"\bno\b.{0,80}\b(?:input|data|value|text)\b.{0,80}\breaches\b", re.IGNORECASE | re.DOTALL),
        "finding says no input reaches the risky path",
    ),
    (
        re.compile(r"\bno\b.{0,80}\b(?:execution|injection|exploit|vulnerability)\b.{0,80}\b(?:path|risk)\b", re.IGNORECASE | re.DOTALL),
        "finding says no execution or injection path exists",
    ),
    (
        re.compile(r"\b(?:out of scope|outside (?:the )?PR scope|no action is required)\b", re.IGNORECASE | re.DOTALL),
        "finding describes itself as out of scope",
    ),
)



