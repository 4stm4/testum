from dataclasses import dataclass, asdict
from typing import List


# ALLOW: Разрешить трафик.
# DENY: Запретить трафик.
# REJECT: Отклонить трафик и отправить ICMP-пакет с ответом (например, "порт недоступен").
# LIMIT: Разрешить трафик, но с ограничением на количество попыток подключиться (например, для защиты от брутфорс-атак).

ACTIONS = ('ALLOW', 'DENY', 'REJECT', 'LIMIT',)


@dataclass
class UFWRule:
    to: str
    action: str
    from_: str


@dataclass
class UFWStatus:
    status: str
    rules: List[UFWRule]

    def dict(self):
            return {k: str(v) for k, v in asdict(self).items()}

def _get_rule(rule_str: str):
    rule_list = []
    rule = None
    for action in ACTIONS:
        if action in rule_str:
            rule_list = rule_str.split(action)
            if len(rule_list) == 2:
                rule = UFWRule(
                    to=rule_list[0].strip(),
                    action=action,
                    from_=rule_list[1].strip()
                )
                return rule

    return rule


def parse_ufw_status(lines: List[str]) -> UFWStatus:
    rules = []
    status = lines[0].split(': ')[1].strip()
    # Убираем заголовки и разделители
    for line in lines:
        rule = _get_rule(line)
        if rule:
            rules.append(rule)
    return UFWStatus(
        status=status,
        rules=rules,
    )
