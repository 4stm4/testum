from typing_extensions import Self


class XML:

    def __init__(self: Self, label: str, value: str):
        self.label = label
        self.value = value

    def full_tag(self: Self, **values) -> str:
        values_str = ''
        for name, value in values.items():
            values_str += ' {0}="{1}"'.format(name, value)
        xml_str = '<{0}{2}>{1}</{0}>\n'.format(self.label,
                                             self.value, values_str)
        return xml_str

    def half_tag(self: Self, **values) -> str:
        values_str = ''
        for name, value in values.items():
            values_str += ' {0}="{1}"'.format(name, value)
        xml_str = '<{0} {1}/>\n'.format(self.label, values_str)
        return xml_str
