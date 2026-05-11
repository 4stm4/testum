"""Parser for `sudo ufw status numbered` and `sudo ufw status verbose` output."""
import re
from typing import TypedDict


class UFWRule(TypedDict):
    number: int
    to: str
    action: str      # ALLOW / DENY / REJECT / LIMIT  (+  IN / OUT / FWD)
    from_: str


class UFWStatusResult(TypedDict):
    active: bool
    status: str                   # 'active' | 'inactive'
    default_incoming: str         # 'deny' | 'allow' | 'reject'
    default_outgoing: str
    logging: str                  # 'on (low)' etc.
    rules: list[UFWRule]


_RULE_RE = re.compile(
    r'^\[\s*(?P<num>\d+)\]\s+'
    r'(?P<to>.+?)\s{2,}'
    r'(?P<action>ALLOW|DENY|REJECT|LIMIT)(?:\s+(?P<dir>IN|OUT|FWD))?\s+'
    r'(?P<from>.+?)\s*$'
)


def parse_ufw_numbered(output: str) -> UFWStatusResult:
    """Parse `sudo ufw status numbered` (+ verbose if mixed) output."""
    result: UFWStatusResult = {
        'active': False,
        'status': 'inactive',
        'default_incoming': '',
        'default_outgoing': '',
        'logging': '',
        'rules': [],
    }

    for line in output.splitlines():
        line_s = line.strip()

        if line_s.startswith('Status:'):
            val = line_s.split(':', 1)[1].strip().lower()
            result['status'] = val
            result['active'] = val == 'active'
            continue

        if line_s.startswith('Default:'):
            # Default: deny (incoming), allow (outgoing), disabled (routed)
            parts = line_s.split(':', 1)[1]
            m_in  = re.search(r'(\w+)\s+\(incoming\)', parts)
            m_out = re.search(r'(\w+)\s+\(outgoing\)', parts)
            if m_in:  result['default_incoming'] = m_in.group(1)
            if m_out: result['default_outgoing'] = m_out.group(1)
            continue

        if line_s.startswith('Logging:'):
            result['logging'] = line_s.split(':', 1)[1].strip()
            continue

        m = _RULE_RE.match(line)
        if m:
            direction = m.group('dir') or 'IN'
            result['rules'].append({
                'number': int(m.group('num')),
                'to':     m.group('to').strip(),
                'action': f"{m.group('action')} {direction}",
                'from_':  m.group('from').strip(),
            })

    return result
