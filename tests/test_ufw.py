# SPDX-License-Identifier: MIT
"""Tests for src/adapters/ufw/status_parser.py — parse_ufw_numbered."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

import pytest
from adapters.ufw.status_parser import parse_ufw_numbered


# ── helpers ───────────────────────────────────────────────────────────────

def _make_output(*lines: str) -> str:
    return "\n".join(lines)


# ── 1. Empty output ───────────────────────────────────────────────────────

def test_empty_output_returns_inactive():
    result = parse_ufw_numbered("")
    assert result["active"] is False
    assert result["status"] == "inactive"
    assert result["rules"] == []


def test_empty_output_default_fields_empty():
    result = parse_ufw_numbered("")
    assert result["default_incoming"] == ""
    assert result["default_outgoing"] == ""
    assert result["logging"] == ""


# ── 2. Status: active ─────────────────────────────────────────────────────

def test_status_active_sets_active_true():
    result = parse_ufw_numbered("Status: active")
    assert result["active"] is True
    assert result["status"] == "active"


def test_status_active_with_surrounding_whitespace():
    result = parse_ufw_numbered("  Status: active  ")
    assert result["active"] is True
    assert result["status"] == "active"


# ── 3. Status: inactive ───────────────────────────────────────────────────

def test_status_inactive_sets_active_false():
    result = parse_ufw_numbered("Status: inactive")
    assert result["active"] is False
    assert result["status"] == "inactive"


# ── 4. Default policies ───────────────────────────────────────────────────

def test_default_policies_parsed():
    line = "Default: deny (incoming), allow (outgoing), disabled (routed)"
    result = parse_ufw_numbered(line)
    assert result["default_incoming"] == "deny"
    assert result["default_outgoing"] == "allow"


def test_default_policies_reject_incoming():
    line = "Default: reject (incoming), allow (outgoing), disabled (routed)"
    result = parse_ufw_numbered(line)
    assert result["default_incoming"] == "reject"
    assert result["default_outgoing"] == "allow"


# ── 5. Logging line ───────────────────────────────────────────────────────

def test_logging_line_parsed():
    result = parse_ufw_numbered("Logging: on (low)")
    assert result["logging"] == "on (low)"


def test_logging_off():
    result = parse_ufw_numbered("Logging: off")
    assert result["logging"] == "off"


# ── 6. Single ALLOW rule ──────────────────────────────────────────────────

def test_single_allow_rule():
    output = "[ 1] 22/tcp                     ALLOW IN    Anywhere"
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["number"] == 1
    assert rule["to"] == "22/tcp"
    assert rule["action"] == "ALLOW IN"
    assert rule["from_"] == "Anywhere"


# ── 7. Single DENY rule ───────────────────────────────────────────────────

def test_single_deny_rule():
    output = "[ 2] 80/tcp                     DENY IN     Anywhere"
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["number"] == 2
    assert rule["to"] == "80/tcp"
    assert rule["action"] == "DENY IN"
    assert rule["from_"] == "Anywhere"


# ── 8. LIMIT rule ─────────────────────────────────────────────────────────

def test_limit_rule():
    output = "[ 3] 22/tcp                     LIMIT IN    Anywhere"
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["number"] == 3
    assert rule["action"] == "LIMIT IN"


# ── 9. Multiple rules in order ────────────────────────────────────────────

def test_multiple_rules_returned_in_order():
    output = _make_output(
        "[ 1] 22/tcp                     ALLOW IN    Anywhere",
        "[ 2] 80/tcp                     DENY IN     Anywhere",
        "[ 3] 443/tcp                    ALLOW IN    Anywhere",
    )
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 3
    assert result["rules"][0]["number"] == 1
    assert result["rules"][1]["number"] == 2
    assert result["rules"][2]["number"] == 3


# ── 10. ALLOW OUT direction ───────────────────────────────────────────────

def test_allow_out_rule():
    output = "[ 4] 443/tcp                    ALLOW OUT   Anywhere"
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["number"] == 4
    assert rule["action"] == "ALLOW OUT"
    assert rule["to"] == "443/tcp"


# ── 11. Rule with specific from_ ──────────────────────────────────────────

def test_rule_with_specific_source():
    output = "[ 5] 22/tcp                     ALLOW IN    192.168.1.0/24"
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["from_"] == "192.168.1.0/24"


# ── 12. Complete output block ─────────────────────────────────────────────

def test_complete_output_block():
    output = _make_output(
        "Status: active",
        "",
        "Logging: on (low)",
        "Default: deny (incoming), allow (outgoing), disabled (routed)",
        "New profiles: skip",
        "",
        "To                         Action      From",
        "--                         ------      ----",
        "[ 1] 22/tcp                     ALLOW IN    Anywhere",
        "[ 2] 80/tcp                     DENY IN     Anywhere",
        "[ 3] 22/tcp (v6)                ALLOW IN    Anywhere (v6)",
    )
    result = parse_ufw_numbered(output)
    assert result["active"] is True
    assert result["status"] == "active"
    assert result["default_incoming"] == "deny"
    assert result["default_outgoing"] == "allow"
    assert result["logging"] == "on (low)"
    # at least the non-IPv6 rules are parsed
    numbered = [r for r in result["rules"] if r["number"] in (1, 2)]
    assert len(numbered) == 2


# ── 13. IPv6 rule line is tolerated ──────────────────────────────────────

def test_ipv6_rule_line_does_not_crash():
    output = _make_output(
        "Status: active",
        "[ 1] 22/tcp (v6)                ALLOW IN    Anywhere (v6)",
    )
    # must not raise
    result = parse_ufw_numbered(output)
    assert result["active"] is True
    # the result may or may not include the IPv6 line — no crash is the contract


# ── 14. Rule number with extra spaces ─────────────────────────────────────

def test_rule_number_with_extra_spaces():
    output = "[  2] 80/tcp                     DENY IN     Anywhere"
    result = parse_ufw_numbered(output)
    assert len(result["rules"]) == 1
    rule = result["rules"][0]
    assert rule["number"] == 2
    assert rule["action"] == "DENY IN"
